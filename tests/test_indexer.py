"""
Unit tests for core.indexer.
Tests RemoteIndexer parsing/relative-path logic and LocalIndexer recursive scanning.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from core.indexer import LocalFileInfo, LocalIndexer, RemoteFileInfo, RemoteIndexer
from core.path_sanitizer import MAP_FILENAME, PathSanitizer


class TestIndexer(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hypersync_test_indexer_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_compute_rel_path(self):
        """Tests deterministic relative path calculation preserving category subdirectories."""
        cat_paths = ["/sdcard/DCIM", "/sdcard/Pictures", "/sdcard/Movies"]

        self.assertEqual(
            RemoteIndexer.compute_rel_path("/sdcard/DCIM/Camera/IMG_001.jpg", cat_paths),
            "DCIM/Camera/IMG_001.jpg",
        )
        self.assertEqual(
            RemoteIndexer.compute_rel_path("/sdcard/Pictures/Screenshots/sc_01.png", cat_paths),
            "Pictures/Screenshots/sc_01.png",
        )
        self.assertEqual(
            RemoteIndexer.compute_rel_path("/sdcard/Movies/clip.mp4", cat_paths),
            "Movies/clip.mp4",
        )

        # WhatsApp paths
        wa_paths = [
            "/sdcard/Android/media/com.whatsapp/WhatsApp",
            "/sdcard/WhatsApp",
        ]
        self.assertEqual(
            RemoteIndexer.compute_rel_path(
                "/sdcard/Android/media/com.whatsapp/WhatsApp/Databases/msgstore.db",
                wa_paths,
            ),
            "WhatsApp/Databases/msgstore.db",
        )
        self.assertEqual(
            RemoteIndexer.compute_rel_path(
                "/sdcard/WhatsApp/Media/image.jpg",
                wa_paths,
            ),
            "WhatsApp/Media/image.jpg",
        )

    def test_parse_stat_output(self):
        """Tests parsing stdout of remote stat batch find commands."""
        stdout = (
            "102400|1698234567|/sdcard/DCIM/Camera/photo1.jpg\n"
            "204800|1698234600.50|/sdcard/Pictures/wall.png\n"
            "invalid_line_without_pipes\n"
            "not_a_size|1698234600|/sdcard/DCIM/bad.jpg\n"
        )
        cat_paths = ["/sdcard/DCIM", "/sdcard/Pictures"]
        items = RemoteIndexer._parse_stat_output(stdout, "pics", cat_paths)

        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].rel_path, "DCIM/Camera/photo1.jpg")
        self.assertEqual(items[0].size, 102400)
        self.assertEqual(items[0].mtime, 1698234567.0)
        self.assertEqual(items[0].category, "pics")

        self.assertEqual(items[1].rel_path, "Pictures/wall.png")
        self.assertEqual(items[1].size, 204800)
        self.assertEqual(items[1].mtime, 1698234600.50)

    def test_local_indexer_scanning(self):
        """Tests LocalIndexer directory scanning, exclusion of .hyper_map.json and .hyperpart, and path mapping."""
        base = Path(self.temp_dir)
        cam_dir = base / "DCIM" / "Camera"
        cam_dir.mkdir(parents=True, exist_ok=True)

        # Create normal file
        file1 = cam_dir / "photo1.jpg"
        file1.write_bytes(b"content123")
        os.utime(file1, (1690000000, 1690000000))

        # Create sanitized file and record mapping
        file2 = cam_dir / "IMG_12%3A00.jpg"
        file2.write_bytes(b"content456")
        os.utime(file2, (1690001000, 1690001000))
        PathSanitizer.record_mapping(base, "DCIM/Camera/IMG_12%3A00.jpg", "DCIM/Camera/IMG_12:00.jpg")

        # Create temporary file that should be ignored
        part_file = cam_dir / "download.mp4.hyperpart"
        part_file.write_bytes(b"temp_part_content")

        # Scan local category
        local_map = LocalIndexer.scan_local_category(base)

        # Should only contain photo1.jpg and the desanitized IMG_12:00.jpg
        self.assertEqual(len(local_map), 2)
        self.assertIn("DCIM/Camera/photo1.jpg", local_map)
        self.assertIn("DCIM/Camera/IMG_12:00.jpg", local_map)
        self.assertNotIn(MAP_FILENAME, local_map)
        self.assertNotIn("DCIM/Camera/download.mp4.hyperpart", local_map)

        info1 = local_map["DCIM/Camera/photo1.jpg"]
        self.assertEqual(info1.size, len(b"content123"))
        self.assertEqual(info1.mtime, 1690000000)

        info2 = local_map["DCIM/Camera/IMG_12:00.jpg"]
        self.assertEqual(info2.size, len(b"content456"))
        self.assertEqual(info2.rel_path, "DCIM/Camera/IMG_12:00.jpg")
        self.assertEqual(info2.local_rel_path, "DCIM/Camera/IMG_12%3A00.jpg")


if __name__ == "__main__":
    unittest.main()
