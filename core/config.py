"""
Configuration management for Kinetix.
Defines system settings, default paths, backup targets, and category schemas.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Default platform-tools binary path
DEFAULT_ADB_BIN = PROJECT_ROOT / "bin" / "platform-tools" / "adb.exe"

# Default backup root directory
DEFAULT_BACKUP_ROOT = PROJECT_ROOT / "Backups"

# Concurrency & Performance settings
DEFAULT_CONCURRENCY = 4
TIMESTAMP_TOLERANCE_SECONDS = 2.0  # 2.0-second window for FAT32 / Android filesystem precision
ASSUMED_SPEED_BYTES_PER_SEC = 40.0 * 1024 * 1024  # 40 MB/s estimated speed for time-saved calculation
PROGRESS_INTERVAL_SECONDS = 0.25  # Frequency of progress notifications


@dataclass
class CategoryConfig:
    """Configuration descriptor for a backup category."""
    id: str
    label: str
    icon: str
    description: str
    paths: List[str] = field(default_factory=list)
    special_type: Optional[str] = None
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "icon": self.icon,
            "description": self.description,
            "paths": list(self.paths),
            "special_type": self.special_type,
            "enabled": self.enabled,
        }


# Standard predefined backup categories
CATEGORIES: Dict[str, CategoryConfig] = {
    "pics": CategoryConfig(
        id="pics",
        label="Photos & Videos",
        icon="camera",
        description="Camera rolls, screenshots, movies, gallery albums",
        paths=["/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Movies"],
    ),
    "photos": CategoryConfig(
        id="photos",
        label="Photos & Videos",
        icon="camera",
        description="Camera rolls, screenshots, movies, gallery albums",
        paths=["/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Movies"],
    ),
    "music": CategoryConfig(
        id="music",
        label="Music & Audio",
        icon="music",
        description="Songs, albums, recordings, podcasts",
        paths=["/sdcard/Music", "/sdcard/Podcasts", "/sdcard/Audiobooks", "/sdcard/Recordings"],
    ),
    "whatsapp": CategoryConfig(
        id="whatsapp",
        label="WhatsApp Media & Backups",
        icon="message-circle",
        description="Images, video, voice notes, documents & daily encrypted db",
        paths=["/sdcard/Android/media/com.whatsapp/WhatsApp", "/sdcard/WhatsApp"],
    ),
    "telegram": CategoryConfig(
        id="telegram",
        label="Telegram Media & Files",
        icon="send",
        description="Downloaded media and documents",
        paths=["/sdcard/Telegram", "/sdcard/Android/data/org.telegram.messenger/files"],
    ),
    "sms": CategoryConfig(
        id="sms",
        label="SMS & Call Logs",
        icon="mail",
        description="Text messages & call history exported with HTML viewer and standard XML",
        paths=[],
        special_type="telephony",
    ),
    "sms_calls": CategoryConfig(
        id="sms_calls",
        label="SMS & Call Logs",
        icon="mail",
        description="Text messages & call history exported with HTML viewer and standard XML",
        paths=[],
        special_type="telephony",
    ),
    "private_space": CategoryConfig(
        id="private_space",
        label="Android 15+ Private Space",
        icon="lock",
        description="Secondary isolated user profile (/storage/emulated/10+)",
        paths=[],
        special_type="private_space",
    ),
    "custom_folders": CategoryConfig(
        id="custom_folders",
        label="Custom Folders",
        icon="folder-plus",
        description="User-defined additional directories on phone storage",
        paths=["/sdcard/Documents", "/sdcard/Download"],
    ),
}

DEFAULT_CATEGORIES = {k: v.to_dict() for k, v in CATEGORIES.items()}


def get_default_backup_dir() -> Path:
    """Returns the default backup directory, ensuring it exists on disk."""
    backup_dir = DEFAULT_BACKUP_ROOT
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_adb_path() -> str:
    """
    Resolves the ADB executable path.
    Prefers the bundled binary in bin/platform-tools/adb.exe,
    falling back to system PATH.
    """
    if DEFAULT_ADB_BIN.is_file():
        return str(DEFAULT_ADB_BIN)
    
    path_lookup = shutil.which("adb")
    if path_lookup:
        return path_lookup

    raise FileNotFoundError(
        f"ADB executable could not be found at {DEFAULT_ADB_BIN} or on system PATH."
    )


def get_category(category_id: str) -> Optional[CategoryConfig]:
    """Retrieve configuration for a specific category id."""
    return CATEGORIES.get(category_id)


def list_categories() -> List[CategoryConfig]:
    """Return all configured categories."""
    return list(CATEGORIES.values())
