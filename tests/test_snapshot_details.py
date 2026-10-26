"""
Unit tests for snapshot inspection and restore subfolder filtering.
Validates category breakdown, album discovery, file counting, and size calculations.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.snapshot_inspector import inspect_snapshot_dir, format_size_bytes
from core.transfer_engine import TransferEngine


class TestSnapshotDetails(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="kinetix_snap_test_")
        self.snap_path = Path(self.temp_dir) / "25113PN0EI"
        self.snap_path.mkdir(parents=True)

        # Setup Photos & Videos albums
        cam_dir = self.snap_path / "DCIM" / "Camera"
        cam_dir.mkdir(parents=True)
        (cam_dir / "IMG_20261026_001.jpg").write_bytes(b"A" * 1024 * 100) # 100 KB
        (cam_dir / "IMG_20261026_002.jpg").write_bytes(b"B" * 1024 * 200) # 200 KB

        restored_dir = self.snap_path / "DCIM" / "Restored"
        restored_dir.mkdir(parents=True)
        (restored_dir / "Restored_001.png").write_bytes(b"C" * 1024 * 50)  # 50 KB

        # Setup Music albums
        music_dir = self.snap_path / "Music" / "SpotFlac"
        music_dir.mkdir(parents=True)
        (music_dir / "Track01.flac").write_bytes(b"D" * 1024 * 500)       # 500 KB
        (music_dir / "Track02.flac").write_bytes(b"E" * 1024 * 500)       # 500 KB

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_inspect_snapshot_categories_and_subfolders(self):
        """Tests that photos and music folders are properly grouped and indexed."""
        report = inspect_snapshot_dir(self.snap_path)

        self.assertEqual(report["snapshot"], "25113PN0EI")
        self.assertEqual(report["total_files"], 5)
        self.assertIn("categories", report)

        cats = report["categories"]

        # Photos check
        pics = cats["pics"]
        self.assertTrue(pics["has_backup"])
        self.assertEqual(pics["file_count"], 3)
        self.assertEqual(len(pics["subfolders"]), 2)

        sub_names = [s["name"] for s in pics["subfolders"]]
        self.assertIn("DCIM/Camera", sub_names)
        self.assertIn("DCIM/Restored", sub_names)

        cam_info = next(s for s in pics["subfolders"] if s["name"] == "DCIM/Camera")
        self.assertEqual(cam_info["file_count"], 2)

        restored_info = next(s for s in pics["subfolders"] if s["name"] == "DCIM/Restored")
        self.assertEqual(restored_info["file_count"], 1)

        # Music check
        music = cats["music"]
        self.assertTrue(music["has_backup"])
        self.assertEqual(music["file_count"], 2)
        self.assertEqual(len(music["subfolders"]), 1)
        self.assertEqual(music["subfolders"][0]["name"], "Music/SpotFlac")
        self.assertEqual(music["subfolders"][0]["file_count"], 2)

        # Unbacked up categories check
        whatsapp = cats["whatsapp"]
        self.assertFalse(whatsapp["has_backup"])
        self.assertEqual(whatsapp["file_count"], 0)
        self.assertEqual(len(whatsapp["subfolders"]), 0)

        sms = cats["sms"]
        self.assertFalse(sms["has_backup"])
        self.assertEqual(sms["file_count"], 0)

    def test_subfolder_filtering_matching(self):
        """Tests TransferEngine._is_file_in_subfolders matching logic."""
        # 1. Matching 'DCIM/Camera'
        self.assertTrue(
            TransferEngine._is_file_in_subfolders("Camera/photo.jpg", "DCIM", ["DCIM/Camera"])
        )
        self.assertFalse(
            TransferEngine._is_file_in_subfolders("Restored/old.png", "DCIM", ["DCIM/Camera"])
        )

        # 2. Matching 'Music/SpotFlac'
        self.assertTrue(
            TransferEngine._is_file_in_subfolders("SpotFlac/song.flac", "Music", ["Music/SpotFlac"])
        )
        self.assertFalse(
            TransferEngine._is_file_in_subfolders("Other/song.mp3", "Music", ["Music/SpotFlac"])
        )

    def test_format_size_bytes(self):
        """Tests human readable formatting for bytes."""
        self.assertEqual(format_size_bytes(500), "500 B")
        self.assertEqual(format_size_bytes(1024 * 150), "150.0 KB")
        self.assertEqual(format_size_bytes(1024 * 1024 * 45), "45.0 MB")
        self.assertEqual(format_size_bytes(int(1024 * 1024 * 1024 * 3.5)), "3.50 GB")


if __name__ == "__main__":
    unittest.main()
