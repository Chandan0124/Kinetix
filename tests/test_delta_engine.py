"""
Unit tests for core.delta_engine.
Tests the 2.0-second timestamp tolerance window, size checks, and delta classification.
"""

import unittest
from core.delta_engine import DeltaEngine, SyncStatus
from core.indexer import LocalFileInfo, RemoteFileInfo


class TestDeltaEngine(unittest.TestCase):

    def setUp(self):
        self.base_time = 1700000000.0

    def test_already_synced_within_tolerance(self):
        """Files matching in size and having mtime diff <= 2.0s are ALREADY_SYNCED."""
        remote_files = [
            # Exact match
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/exact.jpg",
                rel_path="DCIM/Camera/exact.jpg",
                size=2048,
                mtime=self.base_time,
                category="pics",
            ),
            # 1.5s difference (within 2.0s FAT32 precision window)
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/jitter.jpg",
                rel_path="DCIM/Camera/jitter.jpg",
                size=4096,
                mtime=self.base_time + 1.5,
                category="pics",
            ),
            # Exactly 2.0s difference
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/boundary.jpg",
                rel_path="DCIM/Camera/boundary.jpg",
                size=1024,
                mtime=self.base_time - 2.0,
                category="pics",
            ),
        ]

        local_map = {
            "DCIM/Camera/exact.jpg": LocalFileInfo(
                path=r"C:\Backups\pics\DCIM\Camera\exact.jpg",
                rel_path="DCIM/Camera/exact.jpg",
                size=2048,
                mtime=self.base_time,
            ),
            "DCIM/Camera/jitter.jpg": LocalFileInfo(
                path=r"C:\Backups\pics\DCIM\Camera\jitter.jpg",
                rel_path="DCIM/Camera/jitter.jpg",
                size=4096,
                mtime=self.base_time,
            ),
            "DCIM/Camera/boundary.jpg": LocalFileInfo(
                path=r"C:\Backups\pics\DCIM\Camera\boundary.jpg",
                rel_path="DCIM/Camera/boundary.jpg",
                size=1024,
                mtime=self.base_time,
            ),
        }

        report = DeltaEngine.compute_delta(remote_files, local_map)

        self.assertEqual(report.already_synced_count, 3)
        self.assertEqual(report.to_sync_count, 0)
        self.assertEqual(report.already_synced_bytes, 2048 + 4096 + 1024)
        self.assertEqual(report.to_sync_bytes, 0)
        self.assertEqual(len(report.items_to_sync), 0)

    def test_modified_outside_tolerance_or_size_diff(self):
        """Files outside 2.0s window or with size difference are TO_SYNC_MODIFIED."""
        remote_files = [
            # Time diff 2.1s (exceeds 2.0s tolerance)
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/late.jpg",
                rel_path="DCIM/Camera/late.jpg",
                size=5000,
                mtime=self.base_time + 2.1,
                category="pics",
            ),
            # Same time, different size
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/resized.jpg",
                rel_path="DCIM/Camera/resized.jpg",
                size=5001,
                mtime=self.base_time,
                category="pics",
            ),
        ]

        local_map = {
            "DCIM/Camera/late.jpg": LocalFileInfo(
                path=r"C:\Backups\pics\DCIM\Camera\late.jpg",
                rel_path="DCIM/Camera/late.jpg",
                size=5000,
                mtime=self.base_time,
            ),
            "DCIM/Camera/resized.jpg": LocalFileInfo(
                path=r"C:\Backups\pics\DCIM\Camera\resized.jpg",
                rel_path="DCIM/Camera/resized.jpg",
                size=4000,
                mtime=self.base_time,
            ),
        }

        report = DeltaEngine.compute_delta(remote_files, local_map)

        self.assertEqual(report.already_synced_count, 0)
        self.assertEqual(report.to_sync_count, 2)
        for item in report.items_to_sync:
            self.assertEqual(item.status, SyncStatus.TO_SYNC_MODIFIED)

    def test_new_and_deleted_files(self):
        """Detects new files to sync and files removed from remote device."""
        remote_files = [
            RemoteFileInfo(
                path="/sdcard/DCIM/Camera/brand_new.jpg",
                rel_path="DCIM/Camera/brand_new.jpg",
                size=12000,
                mtime=self.base_time,
                category="pics",
            ),
        ]

        local_map = {
            "DCIM/Camera/old_deleted.jpg": LocalFileInfo(
                path=r"C:\Backups\pics\DCIM\Camera\old_deleted.jpg",
                rel_path="DCIM/Camera/old_deleted.jpg",
                size=8000,
                mtime=self.base_time,
            ),
        }

        report = DeltaEngine.compute_delta(remote_files, local_map)

        self.assertEqual(report.to_sync_count, 1)
        self.assertEqual(report.to_sync_bytes, 12000)
        self.assertEqual(report.items_to_sync[0].status, SyncStatus.TO_SYNC_NEW)

        self.assertEqual(report.deleted_remote_count, 1)
        self.assertEqual(report.deleted_remote_items[0].status, SyncStatus.DELETED_REMOTE)
        self.assertEqual(report.deleted_remote_items[0].rel_path, "DCIM/Camera/old_deleted.jpg")

    def test_time_saved_estimate_and_breakdown(self):
        """Verifies calculation of time saved (at 40 MB/s) and category metrics breakdown."""
        # 80 MB already synced file = ~2.00 seconds saved
        eighty_mb = 80 * 1024 * 1024
        ten_mb = 10 * 1024 * 1024

        remote_files = [
            RemoteFileInfo(
                path="/sdcard/DCIM/video.mp4",
                rel_path="DCIM/video.mp4",
                size=eighty_mb,
                mtime=self.base_time,
                category="pics",
            ),
            RemoteFileInfo(
                path="/sdcard/Music/album.mp3",
                rel_path="Music/album.mp3",
                size=ten_mb,
                mtime=self.base_time,
                category="music",
            ),
        ]

        local_map = {
            "DCIM/video.mp4": LocalFileInfo(
                path="dummy",
                rel_path="DCIM/video.mp4",
                size=eighty_mb,
                mtime=self.base_time,
            )
        }

        report = DeltaEngine.compute_delta(remote_files, local_map)

        # Pics is already synced (80 MB) -> ~2.0s saved
        self.assertAlmostEqual(report.time_saved_seconds_estimate, 2.0, delta=0.05)
        self.assertIn("pics", report.breakdown_by_category)
        self.assertIn("music", report.breakdown_by_category)

        pics_cat = report.breakdown_by_category["pics"]
        self.assertEqual(pics_cat["already_synced_count"], 1)
        self.assertEqual(pics_cat["to_sync_count"], 0)

        music_cat = report.breakdown_by_category["music"]
        self.assertEqual(music_cat["already_synced_count"], 0)
        self.assertEqual(music_cat["to_sync_count"], 1)
        self.assertEqual(music_cat["to_sync_bytes"], ten_mb)


if __name__ == "__main__":
    unittest.main()
