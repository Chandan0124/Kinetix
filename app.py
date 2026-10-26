"""
Kinetix - High-Speed Phone-to-PC Delta Mirror & Recovery
Desktop Backend & Local API Server
"""

import os
import sys
import json
import time
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# Ensure core package can be imported
APP_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(APP_DIR))

try:
    from core.config import CategoryConfig, DEFAULT_CATEGORIES
    from core.adb_manager import AdbManager
    from core.indexer import RemoteIndexer, LocalIndexer
    from core.delta_engine import DeltaEngine, DeltaReport
    from core.transfer_engine import TransferEngine
    from core.sms_exporter import SmsExporter
except ImportError as err:
    print(f"Warning importing core modules: {err}")
    AdbManager = None

app = FastAPI(title="Kinetix Desktop Backend", version="1.0.0")

# Serve Web UI
WEB_DIR = APP_DIR / "web"
WEB_DIR.mkdir(exist_ok=True)

# State Management
class AppState:
    def __init__(self):
        self.adb = AdbManager() if AdbManager else None
        self.backup_root = APP_DIR / "Backups"
        self.backup_root.mkdir(parents=True, exist_ok=True)
        self.active_serial: Optional[str] = None
        self.last_delta_report: Optional[Dict[str, Any]] = None
        self.is_syncing: bool = False
        self.is_restoring: bool = False
        self.connected_websockets: List[WebSocket] = []
        self.lock = threading.Lock()
        self.main_loop: Optional[asyncio.AbstractEventLoop] = None
        self.current_telemetry: Dict[str, Any] = {}
        self.sync_summary: Optional[Dict[str, Any]] = None
        self.sync_error: Optional[str] = None
        self.restore_summary: Optional[Dict[str, Any]] = None
        self.restore_error: Optional[str] = None

state = AppState()

@app.on_event("startup")
async def on_startup():
    state.main_loop = asyncio.get_running_loop()

# WebSocket Progress Broadcast Helper
async def broadcast_progress(event_type: str, data: Dict[str, Any]):
    message = json.dumps({"type": event_type, **data})
    dead_sockets = []
    for ws in list(state.connected_websockets):
        try:
            await ws.send_text(message)
        except Exception:
            dead_sockets.append(ws)
    for ws in dead_sockets:
        if ws in state.connected_websockets:
            state.connected_websockets.remove(ws)

def send_ws_broadcast(event_type: str, data: Dict[str, Any]):
    """Thread-safe WebSocket event dispatch to main loop"""
    try:
        if state.main_loop and state.main_loop.is_running() and state.connected_websockets:
            asyncio.run_coroutine_threadsafe(broadcast_progress(event_type, data), state.main_loop)
    except Exception:
        pass

def sync_progress_callback(stats: Any):
    """Bridge sync thread callbacks to async WebSocket broadcast and in-memory state"""
    try:
        if hasattr(stats, "bytes_synced"):
            data = {
                "bytes_synced": getattr(stats, "bytes_synced", 0),
                "total_bytes": getattr(stats, "total_bytes", 0),
                "files_synced": getattr(stats, "files_synced", 0),
                "total_files": getattr(stats, "total_files", 0),
                "current_speed_mbps": getattr(stats, "current_speed_mbps", 0.0),
                "eta_seconds": getattr(stats, "eta_seconds", 0.0),
                "current_file": getattr(stats, "current_file", ""),
                "percentage": getattr(stats, "percentage", 0.0),
                "status": getattr(stats, "status", "transferring"),
            }
        elif isinstance(stats, dict):
            data = stats
        else:
            data = {}

        state.current_telemetry = data
        send_ws_broadcast("telemetry", data)
    except Exception:
        pass


@app.websocket("/ws/progress")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    state.connected_websockets.append(websocket)
    try:
        while True:
            # Keep socket alive
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        if websocket in state.connected_websockets:
            state.connected_websockets.remove(websocket)


@app.get("/api/sync/status")
async def get_sync_status():
    return {
        "is_syncing": state.is_syncing,
        "telemetry": state.current_telemetry,
        "completed": state.sync_summary is not None,
        "summary": state.sync_summary,
        "error": state.sync_error
    }


@app.get("/api/restore/status")
async def get_restore_status():
    return {
        "is_restoring": state.is_restoring,
        "telemetry": state.current_telemetry,
        "completed": state.restore_summary is not None,
        "summary": state.restore_summary,
        "error": state.restore_error
    }


@app.get("/api/status")
async def get_status():
    if not state.adb:
        from core.adb_manager import AdbManager
        state.adb = AdbManager()

    devices = state.adb.get_devices()
    selected_device = None
    profiles = []

    if devices:
        # Default to first connected device or currently active
        if state.active_serial:
            match = [d for d in devices if d.get("serial") == state.active_serial]
            selected_device = match[0] if match else devices[0]
        else:
            selected_device = devices[0]
        
        state.active_serial = selected_device.get("serial")
        profiles = state.adb.get_user_profiles(state.active_serial)

    from core.config import DEFAULT_CATEGORIES
    return {
        "connected": bool(selected_device),
        "device": selected_device,
        "devices": devices,
        "profiles": profiles,
        "backup_path": str(state.backup_root),
        "categories": DEFAULT_CATEGORIES,
        "is_syncing": state.is_syncing,
        "is_restoring": state.is_restoring
    }


class TargetPathRequest(BaseModel):
    path: str

@app.post("/api/target")
async def set_target_path(req: TargetPathRequest):
    new_path = Path(req.path)
    try:
        new_path.mkdir(parents=True, exist_ok=True)
        state.backup_root = new_path
        return {"success": True, "path": str(state.backup_root)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/browse_folder")
async def browse_folder():
    """Opens native Windows folder picker dialog"""
    import subprocess
    ps_cmd = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$f = New-Object System.Windows.Forms.FolderBrowserDialog; "
        "$f.Description = 'Select PC Target Backup Folder for Kinetix'; "
        "$f.ShowNewFolderButton = $true; "
        "if ($f.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) { Write-Output $f.SelectedPath }"
    )
    try:
        proc = subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True, text=True, timeout=60)
        selected = proc.stdout.strip()
        if selected and os.path.exists(selected):
            state.backup_root = Path(selected)
            return {"success": True, "path": selected}
        return {"success": False, "cancelled": True}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/open_folder")
async def open_backup_folder():
    """Opens the backup destination directory in Windows File Explorer"""
    try:
        target = resolve_device_backup_dir(state.backup_root)
        target.mkdir(parents=True, exist_ok=True)
        os.startfile(str(target))
        return {"success": True, "path": str(target)}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _to_canonical_category(cat: str) -> str:
    """Normalizes category IDs across frontend variations."""
    mapping = {
        "photos": "pics",
        "pics": "pics",
        "music": "music",
        "whatsapp": "whatsapp",
        "telegram": "telegram",
        "sms": "sms",
        "sms_calls": "sms",
        "private_space": "private_space",
        "custom_folders": "custom_folders",
        "custom": "custom_folders",
    }
    return mapping.get(cat, cat)


def _resolve_serial(serial: Optional[str] = None) -> Optional[str]:
    """Resolves device serial from request, active session, or auto-detection."""
    if serial:
        state.active_serial = serial
        return serial
    if state.active_serial:
        return state.active_serial
    if not state.adb:
        from core.adb_manager import AdbManager
        state.adb = AdbManager()
    devices = state.adb.get_devices()
    if devices:
        state.active_serial = devices[0].get("serial")
        return state.active_serial
    return None


def resolve_device_backup_dir(backup_root: Path, serial: Optional[str] = None) -> Path:
    r"""
    Intelligently determines the target backup folder for the given device.

    Handles:
    - User selected a general backup root (e.g. 'F:\Xiaomi17' or 'B:\MobilePCSync\Backups')
      -> returns root / safe_model (e.g. 'F:\Xiaomi17\25113PN0EI')
    - User selected the device model directory directly (e.g. 'F:\Xiaomi17\25113PN0EI')
      -> avoids duplicating model folder, returns 'F:\Xiaomi17\25113PN0EI'
    - User selected a subfolder inside the backup (e.g. 'F:\Xiaomi17\25113PN0EI\DCIM\Camera')
      -> truncates back to 'F:\Xiaomi17\25113PN0EI'
    - User selected an existing backup folder that directly contains phone storage folders ('DCIM', 'Music', etc.)
      -> returns that folder directly
    """
    safe_model = "AndroidPhone"
    safe_market = ""
    resolved_serial = serial or state.active_serial
    if resolved_serial and state.adb:
        try:
            device_info = state.adb.get_device_info(resolved_serial)
            raw = device_info.get("raw_model") or device_info.get("model", "AndroidPhone")
            safe_model = "".join([c if c.isalnum() or c in "-_" else "_" for c in raw])
            market = device_info.get("market_name", "")
            if market:
                safe_market = "".join([c if c.isalnum() or c in "-_" else "_" for c in market])
        except Exception:
            pass

    root = Path(backup_root).resolve()

    # 1. If safe_model or safe_market is one of the path components, truncate to that component
    lower_parts = [p.lower() for p in root.parts]
    candidate_names = [safe_model.lower()]
    if safe_market:
        candidate_names.append(safe_market.lower())
        candidate_names.append(safe_market.lower().replace("_", ""))

    for cand in candidate_names:
        if cand in lower_parts:
            idx = lower_parts.index(cand)
            return Path(*root.parts[:idx + 1])

    # 2. If a phone root folder (e.g., DCIM, Pictures, Music) is in the path components, truncate up to its parent
    phone_folders = {"dcim", "pictures", "movies", "music", "whatsapp", "telegram", "documents", "download"}
    for idx, part in enumerate(lower_parts):
        if part in phone_folders and idx > 0:
            return Path(*root.parts[:idx])

    # 3. If root has an existing subdirectory matching safe_model or safe_market, use it
    model_sub = root / safe_model
    if model_sub.is_dir():
        return model_sub
    if safe_market:
        market_sub = root / safe_market
        if market_sub.is_dir():
            return market_sub

    # 4. If root itself directly contains phone folders and no safe_model subdirectory, use root
    if root.is_dir():
        try:
            existing_subs = {e.name.lower() for e in os.scandir(root) if e.is_dir()}
            if existing_subs & phone_folders:
                return root
        except Exception:
            pass

    # 5. Default: root / safe_model
    return root / safe_model


def get_category_prefixes(category_id: str, paths: Optional[List[str]] = None) -> List[str]:
    """Computes relative folder prefixes that belong to a category."""
    prefixes = []
    if paths:
        for p in paths:
            norm = p.replace("\\", "/").strip("/")
            for sd_prefix in ("sdcard/", "storage/emulated/0/", "storage/emulated/10/"):
                if norm.lower().startswith(sd_prefix):
                    norm = norm[len(sd_prefix):]
                    break
            if norm:
                prefixes.append(norm.lower().rstrip("/") + "/")

    # Standard fallback defaults if no custom paths
    if not prefixes:
        defaults = {
            "pics": ["dcim/", "pictures/", "movies/"],
            "photos": ["dcim/", "pictures/", "movies/"],
            "music": ["music/", "podcasts/", "audiobooks/", "recordings/"],
            "whatsapp": ["whatsapp/", "android/media/com.whatsapp/"],
            "telegram": ["telegram/"],
            "custom_folders": ["documents/", "download/"],
        }
        prefixes = defaults.get(category_id, [category_id.lower().rstrip("/") + "/"])

    prefixes.append(category_id.lower().rstrip("/") + "/")
    return list(dict.fromkeys(prefixes))


def scan_local_files_for_category(
    device_backup_dir: Path,
    canonical_cat: str,
    paths: Optional[List[str]] = None,
    cached_all_local: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Scans and indexes local backup files for a specific category.
    Supports both direct phone folder layouts (DCIM/Camera) and category subfolder layouts (pics/DCIM/Camera).
    """
    from core.indexer import LocalIndexer

    if not device_backup_dir.is_dir():
        return {}

    # If category directory exists (e.g. device_backup_dir / "pics"), scan that too
    cat_dir = device_backup_dir / canonical_cat
    cat_dir_files = {}
    if cat_dir.is_dir():
        cat_dir_files = LocalIndexer.scan_local_category(cat_dir)

    all_local = cached_all_local
    if all_local is None:
        all_local = LocalIndexer.scan_local_category(device_backup_dir)

    prefixes = tuple(get_category_prefixes(canonical_cat, paths))
    cat_prefix_with_slash = f"{canonical_cat.lower()}/"
    result_map = {}

    # Map files from root scan
    for rel_path, info in all_local.items():
        rel_lower = rel_path.lower()
        if any(rel_lower.startswith(p) for p in prefixes):
            result_map[rel_path] = info
            if rel_lower.startswith(cat_prefix_with_slash):
                stripped = rel_path[len(cat_prefix_with_slash):]
                if stripped:
                    result_map[stripped] = info

    # Map files from cat_dir if separate
    for rel_path, info in cat_dir_files.items():
        result_map[rel_path] = info
        result_map[f"{canonical_cat}/{rel_path}"] = info

    return result_map


class FolderListRequest(BaseModel):
    category: str
    serial: Optional[str] = None

@app.post("/api/folders")
async def list_category_folders(req: FolderListRequest):
    """Discovers subfolders present under the category parent paths on the connected phone."""
    serial = _resolve_serial(req.serial)
    if not serial:
        raise HTTPException(status_code=400, detail="No Android device connected")

    from core.config import DEFAULT_CATEGORIES
    canonical_cat = _to_canonical_category(req.category)
    cat_meta = DEFAULT_CATEGORIES.get(canonical_cat) or DEFAULT_CATEGORIES.get(req.category)
    if not cat_meta:
        return {"category": req.category, "parent_paths": [], "subfolders": []}

    parent_paths = cat_meta.get("paths", [])
    subdirs = state.adb.list_subdirectories(serial, parent_paths)
    return {
        "category": canonical_cat,
        "parent_paths": parent_paths,
        "subfolders": subdirs
    }


class ScanRequest(BaseModel):
    categories: List[str]
    serial: Optional[str] = None
    custom_paths: Optional[Dict[str, List[str]]] = None

@app.post("/api/scan")
async def scan_differences(req: ScanRequest):
    serial = _resolve_serial(req.serial)
    if not serial:
        raise HTTPException(status_code=400, detail="No Android device connected")

    from core.config import DEFAULT_CATEGORIES
    from core.indexer import RemoteIndexer, LocalIndexer
    from core.delta_engine import DeltaEngine

    remote_indexer = RemoteIndexer(state.adb)
    delta_engine = DeltaEngine(tolerance_seconds=2.0)

    # Intelligently resolve the target backup directory on PC
    device_backup_dir = resolve_device_backup_dir(state.backup_root, serial)
    cached_all_local = LocalIndexer.scan_local_category(device_backup_dir) if device_backup_dir.is_dir() else {}

    all_remote = []
    all_local_map = {}

    seen_categories = set()
    for cat_id in req.categories:
        canonical_cat = _to_canonical_category(cat_id)
        if canonical_cat in seen_categories:
            continue
        seen_categories.add(canonical_cat)

        cat_meta = DEFAULT_CATEGORIES.get(canonical_cat) or DEFAULT_CATEGORIES.get(cat_id)
        if not cat_meta or cat_meta.get("special_type") == "telephony":
            continue

        # Use custom selected subfolders if specified; otherwise default paths
        paths = None
        if req.custom_paths:
            paths = req.custom_paths.get(cat_id) or req.custom_paths.get(canonical_cat)
        if not paths:
            paths = cat_meta.get("paths", [])

        remote_files = remote_indexer.scan_remote_category(serial, canonical_cat, paths)
        all_remote.extend(remote_files)

        cat_local_map = scan_local_files_for_category(
            device_backup_dir, canonical_cat, paths, cached_all_local=cached_all_local
        )
        all_local_map.update(cat_local_map)

    report = delta_engine.compare(all_remote, all_local_map)
    state.last_delta_report = report.to_dict()

    return {
        "success": True,
        "report": state.last_delta_report,
        "device_backup_dir": str(device_backup_dir)
    }


class SyncRequest(BaseModel):
    categories: List[str]
    serial: Optional[str] = None
    use_compression: bool = True
    max_workers: int = 4
    custom_paths: Optional[Dict[str, List[str]]] = None

@app.post("/api/sync")
async def start_sync(req: SyncRequest):
    if state.is_syncing:
        raise HTTPException(status_code=409, detail="A sync operation is already in progress")

    serial = _resolve_serial(req.serial)
    if not serial:
        raise HTTPException(status_code=400, detail="No Android device connected")

    def run_sync_thread():
        state.is_syncing = True
        state.sync_summary = None
        state.sync_error = None
        state.current_telemetry = {}
        try:
            from core.config import DEFAULT_CATEGORIES
            from core.indexer import RemoteIndexer, LocalIndexer
            from core.delta_engine import DeltaEngine
            from core.transfer_engine import TransferEngine
            from core.sms_exporter import SmsExporter

            device_backup_dir = resolve_device_backup_dir(state.backup_root, serial)
            device_backup_dir.mkdir(parents=True, exist_ok=True)

            # Keep screen awake during backup
            state.adb.stay_awake(serial, True)

            # Handle SMS export if selected
            sms_selected = any(_to_canonical_category(c) == "sms" for c in req.categories)
            if sms_selected:
                sms_dir = device_backup_dir / "SMS_and_Calls"
                sms_exporter = SmsExporter(state.adb)
                sms_exporter.export_sms_and_calls(serial, sms_dir)

            # Run Delta Scan
            remote_indexer = RemoteIndexer(state.adb)
            delta_engine = DeltaEngine(tolerance_seconds=2.0)
            cached_all_local = LocalIndexer.scan_local_category(device_backup_dir) if device_backup_dir.is_dir() else {}

            all_remote = []
            all_local_map = {}

            seen_categories = set()
            for cat_id in req.categories:
                canonical_cat = _to_canonical_category(cat_id)
                if canonical_cat in seen_categories:
                    continue
                seen_categories.add(canonical_cat)

                cat_meta = DEFAULT_CATEGORIES.get(canonical_cat) or DEFAULT_CATEGORIES.get(cat_id)
                if not cat_meta or cat_meta.get("special_type") == "telephony":
                    continue

                paths = None
                if req.custom_paths:
                    paths = req.custom_paths.get(cat_id) or req.custom_paths.get(canonical_cat)
                if not paths:
                    paths = cat_meta.get("paths", [])

                remote_files = remote_indexer.scan_remote_category(serial, canonical_cat, paths)
                all_remote.extend(remote_files)

                cat_local_map = scan_local_files_for_category(
                    device_backup_dir, canonical_cat, paths, cached_all_local=cached_all_local
                )
                all_local_map.update(cat_local_map)

            report = delta_engine.compare(all_remote, all_local_map)
            files_to_sync = report.items_to_sync

            # Transfer Engine
            transfer = TransferEngine(state.adb)
            transfer.sync_files(
                serial=serial,
                items_to_sync=files_to_sync,
                local_base_dir=device_backup_dir,
                progress_callback=sync_progress_callback,
                max_workers=req.max_workers,
                use_compression=req.use_compression
            )

            # Release stay awake
            state.adb.stay_awake(serial, False)

            summary = {
                "files_synced": len(files_to_sync),
                "bytes_synced": report.to_sync_bytes,
                "already_synced": report.already_synced_count,
                "bandwidth_saved_bytes": report.already_synced_bytes,
                "backup_dir": str(device_backup_dir)
            }
            state.sync_summary = summary
            send_ws_broadcast("completed", summary)
        except Exception as e:
            state.sync_error = str(e)
            send_ws_broadcast("error", {"error": str(e)})
        finally:
            state.is_syncing = False
            state.adb.stay_awake(serial, False)

    thread = threading.Thread(target=run_sync_thread, daemon=True)
    thread.start()

    return {"success": True, "message": "Superfast sync initiated"}


@app.get("/api/snapshots")
async def list_snapshots():
    """Lists existing local PC backups created in the target backup directory."""
    snapshots = []
    backup_root = state.backup_root
    if backup_root.is_dir():
        candidate_dirs = []

        # Check if backup_root itself directly contains phone folders
        phone_markers = {"dcim", "pictures", "movies", "music", "whatsapp", "pics"}
        try:
            root_subs = [s.name for s in os.scandir(backup_root) if s.is_dir() and not s.name.startswith(".")]
            if any(s.lower() in phone_markers for s in root_subs):
                candidate_dirs.append(backup_root)
        except Exception:
            pass

        for entry in os.scandir(str(backup_root)):
            if entry.is_dir() and not entry.name.startswith("."):
                candidate_dirs.append(Path(entry.path))

        seen_paths = set()
        for cand in candidate_dirs:
            cand_resolved = cand.resolve()
            if cand_resolved in seen_paths:
                continue
            seen_paths.add(cand_resolved)

            total_bytes = 0
            file_count = 0
            cats_present = []
            try:
                for sub in os.scandir(cand):
                    if sub.is_dir() and not sub.name.startswith("."):
                        cats_present.append(sub.name)
                for root, _, files in os.walk(cand):
                    file_count += len(files)
                    for f in files:
                        try:
                            total_bytes += os.path.getsize(os.path.join(root, f))
                        except Exception:
                            pass
                mtime_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(cand.stat().st_mtime))
                snapshots.append({
                    "id": cand.name,
                    "name": cand.name,
                    "mtime": mtime_str,
                    "file_count": file_count,
                    "size_bytes": total_bytes,
                    "size_gb": round(total_bytes / (1024 ** 3), 2),
                    "categories": cats_present,
                    "path": str(cand)
                })
            except Exception:
                pass
    return {"snapshots": sorted(snapshots, key=lambda s: s["mtime"], reverse=True)}


@app.get("/api/snapshot/details")
async def get_snapshot_details(snapshot: Optional[str] = None):
    """Returns detailed category, file count, size, and folder breakdowns for a PC snapshot."""
    from core.snapshot_inspector import inspect_snapshot_dir
    snap_path = None
    backup_root = state.backup_root

    if snapshot:
        cand = backup_root / snapshot
        if cand.is_dir():
            snap_path = cand
        elif backup_root.is_dir() and (backup_root.name == snapshot or str(backup_root) == snapshot):
            snap_path = backup_root
        else:
            try:
                for entry in os.scandir(str(backup_root)):
                    if entry.is_dir() and entry.name.lower() == snapshot.lower():
                        snap_path = Path(entry.path)
                        break
            except Exception:
                pass

    if not snap_path:
        snap_path = resolve_device_backup_dir(backup_root, state.active_serial)
        if not snap_path.is_dir():
            snap_path = backup_root

    return inspect_snapshot_dir(snap_path)


class RestoreAnalyzeRequest(BaseModel):
    categories: List[str]
    serial: Optional[str] = None
    snapshot: Optional[str] = None
    subfolders: Optional[Dict[str, List[str]]] = None

@app.post("/api/restore/analyze")
async def analyze_restore_endpoint(req: RestoreAnalyzeRequest):
    serial = _resolve_serial(req.serial)
    if not serial:
        raise HTTPException(status_code=400, detail="No Android device connected")

    if req.snapshot:
        snap_dir = state.backup_root / req.snapshot
        if snap_dir.is_dir():
            device_backup_dir = snap_dir
        elif state.backup_root.is_dir() and state.backup_root.name == req.snapshot:
            device_backup_dir = state.backup_root
        else:
            device_backup_dir = resolve_device_backup_dir(state.backup_root, serial)
    else:
        device_backup_dir = resolve_device_backup_dir(state.backup_root, serial)

    if not device_backup_dir.exists():
        raise HTTPException(status_code=404, detail=f"No backup snapshot found at {device_backup_dir}")

    canonical_categories = []
    for c in req.categories:
        can = _to_canonical_category(c)
        if can not in canonical_categories:
            canonical_categories.append(can)

    try:
        from core.transfer_engine import TransferEngine
        transfer = TransferEngine(state.adb)
        analysis = transfer.analyze_restore(
            serial=serial,
            categories=canonical_categories,
            device_backup_dir=device_backup_dir,
            subfolders=req.subfolders,
        )
        return analysis
    except Exception as exc:
        logger.error("Restore analysis error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

class RestoreRequest(BaseModel):
    categories: List[str]
    serial: Optional[str] = None
    snapshot: Optional[str] = None
    max_workers: int = 4
    subfolders: Optional[Dict[str, List[str]]] = None
    smart_delta: bool = True

@app.post("/api/restore")
async def start_restore(req: RestoreRequest):
    if state.is_restoring:
        raise HTTPException(status_code=409, detail="A restore operation is already in progress")

    serial = _resolve_serial(req.serial)
    if not serial:
        raise HTTPException(status_code=400, detail="No Android device connected")

    state.restore_cancel_event = threading.Event()

    def run_restore_thread():
        state.is_restoring = True
        state.restore_summary = None
        state.restore_error = None
        try:
            from core.transfer_engine import TransferEngine
            device_info = state.adb.get_device_info(serial)
            raw = device_info.get("raw_model") or device_info.get("model", "AndroidPhone")
            safe_model = "".join([c if c.isalnum() or c in "-_" else "_" for c in raw])

            if req.snapshot:
                snap_dir = state.backup_root / req.snapshot
                if snap_dir.is_dir():
                    device_backup_dir = snap_dir
                elif state.backup_root.is_dir() and state.backup_root.name == req.snapshot:
                    device_backup_dir = state.backup_root
                else:
                    device_backup_dir = resolve_device_backup_dir(state.backup_root, serial)
            else:
                device_backup_dir = resolve_device_backup_dir(state.backup_root, serial)

            if not device_backup_dir.exists():
                raise Exception(f"No backup found at {device_backup_dir}")

            canonical_categories = []
            for c in req.categories:
                can = _to_canonical_category(c)
                if can not in canonical_categories:
                    canonical_categories.append(can)

            transfer = TransferEngine(state.adb)
            results = transfer.restore_backup(
                serial=serial,
                categories=canonical_categories,
                device_backup_dir=device_backup_dir,
                progress_callback=sync_progress_callback,
                cancel_event=state.restore_cancel_event,
                max_workers=req.max_workers,
                subfolders=req.subfolders,
                smart_delta=req.smart_delta,
            )

            # Trigger MediaScanner volume re-index on Android 11-17+
            try:
                state.adb.trigger_media_scan(serial)
            except Exception as scan_err:
                logger.warning("Media scan dispatch completed with notice (non-fatal): %s", scan_err)

            total_pushed = sum(r.files_transferred for r in results.values())
            total_pushed_bytes = sum(r.bytes_transferred for r in results.values())
            total_skipped = sum(r.already_synced_files for r in results.values())
            total_skipped_bytes = sum(r.already_synced_bytes for r in results.values())

            pushed_mb = round(total_pushed_bytes / (1024 * 1024), 1)
            skipped_mb = round(total_skipped_bytes / (1024 * 1024), 1)

            if total_pushed == 0 and total_skipped > 0:
                msg = f"⚡ 100% Up-to-date! All {total_skipped} files ({skipped_mb} MB) are already identical on your phone. Nothing needed to be transferred!"
            elif total_skipped > 0:
                msg = f"Restore completed! Restored {total_pushed} files ({pushed_mb} MB). Verified & skipped {total_skipped} files ({skipped_mb} MB) already identical on phone."
            else:
                msg = f"Restore completed! {total_pushed} files restored ({pushed_mb} MB) successfully. MediaScanner triggered."

            summary = {
                "message": msg,
                "files_transferred": total_pushed,
                "bytes_transferred": total_pushed_bytes,
                "already_synced_files": total_skipped,
                "already_synced_bytes": total_skipped_bytes,
            }
            state.restore_summary = summary
            send_ws_broadcast("restore_completed", summary)
        except Exception as e:
            state.restore_error = str(e)
            send_ws_broadcast("error", {"error": str(e)})
        finally:
            state.is_restoring = False

    thread = threading.Thread(target=run_restore_thread, daemon=True)
    thread.start()

    return {"success": True, "message": "1-Click Restore initiated"}


@app.post("/api/restore/abort")
async def abort_restore():
    if not state.is_restoring:
        return {"success": True, "message": "No restore in progress"}
    if hasattr(state, "restore_cancel_event") and state.restore_cancel_event:
        state.restore_cancel_event.set()
    return {"success": True, "message": "Restore cancellation requested"}


@app.post("/api/device/media-scan")
async def manual_media_scan(serial: Optional[str] = None):
    target_serial = serial or state.active_serial
    if not target_serial:
        raise HTTPException(status_code=400, detail="No device connected")
    success = state.adb.trigger_media_scan(target_serial)
    return {"success": success, "message": "Volume media scan signal sent to Android"}


@app.get("/api/sms_data")
async def get_sms_data(serial: Optional[str] = None):
    target_serial = serial or state.active_serial
    device_info = state.adb.get_device_info(target_serial) if target_serial else {}
    raw = device_info.get("raw_model") or device_info.get("model", "AndroidPhone")
    safe_model = "".join([c if c.isalnum() or c in "-_" else "_" for c in raw])
    device_backup_dir = resolve_device_backup_dir(state.backup_root, target_serial)
    sms_dir = device_backup_dir / "SMS_and_Calls"

    sms_json = sms_dir / "sms_backup.json"
    call_json = sms_dir / "call_log_backup.json"

    data = {"messages": [], "calls": [], "has_backup": False}
    if sms_json.exists():
        data["has_backup"] = True
        try:
            with open(sms_json, "r", encoding="utf-8") as f:
                data["messages"] = json.load(f)
        except Exception:
            pass
    if call_json.exists():
        try:
            with open(call_json, "r", encoding="utf-8") as f:
                data["calls"] = json.load(f)
        except Exception:
            pass

    return data


# Mount static web directory
app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


def main():
    """
    Launches Kinetix with Windows 11 standalone application window,
    falling back gracefully to the default browser.
    """
    import uvicorn
    import webbrowser

    port = 8765
    url = f"http://127.0.0.1:{port}"

    def launch_window():
        time.sleep(1.0)
        # Windows 11 Standalone App Window (Native frame, no URL address bar or browser tabs)
        edge_candidates = [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        launched = False
        for ep in edge_candidates:
            if os.path.exists(ep):
                try:
                    import subprocess
                    cmd = [
                        ep,
                        f"--app={url}",
                        "--window-size=1280,840",
                        "--window-position=100,50",
                    ]
                    subprocess.Popen(cmd)
                    launched = True
                    break
                except Exception:
                    pass

        if not launched:
            webbrowser.open(url)

    threading.Thread(target=launch_window, daemon=True).start()
    print(f"\n========================================================")
    print(f"  Kinetix Desktop Application")
    print(f"  Active URL: {url}")
    print(f"  Press Ctrl+C in this console to terminate.")
    print(f"========================================================\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()

