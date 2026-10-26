"""
Unit tests for app.py FastAPI API endpoints.
Tests /api/status, /api/snapshots, /api/folders, /api/scan, and category canonicalization.
"""

import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import shutil

from fastapi.testclient import TestClient
from app import app, state


class TestApiEndpoints(unittest.TestCase):

    def setUp(self):
        self.temp_backup_dir = tempfile.mkdtemp(prefix="hypersync_api_test_")
        self.orig_backup_root = state.backup_root
        state.backup_root = Path(self.temp_backup_dir)
        self.client = TestClient(app)

    def tearDown(self):
        state.backup_root = self.orig_backup_root
        shutil.rmtree(self.temp_backup_dir, ignore_errors=True)

    def test_status_disconnected(self):
        """When no device is connected, status returns connected=False and empty device list."""
        with patch.object(state.adb, 'get_devices', return_value=[]):
            res = self.client.get("/api/status")
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertFalse(data["connected"])
            self.assertIsNone(data["device"])

    def test_status_connected(self):
        """When device is connected, status returns rich device metrics."""
        mock_device = {
            "serial": "TEST123456",
            "model": "Pixel 9 Pro",
            "manufacturer": "Google",
            "android_version": "15",
            "sdk_level": 35,
            "battery_level": 88,
            "storage_total": 256000000000,
            "storage_free": 120000000000,
            "storage_info": {"total_bytes": 256000000000, "free_bytes": 120000000000}
        }
        with patch.object(state.adb, 'get_devices', return_value=[mock_device]):
            with patch.object(state.adb, 'get_user_profiles', return_value=[]):
                res = self.client.get("/api/status")
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["connected"])
                self.assertEqual(data["device"]["model"], "Pixel 9 Pro")
                self.assertEqual(data["device"]["battery_level"], 88)

    def test_snapshots_empty_and_populated(self):
        """Tests /api/snapshots when empty and when backups exist on disk."""
        res = self.client.get("/api/snapshots")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["snapshots"], [])

        # Create a mock backup snapshot on disk
        snap_dir = state.backup_root / "Pixel_9_Pro"
        (snap_dir / "pics" / "DCIM").mkdir(parents=True, exist_ok=True)
        (snap_dir / "pics" / "DCIM" / "test.jpg").write_bytes(b"hello world")

        res2 = self.client.get("/api/snapshots")
        self.assertEqual(res2.status_code, 200)
        snaps = res2.json()["snapshots"]
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps[0]["name"], "Pixel_9_Pro")
        self.assertIn("pics", snaps[0]["categories"])
        self.assertEqual(snaps[0]["file_count"], 1)

    def test_folders_alias_resolution(self):
        """Tests that /api/folders works for 'photos' and 'pics' aliases."""
        with patch.object(state.adb, 'list_subdirectories', return_value=["/sdcard/DCIM/Camera"]):
            state.active_serial = "TEST123456"
            res = self.client.post("/api/folders", json={"category": "photos"})
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertEqual(data["category"], "pics")
            self.assertEqual(data["subfolders"], ["/sdcard/DCIM/Camera"])

    def test_sync_status_endpoint(self):
        """Tests /api/sync/status telemetry and completion status."""
        state.is_syncing = False
        state.current_telemetry = {"bytes_synced": 1024, "current_speed_mbps": 45.2}
        state.sync_summary = {"files_synced": 5}
        res = self.client.get("/api/sync/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["is_syncing"])
        self.assertEqual(data["telemetry"]["bytes_synced"], 1024)
        self.assertTrue(data["completed"])
        self.assertEqual(data["summary"]["files_synced"], 5)

    def test_restore_status_endpoint(self):
        """Tests /api/restore/status endpoint."""
        state.is_restoring = False
        state.restore_summary = {"message": "Restore completed"}
        res = self.client.get("/api/restore/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data["is_restoring"])
        self.assertTrue(data["completed"])
        self.assertEqual(data["summary"]["message"], "Restore completed")

    def test_resolve_device_backup_dir_nested_and_direct(self):
        """Tests that resolve_device_backup_dir correctly resolves device root from any subfolder."""
        from app import resolve_device_backup_dir

        with patch.object(state.adb, 'get_device_info', return_value={"model": "25113PN0EI"}):
            state.active_serial = "TEST123456"

            # 1. Base root path -> appends model
            p1 = Path(r"C:\Backups")
            self.assertEqual(resolve_device_backup_dir(p1, "TEST123456"), Path(r"C:\Backups\25113PN0EI"))

            # 2. Already device folder -> does not duplicate
            p2 = Path(r"C:\Backups\25113PN0EI")
            self.assertEqual(resolve_device_backup_dir(p2, "TEST123456"), Path(r"C:\Backups\25113PN0EI"))

            # 3. Subfolder DCIM\Camera -> climbs to 25113PN0EI
            p3 = Path(r"C:\Backups\25113PN0EI\DCIM\Camera")
            self.assertEqual(resolve_device_backup_dir(p3, "TEST123456"), Path(r"C:\Backups\25113PN0EI"))

    def test_scan_detects_already_synced_photos(self):
        """Tests that existing backup files under DCIM/Camera are detected as ALREADY_SYNCED."""
        from core.indexer import RemoteFileInfo

        # Create a mock device backup with existing photo on disk
        device_dir = state.backup_root / "25113PN0EI"
        cam_dir = device_dir / "DCIM" / "Camera"
        cam_dir.mkdir(parents=True, exist_ok=True)
        photo1 = cam_dir / "existing_photo.jpg"
        photo1.write_bytes(b"A" * 2048)
        import os
        os.utime(photo1, (1700000000, 1700000000))

        mock_remote = [
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/existing_photo.jpg",
                rel_path="DCIM/Camera/existing_photo.jpg",
                size=2048,
                mtime=1700000000.0,
                category="pics",
            ),
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/new_photo.jpg",
                rel_path="DCIM/Camera/new_photo.jpg",
                size=4096,
                mtime=1700000100.0,
                category="pics",
            ),
        ]

        with patch.object(state.adb, 'get_device_info', return_value={"model": "25113PN0EI"}):
            with patch('core.indexer.RemoteIndexer.scan_remote_category', return_value=mock_remote):
                state.active_serial = "TEST123456"
                res = self.client.post("/api/scan", json={"categories": ["photos"]})
                self.assertEqual(res.status_code, 200)
                data = res.json()
                self.assertTrue(data["success"])
                rep = data["report"]
                self.assertEqual(rep["total_remote_files"], 2)
                self.assertEqual(rep["already_synced_count"], 1)
                self.assertEqual(rep["to_sync_count"], 1)
                self.assertEqual(rep["items_to_sync"][0]["rel_path"], "DCIM/Camera/new_photo.jpg")


if __name__ == "__main__":
    unittest.main()
