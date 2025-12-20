"""Tests for the update_check module.

Tests the update notification functionality including:
- Version comparison
- PyPI version fetching
- Cache reading/writing
- Cache TTL validation
- Update availability detection
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from nextdns_blocker.update_check import (
    UpdateInfo,
    _compare_versions,
    _fetch_latest_version,
    _get_cache_file,
    _is_cache_valid,
    _parse_version,
    _read_cache,
    _write_cache,
    check_for_update,
    clear_cache,
)


class TestVersionParsing:
    """Tests for version string parsing."""

    def test_parse_standard_version(self) -> None:
        """Test parsing a standard semantic version."""
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_parse_major_minor(self) -> None:
        """Test parsing a major.minor version."""
        assert _parse_version("1.2") == (1, 2)

    def test_parse_major_only(self) -> None:
        """Test parsing a major-only version."""
        assert _parse_version("1") == (1,)

    def test_parse_version_with_leading_zeros(self) -> None:
        """Test parsing version with leading zeros (should work)."""
        assert _parse_version("01.02.03") == (1, 2, 3)

    def test_parse_invalid_version(self) -> None:
        """Test parsing an invalid version returns empty tuple."""
        assert _parse_version("invalid") == ()

    def test_parse_empty_version(self) -> None:
        """Test parsing empty string returns empty tuple."""
        assert _parse_version("") == ()

    def test_parse_version_with_pre_release(self) -> None:
        """Test parsing version with pre-release suffix extracts numeric part."""
        # Pre-release suffixes are stripped, only numeric part is extracted
        assert _parse_version("1.0.0-beta") == (1, 0, 0)
        assert _parse_version("2.1.0rc1") == (2, 1, 0)
        assert _parse_version("3.0.0-alpha.1") == (3, 0, 0)


class TestVersionComparison:
    """Tests for version comparison."""

    def test_current_less_than_latest(self) -> None:
        """Test when current version is less than latest."""
        assert _compare_versions("1.0.0", "2.0.0") == -1
        assert _compare_versions("1.0.0", "1.1.0") == -1
        assert _compare_versions("1.0.0", "1.0.1") == -1

    def test_current_equals_latest(self) -> None:
        """Test when current version equals latest."""
        assert _compare_versions("1.0.0", "1.0.0") == 0

    def test_current_greater_than_latest(self) -> None:
        """Test when current version is greater than latest."""
        assert _compare_versions("2.0.0", "1.0.0") == 1
        assert _compare_versions("1.1.0", "1.0.0") == 1
        assert _compare_versions("1.0.1", "1.0.0") == 1

    def test_semantic_version_comparison(self) -> None:
        """Test that 1.10.0 > 1.2.0 (not string comparison)."""
        assert _compare_versions("1.2.0", "1.10.0") == -1
        assert _compare_versions("1.10.0", "1.2.0") == 1

    def test_different_length_versions(self) -> None:
        """Test comparing versions with different lengths."""
        # (1, 0, 0) > (1,) since tuple comparison pads with nothing
        # Actually in Python, (1, 0, 0) > (1,) is True
        assert _compare_versions("1.0.0", "1") == 1
        assert _compare_versions("1", "1.0.0") == -1


class TestUpdateInfo:
    """Tests for UpdateInfo dataclass."""

    def test_update_available_when_newer(self) -> None:
        """Test update_available is True when latest is newer."""
        info = UpdateInfo(current_version="1.0.0", latest_version="2.0.0")
        assert info.update_available is True

    def test_update_not_available_when_same(self) -> None:
        """Test update_available is False when versions are same."""
        info = UpdateInfo(current_version="1.0.0", latest_version="1.0.0")
        assert info.update_available is False

    def test_update_not_available_when_ahead(self) -> None:
        """Test update_available is False when current is ahead."""
        info = UpdateInfo(current_version="2.0.0", latest_version="1.0.0")
        assert info.update_available is False


class TestCacheOperations:
    """Tests for cache reading and writing."""

    def test_get_cache_file_path(self, tmp_path: Path) -> None:
        """Test cache file path is in data directory."""
        with patch("nextdns_blocker.update_check.user_data_dir", return_value=str(tmp_path)):
            cache_file = _get_cache_file()
            assert cache_file.parent == tmp_path
            assert cache_file.name == ".update_check"

    def test_write_and_read_cache(self, tmp_path: Path) -> None:
        """Test writing and reading cache."""
        cache_file = tmp_path / ".update_check"

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            _write_cache("2.0.0")
            cache = _read_cache()

        assert cache is not None
        assert cache["latest_version"] == "2.0.0"
        assert "last_check" in cache

    def test_read_nonexistent_cache(self, tmp_path: Path) -> None:
        """Test reading cache when file doesn't exist."""
        cache_file = tmp_path / ".update_check"

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            cache = _read_cache()

        assert cache is None

    def test_read_invalid_cache(self, tmp_path: Path) -> None:
        """Test reading cache with invalid JSON."""
        cache_file = tmp_path / ".update_check"
        cache_file.write_text("invalid json")

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            cache = _read_cache()

        assert cache is None

    def test_write_cache_creates_directory(self, tmp_path: Path) -> None:
        """Test that write_cache creates parent directory if needed."""
        cache_file = tmp_path / "subdir" / ".update_check"

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            _write_cache("1.0.0")

        assert cache_file.exists()


class TestCacheValidation:
    """Tests for cache TTL validation."""

    def test_cache_valid_when_fresh(self) -> None:
        """Test cache is valid when recently created."""
        cache = {
            "last_check": datetime.now().isoformat(),
            "latest_version": "1.0.0",
        }
        assert _is_cache_valid(cache) is True

    def test_cache_invalid_when_expired(self) -> None:
        """Test cache is invalid when older than 24 hours."""
        old_time = datetime.now() - timedelta(hours=25)
        cache = {
            "last_check": old_time.isoformat(),
            "latest_version": "1.0.0",
        }
        assert _is_cache_valid(cache) is False

    def test_cache_invalid_when_missing_timestamp(self) -> None:
        """Test cache is invalid when missing last_check."""
        cache = {"latest_version": "1.0.0"}
        assert _is_cache_valid(cache) is False

    def test_cache_invalid_when_malformed_timestamp(self) -> None:
        """Test cache is invalid when timestamp is malformed."""
        cache = {
            "last_check": "not-a-date",
            "latest_version": "1.0.0",
        }
        assert _is_cache_valid(cache) is False

    def test_cache_valid_at_boundary(self) -> None:
        """Test cache validity at the 24-hour boundary."""
        # Just under 24 hours - should be valid
        just_under = datetime.now() - timedelta(hours=23, minutes=59)
        cache = {
            "last_check": just_under.isoformat(),
            "latest_version": "1.0.0",
        }
        assert _is_cache_valid(cache) is True


class TestFetchLatestVersion:
    """Tests for fetching latest version from PyPI."""

    def test_fetch_latest_version_success(self) -> None:
        """Test successfully fetching latest version from PyPI."""
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = pypi_response
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            version = _fetch_latest_version()

        assert version == "2.0.0"

    def test_fetch_latest_version_network_error(self) -> None:
        """Test handling network error when fetching from PyPI."""
        import urllib.error

        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("Network error")

            version = _fetch_latest_version()

        assert version is None

    def test_fetch_latest_version_invalid_json(self) -> None:
        """Test handling invalid JSON from PyPI."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = b"not json"
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            version = _fetch_latest_version()

        assert version is None

    def test_fetch_latest_version_missing_info(self) -> None:
        """Test handling response missing info field."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps({}).encode()
            mock_response.__enter__ = lambda s: s
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            version = _fetch_latest_version()

        assert version is None


class TestCheckForUpdate:
    """Tests for the main check_for_update function."""

    def test_check_for_update_with_update_available(self, tmp_path: Path) -> None:
        """Test check_for_update returns UpdateInfo when update available."""
        cache_file = tmp_path / ".update_check"
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = pypi_response
                mock_response.__enter__ = lambda s: s
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                result = check_for_update("1.0.0")

        assert result is not None
        assert result.current_version == "1.0.0"
        assert result.latest_version == "2.0.0"
        assert result.update_available is True

    def test_check_for_update_no_update_available(self, tmp_path: Path) -> None:
        """Test check_for_update returns None when no update available."""
        cache_file = tmp_path / ".update_check"
        pypi_response = json.dumps({"info": {"version": "1.0.0"}}).encode()

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = pypi_response
                mock_response.__enter__ = lambda s: s
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                result = check_for_update("1.0.0")

        assert result is None

    def test_check_for_update_uses_cache(self, tmp_path: Path) -> None:
        """Test check_for_update uses valid cache."""
        cache_file = tmp_path / ".update_check"
        cache_data = {
            "last_check": datetime.now().isoformat(),
            "latest_version": "2.0.0",
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache_data))

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            with patch("urllib.request.urlopen") as mock_urlopen:
                result = check_for_update("1.0.0")

        # Should not call PyPI since cache is valid
        mock_urlopen.assert_not_called()
        assert result is not None
        assert result.latest_version == "2.0.0"

    def test_check_for_update_refreshes_expired_cache(self, tmp_path: Path) -> None:
        """Test check_for_update refreshes expired cache."""
        cache_file = tmp_path / ".update_check"
        old_time = datetime.now() - timedelta(hours=25)
        cache_data = {
            "last_check": old_time.isoformat(),
            "latest_version": "1.5.0",
        }
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache_data))

        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = pypi_response
                mock_response.__enter__ = lambda s: s
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                result = check_for_update("1.0.0")

        # Should call PyPI since cache expired
        mock_urlopen.assert_called_once()
        assert result is not None
        assert result.latest_version == "2.0.0"

    def test_check_for_update_handles_network_error(self, tmp_path: Path) -> None:
        """Test check_for_update handles network error gracefully."""
        import urllib.error

        cache_file = tmp_path / ".update_check"

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.side_effect = urllib.error.URLError("Network error")

                result = check_for_update("1.0.0")

        assert result is None

    def test_check_for_update_writes_cache_after_fetch(self, tmp_path: Path) -> None:
        """Test check_for_update writes cache after successful fetch."""
        cache_file = tmp_path / ".update_check"
        pypi_response = json.dumps({"info": {"version": "2.0.0"}}).encode()

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_response = MagicMock()
                mock_response.read.return_value = pypi_response
                mock_response.__enter__ = lambda s: s
                mock_response.__exit__ = MagicMock(return_value=False)
                mock_urlopen.return_value = mock_response

                check_for_update("1.0.0")

        # Cache should be written
        assert cache_file.exists()
        cache_data = json.loads(cache_file.read_text())
        assert cache_data["latest_version"] == "2.0.0"


class TestClearCache:
    """Tests for clear_cache function."""

    def test_clear_cache_removes_file(self, tmp_path: Path) -> None:
        """Test clear_cache removes the cache file."""
        cache_file = tmp_path / ".update_check"
        cache_file.write_text("{}")

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            result = clear_cache()

        assert result is True
        assert not cache_file.exists()

    def test_clear_cache_returns_false_when_no_file(self, tmp_path: Path) -> None:
        """Test clear_cache returns False when no cache file exists."""
        cache_file = tmp_path / ".update_check"

        with patch("nextdns_blocker.update_check._get_cache_file", return_value=cache_file):
            result = clear_cache()

        assert result is False
