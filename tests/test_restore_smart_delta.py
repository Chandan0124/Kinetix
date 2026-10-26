import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.adb_manager import AdbManager
from core.indexer import RemoteFileInfo
from core.transfer_engine import TransferEngine


class TestRestoreSmartDelta(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="test_restore_delta_")
        self.mock_adb = MagicMock(spec=AdbManager)
        self.engine = TransferEngine(adb_manager=self.mock_adb, max_workers=2)

        # Create mock backup directory with 3 music files
        self.backup_dir = Path(self.temp_dir) / "Music" / "SpotFlac"
        self.backup_dir.mkdir(parents=True)
        (self.backup_dir / "track1.flac").write_bytes(b"A" * 1000)
        (self.backup_dir / "track2.flac").write_bytes(b"B" * 2000)
        (self.backup_dir / "track3.flac").write_bytes(b"C" * 3000)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch("core.transfer_engine.RemoteIndexer")
    def test_smart_delta_all_files_already_on_phone(self, mock_remote_indexer_cls):
        """When all files already exist with identical size, 0 files should be pushed."""
        mock_indexer_inst = MagicMock()
        mock_remote_indexer_cls.return_value = mock_indexer_inst

        # Simulate phone already having track1, track2, and track3 with identical sizes
        mock_indexer_inst.scan_remote_category.return_value = [
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track1.flac", rel_path="track1.flac", size=1000, mtime=1700000.0, category="restore"),
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track2.flac", rel_path="track2.flac", size=2000, mtime=1700000.0, category="restore"),
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track3.flac", rel_path="track3.flac", size=3000, mtime=1700000.0, category="restore"),
        ]

        progress_events = []
        res = self.engine.restore_backup(
            serial="test_serial",
            categories=["music"],
            device_backup_dir=self.temp_dir,
            progress_callback=lambda p: progress_events.append(p),
            smart_delta=True,
        )

        # ADB push should NEVER have been called!
        self.assertEqual(self.mock_adb.push.call_count, 0)
        # Results should show 0 transferred, 3 skipped
        self.assertEqual(res["music"].files_transferred, 0)
        self.assertEqual(res["music"].already_synced_files, 3)
        self.assertEqual(res["music"].already_synced_bytes, 6000)
        self.assertTrue(res["music"].success)

    @patch("core.transfer_engine.RemoteIndexer")
    def test_smart_delta_partial_files_missing(self, mock_remote_indexer_cls):
        """When only 1 file is missing, only that 1 file should be pushed."""
        mock_indexer_inst = MagicMock()
        mock_remote_indexer_cls.return_value = mock_indexer_inst

        # Phone only has track1 and track2, missing track3
        mock_indexer_inst.scan_remote_category.return_value = [
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track1.flac", rel_path="track1.flac", size=1000, mtime=1700000.0, category="restore"),
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track2.flac", rel_path="track2.flac", size=2000, mtime=1700000.0, category="restore"),
        ]
        self.mock_adb.push.return_value = True

        res = self.engine.restore_backup(
            serial="test_serial",
            categories=["music"],
            device_backup_dir=self.temp_dir,
            smart_delta=True,
        )

        # ADB push should have been called EXACTLY once for track3
        self.assertEqual(self.mock_adb.push.call_count, 1)
        self.assertEqual(res["music"].files_transferred, 1)
        self.assertEqual(res["music"].bytes_transferred, 3000)
        self.assertEqual(res["music"].already_synced_files, 2)
        self.assertEqual(res["music"].already_synced_bytes, 3000)

    @patch("core.transfer_engine.RemoteIndexer")
    def test_analyze_restore_metrics(self, mock_remote_indexer_cls):
        """Tests that analyze_restore calculates exact counts and time saved without pushing."""
        mock_indexer_inst = MagicMock()
        mock_remote_indexer_cls.return_value = mock_indexer_inst

        # Phone already has track1 (1000b) and track2 (2000b), track3 (3000b) is missing
        mock_indexer_inst.scan_remote_category.return_value = [
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track1.flac", rel_path="track1.flac", size=1000, mtime=1700000.0, category="restore"),
            RemoteFileInfo(path="/sdcard/Music/SpotFlac/track2.flac", rel_path="track2.flac", size=2000, mtime=1700000.0, category="restore"),
        ]

        analysis = self.engine.analyze_restore(
            serial="test_serial",
            categories=["music"],
            device_backup_dir=self.temp_dir,
        )

        self.assertEqual(analysis["total_files"], 3)
        self.assertEqual(analysis["total_bytes"], 6000)
        self.assertEqual(analysis["already_on_phone_count"], 2)
        self.assertEqual(analysis["already_on_phone_bytes"], 3000)
        self.assertEqual(analysis["to_restore_count"], 1)
        self.assertEqual(analysis["to_restore_bytes"], 3000)
        self.assertEqual(len(analysis["to_restore_sample"]), 1)
        self.assertEqual(analysis["to_restore_sample"][0]["name"], "track3.flac")
        # Ensure 0 pushes were made
        self.assertEqual(self.mock_adb.push.call_count, 0)


if __name__ == "__main__":
    unittest.main()
