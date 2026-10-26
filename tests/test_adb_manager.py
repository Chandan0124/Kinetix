"""
Unit tests for core.adb_manager.
Tests command generation, device discovery parsing, profile inspection, and media scanning.
"""

import subprocess
import unittest
from unittest.mock import MagicMock, patch

from core.adb_manager import AdbManager


class TestAdbManager(unittest.TestCase):

    def setUp(self):
        # Initialize AdbManager with a dummy path for testing
        self.adb = AdbManager()

    @patch.object(AdbManager, "_exec")
    @patch.object(AdbManager, "run_shell")
    def test_get_devices_parsing(self, mock_shell, mock_exec):
        """Tests parsing of `adb devices -l` output for both USB and wireless devices."""
        mock_exec.return_value = subprocess.CompletedProcess(
            args=["adb", "devices", "-l"],
            returncode=0,
            stdout=(
                "List of devices attached\n"
                "emulator-5554          device product:sdk_gphone64_arm64 model:sdk_gphone64_arm64 device:emu64a transport_id:1\n"
                "192.168.1.150:5555     device product:coral model:Pixel_4 device:coral transport_id:2\n"
                "RF8M123456X            unauthorized usb:1-1\n"
            ),
            stderr="",
        )

        def mock_shell_side_effect(serial, cmd, timeout=60):
            if "getprop" in cmd:
                if serial == "emulator-5554":
                    return "sdk_gphone64_arm64\n===PROP===\nGoogle\n===PROP===\n14\n===PROP===\n34\n"
                else:
                    return "Pixel 4\n===PROP===\nGoogle\n===PROP===\n13\n===PROP===\n33\n"
            elif "dumpsys battery" in cmd:
                return "Current Battery Service state:\n  level: 88\n  scale: 100\n"
            elif "df" in cmd:
                return (
                    "Filesystem     1K-blocks      Used Available Use% Mounted on\n"
                    "/dev/fuse      240000000 140000000 100000000  58% /storage/emulated/0\n"
                )
            return ""

        mock_shell.side_effect = mock_shell_side_effect

        devices = self.adb.get_devices()
        self.assertEqual(len(devices), 3)

        # Device 1: USB Emulator
        dev1 = devices[0]
        self.assertEqual(dev1["serial"], "emulator-5554")
        self.assertEqual(dev1["state"], "device")
        self.assertEqual(dev1["connection_type"], "USB")
        self.assertEqual(dev1["model"], "sdk_gphone64_arm64")
        self.assertEqual(dev1["battery_level"], 88)
        self.assertEqual(dev1["storage_total"], 240000000 * 1024)
        self.assertEqual(dev1["storage_free"], 100000000 * 1024)

        # Device 2: Wireless Pixel
        dev2 = devices[1]
        self.assertEqual(dev2["serial"], "192.168.1.150:5555")
        self.assertEqual(dev2["connection_type"], "Wireless")
        self.assertEqual(dev2["model"], "Pixel 4")

        # Device 3: Unauthorized
        dev3 = devices[2]
        self.assertEqual(dev3["serial"], "RF8M123456X")
        self.assertEqual(dev3["state"], "unauthorized")
        self.assertEqual(dev3["model"], "Unknown")

    @patch.object(AdbManager, "run_shell")
    def test_get_user_profiles_primary_and_private_space(self, mock_shell):
        """Tests user profiles discovery detecting User 0 and Android 15+ Private Space."""
        mock_shell.return_value = (
            "Users:\n"
            "	UserInfo{0:Owner:13} running\n"
            "	UserInfo{10:Private:10000000} running\n"
            "	UserInfo{11:Work Profile:30} stopped\n"
        )

        profiles = self.adb.get_user_profiles("device123")
        self.assertEqual(len(profiles), 3)

        # User 0 - Primary
        self.assertEqual(profiles[0]["id"], 0)
        self.assertEqual(profiles[0]["name"], "Owner")
        self.assertTrue(profiles[0]["is_primary"])
        self.assertFalse(profiles[0]["is_private_space"])

        # User 10 - Private Space
        self.assertEqual(profiles[1]["id"], 10)
        self.assertEqual(profiles[1]["name"], "Private")
        self.assertFalse(profiles[1]["is_primary"])
        self.assertTrue(profiles[1]["is_private_space"])

        # User 11 - Work Profile
        self.assertEqual(profiles[2]["id"], 11)
        self.assertTrue(profiles[2]["is_private_space"])

    @patch.object(AdbManager, "run_shell")
    def test_stay_awake(self, mock_shell):
        """Tests stay awake commands for USB wake-lock."""
        mock_shell.return_value = ""
        res_enable = self.adb.stay_awake("serial1", enable=True)
        self.assertTrue(res_enable)
        mock_shell.assert_called_with("serial1", "svc power stayon usb", timeout=10)

        res_disable = self.adb.stay_awake("serial1", enable=False)
        self.assertTrue(res_disable)
        mock_shell.assert_called_with("serial1", "svc power stayon false", timeout=10)

    @patch.object(AdbManager, "run_shell")
    def test_trigger_media_scan(self, mock_shell):
        """Tests media scan dispatch command."""
        mock_shell.return_value = "Result: Bundle[{}]"
        ok = self.adb.trigger_media_scan("serial1", "external_primary")
        self.assertTrue(ok)
        mock_shell.assert_called_with(
            "serial1",
            "content call --uri content://media/ --method scan_volume --arg external_primary",
            timeout=15,
        )

    @patch.object(AdbManager, "run_shell")
    def test_market_name_resolution(self, mock_shell):
        """Tests commercial market name resolution (e.g. 25113PN0EI -> Xiaomi 17 (25113PN0EI))."""
        mock_shell.return_value = (
            "Xiaomi 17\n===PROP===\nXiaomi 17\n===PROP===\n25113PN0EI\n===PROP===\nXiaomi\n===PROP===\n15\n===PROP===\n35\n"
        )
        info = {"serial": "XIAOMI123", "state": "device"}
        self.adb._enrich_device_info("XIAOMI123", info)
        self.assertEqual(info["raw_model"], "25113PN0EI")
        self.assertEqual(info["market_name"], "Xiaomi 17")
        self.assertEqual(info["model"], "Xiaomi 17 (25113PN0EI)")
        self.assertEqual(info["display_name"], "Xiaomi 17 (25113PN0EI)")

    @patch.object(AdbManager, "_exec")
    def test_connect_wireless(self, mock_exec):
        """Tests wireless connection parsing."""
        mock_exec.return_value = subprocess.CompletedProcess(
            args=["adb", "connect", "192.168.1.100:5555"],
            returncode=0,
            stdout="connected to 192.168.1.100:5555\n",
            stderr="",
        )
        success, msg = self.adb.connect_wireless("192.168.1.100", 5555)
        self.assertTrue(success)
        self.assertIn("connected to", msg)


if __name__ == "__main__":
    unittest.main()
