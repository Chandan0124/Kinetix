"""
Unit tests for core.transfer_engine.
Tests multi-threaded concurrent transfers, .hyperpart atomic rename,
size verification, mtime preservation, restore flow, and progress callbacks.
"""

import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.adb_manager import AdbManager
from core.delta_engine import DeltaItem, SyncStatus
from core.indexer import LocalFileInfo, RemoteFileInfo
from core.transfer_engine import TransferEngine, TransferProgress


class TestTransferEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hypersync_test_transfer_")
        self.mock_adb = MagicMock(spec=AdbManager)
        self.engine = TransferEngine(adb_manager=self.mock_adb, max_workers=2)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_sync_items_success_atomic_and_mtime(self):
        """Tests successful pull with .hyperpart atomic rename and mtime preservation."""
        items = [
            DeltaItem(
                rel_path="DCIM/Camera/IMG_01.jpg",
                status=SyncStatus.TO_SYNC_NEW,
                remote_file=RemoteFileInfo(
                    path="/sdcard/DCIM/Camera/IMG_01.jpg",
                    rel_path="DCIM/Camera/IMG_01.jpg",
                    size=1024,
                    mtime=1690000000.0,
                    category="pics",
                ),
            ),
            DeltaItem(
                rel_path="DCIM/Camera/IMG_02:colon.jpg",
                status=SyncStatus.TO_SYNC_NEW,
                remote_file=RemoteFileInfo(
                    path="/sdcard/DCIM/Camera/IMG_02:colon.jpg",
                    rel_path="DCIM/Camera/IMG_02:colon.jpg",
                    size=2048,
                    mtime=1690001000.0,
                    category="pics",
                ),
            ),
        ]

        # Mock adb.pull to create the .hyperpart file with matching size
        def mock_pull(serial, remote_path, local_path, timeout=600):
            self.assertTrue(local_path.endswith(".hyperpart"))
            p = Path(local_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            if "IMG_01.jpg" in remote_path:
                p.write_bytes(b"A" * 1024)
            else:
                p.write_bytes(b"B" * 2048)
            return True

        self.mock_adb.pull.side_effect = mock_pull

        progress_reports = []
        def on_progress(p: TransferProgress):
            progress_reports.append(p)

        res = self.engine.sync_items(
            serial="test_serial",
            items=items,
            backup_root_dir=self.temp_dir,
            progress_callback=on_progress,
        )

        self.assertTrue(res.success)
        self.assertEqual(res.files_transferred, 2)
        self.assertEqual(res.bytes_transferred, 1024 + 2048)
        self.assertEqual(len(res.errors), 0)

        # Verify final files on disk (not .hyperpart)
        file1 = Path(self.temp_dir) / "DCIM" / "Camera" / "IMG_01.jpg"
        file2 = Path(self.temp_dir) / "DCIM" / "Camera" / "IMG_02%3Acolon.jpg"

        self.assertTrue(file1.is_file())
        self.assertTrue(file2.is_file())
        self.assertEqual(file1.stat().st_size, 1024)
        self.assertEqual(file2.stat().st_size, 2048)

        # Verify mtime preserved
        self.assertEqual(file1.stat().st_mtime, 1690000000.0)
        self.assertEqual(file2.stat().st_mtime, 1690001000.0)

        # Verify progress callback was invoked
        self.assertTrue(len(progress_reports) > 0)
        last_prog = progress_reports[-1]
        self.assertEqual(last_prog.files_synced, 2)
        self.assertEqual(last_prog.total_files, 2)

    def test_sync_size_mismatch_fails_and_cleans_part(self):
        """Tests that a file whose downloaded size differs from expected size is rejected."""
        items = [
            DeltaItem(
                rel_path="DCIM/bad_size.jpg",
                status=SyncStatus.TO_SYNC_NEW,
                remote_file=RemoteFileInfo(
                    path="/sdcard/DCIM/bad_size.jpg",
                    rel_path="DCIM/bad_size.jpg",
                    size=5000,
                    mtime=1690000000.0,
                    category="pics",
                ),
            )
        ]

        def mock_pull(serial, remote_path, local_path, timeout=600):
            # Write only 100 bytes instead of expected 5000
            p = Path(local_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b"X" * 100)
            return True

        self.mock_adb.pull.side_effect = mock_pull

        res = self.engine.sync_items(
            serial="test_serial",
            items=items,
            backup_root_dir=self.temp_dir,
        )

        self.assertFalse(res.success)
        self.assertEqual(res.files_transferred, 0)
        self.assertEqual(len(res.errors), 1)
        self.assertIn("Size mismatch", res.errors[0])

        # Verify neither final file nor part file remained
        dest_final = Path(self.temp_dir) / "DCIM" / "bad_size.jpg"
        dest_part = Path(self.temp_dir) / "DCIM" / "bad_size.jpg.hyperpart"
        self.assertFalse(dest_final.exists())
        self.assertFalse(dest_part.exists())

    def test_restore_category_and_media_scan(self):
        """Tests restore flow pushing files back to device and triggering media scan."""
        # Create local file to restore
        cat_dir = Path(self.temp_dir) / "pics"
        img_dir = cat_dir / "DCIM" / "Camera"
        img_dir.mkdir(parents=True, exist_ok=True)
        local_img = img_dir / "restore_me.jpg"
        local_img.write_bytes(b"RESTORE_CONTENT")

        self.mock_adb.push.return_value = True
        self.mock_adb.run_shell.side_effect = lambda serial, cmd, **kw: (
            str(len(b"RESTORE_CONTENT")) if "stat -c" in cmd else ""
        )
        self.mock_adb.trigger_media_scan.return_value = True

        res = self.engine.restore_category(
            serial="test_serial",
            local_category_dir=cat_dir,
            remote_dest_path="/sdcard",
        )

        self.assertTrue(res.success)
        self.assertEqual(res.files_transferred, 1)
        self.assertEqual(res.bytes_transferred, len(b"RESTORE_CONTENT"))

        # Verify push called with correct remote path
        expected_remote = "/sdcard/DCIM/Camera/restore_me.jpg"
        self.mock_adb.push.assert_called_with("test_serial", str(local_img), expected_remote)

        # Verify media scan was triggered
        self.mock_adb.trigger_media_scan.assert_called_with("test_serial", folder_or_volume="external_primary")

    def test_restore_category_with_subfolder_filter(self):
        """Tests that user-selected subfolder filtering restores ONLY matching files."""
        backup_root = Path(self.temp_dir) / "device_snap"
        cam_dir = backup_root / "DCIM" / "Camera"
        res_dir = backup_root / "DCIM" / "Restored"
        cam_dir.mkdir(parents=True, exist_ok=True)
        res_dir.mkdir(parents=True, exist_ok=True)

        cam_file = cam_dir / "photo1.jpg"
        cam_file.write_bytes(b"CAMERA_PHOTO")
        res_file = res_dir / "old_photo.jpg"
        res_file.write_bytes(b"RESTORED_PHOTO")

        self.mock_adb.push.return_value = True
        self.mock_adb.run_shell.side_effect = lambda serial, cmd, **kw: (
            str(len(b"CAMERA_PHOTO")) if "stat -c" in cmd else ""
        )
        self.mock_adb.trigger_media_scan.return_value = True

        # Restore with ONLY 'DCIM/Camera' selected
        results = self.engine.restore_backup(
            serial="test_serial",
            categories=["pics"],
            device_backup_dir=backup_root,
            subfolders={"pics": ["DCIM/Camera"]}
        )

        self.assertIn("pics", results)
        res = results["pics"]
        self.assertTrue(res.success)
        # Only photo1.jpg transferred, old_photo.jpg was filtered out
        self.assertEqual(res.files_transferred, 1)
        self.assertEqual(res.bytes_transferred, len(b"CAMERA_PHOTO"))


if __name__ == "__main__":
    unittest.main()
