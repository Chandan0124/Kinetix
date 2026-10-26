"""
Unit tests for core.path_sanitizer.
Tests NTFS illegal character escaping, reserved device names, and roundtrip mapping.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from core.path_sanitizer import MAP_FILENAME, PathSanitizer


class TestPathSanitizer(unittest.TestCase):

    def setUp(self):
        PathSanitizer.clear_memory_cache()
        self.temp_dir = tempfile.mkdtemp(prefix="hypersync_test_sanitizer_")

    def tearDown(self):
        PathSanitizer.clear_memory_cache()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_clean_path_unmodified(self):
        """Standard valid paths should not be modified."""
        path = "DCIM/Camera/IMG_20231025_001.jpg"
        sanitized, modified = PathSanitizer.sanitize_relpath(path)
        self.assertFalse(modified)
        self.assertEqual(sanitized, path)
        self.assertEqual(PathSanitizer.desanitize_relpath(sanitized), path)

    def test_colon_escaping(self):
        """Colons in filenames (e.g. Android timestamp photos) must be escaped."""
        orig = "DCIM/Camera/VID_2023-10-25_12:30:45.mp4"
        sanitized, modified = PathSanitizer.sanitize_relpath(orig)
        self.assertTrue(modified)
        self.assertEqual(sanitized, "DCIM/Camera/VID_2023-10-25_12%3A30%3A45.mp4")
        self.assertNotIn(":", sanitized)
        # Verify desanitization
        restored = PathSanitizer.desanitize_relpath(sanitized)
        self.assertEqual(restored, orig)

    def test_all_illegal_ntfs_characters(self):
        """Tests that all NTFS illegal characters (*, ?, \", <, >, |, \\) are properly escaped."""
        test_cases = [
            ("pics/star*photo.jpg", "pics/star%2Aphoto.jpg"),
            ("pics/question?mark.jpg", "pics/question%3Fmark.jpg"),
            ('pics/quote"name".png', "pics/quote%22name%22.png"),
            ("data/<tag>.xml", "data/%3Ctag%3E.xml"),
            ("audio/artist|track.mp3", "audio/artist%7Ctrack.mp3"),
            ("notes/back\\slash.txt", "notes/back%5Cslash.txt"),
        ]

        for orig, expected in test_cases:
            sanitized, modified = PathSanitizer.sanitize_relpath(orig)
            self.assertTrue(modified, f"Expected {orig} to be marked modified")
            self.assertEqual(sanitized, expected)
            restored = PathSanitizer.desanitize_relpath(sanitized)
            self.assertEqual(restored, orig)

    def test_trailing_dot_and_space(self):
        """Trailing dots and spaces are illegal on Windows NTFS and must be escaped."""
        path_dot = "folder./file."
        sanitized_dot, mod_dot = PathSanitizer.sanitize_relpath(path_dot)
        self.assertTrue(mod_dot)
        self.assertEqual(sanitized_dot, "folder%2E/file%2E")
        self.assertEqual(PathSanitizer.desanitize_relpath(sanitized_dot), path_dot)

        path_space = "folder /file "
        sanitized_space, mod_space = PathSanitizer.sanitize_relpath(path_space)
        self.assertTrue(mod_space)
        self.assertEqual(sanitized_space, "folder%20/file%20")
        self.assertEqual(PathSanitizer.desanitize_relpath(sanitized_space), path_space)

    def test_windows_reserved_names(self):
        """Windows device names like CON, AUX, COM1 must be protected."""
        reserved_paths = [
            ("documents/con.txt", "documents/_con.txt"),
            ("audio/AUX.mp3", "audio/_AUX.mp3"),
            ("com1.log", "_com1.log"),
            ("nul", "_nul"),
        ]

        for orig, expected in reserved_paths:
            sanitized, modified = PathSanitizer.sanitize_relpath(orig)
            self.assertTrue(modified)
            self.assertEqual(sanitized, expected)
            self.assertEqual(PathSanitizer.desanitize_relpath(sanitized), orig)

    def test_hyper_map_file_creation_and_recovery(self):
        """When base_dir is supplied, .hyper_map.json should be saved and used for 100% reversible roundtrip."""
        orig = "DCIM/Camera/IMG_2023-10-25 15:45:00.jpg"
        win_path, modified = PathSanitizer.sanitize_relpath(orig, base_dir=self.temp_dir)
        self.assertTrue(modified)

        # Check root map file
        root_map = Path(self.temp_dir) / MAP_FILENAME
        self.assertTrue(root_map.is_file())
        with open(root_map, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.assertIn(win_path, data)
            self.assertEqual(data[win_path], orig)

        # Check subdirectory map file
        sub_map = Path(self.temp_dir) / "DCIM" / "Camera" / MAP_FILENAME
        self.assertTrue(sub_map.is_file())
        with open(sub_map, "r", encoding="utf-8") as f:
            sub_data = json.load(f)
            self.assertIn("IMG_2023-10-25 15%3A45%3A00.jpg", sub_data)
            self.assertEqual(sub_data["IMG_2023-10-25 15%3A45%3A00.jpg"], "IMG_2023-10-25 15:45:00.jpg")

        # Clear in-memory cache to guarantee reading from disk
        PathSanitizer.clear_memory_cache()
        desanitized = PathSanitizer.desanitize_relpath(win_path, base_dir=self.temp_dir)
        self.assertEqual(desanitized, orig)

    def test_complex_multi_illegal_path(self):
        """Test path containing multiple colons, pipes, and quotes in nested folders."""
        complex_path = "WhatsApp/Media/WhatsApp Audio/audio:test|sample\"1\".aac"
        sanitized, mod = PathSanitizer.sanitize_relpath(complex_path, base_dir=self.temp_dir)
        self.assertTrue(mod)
        for bad_char in [":", "|", '"']:
            self.assertNotIn(bad_char, sanitized)

        PathSanitizer.clear_memory_cache()
        restored = PathSanitizer.desanitize_relpath(sanitized, base_dir=self.temp_dir)
        self.assertEqual(restored, complex_path)


if __name__ == "__main__":
    unittest.main()
