"""
Kinetix Core Engine.
High-performance cross-platform backup, delta sync, path sanitization,
and telephony archive engine for Android.
"""

from core.adb_manager import AdbManager
from core.config import (
    CATEGORIES,
    DEFAULT_ADB_BIN,
    DEFAULT_BACKUP_ROOT,
    DEFAULT_CONCURRENCY,
    TIMESTAMP_TOLERANCE_SECONDS,
    CategoryConfig,
    get_adb_path,
    get_default_backup_dir,
)
from core.delta_engine import (
    DeltaEngine,
    DeltaItem,
    DeltaReport,
    SyncStatus,
)
from core.indexer import (
    LocalFileInfo,
    LocalIndexer,
    RemoteFileInfo,
    RemoteIndexer,
)
from core.path_sanitizer import MAP_FILENAME, PathSanitizer
from core.sms_exporter import SmsExporter
from core.transfer_engine import (
    ProgressCallback,
    TransferEngine,
    TransferProgress,
    TransferResult,
)

__all__ = [
    "AdbManager",
    "CATEGORIES",
    "CategoryConfig",
    "DEFAULT_ADB_BIN",
    "DEFAULT_BACKUP_ROOT",
    "DEFAULT_CONCURRENCY",
    "DeltaEngine",
    "DeltaItem",
    "DeltaReport",
    "LocalFileInfo",
    "LocalIndexer",
    "PathSanitizer",
    "ProgressCallback",
    "RemoteFileInfo",
    "RemoteIndexer",
    "SmsExporter",
    "SyncStatus",
    "TIMESTAMP_TOLERANCE_SECONDS",
    "TransferEngine",
    "TransferProgress",
    "TransferResult",
    "get_adb_path",
    "get_default_backup_dir",
]
