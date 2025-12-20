"""Update check functionality for NextDNS Blocker.

This module provides version checking against PyPI with caching
to avoid excessive API calls.
"""

import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir

from .common import APP_NAME, write_secure_file

logger = logging.getLogger(__name__)

# Cache configuration
CACHE_TTL_HOURS = 24
PYPI_URL = "https://pypi.org/pypi/nextdns-blocker/json"
PYPI_TIMEOUT = 5  # seconds - short timeout to avoid blocking status command


def _get_cache_file() -> Path:
    """Get the path to the update check cache file."""
    return Path(user_data_dir(APP_NAME)) / ".update_check"


@dataclass
class UpdateInfo:
    """Information about an available update."""

    current_version: str
    latest_version: str

    @property
    def update_available(self) -> bool:
        """Check if an update is available."""
        return _compare_versions(self.current_version, self.latest_version) < 0


def _parse_version(version: str) -> tuple[int, ...]:
    """
    Parse a version string into a tuple of integers.

    Handles versions with suffixes like "1.0.0rc1", "2.0.0-beta.1" by
    extracting only the numeric parts.

    Args:
        version: Version string like "1.2.3" or "1.0.0rc1"

    Returns:
        Tuple of integers for comparison
    """
    try:
        # Extract only the numeric parts (e.g., "1.0.0rc1" -> "1.0.0")
        numeric_match = re.match(r"^(\d+(?:\.\d+)*)", version)
        if not numeric_match:
            return ()
        numeric_part = numeric_match.group(1)
        return tuple(int(x) for x in numeric_part.split("."))
    except ValueError:
        # If parsing fails, return empty tuple (will compare as less than anything)
        return ()


def _compare_versions(current: str, latest: str) -> int:
    """
    Compare two version strings.

    Args:
        current: Current version string
        latest: Latest version string

    Returns:
        -1 if current < latest
         0 if current == latest
         1 if current > latest
    """
    current_tuple = _parse_version(current)
    latest_tuple = _parse_version(latest)

    if current_tuple < latest_tuple:
        return -1
    elif current_tuple > latest_tuple:
        return 1
    return 0


def _read_cache() -> Optional[dict[str, Any]]:
    """
    Read the update check cache.

    Returns:
        Cache data dict or None if cache doesn't exist or is invalid
    """
    cache_file = _get_cache_file()
    if not cache_file.exists():
        return None

    try:
        with open(cache_file, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError) as e:
        logger.debug(f"Failed to read update cache: {e}")
        return None


def _write_cache(latest_version: str) -> None:
    """
    Write the update check cache with secure permissions (0o600).

    Args:
        latest_version: The latest version found on PyPI
    """
    cache_file = _get_cache_file()
    cache_data = {
        "last_check": datetime.now().isoformat(),
        "latest_version": latest_version,
    }

    try:
        # Ensure parent directory exists
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        # Use write_secure_file for consistent secure permissions
        write_secure_file(cache_file, json.dumps(cache_data))
    except OSError as e:
        logger.debug(f"Failed to write update cache: {e}")


def _is_cache_valid(cache: dict[str, Any]) -> bool:
    """
    Check if the cache is still valid (within TTL).

    Args:
        cache: Cache data dict

    Returns:
        True if cache is valid, False otherwise
    """
    try:
        last_check = datetime.fromisoformat(cache["last_check"])
        age = datetime.now() - last_check
        return age < timedelta(hours=CACHE_TTL_HOURS)
    except (KeyError, ValueError):
        return False


def _fetch_latest_version() -> Optional[str]:
    """
    Fetch the latest version from PyPI.

    Returns:
        Latest version string or None if fetch failed
    """
    import ssl

    try:
        # Security: Using urllib.request.urlopen with hardcoded HTTPS URL to PyPI.
        # This is safe because:
        # 1. URL is hardcoded constant, not user-controlled
        # 2. Uses HTTPS with certificate validation
        # 3. Only fetches public package metadata (read-only)
        with urllib.request.urlopen(PYPI_URL, timeout=PYPI_TIMEOUT) as response:  # nosec B310
            data: dict[str, Any] = json.loads(response.read().decode())
            # Safely access nested keys
            info = data.get("info")
            if not isinstance(info, dict):
                logger.debug("PyPI response missing 'info' object")
                return None
            version = info.get("version")
            if not isinstance(version, str):
                logger.debug("PyPI response missing 'version' string")
                return None
            return version
    except ssl.SSLError as e:
        # SSLError is the base class and includes SSLCertVerificationError
        logger.warning(f"SSL error fetching PyPI version: {e}")
        return None
    except urllib.error.URLError as e:
        logger.debug(f"URL error fetching latest version from PyPI: {e}")
        return None
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Failed to parse PyPI response: {e}")
        return None
    except OSError as e:
        logger.debug(f"Network error fetching latest version from PyPI: {e}")
        return None


def check_for_update(current_version: str) -> Optional[UpdateInfo]:
    """
    Check if an update is available.

    This function uses caching to avoid excessive API calls.
    It will only contact PyPI if the cache is older than 24 hours.

    Args:
        current_version: The current installed version

    Returns:
        UpdateInfo if an update is available, None otherwise
        Also returns None if the check fails (network error, etc.)
    """
    # Try to use cached version first
    cache = _read_cache()
    latest_version: Optional[str] = None

    if cache and _is_cache_valid(cache):
        latest_version = cache.get("latest_version")
    else:
        # Cache expired or doesn't exist, fetch from PyPI
        latest_version = _fetch_latest_version()
        if latest_version:
            _write_cache(latest_version)

    if not latest_version:
        return None

    info = UpdateInfo(current_version=current_version, latest_version=latest_version)

    if info.update_available:
        return info

    return None


def clear_cache() -> bool:
    """
    Clear the update check cache.

    Returns:
        True if cache was cleared, False if it didn't exist
    """
    cache_file = _get_cache_file()
    if cache_file.exists():
        cache_file.unlink()
        return True
    return False
