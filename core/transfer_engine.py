"""
Concurrent transfer engine for MobilePCSync.
Executes high-throughput multi-threaded adb pull/push operations with atomic part-file writing,
strict size validation, timestamp preservation, and real-time speed/ETA metrics.
"""

from __future__ import annotations

import collections
import logging
import os
import posixpath
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Deque, Dict, List, Optional, Tuple, Union

from core.adb_manager import AdbManager
from core.config import DEFAULT_CONCURRENCY
from core.delta_engine import DeltaItem
from core.indexer import LocalFileInfo, LocalIndexer, RemoteIndexer
from core.path_sanitizer import PathSanitizer

logger = logging.getLogger(__name__)


@dataclass
class TransferProgress:
    """Snapshot of active transfer progress."""
    bytes_synced: int
    total_bytes: int
    files_synced: int
    total_files: int
    current_speed_mbps: float
    eta_seconds: float
    current_file: str
    status: str = "transferring"  # "transferring", "completed", "error", "cancelled"
    error: Optional[str] = None

    @property
    def percentage(self) -> float:
        if self.total_bytes <= 0:
            return 100.0 if self.files_synced >= self.total_files else 0.0
        return min(100.0, (self.bytes_synced / self.total_bytes) * 100.0)


@dataclass
class TransferResult:
    """Summary of transfer session execution."""
    success: bool
    files_transferred: int
    bytes_transferred: int
    duration_seconds: float
    average_speed_mbps: float
    errors: List[str]
    already_synced_files: int = 0
    already_synced_bytes: int = 0


ProgressCallback = Callable[[TransferProgress], None]


class TransferEngine:
    """Orchestrates concurrent file transfers between Android device and PC."""

    def __init__(
        self,
        adb_manager: Optional[AdbManager] = None,
        max_workers: int = DEFAULT_CONCURRENCY,
    ) -> None:
        self.adb = adb_manager or AdbManager()
        self.max_workers = max(1, max_workers)

    def sync_items(
        self,
        serial: str,
        items: List[DeltaItem],
        backup_root_dir: Union[str, Path],
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
    ) -> TransferResult:
        """
        Transfers items from device to local PC concurrently.

        Each file is pulled to <dest>.hyperpart, size is validated, renamed atomically,
        and mtime is preserved with os.utime.

        Args:
            serial: Device serial.
            items: DeltaItem list (filtered to TO_SYNC_NEW or TO_SYNC_MODIFIED).
            backup_root_dir: Category root directory on PC.
            progress_callback: Optional callback receiving TransferProgress.
            cancel_event: Optional threading.Event to abort sync.

        Returns:
            TransferResult summary.
        """
        start_time = time.time()
        backup_dir = Path(backup_root_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Filter valid transfer candidates
        valid_items = [
            it for it in items
            if it.remote_file and it.remote_file.path
        ]

        total_files = len(valid_items)
        total_bytes = sum(it.remote_file.size for it in valid_items if it.remote_file)

        if total_files == 0:
            return TransferResult(
                success=True,
                files_transferred=0,
                bytes_transferred=0,
                duration_seconds=0.0,
                average_speed_mbps=0.0,
                errors=[],
            )

        lock = threading.Lock()
        bytes_synced = 0
        files_synced = 0
        errors: List[str] = []

        # Sliding window for current speed calculation (time, bytes)
        speed_history: Deque[Tuple[float, int]] = collections.deque(maxlen=30)
        speed_history.append((start_time, 0))

        def notify_progress(current_filename: str, status: str = "transferring", err_msg: Optional[str] = None):
            if not progress_callback:
                return

            now = time.time()
            with lock:
                speed_history.append((now, bytes_synced))
                old_time, old_bytes = speed_history[0]
                dt = now - old_time
                if dt >= 0.5:
                    speed_bps = (bytes_synced - old_bytes) / dt
                else:
                    speed_bps = bytes_synced / max(0.1, (now - start_time))

                speed_mbps = round(speed_bps / (1024 * 1024), 2)
                remaining_bytes = max(0, total_bytes - bytes_synced)
                eta = round(remaining_bytes / speed_bps, 1) if speed_bps > 1024 else 0.0

                prog = TransferProgress(
                    bytes_synced=bytes_synced,
                    total_bytes=total_bytes,
                    files_synced=files_synced,
                    total_files=total_files,
                    current_speed_mbps=speed_mbps,
                    eta_seconds=eta,
                    current_file=current_filename,
                    status=status,
                    error=err_msg,
                )
            try:
                progress_callback(prog)
            except Exception as cb_exc:
                logger.debug("Progress callback exception: %s", cb_exc)

        def transfer_single_file(item: DeltaItem) -> Tuple[bool, int, Optional[str]]:
            if cancel_event and cancel_event.is_set():
                return False, 0, "Transfer cancelled"

            remote = item.remote_file
            assert remote is not None

            # Path sanitization for Windows NTFS
            win_rel, was_mod = PathSanitizer.sanitize_relpath(remote.rel_path, base_dir=backup_dir)
            dest_final = (backup_dir / Path(*win_rel.split("/"))).resolve()
            dest_part = Path(str(dest_final) + ".hyperpart")

            try:
                dest_final.parent.mkdir(parents=True, exist_ok=True)

                # Remove stale part file if present
                if dest_part.exists():
                    dest_part.unlink()

                # Pull to .hyperpart
                pull_ok = self.adb.pull(serial, remote.path, str(dest_part), timeout=600)
                if not pull_ok or not dest_part.exists():
                    return False, 0, f"ADB pull failed for: {remote.path}"

                # Strict size validation
                actual_size = dest_part.stat().st_size
                if actual_size != remote.size:
                    if dest_part.exists():
                        dest_part.unlink()
                    return False, 0, (
                        f"Size mismatch on {remote.path}: expected {remote.size}b, got {actual_size}b"
                    )

                # Atomic replace
                if dest_final.exists():
                    dest_final.unlink()
                dest_part.replace(dest_final)

                # Preserve original Linux mtime
                try:
                    os.utime(dest_final, (remote.mtime, remote.mtime))
                except Exception as ut_exc:
                    logger.debug("Failed to set mtime on %s: %s", dest_final, ut_exc)

                return True, actual_size, None

            except Exception as exc:
                if dest_part.exists():
                    try:
                        dest_part.unlink()
                    except Exception:
                        pass
                return False, 0, str(exc)

        # Execute concurrent worker pool
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {
                executor.submit(transfer_single_file, it): it
                for it in valid_items
            }

            for future in as_completed(future_to_item):
                item = future_to_item[future]
                remote_name = posixpath.basename(item.remote_file.path) if item.remote_file else ""

                if cancel_event and cancel_event.is_set():
                    errors.append("Transfer cancelled by user")
                    break

                try:
                    ok, file_bytes, err = future.result()
                    if ok:
                        with lock:
                            bytes_synced += file_bytes
                            files_synced += 1
                        notify_progress(remote_name)
                    else:
                        with lock:
                            errors.append(f"{remote_name}: {err}")
                        notify_progress(remote_name, status="error", err_msg=err)
                except Exception as exc:
                    err_msg = str(exc)
                    with lock:
                        errors.append(f"{remote_name}: {err_msg}")
                    notify_progress(remote_name, status="error", err_msg=err_msg)

        duration = max(0.01, time.time() - start_time)
        avg_speed_mbps = round((bytes_synced / duration) / (1024 * 1024), 2)
        success = (len(errors) == 0 and (not cancel_event or not cancel_event.is_set()))

        final_status = "completed" if success else ("cancelled" if cancel_event and cancel_event.is_set() else "error")
        notify_progress(
            "All transfers finished" if success else "Transfer ended with issues",
            status=final_status,
        )

        return TransferResult(
            success=success,
            files_transferred=files_synced,
            bytes_transferred=bytes_synced,
            duration_seconds=duration,
            average_speed_mbps=avg_speed_mbps,
            errors=errors,
        )

    def sync_files(
        self,
        serial: str,
        items_to_sync: List[DeltaItem],
        local_base_dir: Union[str, Path],
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        max_workers: Optional[int] = None,
        use_compression: bool = True,
    ) -> TransferResult:
        """Alias for sync_items matching API conventions."""
        if max_workers:
            self.max_workers = max_workers
        return self.sync_items(
            serial=serial,
            items=items_to_sync,
            backup_root_dir=local_base_dir,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )

    def restore_backup(
        self,
        serial: str,
        categories: List[str],
        device_backup_dir: Union[str, Path],
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        max_workers: Optional[int] = None,
        subfolders: Optional[Dict[str, List[str]]] = None,
        smart_delta: bool = True,
    ) -> Dict[str, TransferResult]:
        """
        Restores selected categories from PC back to the Android device with
        intelligent Smart Delta pre-scanning, multithreaded concurrent streaming,
        and real-time telemetry updates.
        """
        from core.config import DEFAULT_CATEGORIES
        backup_path = Path(device_backup_dir)
        workers = max_workers or self.max_workers

        # 1. Collect all candidate files across all selected categories
        all_items = []
        all_remote_scan_paths = set()

        for cat_id in categories:
            cat_subs = None
            if subfolders:
                cat_subs = subfolders.get(cat_id) or subfolders.get("pics" if cat_id == "photos" else cat_id)

            cat_dir = backup_path / cat_id
            if not cat_dir.is_dir() and cat_id in ("sms", "sms_calls"):
                sms_cand = backup_path / "SMS_and_Calls"
                if sms_cand.is_dir():
                    cat_dir = sms_cand

            matched_dirs = []
            if cat_dir.is_dir():
                remote_root = "/sdcard"
                if cat_id == "whatsapp":
                    remote_root = "/sdcard/Android/media/com.whatsapp/WhatsApp"
                elif cat_id in ("sms", "sms_calls"):
                    remote_root = "/sdcard/SMS_and_Calls"
                elif cat_dir.name.lower() in ("dcim", "pictures", "movies", "music", "podcasts", "audiobooks", "download", "documents"):
                    remote_root = f"/sdcard/{cat_dir.name}"
                matched_dirs.append((cat_dir, remote_root, cat_dir.name))
            else:
                cat_meta = DEFAULT_CATEGORIES.get(cat_id, {})
                cat_paths = cat_meta.get("paths", [])
                if backup_path.is_dir():
                    for p in cat_paths:
                        base_name = posixpath.basename(p.rstrip("/"))
                        try:
                            with os.scandir(backup_path) as entries:
                                for entry in entries:
                                    if entry.is_dir() and entry.name.lower() == base_name.lower():
                                        matched_dirs.append((Path(entry.path), f"/sdcard/{base_name}", base_name))
                                        break
                        except Exception:
                            pass

            for local_dir, remote_root, base_name in matched_dirs:
                if cat_subs:
                    for s in cat_subs:
                        clean_sub = s.strip("/").replace("\\", "/")
                        all_remote_scan_paths.add(f"{remote_root.rstrip('/')}/{clean_sub}")
                else:
                    all_remote_scan_paths.add(remote_root.rstrip("/"))

                files_map = LocalIndexer.scan_local_category(local_dir)
                clean_root = remote_root.rstrip("/")
                for f in files_map.values():
                    if cat_subs and not self._is_file_in_subfolders(f.rel_path, base_name, cat_subs):
                        continue
                    clean_rel = f.rel_path.lstrip("/")
                    remote_target = f"{clean_root}/{clean_rel}"
                    filename = posixpath.basename(f.rel_path)
                    all_items.append((f.path, remote_target, f.size, filename, cat_id))

        total_candidate_files = len(all_items)
        total_candidate_bytes = sum(it[2] for it in all_items)

        # 1.5. Smart Delta Phone Scan (sub-second remote scan to skip already identical files)
        already_synced_files = 0
        already_synced_bytes = 0
        cat_skipped = {c: {"files": 0, "bytes": 0} for c in categories}

        if smart_delta and all_items:
            if progress_callback:
                progress_callback(
                    TransferProgress(
                        bytes_synced=0,
                        total_bytes=total_candidate_bytes,
                        files_synced=0,
                        total_files=total_candidate_files,
                        current_speed_mbps=0.0,
                        eta_seconds=0.0,
                        current_file="⚡ Running superfast scan on phone to check existing files...",
                        status="transferring",
                    )
                )

            try:
                remote_indexer = RemoteIndexer(self.adb)
                scan_targets = list(all_remote_scan_paths)
                remote_files = remote_indexer.scan_remote_category(serial, "restore", scan_targets)
                phone_files = {posixpath.normpath(rf.path).lower(): rf.size for rf in remote_files}

                items_to_push = []
                for it in all_items:
                    l_path, r_target, f_size, f_name, c_id = it
                    norm_target = posixpath.normpath(r_target).lower()
                    if norm_target in phone_files and phone_files[norm_target] == f_size:
                        already_synced_files += 1
                        already_synced_bytes += f_size
                        if c_id in cat_skipped:
                            cat_skipped[c_id]["files"] += 1
                            cat_skipped[c_id]["bytes"] += f_size
                    else:
                        items_to_push.append(it)

                all_items = items_to_push
            except Exception as scan_err:
                logger.warning("Smart Delta remote scan notice, proceeding with standard push: %s", scan_err)

        total_files = len(all_items)
        total_bytes = sum(it[2] for it in all_items)

        results = {
            cat_id: TransferResult(
                success=True,
                files_transferred=0,
                bytes_transferred=0,
                duration_seconds=0.0,
                average_speed_mbps=0.0,
                errors=[],
                already_synced_files=cat_skipped.get(cat_id, {}).get("files", 0),
                already_synced_bytes=cat_skipped.get(cat_id, {}).get("bytes", 0),
            )
            for cat_id in categories
        }

        if total_files == 0:
            if progress_callback:
                skipped_mb = round(already_synced_bytes / (1024 * 1024), 1)
                msg = (
                    f"⚡ 100% Up-to-date! All {already_synced_files} files "
                    f"({skipped_mb} MB) are already identical on your phone."
                ) if already_synced_files > 0 else "No files to restore"
                progress_callback(
                    TransferProgress(
                        bytes_synced=already_synced_bytes,
                        total_bytes=already_synced_bytes,
                        files_synced=already_synced_files,
                        total_files=already_synced_files,
                        current_speed_mbps=0.0,
                        eta_seconds=0.0,
                        current_file=msg,
                        status="completed",
                    )
                )
            return results

        # 2. Multithreaded Push with real-time telemetry
        bytes_synced = 0
        files_synced = 0
        lock = threading.Lock()
        start_time = time.time()
        created_dirs = set()
        cat_stats = {c: {"files": 0, "bytes": 0, "errors": []} for c in categories}

        def push_single_item(item):
            l_path, r_target, f_size, f_name, c_id = item
            if cancel_event and cancel_event.is_set():
                return False, 0, "Restore cancelled by user", f_name, c_id

            r_dir = posixpath.dirname(r_target)
            with lock:
                if r_dir not in created_dirs:
                    self.adb.run_shell(serial, f'mkdir -p "{r_dir}"')
                    created_dirs.add(r_dir)

            push_ok = self.adb.push(serial, l_path, r_target)
            if not push_ok:
                return False, 0, f"Failed to push {f_name} to {r_target}", f_name, c_id
            return True, f_size, None, f_name, c_id

        # Emit initial progress (0%)
        if progress_callback:
            progress_callback(
                TransferProgress(
                    bytes_synced=0,
                    total_bytes=total_bytes,
                    files_synced=0,
                    total_files=total_files,
                    current_speed_mbps=0.0,
                    eta_seconds=0.0,
                    current_file="Connecting restore stream...",
                    status="transferring",
                )
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_item = {
                executor.submit(push_single_item, it): it
                for it in all_items
            }

            for future in as_completed(future_to_item):
                if cancel_event and cancel_event.is_set():
                    break

                try:
                    ok, f_bytes, err, f_name, c_id = future.result()
                    with lock:
                        if ok:
                            bytes_synced += f_bytes
                            files_synced += 1
                            cat_stats[c_id]["files"] += 1
                            cat_stats[c_id]["bytes"] += f_bytes
                        else:
                            cat_stats[c_id]["errors"].append(err)

                    if progress_callback:
                        now = time.time()
                        elapsed = max(0.01, now - start_time)
                        speed_mbps = round((bytes_synced / elapsed) / (1024 * 1024), 2)
                        remaining_bytes = max(0, total_bytes - bytes_synced)
                        rate = (bytes_synced / elapsed) if bytes_synced > 0 else 1.0
                        eta = round(remaining_bytes / (rate or 1.0), 1)

                        prog = TransferProgress(
                            bytes_synced=bytes_synced,
                            total_bytes=total_bytes,
                            files_synced=files_synced,
                            total_files=total_files,
                            current_speed_mbps=speed_mbps,
                            eta_seconds=eta,
                            current_file=f_name,
                        )
                        try:
                            progress_callback(prog)
                        except Exception:
                            pass
                except Exception as exc:
                    logger.debug("Exception in restore future: %s", exc)

        # 3. Trigger Android media scan
        try:
            self.adb.trigger_media_scan(serial, folder_or_volume="external_primary")
        except Exception as scan_exc:
            logger.warning("Media scan trigger failed: %s", scan_exc)

        # 4. Final summary calculation
        total_duration = max(0.01, time.time() - start_time)
        overall_speed = round((bytes_synced / total_duration) / (1024 * 1024), 2)

        for c_id in categories:
            stats = cat_stats[c_id]
            results[c_id] = TransferResult(
                success=(len(stats["errors"]) == 0),
                files_transferred=stats["files"],
                bytes_transferred=stats["bytes"],
                duration_seconds=total_duration,
                average_speed_mbps=overall_speed,
                errors=stats["errors"],
                already_synced_files=cat_skipped.get(c_id, {}).get("files", 0),
                already_synced_bytes=cat_skipped.get(c_id, {}).get("bytes", 0),
            )

        return results

    def analyze_restore(
        self,
        serial: str,
        categories: List[str],
        device_backup_dir: Union[str, Path],
        subfolders: Optional[Dict[str, List[str]]] = None,
    ) -> Dict[str, Any]:
        """
        Scans both PC backup and device destination directories in sub-second time
        to calculate pre-restore delta metrics: files already on phone, files to restore,
        bytes to restore, and estimated time saved.
        """
        from core.config import DEFAULT_CATEGORIES
        backup_path = Path(device_backup_dir)

        all_items = []
        all_remote_scan_paths = set()
        cat_file_counts = {c: {"total_files": 0, "total_bytes": 0} for c in categories}

        for cat_id in categories:
            cat_subs = None
            if subfolders:
                cat_subs = subfolders.get(cat_id) or subfolders.get("pics" if cat_id == "photos" else cat_id)

            cat_dir = backup_path / cat_id
            if not cat_dir.is_dir() and cat_id in ("sms", "sms_calls"):
                sms_cand = backup_path / "SMS_and_Calls"
                if sms_cand.is_dir():
                    cat_dir = sms_cand

            matched_dirs = []
            if cat_dir.is_dir():
                remote_root = "/sdcard"
                if cat_id == "whatsapp":
                    remote_root = "/sdcard/Android/media/com.whatsapp/WhatsApp"
                elif cat_id in ("sms", "sms_calls"):
                    remote_root = "/sdcard/SMS_and_Calls"
                elif cat_dir.name.lower() in ("dcim", "pictures", "movies", "music", "podcasts", "audiobooks", "download", "documents"):
                    remote_root = f"/sdcard/{cat_dir.name}"
                matched_dirs.append((cat_dir, remote_root, cat_dir.name))
            else:
                cat_meta = DEFAULT_CATEGORIES.get(cat_id, {})
                cat_paths = cat_meta.get("paths", [])
                if backup_path.is_dir():
                    for p in cat_paths:
                        base_name = posixpath.basename(p.rstrip("/"))
                        try:
                            with os.scandir(backup_path) as entries:
                                for entry in entries:
                                    if entry.is_dir() and entry.name.lower() == base_name.lower():
                                        matched_dirs.append((Path(entry.path), f"/sdcard/{base_name}", base_name))
                                        break
                        except Exception:
                            pass

            for local_dir, remote_root, base_name in matched_dirs:
                if cat_subs:
                    for s in cat_subs:
                        clean_sub = s.strip("/").replace("\\", "/")
                        all_remote_scan_paths.add(f"{remote_root.rstrip('/')}/{clean_sub}")
                else:
                    all_remote_scan_paths.add(remote_root.rstrip("/"))

                files_map = LocalIndexer.scan_local_category(local_dir)
                clean_root = remote_root.rstrip("/")
                for f in files_map.values():
                    if cat_subs and not self._is_file_in_subfolders(f.rel_path, base_name, cat_subs):
                        continue
                    clean_rel = f.rel_path.lstrip("/")
                    remote_target = f"{clean_root}/{clean_rel}"
                    filename = posixpath.basename(f.rel_path)
                    all_items.append((f.path, remote_target, f.size, filename, cat_id))
                    if cat_id in cat_file_counts:
                        cat_file_counts[cat_id]["total_files"] += 1
                        cat_file_counts[cat_id]["total_bytes"] += f.size

        total_files = len(all_items)
        total_bytes = sum(it[2] for it in all_items)

        if total_files == 0:
            return {
                "total_files": 0,
                "total_bytes": 0,
                "already_on_phone_count": 0,
                "already_on_phone_bytes": 0,
                "to_restore_count": 0,
                "to_restore_bytes": 0,
                "time_saved_seconds": 0.0,
                "category_breakdown": {},
                "to_restore_sample": [],
            }

        # Sub-second remote phone scan
        remote_files = []
        try:
            remote_indexer = RemoteIndexer(self.adb)
            remote_files = remote_indexer.scan_remote_category(serial, "restore", list(all_remote_scan_paths))
        except Exception as scan_err:
            logger.warning("Remote scan in analyze_restore encountered notice: %s", scan_err)

        phone_files = {posixpath.normpath(rf.path).lower(): rf.size for rf in remote_files}

        already_count = 0
        already_bytes = 0
        to_restore_items = []
        cat_breakdown = {
            c: {
                "total_files": cat_file_counts[c]["total_files"],
                "total_bytes": cat_file_counts[c]["total_bytes"],
                "already_files": 0,
                "already_bytes": 0,
                "to_restore_files": 0,
                "to_restore_bytes": 0,
            }
            for c in categories
        }

        for it in all_items:
            l_path, r_target, f_size, f_name, c_id = it
            norm_target = posixpath.normpath(r_target).lower()
            if norm_target in phone_files and phone_files[norm_target] == f_size:
                already_count += 1
                already_bytes += f_size
                if c_id in cat_breakdown:
                    cat_breakdown[c_id]["already_files"] += 1
                    cat_breakdown[c_id]["already_bytes"] += f_size
            else:
                to_restore_items.append({
                    "name": f_name,
                    "size": f_size,
                    "target": r_target,
                    "category": c_id,
                })
                if c_id in cat_breakdown:
                    cat_breakdown[c_id]["to_restore_files"] += 1
                    cat_breakdown[c_id]["to_restore_bytes"] += f_size

        time_saved_sec = round(already_bytes / (35.0 * 1024 * 1024), 1)

        return {
            "total_files": total_files,
            "total_bytes": total_bytes,
            "already_on_phone_count": already_count,
            "already_on_phone_bytes": already_bytes,
            "to_restore_count": len(to_restore_items),
            "to_restore_bytes": sum(x["size"] for x in to_restore_items),
            "time_saved_seconds": time_saved_sec,
            "category_breakdown": cat_breakdown,
            "to_restore_sample": to_restore_items[:50],
        }

    @staticmethod
    def _is_file_in_subfolders(rel_path: str, parent_name: str, allowed: List[str]) -> bool:
        """Determines if a relative file path is included in user-selected restore subfolders."""
        norm_rel = rel_path.replace("\\", "/").strip("/").lower()
        full_rel = f"{parent_name.lower()}/{norm_rel}" if parent_name else norm_rel
        for a in allowed:
            norm_a = a.replace("\\", "/").strip("/").lower()
            if norm_rel == norm_a or norm_rel.startswith(norm_a + "/"):
                return True
            if full_rel == norm_a or full_rel.startswith(norm_a + "/"):
                return True
            if norm_a.endswith("/" + norm_rel) or ("/" + norm_rel).startswith("/" + norm_a + "/"):
                return True
            parts_a = norm_a.split("/")
            if len(parts_a) >= 2:
                tail = "/".join(parts_a[1:])
                if norm_rel == tail or norm_rel.startswith(tail + "/"):
                    return True
        return False

    def restore_category(
        self,
        serial: str,
        local_category_dir: Union[str, Path],
        remote_dest_path: str,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_event: Optional[threading.Event] = None,
        allowed_subfolders: Optional[List[str]] = None,
        base_name: str = "",
    ) -> TransferResult:
        """
        Restores files from PC back to the Android device.
        Pushes files via adb push, verifies sizes, and triggers MediaStore scan.

        Args:
            serial: Device serial.
            local_category_dir: Root directory of category on PC.
            remote_dest_path: Remote Android root path (e.g. /sdcard or /sdcard/DCIM).
            progress_callback: Optional progress callback.
            cancel_event: Optional cancellation event.

        Returns:
            TransferResult summary.
        """
        start_time = time.time()
        local_dir = Path(local_category_dir)
        if not local_dir.is_dir():
            return TransferResult(
                success=False,
                files_transferred=0,
                bytes_transferred=0,
                duration_seconds=0.0,
                average_speed_mbps=0.0,
                errors=[f"Local category directory not found: {local_category_dir}"],
            )

        # Scan local PC files
        local_files_map = LocalIndexer.scan_local_category(local_dir)
        local_files = list(local_files_map.values())
        if allowed_subfolders:
            parent_name = base_name or local_dir.name
            local_files = [
                f for f in local_files
                if self._is_file_in_subfolders(f.rel_path, parent_name, allowed_subfolders)
            ]
        total_files = len(local_files)
        total_bytes = sum(f.size for f in local_files)

        if total_files == 0:
            return TransferResult(
                success=True,
                files_transferred=0,
                bytes_transferred=0,
                duration_seconds=0.0,
                average_speed_mbps=0.0,
                errors=[],
            )

        bytes_synced = 0
        files_synced = 0
        errors: List[str] = []

        norm_dest = remote_dest_path.replace("\\", "/").rstrip("/")

        for file_info in local_files:
            if cancel_event and cancel_event.is_set():
                errors.append("Restore cancelled by user")
                break

            # Target remote path combining destination root and desanitized relative path
            remote_target = f"{norm_dest}/{file_info.rel_path.lstrip('/')}"
            remote_target_dir = posixpath.dirname(remote_target)

            # Ensure remote directory exists
            self.adb.run_shell(serial, f'mkdir -p "{remote_target_dir}"')

            # Push file
            push_ok = self.adb.push(serial, file_info.path, remote_target)
            if not push_ok:
                errors.append(f"Failed to push {file_info.rel_path} to {remote_target}")
                continue

            # Size verification
            try:
                stat_out = self.adb.run_shell(serial, f'stat -c "%s" "{remote_target}" 2>/dev/null')
                stat_out = stat_out.strip()
                if stat_out.isdigit() and int(stat_out) != file_info.size:
                    errors.append(
                        f"Size mismatch restoring {file_info.rel_path}: PC {file_info.size}b, device {stat_out}b"
                    )
                    continue
            except Exception:
                pass

            bytes_synced += file_info.size
            files_synced += 1

            if progress_callback:
                now = time.time()
                elapsed = max(0.1, now - start_time)
                speed_mbps = round((bytes_synced / elapsed) / (1024 * 1024), 2)
                eta = round((total_bytes - bytes_synced) / ((bytes_synced / elapsed) or 1), 1)

                prog = TransferProgress(
                    bytes_synced=bytes_synced,
                    total_bytes=total_bytes,
                    files_synced=files_synced,
                    total_files=total_files,
                    current_speed_mbps=speed_mbps,
                    eta_seconds=eta,
                    current_file=posixpath.basename(file_info.rel_path),
                )
                try:
                    progress_callback(prog)
                except Exception:
                    pass

        # Trigger media scan to refresh Android Gallery and Music immediately
        try:
            self.adb.trigger_media_scan(serial, folder_or_volume="external_primary")
        except Exception as scan_exc:
            logger.warning("Media scan trigger failed: %s", scan_exc)

        duration = max(0.01, time.time() - start_time)
        avg_speed = round((bytes_synced / duration) / (1024 * 1024), 2)

        return TransferResult(
            success=(len(errors) == 0 and (not cancel_event or not cancel_event.is_set())),
            files_transferred=files_synced,
            bytes_transferred=bytes_synced,
            duration_seconds=duration,
            average_speed_mbps=avg_speed,
            errors=errors,
        )
