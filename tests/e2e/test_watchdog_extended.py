"""Extended E2E tests for watchdog functionality."""

from __future__ import annotations

import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from nextdns_blocker.watchdog import (
    LAUNCHD_SYNC_LABEL,
    LAUNCHD_WATCHDOG_LABEL,
    SUBPROCESS_TIMEOUT,
    WINDOWS_TASK_SYNC_NAME,
    WINDOWS_TASK_WATCHDOG_NAME,
    _build_task_command,
    _create_sync_plist,
    _create_watchdog_plist,
    _escape_windows_path,
    _safe_unlink,
    _write_plist_file,
    audit_log,
    clear_disabled,
    filter_our_cron_jobs,
    generate_plist,
    get_cron_sync,
    get_cron_watchdog,
    get_crontab,
    get_disabled_file,
    get_disabled_remaining,
    get_launch_agents_dir,
    get_sync_plist_path,
    get_watchdog_plist_path,
    has_sync_cron,
    has_watchdog_cron,
    has_windows_task,
    is_disabled,
    is_launchd_job_loaded,
    load_launchd_job,
    set_crontab,
    set_disabled,
    unload_launchd_job,
    watchdog_cli,
)


class TestWatchdogConstants:
    """Tests for watchdog constants."""

    def test_launchd_labels(self) -> None:
        """Test launchd label constants."""
        assert LAUNCHD_SYNC_LABEL == "com.nextdns-blocker.sync"
        assert LAUNCHD_WATCHDOG_LABEL == "com.nextdns-blocker.watchdog"

    def test_windows_task_names(self) -> None:
        """Test Windows task name constants."""
        assert WINDOWS_TASK_SYNC_NAME == "NextDNS-Blocker-Sync"
        assert WINDOWS_TASK_WATCHDOG_NAME == "NextDNS-Blocker-Watchdog"

    def test_subprocess_timeout(self) -> None:
        """Test subprocess timeout constant."""
        assert SUBPROCESS_TIMEOUT == 60


class TestPathFunctions:
    """Tests for path-related functions."""

    @patch.object(Path, "home")
    def test_get_launch_agents_dir(self, mock_home: MagicMock, tmp_path: Path) -> None:
        """Test get_launch_agents_dir returns correct path."""
        mock_home.return_value = tmp_path

        result = get_launch_agents_dir()

        assert result == tmp_path / "Library" / "LaunchAgents"

    @patch("nextdns_blocker.watchdog.get_launch_agents_dir")
    def test_get_sync_plist_path(self, mock_dir: MagicMock, tmp_path: Path) -> None:
        """Test get_sync_plist_path returns correct path."""
        mock_dir.return_value = tmp_path

        result = get_sync_plist_path()

        assert result == tmp_path / f"{LAUNCHD_SYNC_LABEL}.plist"

    @patch("nextdns_blocker.watchdog.get_launch_agents_dir")
    def test_get_watchdog_plist_path(self, mock_dir: MagicMock, tmp_path: Path) -> None:
        """Test get_watchdog_plist_path returns correct path."""
        mock_dir.return_value = tmp_path

        result = get_watchdog_plist_path()

        assert result == tmp_path / f"{LAUNCHD_WATCHDOG_LABEL}.plist"

    @patch("nextdns_blocker.watchdog.get_log_dir")
    def test_get_disabled_file(self, mock_log_dir: MagicMock, tmp_path: Path) -> None:
        """Test get_disabled_file returns correct path."""
        mock_log_dir.return_value = tmp_path / "logs"

        result = get_disabled_file()

        assert result == tmp_path / "logs" / ".watchdog_disabled"


class TestCronJobDefinitions:
    """Tests for cron job definition functions."""

    @patch("nextdns_blocker.watchdog.get_log_dir")
    @patch("nextdns_blocker.watchdog.get_executable_path")
    def test_get_cron_sync(
        self, mock_exe: MagicMock, mock_log_dir: MagicMock, tmp_path: Path
    ) -> None:
        """Test get_cron_sync returns correct cron definition."""
        mock_exe.return_value = "/usr/bin/nextdns-blocker"
        mock_log_dir.return_value = tmp_path

        result = get_cron_sync()

        assert "*/2 * * * *" in result
        assert "nextdns-blocker config sync" in result
        assert "cron.log" in result

    @patch("nextdns_blocker.watchdog.get_log_dir")
    @patch("nextdns_blocker.watchdog.get_executable_path")
    def test_get_cron_watchdog(
        self, mock_exe: MagicMock, mock_log_dir: MagicMock, tmp_path: Path
    ) -> None:
        """Test get_cron_watchdog returns correct cron definition."""
        mock_exe.return_value = "/usr/bin/nextdns-blocker"
        mock_log_dir.return_value = tmp_path

        result = get_cron_watchdog()

        assert "* * * * *" in result
        assert "nextdns-blocker watchdog check" in result
        assert "wd.log" in result


class TestDisabledState:
    """Tests for disabled state management."""

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_is_disabled_false_when_no_file(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test is_disabled returns False when no disabled file."""
        mock_read.return_value = None

        assert is_disabled() is False

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_is_disabled_true_when_permanent(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test is_disabled returns True for permanent disable."""
        mock_read.return_value = "permanent"

        assert is_disabled() is True

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_is_disabled_true_when_future_timestamp(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test is_disabled returns True when disabled until future time."""
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        mock_read.return_value = future_time

        assert is_disabled() is True

    @patch("nextdns_blocker.watchdog._remove_disabled_file")
    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_is_disabled_false_when_expired(
        self, mock_read: MagicMock, mock_file: MagicMock, mock_remove: MagicMock
    ) -> None:
        """Test is_disabled returns False when timestamp expired."""
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        mock_read.return_value = past_time

        assert is_disabled() is False
        mock_remove.assert_called_once()

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_is_disabled_false_on_invalid_content(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test is_disabled returns False on invalid content."""
        mock_read.return_value = "invalid-content"

        assert is_disabled() is False

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_get_disabled_remaining_empty_when_no_file(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test get_disabled_remaining returns empty when no file."""
        mock_read.return_value = None

        assert get_disabled_remaining() == ""

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_get_disabled_remaining_permanent(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test get_disabled_remaining returns 'permanently' for permanent."""
        mock_read.return_value = "permanent"

        assert get_disabled_remaining() == "permanently"

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.read_secure_file")
    def test_get_disabled_remaining_shows_minutes(
        self, mock_read: MagicMock, mock_file: MagicMock
    ) -> None:
        """Test get_disabled_remaining shows remaining minutes."""
        future_time = (datetime.now() + timedelta(minutes=30)).isoformat()
        mock_read.return_value = future_time

        result = get_disabled_remaining()

        assert "min" in result

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.write_secure_file")
    @patch("nextdns_blocker.watchdog.audit_log")
    def test_set_disabled_with_minutes(
        self, mock_audit: MagicMock, mock_write: MagicMock, mock_file: MagicMock, tmp_path: Path
    ) -> None:
        """Test set_disabled sets temporary disable."""
        mock_file.return_value = tmp_path / ".watchdog_disabled"

        set_disabled(30)

        mock_write.assert_called_once()
        mock_audit.assert_called_once()

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog.write_secure_file")
    @patch("nextdns_blocker.watchdog.audit_log")
    def test_set_disabled_permanent(
        self, mock_audit: MagicMock, mock_write: MagicMock, mock_file: MagicMock, tmp_path: Path
    ) -> None:
        """Test set_disabled sets permanent disable."""
        mock_file.return_value = tmp_path / ".watchdog_disabled"

        set_disabled(None)

        mock_write.assert_called_once_with(mock_file.return_value, "permanent")

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    @patch("nextdns_blocker.watchdog._remove_disabled_file")
    @patch("nextdns_blocker.watchdog.audit_log")
    def test_clear_disabled_when_exists(
        self, mock_audit: MagicMock, mock_remove: MagicMock, mock_file: MagicMock, tmp_path: Path
    ) -> None:
        """Test clear_disabled when disabled file exists."""
        disabled_file = tmp_path / ".watchdog_disabled"
        disabled_file.write_text("permanent")
        mock_file.return_value = disabled_file

        result = clear_disabled()

        assert result is True
        mock_remove.assert_called_once()

    @patch("nextdns_blocker.watchdog.get_disabled_file")
    def test_clear_disabled_when_not_exists(self, mock_file: MagicMock, tmp_path: Path) -> None:
        """Test clear_disabled when not disabled."""
        mock_file.return_value = tmp_path / ".watchdog_disabled"  # Does not exist

        result = clear_disabled()

        assert result is False


class TestCronManagement:
    """Tests for cron management functions."""

    @patch("subprocess.run")
    def test_get_crontab_success(self, mock_run: MagicMock) -> None:
        """Test get_crontab returns crontab contents."""
        mock_run.return_value = MagicMock(returncode=0, stdout="cron content")

        result = get_crontab()

        assert result == "cron content"

    @patch("subprocess.run")
    def test_get_crontab_empty_on_error(self, mock_run: MagicMock) -> None:
        """Test get_crontab returns empty on error."""
        mock_run.return_value = MagicMock(returncode=1, stdout="")

        result = get_crontab()

        assert result == ""

    @patch("subprocess.run")
    def test_get_crontab_handles_exception(self, mock_run: MagicMock) -> None:
        """Test get_crontab handles exception."""
        mock_run.side_effect = subprocess.TimeoutExpired("crontab", 60)

        result = get_crontab()

        assert result == ""

    @patch("subprocess.run")
    def test_set_crontab_success(self, mock_run: MagicMock) -> None:
        """Test set_crontab on success."""
        mock_run.return_value = MagicMock(returncode=0)

        result = set_crontab("new content")

        assert result is True

    @patch("subprocess.run")
    def test_set_crontab_failure(self, mock_run: MagicMock) -> None:
        """Test set_crontab on failure."""
        mock_run.return_value = MagicMock(returncode=1)

        result = set_crontab("new content")

        assert result is False

    @patch("subprocess.run")
    def test_set_crontab_handles_exception(self, mock_run: MagicMock) -> None:
        """Test set_crontab handles exception."""
        mock_run.side_effect = OSError("Permission denied")

        result = set_crontab("content")

        assert result is False

    def test_has_sync_cron(self) -> None:
        """Test has_sync_cron detection."""
        crontab_with = "*/2 * * * * nextdns-blocker config sync >> log 2>&1"
        crontab_without = "0 * * * * other-job"

        assert has_sync_cron(crontab_with) is True
        assert has_sync_cron(crontab_without) is False

    def test_has_watchdog_cron(self) -> None:
        """Test has_watchdog_cron detection."""
        crontab_with = "* * * * * nextdns-blocker watchdog check >> log 2>&1"
        crontab_without = "0 * * * * other-job"

        assert has_watchdog_cron(crontab_with) is True
        assert has_watchdog_cron(crontab_without) is False

    def test_filter_our_cron_jobs(self) -> None:
        """Test filter_our_cron_jobs removes our entries."""
        crontab = """*/2 * * * * nextdns-blocker config sync
* * * * * nextdns-blocker watchdog check
0 * * * * other-job
"""
        result = filter_our_cron_jobs(crontab)

        assert len(result) == 1
        assert "other-job" in result[0]
        assert "nextdns-blocker" not in " ".join(result)


class TestLaunchdManagement:
    """Tests for launchd management functions."""

    def test_generate_plist(self, tmp_path: Path) -> None:
        """Test generate_plist creates valid plist."""
        import plistlib

        log_file = tmp_path / "test.log"
        result = generate_plist(
            label="com.test.job",
            program_args=["/usr/bin/test", "arg"],
            start_interval=60,
            log_file=log_file,
        )

        # Parse the result
        parsed = plistlib.loads(result)

        assert parsed["Label"] == "com.test.job"
        assert parsed["ProgramArguments"] == ["/usr/bin/test", "arg"]
        assert parsed["StartInterval"] == 60
        assert parsed["RunAtLoad"] is True

    @patch("subprocess.run")
    def test_load_launchd_job_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test load_launchd_job on success."""
        mock_run.return_value = MagicMock(returncode=0)
        plist_path = tmp_path / "test.plist"
        plist_path.write_text("<plist></plist>")

        result = load_launchd_job(plist_path)

        assert result is True
        assert mock_run.call_count == 2  # unload then load

    @patch("subprocess.run")
    def test_load_launchd_job_failure(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test load_launchd_job on failure."""
        mock_run.side_effect = [
            MagicMock(returncode=0),  # unload
            MagicMock(returncode=1),  # load fails
        ]
        plist_path = tmp_path / "test.plist"

        result = load_launchd_job(plist_path)

        assert result is False

    @patch("subprocess.run")
    def test_load_launchd_job_handles_exception(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test load_launchd_job handles exception."""
        mock_run.side_effect = subprocess.TimeoutExpired("launchctl", 60)
        plist_path = tmp_path / "test.plist"

        result = load_launchd_job(plist_path)

        assert result is False

    @patch("subprocess.run")
    def test_unload_launchd_job_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test unload_launchd_job on success."""
        mock_run.return_value = MagicMock(returncode=0)
        plist_path = tmp_path / "test.plist"
        plist_path.write_text("<plist></plist>")

        result = unload_launchd_job(plist_path, "com.test.job")

        assert result is True
        assert not plist_path.exists()

    @patch("subprocess.run")
    def test_unload_launchd_job_handles_exception(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        """Test unload_launchd_job handles exception."""
        mock_run.side_effect = OSError("Permission denied")
        plist_path = tmp_path / "test.plist"

        result = unload_launchd_job(plist_path, "com.test.job")

        assert result is False

    @patch("subprocess.run")
    def test_is_launchd_job_loaded_true(self, mock_run: MagicMock) -> None:
        """Test is_launchd_job_loaded returns True when loaded."""
        mock_run.return_value = MagicMock(returncode=0)

        result = is_launchd_job_loaded("com.test.job")

        assert result is True

    @patch("subprocess.run")
    def test_is_launchd_job_loaded_false(self, mock_run: MagicMock) -> None:
        """Test is_launchd_job_loaded returns False when not loaded."""
        mock_run.return_value = MagicMock(returncode=1)

        result = is_launchd_job_loaded("com.test.job")

        assert result is False


class TestWindowsHelpers:
    """Tests for Windows-specific helper functions."""

    def test_escape_windows_path_percent(self) -> None:
        """Test percent sign escaping."""
        result = _escape_windows_path("C:\\Users\\%USERNAME%\\file")

        assert result == "C:\\Users\\%%USERNAME%%\\file"

    def test_escape_windows_path_quotes(self) -> None:
        """Test quote escaping."""
        result = _escape_windows_path('C:\\path\\"quoted"')

        assert result == 'C:\\path\\""quoted""'

    def test_build_task_command(self) -> None:
        """Test task command building."""
        result = _build_task_command(
            exe="C:\\Program Files\\app.exe",
            args="sync",
            log_file="C:\\Logs\\app.log",
        )

        assert "cmd /c" in result
        assert "sync" in result
        assert ">>" in result
        assert "2>&1" in result

    @patch("subprocess.run")
    def test_has_windows_task_true(self, mock_run: MagicMock) -> None:
        """Test has_windows_task returns True when task exists."""
        mock_run.return_value = MagicMock(returncode=0)

        result = has_windows_task("TestTask")

        assert result is True

    @patch("subprocess.run")
    def test_has_windows_task_false(self, mock_run: MagicMock) -> None:
        """Test has_windows_task returns False when task doesn't exist."""
        mock_run.return_value = MagicMock(returncode=1)

        result = has_windows_task("TestTask")

        assert result is False

    @patch("subprocess.run")
    def test_has_windows_task_handles_exception(self, mock_run: MagicMock) -> None:
        """Test has_windows_task handles exception."""
        mock_run.side_effect = OSError("Not available")

        result = has_windows_task("TestTask")

        assert result is False


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_write_plist_file_success(self, tmp_path: Path) -> None:
        """Test _write_plist_file on success."""
        plist_path = tmp_path / "test.plist"

        result = _write_plist_file(plist_path, b"<plist></plist>")

        assert result is True
        assert plist_path.exists()

    def test_write_plist_file_failure(self, tmp_path: Path) -> None:
        """Test _write_plist_file on failure."""
        # Try to write to non-existent directory
        plist_path = tmp_path / "nonexistent" / "test.plist"

        result = _write_plist_file(plist_path, b"<plist></plist>")

        assert result is False

    def test_safe_unlink_existing_file(self, tmp_path: Path) -> None:
        """Test _safe_unlink removes existing file."""
        file_path = tmp_path / "test.txt"
        file_path.write_text("content")

        _safe_unlink(file_path)

        assert not file_path.exists()

    def test_safe_unlink_nonexistent_file(self, tmp_path: Path) -> None:
        """Test _safe_unlink handles nonexistent file."""
        file_path = tmp_path / "nonexistent.txt"

        # Should not raise
        _safe_unlink(file_path)

    @patch("nextdns_blocker.watchdog.get_executable_args")
    @patch("nextdns_blocker.watchdog.get_log_dir")
    @patch("nextdns_blocker.watchdog.get_sync_plist_path")
    @patch("nextdns_blocker.watchdog._write_plist_file")
    def test_create_sync_plist_success(
        self,
        mock_write: MagicMock,
        mock_path: MagicMock,
        mock_log_dir: MagicMock,
        mock_exe: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test _create_sync_plist on success."""
        mock_exe.return_value = ["/usr/bin/nextdns-blocker"]
        mock_log_dir.return_value = tmp_path / "logs"
        mock_path.return_value = tmp_path / "sync.plist"
        mock_write.return_value = True

        result = _create_sync_plist()

        assert result is True
        mock_write.assert_called_once()

    @patch("nextdns_blocker.watchdog.get_executable_args")
    @patch("nextdns_blocker.watchdog.get_log_dir")
    @patch("nextdns_blocker.watchdog.get_watchdog_plist_path")
    @patch("nextdns_blocker.watchdog._write_plist_file")
    def test_create_watchdog_plist_success(
        self,
        mock_write: MagicMock,
        mock_path: MagicMock,
        mock_log_dir: MagicMock,
        mock_exe: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Test _create_watchdog_plist on success."""
        mock_exe.return_value = ["/usr/bin/nextdns-blocker"]
        mock_log_dir.return_value = tmp_path / "logs"
        mock_path.return_value = tmp_path / "watchdog.plist"
        mock_write.return_value = True

        result = _create_watchdog_plist()

        assert result is True
        mock_write.assert_called_once()


class TestAuditLog:
    """Tests for watchdog audit log wrapper."""

    @patch("nextdns_blocker.watchdog._base_audit_log")
    def test_audit_log_adds_wd_prefix(self, mock_base: MagicMock) -> None:
        """Test audit_log adds WD prefix."""
        audit_log("TEST_ACTION", "detail")

        mock_base.assert_called_once_with("TEST_ACTION", "detail", prefix="WD")


class TestWatchdogCLI:
    """Tests for watchdog CLI commands."""

    def test_watchdog_cli_group(self, runner: CliRunner) -> None:
        """Test watchdog CLI group."""
        result = runner.invoke(watchdog_cli, ["--help"])

        assert result.exit_code == 0
        assert "Watchdog commands" in result.output

    @patch("nextdns_blocker.watchdog.is_disabled", return_value=True)
    @patch("nextdns_blocker.watchdog.get_disabled_remaining", return_value="30 min")
    def test_cmd_check_when_disabled(
        self,
        mock_remaining: MagicMock,
        mock_disabled: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test check command when watchdog is disabled."""
        result = runner.invoke(watchdog_cli, ["check"])

        assert result.exit_code == 0
        assert "disabled" in result.output

    @patch("nextdns_blocker.watchdog.is_disabled", return_value=False)
    @patch("nextdns_blocker.watchdog.is_macos", return_value=False)
    @patch("nextdns_blocker.watchdog.is_windows", return_value=False)
    @patch("nextdns_blocker.watchdog.has_systemd", return_value=False)
    @patch("nextdns_blocker.watchdog._check_cron_jobs")
    def test_cmd_check_uses_cron_on_linux(
        self,
        mock_check: MagicMock,
        mock_has_systemd: MagicMock,
        mock_is_windows: MagicMock,
        mock_is_macos: MagicMock,
        mock_disabled: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test check command uses cron on Linux without systemd."""
        runner.invoke(watchdog_cli, ["check"])

        mock_check.assert_called_once()

    @patch("nextdns_blocker.watchdog.is_disabled", return_value=False)
    @patch("nextdns_blocker.watchdog.is_macos", return_value=False)
    @patch("nextdns_blocker.watchdog.is_windows", return_value=False)
    @patch("nextdns_blocker.watchdog.has_systemd", return_value=True)
    @patch("nextdns_blocker.watchdog._check_systemd_timers")
    def test_cmd_check_uses_systemd_on_linux(
        self,
        mock_check: MagicMock,
        mock_has_systemd: MagicMock,
        mock_is_windows: MagicMock,
        mock_is_macos: MagicMock,
        mock_disabled: MagicMock,
        runner: CliRunner,
    ) -> None:
        """Test check command uses systemd on Linux with systemd."""
        runner.invoke(watchdog_cli, ["check"])

        mock_check.assert_called_once()

    @patch("nextdns_blocker.watchdog.set_disabled")
    def test_cmd_disable_with_minutes(self, mock_set: MagicMock, runner: CliRunner) -> None:
        """Test disable command with minutes."""
        result = runner.invoke(watchdog_cli, ["disable", "30"])

        assert result.exit_code == 0
        mock_set.assert_called_once_with(30)
        assert "30 minutes" in result.output

    @patch("nextdns_blocker.watchdog.set_disabled")
    def test_cmd_disable_permanent(self, mock_set: MagicMock, runner: CliRunner) -> None:
        """Test disable command permanently."""
        result = runner.invoke(watchdog_cli, ["disable"])

        assert result.exit_code == 0
        mock_set.assert_called_once_with(None)
        assert "permanently" in result.output

    @patch("nextdns_blocker.watchdog.clear_disabled", return_value=True)
    def test_cmd_enable_when_disabled(self, mock_clear: MagicMock, runner: CliRunner) -> None:
        """Test enable command when disabled."""
        result = runner.invoke(watchdog_cli, ["enable"])

        assert result.exit_code == 0
        assert "enabled" in result.output

    @patch("nextdns_blocker.watchdog.clear_disabled", return_value=False)
    def test_cmd_enable_when_already_enabled(
        self, mock_clear: MagicMock, runner: CliRunner
    ) -> None:
        """Test enable command when already enabled."""
        result = runner.invoke(watchdog_cli, ["enable"])

        assert result.exit_code == 0
        assert "already enabled" in result.output
