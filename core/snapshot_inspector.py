"""
Snapshot inspector for Kinetix backups.
Inspects local PC backup snapshots, discovering category breakdown,
subdirectories, albums, file counts, and formatted sizes.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


def format_size_bytes(bytes_val: int) -> str:
    """Formats bytes into human-readable B, KB, MB, or GB."""
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024**2:
        return f"{bytes_val / 1024:.1f} KB"
    elif bytes_val < 1024**3:
        return f"{bytes_val / (1024**2):.1f} MB"
    else:
        return f"{bytes_val / (1024**3):.2f} GB"


CATEGORIES_CONFIG = {
    "pics": {
        "id": "pics",
        "name": "Photos & Videos",
        "dest_path": "/sdcard/DCIM",
        "icon": "photos",
        "prefixes": ["dcim", "pictures", "movies", "pics", "photos"],
    },
    "music": {
        "id": "music",
        "name": "Music & Audio",
        "dest_path": "/sdcard/Music",
        "icon": "music",
        "prefixes": ["music", "podcasts", "audiobooks", "recordings"],
    },
    "whatsapp": {
        "id": "whatsapp",
        "name": "WhatsApp Media & Backups",
        "dest_path": "/sdcard/Android/media/com.whatsapp",
        "icon": "whatsapp",
        "prefixes": ["whatsapp", "com.whatsapp"],
    },
    "telegram": {
        "id": "telegram",
        "name": "Telegram Media & Files",
        "dest_path": "/sdcard/Movies/Telegram",
        "icon": "telegram",
        "prefixes": ["telegram", "org.telegram.messenger"],
    },
    "sms": {
        "id": "sms",
        "name": "SMS & Call Logs",
        "dest_path": "Telephony Database / XML",
        "icon": "sms",
        "prefixes": ["sms_and_calls", "sms", "calls"],
    },
    "private_space": {
        "id": "private_space",
        "name": "Android 15+ Private Space",
        "dest_path": "/storage/emulated/10",
        "icon": "private_space",
        "prefixes": ["private_space", "privatespace", "private"],
    },
    "custom_folders": {
        "id": "custom_folders",
        "name": "Custom Folders",
        "dest_path": "/sdcard/Documents",
        "icon": "custom",
        "prefixes": ["documents", "download", "custom_folders", "custom"],
    },
}


def inspect_snapshot_dir(snap_dir: Path) -> Dict[str, Any]:
    """
    Discovers all categories, albums, and subfolders inside a PC backup snapshot directory.
    Returns file counts, sizes, and subfolder lists.
    """
    cat_stats = {
        k: {
            "id": k,
            "name": v["name"],
            "dest_path": v["dest_path"],
            "icon": v["icon"],
            "file_count": 0,
            "size_bytes": 0,
            "has_backup": False,
            "subfolders_map": {},
        }
        for k, v in CATEGORIES_CONFIG.items()
    }

    if not snap_dir.is_dir():
        return {
            "snapshot": snap_dir.name,
            "path": str(snap_dir),
            "total_files": 0,
            "total_bytes": 0,
            "total_formatted": "0 B",
            "categories": {
                k: {
                    "id": v["id"],
                    "name": v["name"],
                    "dest_path": v["dest_path"],
                    "icon": v["icon"],
                    "has_backup": False,
                    "file_count": 0,
                    "size_bytes": 0,
                    "size_formatted": "0 B",
                    "subfolders": [],
                }
                for k, v in cat_stats.items()
            },
        }

    total_files = 0
    total_bytes = 0

    for root, _, files in os.walk(snap_dir):
        for f in files:
            if f.startswith(".") or f.endswith(".hyperpart") or f == ".hyper_map.json":
                continue
            full_path = Path(root) / f
            try:
                size = full_path.stat().st_size
            except Exception:
                size = 0

            total_files += 1
            total_bytes += size

            rel = full_path.relative_to(snap_dir).as_posix()
            parts = [p for p in rel.split("/") if p]
            if not parts:
                continue

            first = parts[0].lower()
            target_cat = None
            for c_id, conf in CATEGORIES_CONFIG.items():
                if first == c_id or first in conf["prefixes"]:
                    target_cat = c_id
                    break
                if first == "android" and len(parts) > 2 and "whatsapp" in parts[2].lower():
                    target_cat = "whatsapp"
                    break

            if not target_cat:
                target_cat = "custom_folders"

            # Compute subfolder key (e.g. DCIM/Camera, Music/SpotFlac)
            parent_rel = full_path.parent.relative_to(snap_dir).as_posix()
            if parent_rel == ".":
                sub_key = parts[0]
            else:
                d_parts = [p for p in parent_rel.split("/") if p]
                if d_parts[0].lower() in ["pics", "photos", "custom_folders"] and len(d_parts) > 1:
                    d_parts = d_parts[1:]
                if len(d_parts) >= 2:
                    sub_key = f"{d_parts[0]}/{d_parts[1]}"
                else:
                    sub_key = d_parts[0]

            cat_dict = cat_stats[target_cat]
            cat_dict["file_count"] += 1
            cat_dict["size_bytes"] += size
            cat_dict["has_backup"] = True

            sub_map = cat_dict["subfolders_map"]
            if sub_key not in sub_map:
                sub_map[sub_key] = {
                    "name": sub_key,
                    "path": sub_key,
                    "file_count": 0,
                    "size_bytes": 0,
                }
            sub_map[sub_key]["file_count"] += 1
            sub_map[sub_key]["size_bytes"] += size

    final_cats = {}
    for k, v in cat_stats.items():
        sub_list = []
        for s_key, s_data in sorted(
            v["subfolders_map"].items(), key=lambda x: x[1]["file_count"], reverse=True
        ):
            sub_list.append(
                {
                    "name": s_data["name"],
                    "path": s_data["path"],
                    "file_count": s_data["file_count"],
                    "size_bytes": s_data["size_bytes"],
                    "size_formatted": format_size_bytes(s_data["size_bytes"]),
                }
            )
        final_cats[k] = {
            "id": v["id"],
            "name": v["name"],
            "dest_path": v["dest_path"],
            "icon": v["icon"],
            "has_backup": v["has_backup"],
            "file_count": v["file_count"],
            "size_bytes": v["size_bytes"],
            "size_formatted": format_size_bytes(v["size_bytes"]),
            "subfolders": sub_list,
        }

    return {
        "snapshot": snap_dir.name,
        "path": str(snap_dir),
        "total_files": total_files,
        "total_bytes": total_bytes,
        "total_formatted": format_size_bytes(total_bytes),
        "categories": final_cats,
    }
