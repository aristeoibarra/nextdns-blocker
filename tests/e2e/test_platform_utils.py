"""E2E tests for platform utilities."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

from nextdns_blocker.platform_utils import (
    get_config_base_dir,
    get_data_base_dir,
    get_executable_args,
    get_executable_path,
    get_log_base_dir,
    get_platform,
    get_platform_display_name,
    get_scheduler_type,
    is_linux,
    is_macos,
    is_windows,
    is_wsl,
)


class TestPlatformDetection:
    """Tests for platform detection functions."""

    @patch("sys.platform", "darwin")
    def test_is_macos_true(self) -> None:
        """Test is_macos returns True on macOS."""
        assert is_macos() is True

    @patch("sys.platform", "linux")
    def test_is_macos_false(self) -> None:
        """Test is_macos returns False on Linux."""
        assert is_macos() is False

    @patch("sys.platform", "win32")
    def test_is_windows_true(self) -> None:
        """Test is_windows returns True on Windows."""
        assert is_windows() is True

    @patch("sys.platform", "darwin")
    def test_is_windows_false(self) -> None:
        """Test is_windows returns False on macOS."""
        assert is_windows() is False

    @patch("sys.platform", "linux")
    def test_is_linux_true(self) -> None:
        """Test is_linux returns True on Linux."""
        assert is_linux() is True

    @patch("sys.platform", "linux2")
    def test_is_linux_true_linux2(self) -> None:
        """Test is_linux returns True on linux2."""
        assert is_linux() is True

    @patch("sys.platform", "darwin")
    def test_is_linux_false(self) -> None:
        """Test is_linux returns False on macOS."""
        assert is_linux() is False


class TestWSLDetection:
    """Tests for WSL detection."""

    @patch("sys.platform", "linux")
    @patch("platform.release")
    def test_is_wsl_true_microsoft(self, mock_release: MagicMock) -> None:
        """Test is_wsl returns True when 'microsoft' in kernel."""
        mock_release.return_value = "5.10.16.3-microsoft-standard-WSL2"

        assert is_wsl() is True

    @patch("sys.platform", "linux")
    @patch("platform.release")
    def test_is_wsl_true_wsl(self, mock_release: MagicMock) -> None:
        """Test is_wsl returns True when 'WSL' in kernel."""
        mock_release.return_value = "5.10.16.3-WSL2"

        assert is_wsl() is True

    @patch("sys.platform", "linux")
    @patch("platform.release")
    def test_is_wsl_false_regular_linux(self, mock_release: MagicMock) -> None:
        """Test is_wsl returns False on regular Linux."""
        mock_release.return_value = "5.15.0-generic"

        assert is_wsl() is False

    @patch("sys.platform", "darwin")
    def test_is_wsl_false_macos(self) -> None:
        """Test is_wsl returns False on macOS."""
        assert is_wsl() is False

    @patch("sys.platform", "linux")
    @patch("platform.release")
    def test_is_wsl_handles_exception(self, mock_release: MagicMock) -> None:
        """Test is_wsl handles exceptions gracefully."""
        # Use OSError as a realistic exception that platform.release() could raise
        mock_release.side_effect = OSError("Error reading platform info")

        assert is_wsl() is False


class TestGetPlatform:
    """Tests for get_platform function."""

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_wsl", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=False)
    def test_get_platform_macos(self, *mocks: Any) -> None:
        """Test get_platform returns 'macos' on macOS."""
        assert get_platform() == "macos"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_wsl", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=False)
    def test_get_platform_windows(self, *mocks: Any) -> None:
        """Test get_platform returns 'windows' on Windows."""
        assert get_platform() == "windows"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_wsl", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=True)
    def test_get_platform_wsl(self, *mocks: Any) -> None:
        """Test get_platform returns 'wsl' on WSL."""
        assert get_platform() == "wsl"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_wsl", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=True)
    def test_get_platform_linux(self, *mocks: Any) -> None:
        """Test get_platform returns 'linux' on Linux."""
        assert get_platform() == "linux"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_wsl", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=False)
    def test_get_platform_unknown(self, *mocks: Any) -> None:
        """Test get_platform returns 'unknown' on unknown platform."""
        assert get_platform() == "unknown"


class TestGetPlatformDisplayName:
    """Tests for get_platform_display_name function."""

    @patch("nextdns_blocker.platform_utils.get_platform", return_value="macos")
    def test_display_name_macos(self, mock_platform: MagicMock) -> None:
        """Test display name for macOS."""
        assert get_platform_display_name() == "macOS"

    @patch("nextdns_blocker.platform_utils.get_platform", return_value="windows")
    def test_display_name_windows(self, mock_platform: MagicMock) -> None:
        """Test display name for Windows."""
        assert get_platform_display_name() == "Windows"

    @patch("nextdns_blocker.platform_utils.get_platform", return_value="wsl")
    def test_display_name_wsl(self, mock_platform: MagicMock) -> None:
        """Test display name for WSL."""
        assert get_platform_display_name() == "Linux (WSL)"

    @patch("nextdns_blocker.platform_utils.get_platform", return_value="linux")
    def test_display_name_linux(self, mock_platform: MagicMock) -> None:
        """Test display name for Linux."""
        assert get_platform_display_name() == "Linux"

    @patch("nextdns_blocker.platform_utils.get_platform", return_value="unknown")
    def test_display_name_unknown(self, mock_platform: MagicMock) -> None:
        """Test display name for unknown platform."""
        assert get_platform_display_name() == "Unknown"


class TestGetSchedulerType:
    """Tests for get_scheduler_type function."""

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=False)
    def test_scheduler_launchd(self, *mocks: Any) -> None:
        """Test scheduler type is launchd on macOS."""
        assert get_scheduler_type() == "launchd"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=False)
    def test_scheduler_task_scheduler(self, *mocks: Any) -> None:
        """Test scheduler type is task_scheduler on Windows."""
        assert get_scheduler_type() == "task_scheduler"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=True)
    def test_scheduler_cron(self, *mocks: Any) -> None:
        """Test scheduler type is cron on Linux."""
        assert get_scheduler_type() == "cron"

    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_linux", return_value=False)
    def test_scheduler_none(self, *mocks: Any) -> None:
        """Test scheduler type is none on unknown platform."""
        assert get_scheduler_type() == "none"


class TestGetExecutablePath:
    """Tests for get_executable_path function."""

    @patch("shutil.which")
    def test_executable_found_in_path(self, mock_which: MagicMock) -> None:
        """Test executable found in PATH."""
        mock_which.return_value = "/usr/local/bin/nextdns-blocker"

        result = get_executable_path()

        assert result == "/usr/local/bin/nextdns-blocker"

    @patch("shutil.which", return_value=None)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    def test_executable_fallback_to_pipx_unix(
        self,
        mock_is_windows: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fallback to pipx location on Unix."""
        with patch.object(Path, "home", return_value=tmp_path):
            pipx_bin = tmp_path / ".local" / "bin" / "nextdns-blocker"
            pipx_bin.parent.mkdir(parents=True)
            pipx_bin.touch()

            result = get_executable_path()

        assert result == str(pipx_bin)

    @patch("shutil.which", return_value=None)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=True)
    def test_executable_fallback_to_pipx_windows(
        self,
        mock_is_windows: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fallback to pipx location on Windows."""
        with patch.object(Path, "home", return_value=tmp_path):
            pipx_bin = tmp_path / ".local" / "bin" / "nextdns-blocker.exe"
            pipx_bin.parent.mkdir(parents=True)
            pipx_bin.touch()

            result = get_executable_path()

        assert result == str(pipx_bin)

    @patch("shutil.which", return_value=None)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    def test_executable_fallback_to_module(
        self,
        mock_is_windows: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test fallback to sys.executable module invocation."""
        with patch.object(Path, "home", return_value=tmp_path):
            # Mock all paths as not existing to force module fallback
            with patch.object(Path, "exists", return_value=False):
                result = get_executable_path()

        assert sys.executable in result
        assert "-m nextdns_blocker" in result


class TestGetExecutableArgs:
    """Tests for get_executable_args function."""

    @patch("shutil.which")
    def test_executable_args_found_in_path(self, mock_which: MagicMock) -> None:
        """Test executable args when found in PATH."""
        mock_which.return_value = "/usr/local/bin/nextdns-blocker"

        result = get_executable_args()

        assert result == ["/usr/local/bin/nextdns-blocker"]

    @patch("shutil.which", return_value=None)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    def test_executable_args_fallback_to_pipx(
        self,
        mock_is_windows: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test executable args fallback to pipx."""
        with patch.object(Path, "home", return_value=tmp_path):
            pipx_bin = tmp_path / ".local" / "bin" / "nextdns-blocker"
            pipx_bin.parent.mkdir(parents=True)
            pipx_bin.touch()

            result = get_executable_args()

        assert result == [str(pipx_bin)]

    @patch("shutil.which", return_value=None)
    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    def test_executable_args_fallback_to_module(
        self,
        mock_is_windows: MagicMock,
        mock_which: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test executable args fallback to module invocation."""
        with patch.object(Path, "home", return_value=tmp_path):
            # Mock all paths as not existing to force module fallback
            with patch.object(Path, "exists", return_value=False):
                result = get_executable_args()

        assert result == [sys.executable, "-m", "nextdns_blocker"]


class TestGetConfigBaseDir:
    """Tests for get_config_base_dir function."""

    @patch("nextdns_blocker.platform_utils.is_windows", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    def test_config_dir_windows(
        self,
        mock_macos: MagicMock,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test config dir on Windows."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_config_base_dir()

        assert result == tmp_path / "AppData" / "Roaming"

    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_macos", return_value=True)
    def test_config_dir_macos(
        self,
        mock_macos: MagicMock,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test config dir on macOS."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_config_base_dir()

        assert result == tmp_path / "Library" / "Application Support"

    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    def test_config_dir_linux(
        self,
        mock_macos: MagicMock,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test config dir on Linux."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_config_base_dir()

        assert result == tmp_path / ".config"


class TestGetDataBaseDir:
    """Tests for get_data_base_dir function."""

    @patch("nextdns_blocker.platform_utils.is_windows", return_value=True)
    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    def test_data_dir_windows(
        self,
        mock_macos: MagicMock,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test data dir on Windows."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_data_base_dir()

        assert result == tmp_path / "AppData" / "Local"

    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_macos", return_value=True)
    def test_data_dir_macos(
        self,
        mock_macos: MagicMock,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test data dir on macOS."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_data_base_dir()

        assert result == tmp_path / "Library" / "Application Support"

    @patch("nextdns_blocker.platform_utils.is_windows", return_value=False)
    @patch("nextdns_blocker.platform_utils.is_macos", return_value=False)
    def test_data_dir_linux(
        self,
        mock_macos: MagicMock,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test data dir on Linux."""
        with patch.object(Path, "home", return_value=tmp_path):
            result = get_data_base_dir()

        assert result == tmp_path / ".local" / "share"


class TestGetLogBaseDir:
    """Tests for get_log_base_dir function."""

    @patch("nextdns_blocker.platform_utils.get_data_base_dir")
    def test_log_dir_uses_data_dir(self, mock_data_dir: MagicMock, tmp_path: Path) -> None:
        """Test log dir uses data base dir."""
        mock_data_dir.return_value = tmp_path / "data"

        result = get_log_base_dir()

        assert result == tmp_path / "data"
        mock_data_dir.assert_called_once()
