"""
Unit tests for core.config.
Validates system configuration, category configurations, and default paths.
"""

import unittest
from pathlib import Path

from core.config import (
    CATEGORIES,
    DEFAULT_ADB_BIN,
    DEFAULT_BACKUP_ROOT,
    CategoryConfig,
    get_adb_path,
    get_category,
    get_default_backup_dir,
    list_categories,
)


class TestConfig(unittest.TestCase):

    def test_categories_presence_and_attributes(self):
        """Verifies required categories and their configured paths and labels."""
        expected_categories = [
            "pics",
            "music",
            "whatsapp",
            "telegram",
            "sms",
            "private_space",
        ]
        for cat_id in expected_categories:
            self.assertIn(cat_id, CATEGORIES)
            cat = CATEGORIES[cat_id]
            self.assertIsInstance(cat, CategoryConfig)
            self.assertEqual(cat.id, cat_id)
            self.assertTrue(len(cat.label) > 0)
            self.assertTrue(len(cat.icon) > 0)
            self.assertTrue(len(cat.description) > 0)

        # Pics specifics
        pics = CATEGORIES["pics"]
        self.assertIn("/sdcard/DCIM", pics.paths)
        self.assertIn("/sdcard/Pictures", pics.paths)
        self.assertIn("/sdcard/Movies", pics.paths)
        self.assertEqual(pics.icon, "camera")

        # Music specifics
        music = CATEGORIES["music"]
        self.assertIn("/sdcard/Music", music.paths)
        self.assertIn("/sdcard/Podcasts", music.paths)
        self.assertIn("/sdcard/Audiobooks", music.paths)
        self.assertIn("/sdcard/Recordings", music.paths)

        # WhatsApp specifics
        whatsapp = CATEGORIES["whatsapp"]
        self.assertIn("/sdcard/Android/media/com.whatsapp/WhatsApp", whatsapp.paths)
        self.assertIn("/sdcard/WhatsApp", whatsapp.paths)

        # Telegram specifics
        telegram = CATEGORIES["telegram"]
        self.assertIn("/sdcard/Telegram", telegram.paths)
        self.assertIn("/sdcard/Android/data/org.telegram.messenger/files", telegram.paths)

        # SMS specifics
        sms = CATEGORIES["sms"]
        self.assertEqual(sms.special_type, "telephony")

        # Private space specifics
        ps = CATEGORIES["private_space"]
        self.assertEqual(ps.special_type, "private_space")

    def test_get_default_backup_dir(self):
        """Ensures backup root directory is returned and exists."""
        backup_dir = get_default_backup_dir()
        self.assertIsInstance(backup_dir, Path)
        self.assertTrue(backup_dir.is_dir())
        self.assertEqual(backup_dir, DEFAULT_BACKUP_ROOT)

    def test_get_adb_path(self):
        """Resolves ADB path to the bundled platform-tools binary."""
        adb_path = get_adb_path()
        self.assertTrue(Path(adb_path).is_file())
        self.assertEqual(Path(adb_path), DEFAULT_ADB_BIN)

    def test_list_and_get_categories(self):
        """Tests helper accessor functions."""
        cats = list_categories()
        self.assertEqual(len(cats), len(CATEGORIES))
        self.assertIsNotNone(get_category("pics"))
        self.assertIsNone(get_category("non_existent_category"))


if __name__ == "__main__":
    unittest.main()
