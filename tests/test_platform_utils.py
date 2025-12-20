"""Tests for platform_utils module."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

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


class TestIsWindows:
    """Tests for is_windows function."""

    def test_is_windows_win32(self):
        """Should return True on Windows platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert is_windows() is True

    def test_is_windows_darwin(self):
        """Should return False on macOS platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_windows() is False

    def test_is_windows_linux(self):
        """Should return False on Linux platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            assert is_windows() is False


class TestIsMacos:
    """Tests for is_macos function."""

    def test_is_macos_darwin(self):
        """Should return True on macOS platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_macos() is True

    def test_is_macos_win32(self):
        """Should return False on Windows platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert is_macos() is False

    def test_is_macos_linux(self):
        """Should return False on Linux platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            assert is_macos() is False


class TestIsLinux:
    """Tests for is_linux function."""

    def test_is_linux_linux(self):
        """Should return True on Linux platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            assert is_linux() is True

    def test_is_linux_linux2(self):
        """Should return True on older Linux platform identifier."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux2"):
            assert is_linux() is True

    def test_is_linux_darwin(self):
        """Should return False on macOS platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_linux() is False

    def test_is_linux_win32(self):
        """Should return False on Windows platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert is_linux() is False


class TestIsWsl:
    """Tests for is_wsl function."""

    def test_is_wsl_microsoft_in_release(self):
        """Should return True when 'microsoft' is in kernel release."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release",
                return_value="5.15.0-microsoft-standard",
            ):
                assert is_wsl() is True

    def test_is_wsl_wsl_in_release(self):
        """Should return True when 'WSL' is in kernel release."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-WSL2"
            ):
                assert is_wsl() is True

    def test_is_wsl_regular_linux(self):
        """Should return False on regular Linux."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-generic"
            ):
                assert is_wsl() is False

    def test_is_wsl_not_linux(self):
        """Should return False on non-Linux platforms."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert is_wsl() is False

    def test_is_wsl_exception_handling(self):
        """Should return False when platform.release() raises exception."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            # Use OSError as a realistic exception that platform.release() could raise
            with patch(
                "nextdns_blocker.platform_utils.platform.release",
                side_effect=OSError("Error reading platform info"),
            ):
                assert is_wsl() is False


class TestGetPlatform:
    """Tests for get_platform function."""

    def test_get_platform_macos(self):
        """Should return 'macos' on Darwin platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert get_platform() == "macos"

    def test_get_platform_windows(self):
        """Should return 'windows' on Windows platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert get_platform() == "windows"

    def test_get_platform_wsl(self):
        """Should return 'wsl' on WSL."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-microsoft"
            ):
                assert get_platform() == "wsl"

    def test_get_platform_linux(self):
        """Should return 'linux' on regular Linux."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-generic"
            ):
                assert get_platform() == "linux"

    def test_get_platform_unknown(self):
        """Should return 'unknown' on unknown platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "freebsd"):
            assert get_platform() == "unknown"


class TestGetPlatformDisplayName:
    """Tests for get_platform_display_name function."""

    def test_display_name_macos(self):
        """Should return 'macOS' on Darwin."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert get_platform_display_name() == "macOS"

    def test_display_name_windows(self):
        """Should return 'Windows' on Windows."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert get_platform_display_name() == "Windows"

    def test_display_name_linux(self):
        """Should return 'Linux' on Linux."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-generic"
            ):
                assert get_platform_display_name() == "Linux"

    def test_display_name_wsl(self):
        """Should return 'Linux (WSL)' on WSL."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-microsoft"
            ):
                assert get_platform_display_name() == "Linux (WSL)"


class TestGetSchedulerType:
    """Tests for get_scheduler_type function."""

    def test_scheduler_type_macos(self):
        """Should return 'launchd' on macOS."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            assert get_scheduler_type() == "launchd"

    def test_scheduler_type_windows(self):
        """Should return 'task_scheduler' on Windows."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            assert get_scheduler_type() == "task_scheduler"

    def test_scheduler_type_linux(self):
        """Should return 'cron' on Linux."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            assert get_scheduler_type() == "cron"

    def test_scheduler_type_wsl(self):
        """Should return 'cron' on WSL (uses Linux cron)."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch(
                "nextdns_blocker.platform_utils.platform.release", return_value="5.15.0-microsoft"
            ):
                assert get_scheduler_type() == "cron"

    def test_scheduler_type_unknown(self):
        """Should return 'none' on unknown platform."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "freebsd"):
            assert get_scheduler_type() == "none"


class TestGetExecutablePath:
    """Tests for get_executable_path function."""

    def test_get_executable_path_which_found(self):
        """Should return path from shutil.which if found."""
        with patch("shutil.which", return_value="/usr/bin/nextdns-blocker"):
            assert get_executable_path() == "/usr/bin/nextdns-blocker"

    def test_get_executable_path_pipx_fallback_unix(self, tmp_path):
        """Should check pipx location on Unix if which fails."""
        pipx_exe = tmp_path / ".local" / "bin" / "nextdns-blocker"
        pipx_exe.parent.mkdir(parents=True)
        pipx_exe.touch()

        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
                with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                    result = get_executable_path()
                    assert str(pipx_exe) == result

    def test_get_executable_path_fallback_to_module(self, tmp_path):
        """Should fallback to module invocation if executable not found."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
                with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                    # Mock all paths as not existing to force module fallback
                    with patch.object(Path, "exists", return_value=False):
                        result = get_executable_path()
                        assert "-m nextdns_blocker" in result

    @pytest.mark.skipif(sys.platform == "win32", reason="Homebrew only on macOS/Linux")
    def test_get_executable_path_homebrew_arm_fallback(self, tmp_path):
        """Should check Homebrew ARM location on macOS if which and pipx fail."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):

                def mock_path_exists(path_self):
                    return "/opt/homebrew/bin/nextdns-blocker" in str(path_self)

                with patch.object(Path, "exists", mock_path_exists):
                    result = get_executable_path()
                    assert result == "/opt/homebrew/bin/nextdns-blocker"

    @pytest.mark.skipif(sys.platform == "win32", reason="Homebrew only on macOS/Linux")
    def test_get_executable_path_homebrew_intel_fallback(self, tmp_path):
        """Should check Homebrew Intel location on macOS if ARM not found."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):

                def mock_path_exists(path_self):
                    return "/usr/local/bin/nextdns-blocker" in str(path_self)

                with patch.object(Path, "exists", mock_path_exists):
                    result = get_executable_path()
                    assert result == "/usr/local/bin/nextdns-blocker"


class TestGetExecutableArgs:
    """Tests for get_executable_args function."""

    def test_get_executable_args_which_found(self):
        """Should return list with path from shutil.which if found."""
        with patch("shutil.which", return_value="/usr/bin/nextdns-blocker"):
            args = get_executable_args()
            assert args == ["/usr/bin/nextdns-blocker"]

    def test_get_executable_args_returns_list(self, tmp_path):
        """Should always return a list."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
                with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                    args = get_executable_args()
                    assert isinstance(args, list)
                    assert len(args) >= 1

    def test_get_executable_args_module_fallback(self, tmp_path):
        """Should return module args when executable not found."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
                with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                    # Mock all paths as not existing to force module fallback
                    with patch.object(Path, "exists", return_value=False):
                        args = get_executable_args()
                        assert "-m" in args
                        assert "nextdns_blocker" in args

    @pytest.mark.skipif(sys.platform == "win32", reason="Homebrew only on macOS/Linux")
    def test_get_executable_args_homebrew_arm_fallback(self, tmp_path):
        """Should check Homebrew ARM location on macOS if which and pipx fail."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):

                def mock_path_exists(path_self):
                    return "/opt/homebrew/bin/nextdns-blocker" in str(path_self)

                with patch.object(Path, "exists", mock_path_exists):
                    args = get_executable_args()
                    assert args == ["/opt/homebrew/bin/nextdns-blocker"]

    @pytest.mark.skipif(sys.platform == "win32", reason="Homebrew only on macOS/Linux")
    def test_get_executable_args_homebrew_intel_fallback(self, tmp_path):
        """Should check Homebrew Intel location on macOS if ARM not found."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):

                def mock_path_exists(path_self):
                    return "/usr/local/bin/nextdns-blocker" in str(path_self)

                with patch.object(Path, "exists", mock_path_exists):
                    args = get_executable_args()
                    assert args == ["/usr/local/bin/nextdns-blocker"]


class TestGetConfigBaseDir:
    """Tests for get_config_base_dir function."""

    def test_config_base_dir_windows(self, tmp_path):
        """Should return AppData\\Roaming on Windows."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_config_base_dir()
                assert result == tmp_path / "AppData" / "Roaming"

    def test_config_base_dir_macos(self, tmp_path):
        """Should return Library/Application Support on macOS."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_config_base_dir()
                assert result == tmp_path / "Library" / "Application Support"

    def test_config_base_dir_linux(self, tmp_path):
        """Should return .config on Linux."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_config_base_dir()
                assert result == tmp_path / ".config"


class TestGetDataBaseDir:
    """Tests for get_data_base_dir function."""

    def test_data_base_dir_windows(self, tmp_path):
        """Should return AppData\\Local on Windows."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_data_base_dir()
                assert result == tmp_path / "AppData" / "Local"

    def test_data_base_dir_macos(self, tmp_path):
        """Should return Library/Application Support on macOS."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "darwin"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_data_base_dir()
                assert result == tmp_path / "Library" / "Application Support"

    def test_data_base_dir_linux(self, tmp_path):
        """Should return .local/share on Linux."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "linux"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_data_base_dir()
                assert result == tmp_path / ".local" / "share"


class TestGetLogBaseDir:
    """Tests for get_log_base_dir function."""

    def test_log_base_dir_windows(self, tmp_path):
        """Should return same as data dir on Windows."""
        with patch("nextdns_blocker.platform_utils.sys.platform", "win32"):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                result = get_log_base_dir()
                assert result == tmp_path / "AppData" / "Local"


class TestWindowsTaskScheduler:
    """Tests for Windows Task Scheduler functions in watchdog."""

    def test_has_windows_task_exists(self):
        """Should return True when task exists."""
        from nextdns_blocker.watchdog import has_windows_task

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("nextdns_blocker.watchdog.subprocess.run", return_value=mock_result):
            assert has_windows_task("TestTask") is True

    def test_has_windows_task_not_exists(self):
        """Should return False when task doesn't exist."""
        from nextdns_blocker.watchdog import has_windows_task

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("nextdns_blocker.watchdog.subprocess.run", return_value=mock_result):
            assert has_windows_task("TestTask") is False

    def test_has_windows_task_exception(self):
        """Should return False on exception."""
        from nextdns_blocker.watchdog import has_windows_task

        with patch("nextdns_blocker.watchdog.subprocess.run", side_effect=OSError("error")):
            assert has_windows_task("TestTask") is False


class TestWindowsWatchdogCommands:
    """Tests for Windows watchdog CLI commands."""

    def test_cmd_install_windows(self):
        """Should call _install_windows_tasks on Windows."""
        from click.testing import CliRunner

        from nextdns_blocker.watchdog import watchdog_cli

        runner = CliRunner()

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=True):
                with patch("nextdns_blocker.watchdog._install_windows_tasks") as mock_install:
                    runner.invoke(watchdog_cli, ["install"])
                    mock_install.assert_called_once()

    def test_cmd_uninstall_windows(self):
        """Should call _uninstall_windows_tasks on Windows."""
        from click.testing import CliRunner

        from nextdns_blocker.watchdog import watchdog_cli

        runner = CliRunner()

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=True):
                with patch("nextdns_blocker.watchdog._uninstall_windows_tasks") as mock_uninstall:
                    runner.invoke(watchdog_cli, ["uninstall"])
                    mock_uninstall.assert_called_once()

    def test_cmd_status_windows(self):
        """Should call _status_windows_tasks on Windows."""
        from click.testing import CliRunner

        from nextdns_blocker.watchdog import watchdog_cli

        runner = CliRunner()

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=True):
                with patch("nextdns_blocker.watchdog._status_windows_tasks") as mock_status:
                    runner.invoke(watchdog_cli, ["status"])
                    mock_status.assert_called_once()

    def test_cmd_check_windows(self):
        """Should call _check_windows_tasks on Windows."""
        from click.testing import CliRunner

        from nextdns_blocker.watchdog import watchdog_cli

        runner = CliRunner()

        with patch("nextdns_blocker.watchdog.is_macos", return_value=False):
            with patch("nextdns_blocker.watchdog.is_windows", return_value=True):
                with patch("nextdns_blocker.watchdog.is_disabled", return_value=False):
                    with patch("nextdns_blocker.watchdog._check_windows_tasks") as mock_check:
                        runner.invoke(watchdog_cli, ["check"])
                        mock_check.assert_called_once()


class TestInstallSchedulingWindows:
    """Tests for install_scheduling function with Windows support."""

    def test_install_scheduling_windows(self):
        """Should call _install_windows_task on Windows."""
        from nextdns_blocker.init import install_scheduling

        with patch("nextdns_blocker.init.is_macos", return_value=False):
            with patch("nextdns_blocker.init.is_windows", return_value=True):
                with patch("nextdns_blocker.init._install_windows_task") as mock_install:
                    mock_install.return_value = (True, "Task Scheduler")
                    result = install_scheduling()
                    mock_install.assert_called_once()
                    assert result == (True, "Task Scheduler")
