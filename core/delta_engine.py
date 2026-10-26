"""
Delta engine for MobilePCSync.
Performs intelligent comparison between Android device files and PC backup files,
using a 2.0-second timestamp tolerance window for filesystem precision differences.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from core.config import ASSUMED_SPEED_BYTES_PER_SEC, TIMESTAMP_TOLERANCE_SECONDS
from core.indexer import LocalFileInfo, RemoteFileInfo


class SyncStatus(str, Enum):
    """Classification status for a file during synchronization."""
    ALREADY_SYNCED = "ALREADY_SYNCED"
    TO_SYNC_NEW = "TO_SYNC_NEW"
    TO_SYNC_MODIFIED = "TO_SYNC_MODIFIED"
    DELETED_REMOTE = "DELETED_REMOTE"


@dataclass
class DeltaItem:
    """Individual item comparison result."""
    rel_path: str
    status: SyncStatus
    remote_file: Optional[RemoteFileInfo] = None
    local_file: Optional[LocalFileInfo] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rel_path": self.rel_path,
            "status": self.status.value if hasattr(self.status, "value") else str(self.status),
            "size": self.remote_file.size if self.remote_file else (self.local_file.size if self.local_file else 0),
            "mtime": self.remote_file.mtime if self.remote_file else (self.local_file.mtime if self.local_file else 0),
            "reason": self.reason,
        }


@dataclass
class DeltaReport:
    """Consolidated synchronization analysis and delta metrics."""
    total_remote_files: int
    total_remote_bytes: int
    already_synced_count: int
    already_synced_bytes: int
    to_sync_count: int
    to_sync_bytes: int
    items_to_sync: List[DeltaItem]
    time_saved_seconds_estimate: float
    breakdown_by_category: Dict[str, Dict[str, Any]]
    all_items: List[DeltaItem] = field(default_factory=list)
    deleted_remote_count: int = 0
    deleted_remote_items: List[DeltaItem] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_remote_files": self.total_remote_files,
            "total_remote_bytes": self.total_remote_bytes,
            "already_synced_count": self.already_synced_count,
            "already_synced_bytes": self.already_synced_bytes,
            "to_sync_count": self.to_sync_count,
            "to_sync_bytes": self.to_sync_bytes,
            "time_saved_seconds_estimate": self.time_saved_seconds_estimate,
            "deleted_remote_count": self.deleted_remote_count,
            "breakdown_by_category": self.breakdown_by_category,
            "items_to_sync": [item.to_dict() for item in self.items_to_sync],
            "all_items": [item.to_dict() for item in self.all_items],
        }


class DeltaEngine:
    """Calculates synchronization deltas between remote device files and local PC files."""

    def __init__(
        self,
        tolerance_seconds: float = TIMESTAMP_TOLERANCE_SECONDS,
        assumed_speed: float = ASSUMED_SPEED_BYTES_PER_SEC,
    ) -> None:
        self.tolerance_seconds = tolerance_seconds
        self.assumed_speed = assumed_speed

    def compare(
        self,
        remote_files: List[RemoteFileInfo],
        local_map: Dict[str, LocalFileInfo],
        tolerance_seconds: Optional[float] = None,
        assumed_speed: Optional[float] = None,
    ) -> DeltaReport:
        tol = tolerance_seconds if tolerance_seconds is not None else self.tolerance_seconds
        spd = assumed_speed if assumed_speed is not None else self.assumed_speed
        return self.compute_delta(remote_files, local_map, tolerance_seconds=tol, assumed_speed=spd)

    @classmethod
    def compute_delta(
        cls,
        remote_files: List[RemoteFileInfo],
        local_map: Dict[str, LocalFileInfo],
        tolerance_seconds: float = TIMESTAMP_TOLERANCE_SECONDS,
        assumed_speed: float = ASSUMED_SPEED_BYTES_PER_SEC,
    ) -> DeltaReport:
        """
        Compares remote files against local backup files.

        Applies a 2.0-second timestamp tolerance:
        If abs(remote.mtime - local.mtime) <= tolerance_seconds and remote.size == local.size,
        the file is classified as ALREADY_SYNCED.

        Args:
            remote_files: List of RemoteFileInfo from device scan.
            local_map: Dict mapping rel_path -> LocalFileInfo from local PC.
            tolerance_seconds: Max acceptable mtime difference (default 2.0s).
            assumed_speed: Transfer speed estimate in bytes/sec (default 40 MB/s).

        Returns:
            DeltaReport with metrics, categories breakdown, and items to transfer.
        """
        all_items: List[DeltaItem] = []
        items_to_sync: List[DeltaItem] = []
        deleted_remote_items: List[DeltaItem] = []

        total_remote_files = len(remote_files)
        total_remote_bytes = sum(f.size for f in remote_files)

        already_synced_count = 0
        already_synced_bytes = 0
        to_sync_count = 0
        to_sync_bytes = 0

        remote_paths_seen: Set[str] = set()
        matched_local_paths: Set[str] = set()
        matched_local_keys: Set[str] = set()

        # Build lowercase lookup for case-insensitive filesystem fallback
        lower_local_map: Dict[str, LocalFileInfo] = {}
        for k, v in local_map.items():
            k_low = k.lower()
            if k_low not in lower_local_map:
                lower_local_map[k_low] = v

        # Category aggregation dictionaries
        categories: Set[str] = set()
        cat_metrics: Dict[str, Dict[str, Any]] = {}

        for remote in remote_files:
            rel_path = remote.rel_path
            remote_paths_seen.add(rel_path)
            category = remote.category or "default"
            categories.add(category)

            if category not in cat_metrics:
                cat_metrics[category] = {
                    "total_remote_files": 0,
                    "total_remote_bytes": 0,
                    "already_synced_count": 0,
                    "already_synced_bytes": 0,
                    "to_sync_count": 0,
                    "to_sync_bytes": 0,
                }

            cat_stats = cat_metrics[category]
            cat_stats["total_remote_files"] += 1
            cat_stats["total_remote_bytes"] += remote.size

            local = local_map.get(rel_path)
            if local is None:
                local = lower_local_map.get(rel_path.lower())

            if local is None:
                # File not found locally -> New
                item = DeltaItem(
                    rel_path=rel_path,
                    status=SyncStatus.TO_SYNC_NEW,
                    remote_file=remote,
                    local_file=None,
                    reason="New file (not present on PC)",
                )
                items_to_sync.append(item)
                all_items.append(item)
                to_sync_count += 1
                to_sync_bytes += remote.size
                cat_stats["to_sync_count"] += 1
                cat_stats["to_sync_bytes"] += remote.size

            else:
                matched_local_paths.add(local.path)
                matched_local_keys.add(local.rel_path)
                matched_local_keys.add(rel_path)

                # Compare size and mtime
                size_match = (remote.size == local.size)
                time_diff = abs(remote.mtime - local.mtime)
                time_match = (time_diff <= tolerance_seconds)

                if size_match and time_match:
                    item = DeltaItem(
                        rel_path=rel_path,
                        status=SyncStatus.ALREADY_SYNCED,
                        remote_file=remote,
                        local_file=local,
                        reason=f"Identical (size={remote.size}, time_diff={time_diff:.3f}s)",
                    )
                    all_items.append(item)
                    already_synced_count += 1
                    already_synced_bytes += remote.size
                    cat_stats["already_synced_count"] += 1
                    cat_stats["already_synced_bytes"] += remote.size
                else:
                    reasons = []
                    if not size_match:
                        reasons.append(f"size changed ({local.size} -> {remote.size})")
                    if not time_match:
                        reasons.append(f"mtime changed (diff={time_diff:.3f}s > {tolerance_seconds}s)")

                    item = DeltaItem(
                        rel_path=rel_path,
                        status=SyncStatus.TO_SYNC_MODIFIED,
                        remote_file=remote,
                        local_file=local,
                        reason=", ".join(reasons),
                    )
                    items_to_sync.append(item)
                    all_items.append(item)
                    to_sync_count += 1
                    to_sync_bytes += remote.size
                    cat_stats["to_sync_count"] += 1
                    cat_stats["to_sync_bytes"] += remote.size

        # Identify files deleted from remote device
        seen_deleted_paths: Set[str] = set()
        for local_rel, local_file in local_map.items():
            if (
                local_file.path not in matched_local_paths
                and local_file.path not in seen_deleted_paths
                and local_rel not in remote_paths_seen
                and local_rel not in matched_local_keys
            ):
                seen_deleted_paths.add(local_file.path)
                del_item = DeltaItem(
                    rel_path=local_rel,
                    status=SyncStatus.DELETED_REMOTE,
                    remote_file=None,
                    local_file=local_file,
                    reason="Present on PC but removed from Android device",
                )
                deleted_remote_items.append(del_item)
                all_items.append(del_item)

        # Estimate time saved assuming 40 MB/s transfer rate
        time_saved = round(already_synced_bytes / max(assumed_speed, 1.0), 2)

        return DeltaReport(
            total_remote_files=total_remote_files,
            total_remote_bytes=total_remote_bytes,
            already_synced_count=already_synced_count,
            already_synced_bytes=already_synced_bytes,
            to_sync_count=to_sync_count,
            to_sync_bytes=to_sync_bytes,
            items_to_sync=items_to_sync,
            time_saved_seconds_estimate=time_saved,
            breakdown_by_category=cat_metrics,
            all_items=all_items,
            deleted_remote_count=len(deleted_remote_items),
            deleted_remote_items=deleted_remote_items,
        )
