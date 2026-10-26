"""
Path sanitization for cross-platform compatibility between Android (Linux) and Windows NTFS.
Escapes illegal NTFS characters and manages .hyper_map.json mapping files for 100% reversible restorations.
"""

from __future__ import annotations

import json
import os
import posixpath
import re
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

# Mapping file name stored in local backup directories
MAP_FILENAME = ".hyper_map.json"

# Characters illegal in NTFS file or directory names: \ / : * ? " < > | and control characters (0x00-0x1F)
ILLEGAL_NTFS_CHARS = set(r'\/:*?"<>|' + "".join(chr(i) for i in range(32)))

# Windows reserved device names
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Explicit replacement encodings
ESCAPE_MAP = {
    ":": "%3A",
    "*": "%2A",
    "?": "%3F",
    '"': "%22",
    "<": "%3C",
    ">": "%3E",
    "|": "%7C",
    "\\": "%5C",
}

# Reverse mapping for decoders
UNESCAPE_MAP = {v: k for k, v in ESCAPE_MAP.items()}


class PathSanitizer:
    """
    Sanitizes Linux relative paths for safe storage on Windows NTFS filesystems,
    and reverses the sanitization to restore exact Android paths.
    """

    _MEMORY_MAP: Dict[str, str] = {}

    @classmethod
    def sanitize_relpath(
        cls,
        linux_relpath: str,
        base_dir: Optional[Union[str, Path]] = None,
    ) -> Tuple[str, bool]:
        """
        Sanitize a Linux relative path into an NTFS-safe relative path.

        Args:
            linux_relpath: Linux relative path (using '/' as separator).
            base_dir: Optional local directory where .hyper_map.json should be saved if modified.

        Returns:
            Tuple of (win_relpath, was_modified).
        """
        if not linux_relpath:
            return "", False

        # Linux relative paths strictly use '/' as directory separator.
        # Do not replace '\\' globally here because '\\' within a Linux filename
        # is a valid character that must be escaped to '%5C'.
        normalized = linux_relpath.strip("/")
        parts = normalized.split("/")

        sanitized_parts = []
        any_modified = False

        for part in parts:
            sanitized_part, modified = cls._sanitize_component(part)
            sanitized_parts.append(sanitized_part)
            if modified:
                any_modified = True

        win_relpath = "/".join(sanitized_parts)

        if any_modified:
            cls._MEMORY_MAP[win_relpath] = normalized
            if base_dir:
                cls.record_mapping(base_dir, win_relpath, normalized)

        return win_relpath, any_modified

    @classmethod
    def _sanitize_component(cls, component: str) -> Tuple[str, bool]:
        """Sanitizes a single path component (directory or file name)."""
        modified = False
        chars = []

        for ch in component:
            if ch in ESCAPE_MAP:
                chars.append(ESCAPE_MAP[ch])
                modified = True
            elif ord(ch) < 32:
                chars.append(f"%{ord(ch):02X}")
                modified = True
            else:
                chars.append(ch)

        result = "".join(chars)

        # Windows does not permit names ending in dot or space
        if result.endswith("."):
            result = result[:-1] + "%2E"
            modified = True
        elif result.endswith(" "):
            result = result[:-1] + "%20"
            modified = True

        # Check for reserved DOS device names (e.g. CON, AUX, COM1.txt)
        stem = result.split(".")[0].upper()
        if stem in RESERVED_NAMES:
            result = "_" + result
            modified = True

        return result, modified

    @classmethod
    def desanitize_relpath(
        cls,
        win_relpath: str,
        base_dir: Optional[Union[str, Path]] = None,
    ) -> str:
        """
        Reconstruct the original Android Linux relative path from a Windows relative path.

        Checks:
        1. Local .hyper_map.json in base_dir or local subdirectory.
        2. In-memory mapping cache.
        3. Deterministic unescape rules.

        Args:
            win_relpath: Relative path on Windows (forward or backslash).
            base_dir: Optional root or category directory where .hyper_map.json resides.

        Returns:
            Original Linux relative path with '/' separators.
        """
        if not win_relpath:
            return ""

        normalized_win = win_relpath.replace("\\", "/").strip("/")

        # 1. Check base_dir root map if available
        if base_dir:
            base_path = Path(base_dir)
            root_map_file = base_path / MAP_FILENAME
            if root_map_file.is_file():
                try:
                    with open(root_map_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if normalized_win in data:
                            return data[normalized_win]
                except Exception:
                    pass

            # Check subdirectory map
            sub_dir = posixpath.dirname(normalized_win)
            file_name = posixpath.basename(normalized_win)
            sub_map_file = base_path / sub_dir / MAP_FILENAME
            if sub_map_file.is_file():
                try:
                    with open(sub_map_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if file_name in data:
                            orig_file = data[file_name]
                            # Combine desanitized sub_dir if applicable
                            desan_dir = cls.desanitize_relpath(sub_dir, base_dir)
                            return f"{desan_dir}/{orig_file}" if desan_dir else orig_file
                except Exception:
                    pass

        # 2. Check in-memory mapping cache
        if normalized_win in cls._MEMORY_MAP:
            return cls._MEMORY_MAP[normalized_win]

        # 3. Fallback to algorithmic reversal
        parts = normalized_win.split("/")
        restored_parts = []
        for part in parts:
            restored_parts.append(cls._desanitize_component(part))

        return "/".join(restored_parts)

    @classmethod
    def _desanitize_component(cls, component: str) -> str:
        """Reverses algorithmic sanitization for a single component."""
        result = component

        # Remove leading underscore if it was added for reserved device names
        stem = result.split(".")[0]
        if stem.startswith("_") and stem[1:].upper() in RESERVED_NAMES:
            result = result[1:]

        # Handle trailing escaped dot or space
        if result.endswith("%2E"):
            result = result[:-3] + "."
        elif result.endswith("%20"):
            result = result[:-3] + " "

        # Replace percent encoded characters
        for enc, orig in UNESCAPE_MAP.items():
            result = result.replace(enc, orig)

        # Handle any other control character encodings (%00 - %1F)
        result = re.sub(
            r"%([01][0-9A-Fa-f])",
            lambda m: chr(int(m.group(1), 16)),
            result,
        )

        return result

    @classmethod
    def record_mapping(
        cls,
        base_dir: Union[str, Path],
        win_relpath: str,
        linux_relpath: str,
    ) -> None:
        """
        Records a mapping entry to .hyper_map.json in the target directory and subdirectories.
        """
        base_path = Path(base_dir)
        norm_win = win_relpath.replace("\\", "/").strip("/")
        norm_linux = linux_relpath.replace("\\", "/").strip("/")

        # Save to root map
        try:
            base_path.mkdir(parents=True, exist_ok=True)
            root_map_path = base_path / MAP_FILENAME
            data = {}
            if root_map_path.is_file():
                try:
                    with open(root_map_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                except Exception:
                    data = {}
            data[norm_win] = norm_linux
            with open(root_map_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Save to local subdirectory map
        sub_dir = posixpath.dirname(norm_win)
        file_name = posixpath.basename(norm_win)
        orig_file = posixpath.basename(norm_linux)

        if sub_dir:
            sub_path = base_path / sub_dir
            try:
                sub_path.mkdir(parents=True, exist_ok=True)
                sub_map_path = sub_path / MAP_FILENAME
                sub_data = {}
                if sub_map_path.is_file():
                    try:
                        with open(sub_map_path, "r", encoding="utf-8") as f:
                            sub_data = json.load(f)
                    except Exception:
                        sub_data = {}
                sub_data[file_name] = orig_file
                with open(sub_map_path, "w", encoding="utf-8") as f:
                    json.dump(sub_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass

    @classmethod
    def load_mappings(cls, directory: Union[str, Path]) -> Dict[str, str]:
        """Loads mappings from .hyper_map.json in the specified directory."""
        map_path = Path(directory) / MAP_FILENAME
        if not map_path.is_file():
            return {}
        try:
            with open(map_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    @classmethod
    def clear_memory_cache(cls) -> None:
        """Clears in-memory cache."""
        cls._MEMORY_MAP.clear()
