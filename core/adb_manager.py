"""
ADB (Android Debug Bridge) process and device management.
Handles device discovery, connection management, shell execution, user profiles,
media scanning, and wake-lock controls.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from core.config import get_adb_path

logger = logging.getLogger(__name__)

# Windows flag to suppress console window flashing
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# Known commercial marketing names for hardware SKU model codes
KNOWN_MODEL_MARKET_NAMES: Dict[str, str] = {
    # Xiaomi 17 Series
    "25113PN0EI": "Xiaomi 17",
    "25113PN0EC": "Xiaomi 17",
    "25113PN0EG": "Xiaomi 17",
    "25113PN0EP": "Xiaomi 17 Pro",
    "25113PN0EU": "Xiaomi 17 Ultra",
    # Xiaomi 15 Series
    "24129PN74C": "Xiaomi 15",
    "24129PN74G": "Xiaomi 15",
    "24129PN74I": "Xiaomi 15",
    # Xiaomi 14 Series
    "23127PN0CC": "Xiaomi 14",
    "23127PN0CG": "Xiaomi 14",
    # Xiaomi 13 Series
    "2211133C": "Xiaomi 13",
    "2211133G": "Xiaomi 13",
}


class AdbManager:
    """Manages interactions with connected Android devices through ADB."""

    def __init__(self, adb_path: Optional[Union[str, Path]] = None) -> None:
        if adb_path:
            self.adb_path = str(adb_path)
        else:
            self.adb_path = get_adb_path()

        if not os.path.isfile(self.adb_path):
            raise FileNotFoundError(f"ADB executable not found at: {self.adb_path}")

    def _exec(
        self,
        args: List[str],
        timeout: int = 60,
        check: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Executes an ADB command synchronously."""
        cmd = [self.adb_path] + args
        kwargs: Dict[str, Any] = {
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
            "timeout": timeout,
        }
        if CREATE_NO_WINDOW:
            kwargs["creationflags"] = CREATE_NO_WINDOW

        try:
            res = subprocess.run(cmd, check=check, **kwargs)
            return res
        except subprocess.TimeoutExpired as exc:
            logger.error("ADB command timed out after %ds: %s", timeout, cmd)
            raise exc
        except Exception as exc:
            logger.error("ADB command failed: %s: %s", cmd, exc)
            raise exc

    def start_server(self) -> bool:
        """Starts the ADB server daemon."""
        res = self._exec(["start-server"], timeout=15)
        return res.returncode == 0

    def kill_server(self) -> bool:
        """Stops the ADB server daemon."""
        res = self._exec(["kill-server"], timeout=10)
        return res.returncode == 0

    def run_shell(self, serial: str, cmd_str: str, timeout: int = 60) -> str:
        """
        Executes a shell command on the specified device.

        Args:
            serial: Device serial identifier.
            cmd_str: Shell command string.
            timeout: Execution timeout in seconds.

        Returns:
            Command standard output as string.
        """
        res = self._exec(["-s", serial, "shell", cmd_str], timeout=timeout)
        return res.stdout

    def get_devices(self) -> List[Dict[str, Any]]:
        """
        Discovers all attached Android devices and queries their attributes.

        Returns:
            List of device information dictionaries.
        """
        res = self._exec(["devices", "-l"], timeout=15)
        lines = res.stdout.strip().splitlines()

        devices: List[Dict[str, Any]] = []

        for line in lines:
            line = line.strip()
            if not line or line.startswith("List of devices"):
                continue

            # Parse line: <serial> <state> [key:val ...]
            parts = line.split()
            if len(parts) < 2:
                continue

            serial = parts[0]
            state = parts[1]

            conn_type = "Wireless" if (":" in serial or "._tcp" in serial) else "USB"

            dev_info: Dict[str, Any] = {
                "serial": serial,
                "state": state,
                "model": "Unknown",
                "manufacturer": "Unknown",
                "android_version": "Unknown",
                "sdk_level": 0,
                "battery_level": 0,
                "storage_total": 0,
                "storage_free": 0,
                "connection_type": conn_type,
            }

            if state == "device":
                self._enrich_device_info(serial, dev_info)

            devices.append(dev_info)

        return devices

    def get_device_info(self, serial: str) -> Dict[str, Any]:
        """Returns detailed system and hardware info for a specific device serial."""
        devices = self.get_devices()
        for d in devices:
            if d.get("serial") == serial:
                if "storage_info" not in d:
                    d["storage_info"] = {
                        "total_bytes": d.get("storage_total", 0),
                        "free_bytes": d.get("storage_free", 0),
                    }
                return d
        info = {"serial": serial, "state": "device"}
        self._enrich_device_info(serial, info)
        info["storage_info"] = {
            "total_bytes": info.get("storage_total", 0),
            "free_bytes": info.get("storage_free", 0),
        }
        return info

    def _enrich_device_info(self, serial: str, info: Dict[str, Any]) -> None:
        """Queries detailed system properties, battery, and storage for an online device."""
        # 1. Properties query in single shell invocation for performance
        try:
            prop_cmd = (
                "getprop ro.product.marketname; echo '===PROP==='; "
                "getprop ro.product.odm.marketname; echo '===PROP==='; "
                "getprop ro.product.model; echo '===PROP==='; "
                "getprop ro.product.manufacturer; echo '===PROP==='; "
                "getprop ro.build.version.release; echo '===PROP==='; "
                "getprop ro.build.version.sdk"
            )
            prop_out = self.run_shell(serial, prop_cmd, timeout=10)
            prop_parts = prop_out.split("===PROP===")
            if len(prop_parts) >= 6:
                m_name = prop_parts[0].strip() or prop_parts[1].strip()
                raw_model = prop_parts[2].strip() or "Unknown"
                mfg = prop_parts[3].strip() or "Unknown"
                rel = prop_parts[4].strip() or "Unknown"
                sdk_str = prop_parts[5].strip()
            elif len(prop_parts) >= 4:
                m_name = ""
                raw_model = prop_parts[0].strip() or "Unknown"
                mfg = prop_parts[1].strip() or "Unknown"
                rel = prop_parts[2].strip() or "Unknown"
                sdk_str = prop_parts[3].strip()
            else:
                m_name = ""
                raw_model = "Unknown"
                mfg = "Unknown"
                rel = "Unknown"
                sdk_str = "0"

            # Determine commercial market name (e.g. 'Xiaomi 17')
            market_name = m_name if m_name and m_name.lower() != "null" else KNOWN_MODEL_MARKET_NAMES.get(raw_model, "")

            # Format user-facing display name, e.g. "Xiaomi 17 (25113PN0EI)"
            if market_name and market_name.lower() != raw_model.lower():
                if raw_model.lower() not in market_name.lower():
                    display_name = f"{market_name} ({raw_model})"
                else:
                    display_name = market_name
            else:
                display_name = raw_model

            info["raw_model"] = raw_model
            info["market_name"] = market_name
            info["display_name"] = display_name
            info["model"] = display_name
            info["manufacturer"] = mfg
            info["android_version"] = rel
            info["sdk_level"] = int(sdk_str) if sdk_str.isdigit() else 0
        except Exception as exc:
            logger.debug("Failed to query device properties: %s", exc)

        # 2. Battery level from dumpsys battery
        try:
            bat_out = self.run_shell(serial, "dumpsys battery", timeout=10)
            m = re.search(r"\blevel:\s*(\d+)", bat_out)
            if m:
                info["battery_level"] = int(m.group(1))
        except Exception as exc:
            logger.debug("Failed to query battery level: %s", exc)

        # 3. Storage space from df /sdcard
        try:
            df_out = self.run_shell(serial, "df -k /sdcard || df /sdcard", timeout=10)
            lines = [l for l in df_out.strip().splitlines() if l.strip()]
            if len(lines) >= 2:
                # Target the last line containing mount or filesystem metrics
                data_line = lines[-1].split()
                # Typical format: Filesystem 1K-blocks Used Available Use% Mounted_on
                if len(data_line) >= 4:
                    # Find numeric blocks columns
                    numeric_cols = [int(p) for p in data_line if p.isdigit()]
                    if len(numeric_cols) >= 3:
                        total_1k = numeric_cols[0]
                        free_1k = numeric_cols[2]
                        info["storage_total"] = total_1k * 1024
                        info["storage_free"] = free_1k * 1024
        except Exception as exc:
            logger.debug("Failed to query storage info: %s", exc)

        info["storage_info"] = {
            "total_bytes": info.get("storage_total", 0),
            "free_bytes": info.get("storage_free", 0),
        }

    def get_user_profiles(self, serial: str) -> List[Dict[str, Any]]:
        """
        Discovers user profiles on the device, including Primary and Private Space.

        Args:
            serial: Device serial.

        Returns:
            List of profile dicts with id, name, flags, is_primary, is_private_space.
        """
        out = self.run_shell(serial, "pm list users", timeout=15)
        # Match pattern: UserInfo{<id>:<name>:<flags>} <state>
        pattern = re.compile(r"UserInfo\{(\d+):([^:]*):([0-9a-fA-Fx]+)\}\s*(\w*)")

        profiles: List[Dict[str, Any]] = []
        for line in out.splitlines():
            m = pattern.search(line)
            if m:
                user_id = int(m.group(1))
                name = m.group(2)
                flags_str = m.group(3)
                state = m.group(4) or "unknown"

                is_primary = (user_id == 0)
                # Android 15+ Private Space or Work profiles typically id >= 10
                # or have names containing 'Private'
                is_private_space = (
                    user_id >= 10 or "private" in name.lower() or "work" in name.lower()
                )

                profiles.append({
                    "id": user_id,
                    "name": name,
                    "flags": flags_str,
                    "state": state,
                    "is_primary": is_primary,
                    "is_private_space": is_private_space,
                })

        return profiles

    def stay_awake(self, serial: str, enable: bool = True) -> bool:
        """
        Configures the device to stay awake while connected to USB power.

        Args:
            serial: Device serial.
            enable: True to keep awake on USB, False to return to default sleep.

        Returns:
            True if command executed successfully.
        """
        arg = "usb" if enable else "false"
        out = self.run_shell(serial, f"svc power stayon {arg}", timeout=10)
        return "error" not in out.lower()

    def trigger_media_scan(
        self,
        serial: str,
        folder_or_volume: str = "external_primary",
    ) -> bool:
        """
        Triggers Android MediaProvider to rescan storage volume or directory,
        refreshing the Gallery, Music, and MediaStore.

        Args:
            serial: Device serial.
            folder_or_volume: Volume name ('external_primary') or file/folder path.

        Returns:
            True if the scan was dispatched.
        """
        # Primary Android modern MediaProvider method
        cmd = f"content call --uri content://media/ --method scan_volume --arg {folder_or_volume}"
        try:
            res = self.run_shell(serial, cmd, timeout=60)
            return "error" not in res.lower()
        except Exception as exc:
            logger.warning("Media scanner dispatch notice (non-fatal): %s", exc)
            return True

    def connect_wireless(self, ip: str, port: int = 5555) -> Tuple[bool, str]:
        """
        Establishes an ADB connection over Wi-Fi.

        Args:
            ip: IP address of the target Android device.
            port: Port number (default 5555).

        Returns:
            Tuple of (success_bool, message_str).
        """
        target = f"{ip}:{port}"
        res = self._exec(["connect", target], timeout=20)
        out = res.stdout.strip()
        success = "connected to" in out.lower() or "already connected" in out.lower()
        return success, out

    def pull(
        self,
        serial: str,
        remote_path: str,
        local_path: str,
        timeout: int = 300,
    ) -> bool:
        """
        Pulls a file or folder from the device to local PC.

        Args:
            serial: Device serial.
            remote_path: Path on Android.
            local_path: Destination path on PC.
            timeout: Timeout in seconds.

        Returns:
            True if pull was successful.
        """
        res = self._exec(["-s", serial, "pull", remote_path, local_path], timeout=timeout)
        return res.returncode == 0

    def push(
        self,
        serial: str,
        local_path: str,
        remote_path: str,
        timeout: int = 300,
    ) -> bool:
        """
        Pushes a file from local PC to device.

        Args:
            serial: Device serial.
            local_path: Source path on PC.
            remote_path: Destination path on Android.
            timeout: Timeout in seconds.

        Returns:
            True if push was successful.
        """
        res = self._exec(["-s", serial, "push", local_path, remote_path], timeout=timeout)
        return res.returncode == 0

    def list_subdirectories(self, serial: str, parent_paths: List[str]) -> List[str]:
        """
        Lists first-level subdirectories under given parent paths on the device.

        Args:
            serial: Device serial.
            parent_paths: List of parent paths on Android (e.g. ['/sdcard/DCIM', '/sdcard/Pictures']).

        Returns:
            List of full directory paths found on device.
        """
        if not parent_paths:
            return []
        quoted = " ".join(f'"{p}"' for p in parent_paths)
        shell_cmd = f'for p in {quoted}; do if [ -d "$p" ]; then find "$p" -mindepth 1 -maxdepth 1 -type d 2>/dev/null; fi; done'
        try:
            out = self.run_shell(serial, shell_cmd, timeout=15)
            dirs = [line.strip() for line in out.strip().splitlines() if line.strip()]
            return sorted(set(dirs))
        except Exception as exc:
            logger.debug("Failed to list subdirectories: %s", exc)
            return []
