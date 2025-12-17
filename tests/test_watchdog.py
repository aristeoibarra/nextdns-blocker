"""Tests for watchdog.py - Scheduled job watchdog functionality (cron/launchd)."""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from nextdns_blocker import watchdog

# Helper for skipping Unix-specific tests on Windows
is_windows = sys.platform == "win32"
skip_on_windows = pytest.mark.skipif(
    is_windows, reason="Unix permissions not applicable on Windows"
)


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_disabled_file(temp_log_dir):
    """Mock the disabled file path by patching the getter function."""
    disabled_file = temp_log_dir / ".watchdog_disabled"
    with patch.object(watchdog, "get_disabled_file", return_value=disabled_file):
        yield disabled_file


@pytest.fixture
def mock_audit_log_file(temp_log_dir):
    """Mock the AUDIT_LOG_FILE path by patching the common module."""
    audit_file = temp_log_dir / "audit.log"
    with patch("nextdns_blocker.common.get_audit_log_file", return_value=audit_file):
        with patch("nextdns_blocker.common.get_log_dir", return_value=temp_log_dir):
            yield audit_file


class TestIsDisabled:
    """Tests for is_disabled function."""

    def test_is_disabled_no_file(self, mock_disabled_file):
        """Should return False when no disabled file exists."""
        assert watchdog.is_disabled() is False

    def test_is_disabled_permanent(self, mock_disabled_file):
        """Should return True when permanently disabled."""
        mock_disabled_file.write_text("permanent")
        assert watchdog.is_disabled() is True

    def test_is_disabled_active_timer(self, mock_disabled_file):
        """Should return True when disabled with active timer."""
        future_time = datetime.now() + timedelta(minutes=30)
        mock_disabled_file.write_text(future_time.isoformat())
        assert watchdog.is_disabled() is True

    def test_is_disabled_expired_timer(self, mock_disabled_file):
        """Should return False and clean up when timer expired."""
        past_time = datetime.now() - timedelta(minutes=30)
        mock_disabled_file.write_text(past_time.isoformat())
        assert watchdog.is_disabled() is False
        # File should be cleaned up
        assert not mock_disabled_file.exists()

    def test_is_disabled_invalid_content(self, mock_disabled_file):
        """Should return False for invalid file content."""
        mock_disabled_file.write_text("invalid content")
        assert watchdog.is_disabled() is False


class TestGetDisabledRemaining:
    """Tests for get_disabled_remaining function."""

    def test_get_disabled_remaining_no_file(self, mock_disabled_file):
        """Should return empty string when no file exists."""
        assert watchdog.get_disabled_remaining() == ""

    def test_get_disabled_remaining_permanent(self, mock_disabled_file):
        """Should return 'permanently' when permanently disabled."""
        mock_disabled_file.write_text("permanent")
        assert watchdog.get_disabled_remaining() == "permanently"

    def test_get_disabled_remaining_minutes(self, mock_disabled_file):
        """Should return remaining minutes."""
        future_time = datetime.now() + timedelta(minutes=45)
        mock_disabled_file.write_text(future_time.isoformat())
        result = watchdog.get_disabled_remaining()
        # Should be around 44-45 min
        assert "min" in result
        assert int(result.split()[0]) >= 44

    def test_get_disabled_remaining_less_than_minute(self, mock_disabled_file):
        """Should return '< 1 min' when less than a minute remaining."""
        future_time = datetime.now() + timedelta(seconds=30)
        mock_disabled_file.write_text(future_time.isoformat())
        assert watchdog.get_disabled_remaining() == "< 1 min"

    def test_get_disabled_remaining_expired(self, mock_disabled_file):
        """Should return empty string and clean up when expired."""
        past_time = datetime.now() - timedelta(minutes=5)
        mock_disabled_file.write_text(past_time.isoformat())
        assert watchdog.get_disabled_remaining() == ""
        assert not mock_disabled_file.exists()


class TestSetDisabled:
    """Tests for set_disabled function."""

    def test_set_disabled_temporary(self, mock_disabled_file, mock_audit_log_file):
        """Should set temporary disabled state."""
        watchdog.set_disabled(30)
        content = mock_disabled_file.read_text()
        # Should be a valid ISO datetime
        disabled_until = datetime.fromisoformat(content)
        expected = datetime.now() + timedelta(minutes=30)
        # Allow 1 second tolerance
        assert abs((disabled_until - expected).total_seconds()) < 1

    def test_set_disabled_permanent(self, mock_disabled_file, mock_audit_log_file):
        """Should set permanent disabled state."""
        watchdog.set_disabled(None)
        assert mock_disabled_file.read_text() == "permanent"


class TestClearDisabled:
    """Tests for clear_disabled function."""

    def test_clear_disabled_when_disabled(self, mock_disabled_file, mock_audit_log_file):
        """Should return True and remove file when disabled."""
        mock_disabled_file.write_text("permanent")
        assert watchdog.clear_disabled() is True
        assert not mock_disabled_file.exists()

    def test_clear_disabled_when_not_disabled(self, mock_disabled_file):
        """Should return False when not disabled."""
        assert watchdog.clear_disabled() is False


class TestCronHelpers:
    """Tests for cron helper functions."""

    def test_has_sync_cron_present(self):
        """Should return True when sync cron is present."""
        crontab = "*/2 * * * * cd /path && nextdns-blocker sync"
        assert watchdog.has_sync_cron(crontab) is True

    def test_has_sync_cron_absent(self):
        """Should return False when sync cron is absent."""
        crontab = "0 * * * * some_other_job"
        assert watchdog.has_sync_cron(crontab) is False

    def test_has_watchdog_cron_present(self):
        """Should return True when watchdog cron is present."""
        crontab = "* * * * * cd /path && nextdns-blocker watchdog check"
        assert watchdog.has_watchdog_cron(crontab) is True

    def test_has_watchdog_cron_absent(self):
        """Should return False when watchdog cron is absent."""
        crontab = "0 * * * * some_other_job"
        assert watchdog.has_watchdog_cron(crontab) is False

    def test_filter_our_cron_jobs_removes_blocker(self):
        """Should remove nextdns-blocker jobs."""
        crontab = """0 * * * * other_job
*/2 * * * * cd /path && nextdns-blocker sync
30 * * * * another_job"""
        result = watchdog.filter_our_cron_jobs(crontab)
        assert len(result) == 2
        assert "nextdns-blocker" not in "\n".join(result)

    def test_filter_our_cron_jobs_removes_watchdog(self):
        """Should remove nextdns-blocker watchdog jobs."""
        crontab = """0 * * * * other_job
* * * * * cd /path && nextdns-blocker watchdog check"""
        result = watchdog.filter_our_cron_jobs(crontab)
        assert len(result) == 1
        assert "nextdns-blocker" not in "\n".join(result)

    def test_filter_our_cron_jobs_keeps_empty_lines_out(self):
        """Should not include empty lines in result."""
        crontab = """0 * * * * other_job

30 * * * * another_job
"""
        result = watchdog.filter_our_cron_jobs(crontab)
        assert len(result) == 2
        assert "" not in result


class TestGetCrontab:
    """Tests for get_crontab function."""

    def test_get_crontab_success(self):
        """Should return crontab content on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "*/5 * * * * some_job\n"

        with patch("subprocess.run", return_value=mock_result):
            result = watchdog.get_crontab()
            assert result == "*/5 * * * * some_job\n"

    def test_get_crontab_no_crontab(self):
        """Should return empty string when no crontab exists."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            result = watchdog.get_crontab()
            assert result == ""

    def test_get_crontab_error(self):
        """Should return empty string on error."""
        with patch("subprocess.run", side_effect=OSError("error")):
            result = watchdog.get_crontab()
            assert result == ""


class TestSetCrontab:
    """Tests for set_crontab function."""

    def test_set_crontab_success(self):
        """Should return True on success."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = watchdog.set_crontab("*/5 * * * * job\n")
            assert result is True

    def test_set_crontab_failure(self):
        """Should return False on failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = watchdog.set_crontab("*/5 * * * * job\n")
            assert result is False

    def test_set_crontab_error(self):
        """Should return False on error."""
        with patch("subprocess.run", side_effect=OSError("error")):
            result = watchdog.set_crontab("*/5 * * * * job\n")
            assert result is False


class TestCmdCheck:
    """Tests for cmd_check function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_check_disabled(self, runner, mock_disabled_file):
        """Should skip check when disabled."""
        mock_disabled_file.write_text("permanent")
        result = runner.invoke(watchdog.cmd_check)
        assert result.exit_code == 0
        assert "disabled" in result.output

    def test_cmd_check_all_present(self, runner):
        """Should do nothing when all cron jobs present."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"

        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "get_crontab", return_value=crontab):
                result = runner.invoke(watchdog.cmd_check)
                assert result.exit_code == 0


class TestCmdStatus:
    """Tests for cmd_status function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_status_all_ok(self, runner, mock_disabled_file):
        """Should show OK status when all cron jobs present."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"

        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    result = runner.invoke(watchdog.cmd_status)
                    assert result.exit_code == 0
                    assert "ok" in result.output
                    assert "active" in result.output

    def test_cmd_status_missing_crons(self, runner, mock_disabled_file):
        """Should show missing status when cron jobs absent."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    result = runner.invoke(watchdog.cmd_status)
                    assert result.exit_code == 0
                    assert "missing" in result.output
                    assert "compromised" in result.output

    def test_cmd_status_disabled(self, runner, mock_disabled_file):
        """Should show disabled status when watchdog disabled."""
        mock_disabled_file.write_text("permanent")
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"

        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    result = runner.invoke(watchdog.cmd_status)
                    assert result.exit_code == 0
                    assert "DISABLED" in result.output


class TestCmdDisable:
    """Tests for cmd_disable function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_disable_temporary(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should disable for specified minutes."""
        result = runner.invoke(watchdog.cmd_disable, ["30"])
        assert result.exit_code == 0
        assert "30 minutes" in result.output

    def test_cmd_disable_permanent(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should disable permanently."""
        # No argument means permanent disable
        result = runner.invoke(watchdog.cmd_disable, [])
        assert result.exit_code == 0
        assert "permanently" in result.output


class TestCmdEnable:
    """Tests for cmd_enable function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_enable_when_disabled(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should enable when currently disabled."""
        mock_disabled_file.write_text("permanent")
        result = runner.invoke(watchdog.cmd_enable)
        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_cmd_enable_when_already_enabled(self, runner, mock_disabled_file):
        """Should indicate already enabled."""
        result = runner.invoke(watchdog.cmd_enable)
        assert result.exit_code == 0
        assert "already enabled" in result.output


class TestWriteSecureFile:
    """Tests for write_secure_file function."""

    def test_write_secure_file_creates_file(self, temp_log_dir):
        """Should create file with content."""
        test_file = temp_log_dir / "test.txt"
        watchdog.write_secure_file(test_file, "test content")
        assert test_file.read_text() == "test content"

    @skip_on_windows
    def test_write_secure_file_secure_permissions(self, temp_log_dir):
        """Should create file with secure permissions."""
        test_file = temp_log_dir / "test.txt"
        watchdog.write_secure_file(test_file, "test content")
        mode = test_file.stat().st_mode & 0o777
        assert mode == 0o600

    def test_write_secure_file_overwrites(self, temp_log_dir):
        """Should overwrite existing file."""
        test_file = temp_log_dir / "test.txt"
        test_file.write_text("old content")
        watchdog.write_secure_file(test_file, "new content")
        assert test_file.read_text() == "new content"


class TestReadSecureFile:
    """Tests for read_secure_file function."""

    def test_read_secure_file_exists(self, temp_log_dir):
        """Should read existing file content."""
        test_file = temp_log_dir / "test.txt"
        test_file.write_text("  test content  ")
        result = watchdog.read_secure_file(test_file)
        assert result == "test content"

    def test_read_secure_file_not_exists(self, temp_log_dir):
        """Should return None for non-existent file."""
        test_file = temp_log_dir / "nonexistent.txt"
        result = watchdog.read_secure_file(test_file)
        assert result is None


class TestCmdInstall:
    """Tests for cmd_install function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_install_success(self, runner, mock_audit_log_file):
        """Should install cron jobs successfully."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        result = runner.invoke(watchdog.cmd_install)
                        assert result.exit_code == 0
                        assert "cron installed" in result.output

    def test_cmd_install_failure(self, runner):
        """Should return error when cron install fails."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=False):
                        result = runner.invoke(watchdog.cmd_install)
                        assert result.exit_code == 1
                        assert "failed" in result.output

    def test_cmd_install_preserves_existing(self, runner, mock_audit_log_file):
        """Should preserve existing cron jobs."""
        existing_cron = "0 * * * * other_job\n"
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=existing_cron):
                    with patch.object(watchdog, "set_crontab", return_value=True) as mock_set:
                        runner.invoke(watchdog.cmd_install)
                        # Verify existing job is preserved
                        call_arg = mock_set.call_args[0][0]
                        assert "other_job" in call_arg


class TestCmdUninstall:
    """Tests for cmd_uninstall function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_uninstall_success(self, runner, mock_audit_log_file):
        """Should uninstall cron jobs successfully."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        result = runner.invoke(watchdog.cmd_uninstall)
                        assert result.exit_code == 0
                        assert "removed" in result.output

    def test_cmd_uninstall_failure(self, runner):
        """Should return error when uninstall fails."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=False):
                        result = runner.invoke(watchdog.cmd_uninstall)
                        assert result.exit_code == 1

    def test_cmd_uninstall_preserves_other_jobs(self, runner, mock_audit_log_file):
        """Should preserve non-blocker cron jobs."""
        crontab = "0 * * * * other_job\n*/2 * * * * nextdns-blocker sync\n"
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    with patch.object(watchdog, "set_crontab", return_value=True) as mock_set:
                        runner.invoke(watchdog.cmd_uninstall)
                        call_arg = mock_set.call_args[0][0]
                        assert "other_job" in call_arg
                        assert "nextdns-blocker" not in call_arg


class TestCmdCheckRestoration:
    """Tests for cmd_check cron restoration using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_check_restores_missing_sync(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should restore missing sync cron."""
        # First call returns no sync, second returns with sync added
        crontab_states = [
            "* * * * * nextdns-blocker watchdog check\n",
            "* * * * * nextdns-blocker watchdog check\n*/2 * * * * nextdns-blocker sync\n",
        ]
        call_count = [0]

        def get_crontab_side_effect():
            result = crontab_states[min(call_count[0], len(crontab_states) - 1)]
            call_count[0] += 1
            return result

        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", side_effect=get_crontab_side_effect):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        with patch("subprocess.run"):
                            result = runner.invoke(watchdog.cmd_check)
                            assert result.exit_code == 0
                            assert "sync cron restored" in result.output

    def test_cmd_check_restores_missing_watchdog(
        self, runner, mock_disabled_file, mock_audit_log_file
    ):
        """Should restore missing watchdog cron."""
        crontab_states = [
            "*/2 * * * * nextdns-blocker sync\n",
            "*/2 * * * * nextdns-blocker sync\n",
        ]
        call_count = [0]

        def get_crontab_side_effect():
            result = crontab_states[min(call_count[0], len(crontab_states) - 1)]
            call_count[0] += 1
            return result

        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", side_effect=get_crontab_side_effect):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        with patch("subprocess.run"):
                            result = runner.invoke(watchdog.cmd_check)
                            assert result.exit_code == 0
                            assert "watchdog cron restored" in result.output


class TestAuditLogWatchdog:
    """Tests for watchdog audit_log function."""

    def test_audit_log_creates_file(self, temp_log_dir):
        """Should create audit log file."""
        audit_file = temp_log_dir / "audit.log"
        with patch("nextdns_blocker.common.get_audit_log_file", return_value=audit_file):
            with patch("nextdns_blocker.common.get_log_dir", return_value=temp_log_dir):
                watchdog.audit_log("TEST", "detail")
                assert audit_file.exists()

    def test_audit_log_writes_wd_prefix(self, temp_log_dir):
        """Should write WD prefix in log entries."""
        audit_file = temp_log_dir / "audit.log"
        with patch("nextdns_blocker.common.get_audit_log_file", return_value=audit_file):
            with patch("nextdns_blocker.common.get_log_dir", return_value=temp_log_dir):
                watchdog.audit_log("ACTION", "detail")
                content = audit_file.read_text()
                assert "WD" in content
                assert "ACTION" in content


class TestMain:
    """Tests for main function using CliRunner."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_main_no_args(self, runner):
        """Should print usage when no args provided."""
        result = runner.invoke(watchdog.main, [])
        # Click group without invoke_without_command returns 0 and shows help
        # Exit code may be 0 or 2 depending on Click version/configuration
        assert "Usage:" in result.output or "usage:" in result.output.lower()

    def test_main_unknown_command(self, runner):
        """Should print error for unknown command."""
        result = runner.invoke(watchdog.main, ["unknown"])
        assert result.exit_code != 0

    def test_main_status_command(self, runner, mock_disabled_file):
        """Should run status command."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    result = runner.invoke(watchdog.main, ["status"])
                    assert result.exit_code == 0

    def test_main_check_command(self, runner, mock_disabled_file):
        """Should run check command."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    result = runner.invoke(watchdog.main, ["check"])
                    assert result.exit_code == 0

    def test_main_install_command(self, runner, mock_audit_log_file):
        """Should run install command."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        result = runner.invoke(watchdog.main, ["install"])
                        assert result.exit_code == 0

    def test_main_uninstall_command(self, runner, mock_audit_log_file):
        """Should run uninstall command."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        result = runner.invoke(watchdog.main, ["uninstall"])
                        assert result.exit_code == 0

    def test_main_disable_command(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should run disable command."""
        result = runner.invoke(watchdog.main, ["disable", "30"])
        assert result.exit_code == 0

    def test_main_disable_permanent(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should run disable command without minutes (permanent)."""
        result = runner.invoke(watchdog.main, ["disable"])
        assert result.exit_code == 0

    def test_main_enable_command(self, runner, mock_disabled_file, mock_audit_log_file):
        """Should run enable command."""
        mock_disabled_file.write_text("permanent")
        result = runner.invoke(watchdog.main, ["enable"])
        assert result.exit_code == 0

    def test_main_disable_invalid_minutes(self, runner):
        """Should error on invalid disable minutes."""
        result = runner.invoke(watchdog.main, ["disable", "abc"])
        assert result.exit_code != 0
        # Click shows its own error message for invalid arguments
        assert "Invalid value" in result.output or "not a valid" in result.output.lower()

    def test_main_disable_negative_minutes(self, runner):
        """Should error on negative disable minutes."""
        result = runner.invoke(watchdog.main, ["disable", "-5"])
        assert result.exit_code != 0
        # Click interprets -5 as an option flag, so it shows "No such option" error
        assert "No such option" in result.output or "Invalid" in result.output


# =============================================================================
# LAUNCHD TESTS (macOS)
# =============================================================================


class TestPlatformDetection:
    """Tests for platform detection functions."""

    def test_is_macos_on_darwin(self):
        """Should return True on macOS."""
        with patch("sys.platform", "darwin"):
            assert watchdog.is_macos() is True

    def test_is_macos_on_linux(self):
        """Should return False on Linux."""
        with patch("sys.platform", "linux"):
            assert watchdog.is_macos() is False

    def test_is_macos_on_windows(self):
        """Should return False on Windows."""
        with patch("sys.platform", "win32"):
            assert watchdog.is_macos() is False


class TestLaunchdPaths:
    """Tests for launchd path functions."""

    def test_get_launch_agents_dir(self):
        """Should return ~/Library/LaunchAgents."""
        result = watchdog.get_launch_agents_dir()
        assert result == Path.home() / "Library" / "LaunchAgents"

    def test_get_sync_plist_path(self):
        """Should return correct sync plist path."""
        result = watchdog.get_sync_plist_path()
        expected = Path.home() / "Library" / "LaunchAgents" / "com.nextdns-blocker.sync.plist"
        assert result == expected

    def test_get_watchdog_plist_path(self):
        """Should return correct watchdog plist path."""
        result = watchdog.get_watchdog_plist_path()
        expected = Path.home() / "Library" / "LaunchAgents" / "com.nextdns-blocker.watchdog.plist"
        assert result == expected


class TestGeneratePlist:
    """Tests for plist generation."""

    def test_generate_plist_valid_content(self):
        """Should generate valid plist content."""
        import plistlib

        content = watchdog.generate_plist(
            label="com.test.label",
            program_args=["/usr/bin/test", "arg"],
            start_interval=60,
            log_file=Path("/tmp/test.log"),
        )
        # Should be parseable
        parsed = plistlib.loads(content)
        assert parsed["Label"] == "com.test.label"
        assert parsed["ProgramArguments"] == ["/usr/bin/test", "arg"]
        assert parsed["StartInterval"] == 60
        assert parsed["RunAtLoad"] is True

    def test_generate_plist_includes_path(self):
        """Should include PATH environment variable with pipx location."""
        import plistlib

        content = watchdog.generate_plist(
            label="test",
            program_args=["test"],
            start_interval=60,
            log_file=Path("/tmp/test.log"),
        )
        parsed = plistlib.loads(content)
        assert "PATH" in parsed["EnvironmentVariables"]
        path_env = parsed["EnvironmentVariables"]["PATH"]
        assert "/opt/homebrew/bin" in path_env
        assert "/.local/bin" in path_env  # pipx location

    def test_generate_plist_log_paths(self, temp_log_dir):
        """Should set stdout and stderr to log file."""
        import plistlib

        log_file = temp_log_dir / "test.log"
        content = watchdog.generate_plist(
            label="test",
            program_args=["test"],
            start_interval=60,
            log_file=log_file,
        )
        parsed = plistlib.loads(content)
        assert parsed["StandardOutPath"] == str(log_file)
        assert parsed["StandardErrorPath"] == str(log_file)


class TestLaunchctlCommands:
    """Tests for launchctl command functions."""

    def test_is_launchd_job_loaded_true(self):
        """Should return True when job is loaded."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            assert watchdog.is_launchd_job_loaded("com.test.label") is True

    def test_is_launchd_job_loaded_false(self):
        """Should return False when job is not loaded."""
        mock_result = MagicMock()
        mock_result.returncode = 3  # Job not found

        with patch("subprocess.run", return_value=mock_result):
            assert watchdog.is_launchd_job_loaded("com.test.label") is False

    def test_is_launchd_job_loaded_error(self):
        """Should return False on error."""
        with patch("subprocess.run", side_effect=OSError("error")):
            assert watchdog.is_launchd_job_loaded("com.test.label") is False

    def test_load_launchd_job_success(self):
        """Should return True on successful load."""
        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = watchdog.load_launchd_job(Path("/tmp/test.plist"))
            assert result is True

    def test_load_launchd_job_failure(self):
        """Should return False on load failure."""
        mock_unload = MagicMock()
        mock_unload.returncode = 0
        mock_load = MagicMock()
        mock_load.returncode = 1

        with patch("subprocess.run", side_effect=[mock_unload, mock_load]):
            result = watchdog.load_launchd_job(Path("/tmp/test.plist"))
            assert result is False

    def test_load_launchd_job_error(self):
        """Should return False on error."""
        with patch("subprocess.run", side_effect=OSError("error")):
            result = watchdog.load_launchd_job(Path("/tmp/test.plist"))
            assert result is False

    def test_unload_launchd_job_success(self, temp_log_dir):
        """Should unload job and remove plist file."""
        plist_file = temp_log_dir / "test.plist"
        plist_file.write_text("<plist></plist>")

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = watchdog.unload_launchd_job(plist_file, "com.test.label")
            assert result is True
            assert not plist_file.exists()

    def test_unload_launchd_job_error(self):
        """Should return False on error."""
        with patch("subprocess.run", side_effect=OSError("error")):
            result = watchdog.unload_launchd_job(Path("/tmp/test.plist"), "com.test.label")
            assert result is False


class TestCmdInstallMultiplatform:
    """Tests for cmd_install with platform dispatch."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_install_macos(self, runner, mock_audit_log_file, temp_log_dir):
        """Should use launchd on macOS."""
        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "get_launch_agents_dir", return_value=temp_log_dir):
                with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                    with patch.object(watchdog, "load_launchd_job", return_value=True):
                        with patch.object(
                            watchdog, "get_executable_path", return_value="/usr/bin/nextdns-blocker"
                        ):
                            result = runner.invoke(watchdog.cmd_install)
                            assert result.exit_code == 0
                            assert "launchd" in result.output

    def test_cmd_install_linux(self, runner, mock_audit_log_file):
        """Should use cron on Linux."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        result = runner.invoke(watchdog.cmd_install)
                        assert result.exit_code == 0
                        assert "cron" in result.output


class TestCmdUninstallMultiplatform:
    """Tests for cmd_uninstall with platform dispatch."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_uninstall_macos(self, runner, mock_audit_log_file, temp_log_dir):
        """Should use launchd on macOS."""
        # Create plist files
        sync_plist = temp_log_dir / "com.nextdns-blocker.sync.plist"
        watchdog_plist = temp_log_dir / "com.nextdns-blocker.watchdog.plist"
        sync_plist.write_text("<plist></plist>")
        watchdog_plist.write_text("<plist></plist>")

        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "get_sync_plist_path", return_value=sync_plist):
                with patch.object(watchdog, "get_watchdog_plist_path", return_value=watchdog_plist):
                    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
                        result = runner.invoke(watchdog.cmd_uninstall)
                        assert result.exit_code == 0
                        assert "launchd" in result.output

    def test_cmd_uninstall_linux(self, runner, mock_audit_log_file):
        """Should use cron on Linux."""
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=""):
                    with patch.object(watchdog, "set_crontab", return_value=True):
                        result = runner.invoke(watchdog.cmd_uninstall)
                        assert result.exit_code == 0
                        assert "Cron" in result.output


class TestCmdStatusMultiplatform:
    """Tests for cmd_status with platform dispatch."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_status_macos(self, runner, mock_disabled_file):
        """Should show launchd status on macOS."""
        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "is_launchd_job_loaded", return_value=True):
                result = runner.invoke(watchdog.cmd_status)
                assert result.exit_code == 0
                assert "launchd" in result.output

    def test_cmd_status_linux(self, runner, mock_disabled_file):
        """Should show cron status on Linux."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    result = runner.invoke(watchdog.cmd_status)
                    assert result.exit_code == 0
                    assert "cron" in result.output


class TestCmdCheckMultiplatform:
    """Tests for cmd_check with platform dispatch."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_cmd_check_macos_all_loaded(self, runner, mock_disabled_file):
        """Should do nothing when launchd jobs are loaded."""
        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "is_launchd_job_loaded", return_value=True):
                result = runner.invoke(watchdog.cmd_check)
                assert result.exit_code == 0

    def test_cmd_check_linux_all_present(self, runner, mock_disabled_file):
        """Should do nothing when cron jobs are present."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"
        with patch.object(watchdog, "is_macos", return_value=False):
            with patch.object(watchdog, "is_windows", return_value=False):
                with patch.object(watchdog, "get_crontab", return_value=crontab):
                    result = runner.invoke(watchdog.cmd_check)
                    assert result.exit_code == 0


class TestGetExecutablePath:
    """Tests for get_executable_path function."""

    def test_get_executable_path_with_installed_binary(self):
        """Should return path when binary is found."""
        with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
            result = watchdog.get_executable_path()
            assert result == "/usr/local/bin/nextdns-blocker"

    def test_get_executable_path_fallback_to_module(self, tmp_path):
        """Should return python module invocation when binary not found anywhere."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.watchdog.Path.home", return_value=tmp_path):
                # Mock all paths as not existing to force module fallback
                with patch.object(Path, "exists", return_value=False):
                    result = watchdog.get_executable_path()
                    assert sys.executable in result
                    assert "-m nextdns_blocker" in result

    def test_get_executable_path_pipx_fallback(self, tmp_path):
        """Should use pipx executable when shutil.which fails but pipx exe exists."""
        # Create pipx executable location
        pipx_bin = tmp_path / ".local" / "bin"
        pipx_bin.mkdir(parents=True)
        pipx_exe = pipx_bin / "nextdns-blocker"
        pipx_exe.touch()

        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                with patch("nextdns_blocker.platform_utils.is_windows", return_value=False):
                    result = watchdog.get_executable_path()
                    assert result == str(pipx_exe)


class TestGetExecutableArgs:
    """Tests for get_executable_args function."""

    def test_get_executable_args_with_installed_binary(self):
        """Should return single-element list when binary is found."""
        with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
            result = watchdog.get_executable_args()
            assert result == ["/usr/local/bin/nextdns-blocker"]

    def test_get_executable_args_fallback_to_module(self, tmp_path):
        """Should return python module invocation when binary not found anywhere."""
        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.watchdog.Path.home", return_value=tmp_path):
                # Mock all paths as not existing to force module fallback
                with patch.object(Path, "exists", return_value=False):
                    result = watchdog.get_executable_args()
                    assert len(result) == 3
                    assert result[0] == sys.executable
                    assert result[1] == "-m"
                    assert result[2] == "nextdns_blocker"

    def test_get_executable_args_pipx_fallback(self, tmp_path):
        """Should use pipx executable when shutil.which fails but pipx exe exists."""
        # Create pipx executable location
        pipx_bin = tmp_path / ".local" / "bin"
        pipx_bin.mkdir(parents=True)
        pipx_exe = pipx_bin / "nextdns-blocker"
        pipx_exe.touch()

        with patch("shutil.which", return_value=None):
            with patch("nextdns_blocker.platform_utils.Path.home", return_value=tmp_path):
                with patch("nextdns_blocker.platform_utils.is_windows", return_value=False):
                    result = watchdog.get_executable_args()
                    assert result == [str(pipx_exe)]

    def test_get_executable_args_returns_list(self):
        """Should always return a list."""
        with patch("shutil.which", return_value="/some/path"):
            result = watchdog.get_executable_args()
            assert isinstance(result, list)


class TestWritePlistFile:
    """Tests for _write_plist_file function."""

    def test_write_plist_file_creates_file(self, temp_log_dir):
        """Should create file with content."""
        plist_file = temp_log_dir / "test.plist"
        content = b"<plist></plist>"

        result = watchdog._write_plist_file(plist_file, content)

        assert result is True
        assert plist_file.exists()
        assert plist_file.read_bytes() == content

    @skip_on_windows
    def test_write_plist_file_sets_permissions(self, temp_log_dir):
        """Should set file permissions to 0o644."""
        plist_file = temp_log_dir / "test.plist"
        content = b"<plist></plist>"

        watchdog._write_plist_file(plist_file, content)

        mode = plist_file.stat().st_mode & 0o777
        assert mode == 0o644

    def test_write_plist_file_returns_false_on_error(self, temp_log_dir):
        """Should return False when write fails."""
        # Try to write to a non-existent directory
        plist_file = temp_log_dir / "nonexistent" / "test.plist"

        result = watchdog._write_plist_file(plist_file, b"content")

        assert result is False


class TestGeneratePlistKeepAlive:
    """Tests for KeepAlive in generated plist."""

    def test_generate_plist_includes_keepalive(self):
        """Should include KeepAlive configuration."""
        import plistlib

        content = watchdog.generate_plist(
            label="test",
            program_args=["test"],
            start_interval=60,
            log_file=Path("/tmp/test.log"),
        )
        parsed = plistlib.loads(content)

        assert "KeepAlive" in parsed
        assert parsed["KeepAlive"] == {"SuccessfulExit": False}


class TestSafeUnlink:
    """Tests for _safe_unlink function."""

    def test_safe_unlink_removes_existing_file(self, temp_log_dir):
        """Should remove file when it exists."""
        test_file = temp_log_dir / "test.txt"
        test_file.write_text("content")

        watchdog._safe_unlink(test_file)

        assert not test_file.exists()

    def test_safe_unlink_handles_nonexistent_file(self, temp_log_dir):
        """Should not raise error for non-existent file."""
        test_file = temp_log_dir / "nonexistent.txt"

        # Should not raise
        watchdog._safe_unlink(test_file)

    def test_safe_unlink_handles_permission_error(self, temp_log_dir):
        """Should handle errors gracefully."""
        test_file = temp_log_dir / "test.txt"

        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "unlink", side_effect=OSError("Permission denied")):
                # Should not raise
                watchdog._safe_unlink(test_file)


class TestCreateSyncPlist:
    """Tests for _create_sync_plist function."""

    def test_create_sync_plist_success(self, temp_log_dir):
        """Should create sync plist file."""
        sync_plist = temp_log_dir / "com.nextdns-blocker.sync.plist"

        with patch.object(watchdog, "get_sync_plist_path", return_value=sync_plist):
            with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                result = watchdog._create_sync_plist()

        assert result is True
        assert sync_plist.exists()

    def test_create_sync_plist_correct_content(self, temp_log_dir):
        """Should create plist with correct label and args."""
        import plistlib

        sync_plist = temp_log_dir / "com.nextdns-blocker.sync.plist"

        with patch.object(watchdog, "get_sync_plist_path", return_value=sync_plist):
            with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                with patch.object(watchdog, "get_executable_args", return_value=["/usr/bin/test"]):
                    watchdog._create_sync_plist()

        parsed = plistlib.loads(sync_plist.read_bytes())
        assert parsed["Label"] == watchdog.LAUNCHD_SYNC_LABEL
        assert parsed["ProgramArguments"] == ["/usr/bin/test", "sync"]
        assert parsed["StartInterval"] == 120

    def test_create_sync_plist_failure(self, temp_log_dir):
        """Should return False when write fails."""
        sync_plist = temp_log_dir / "test.plist"

        with patch.object(watchdog, "get_sync_plist_path", return_value=sync_plist):
            with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                with patch.object(watchdog, "_write_plist_file", return_value=False):
                    result = watchdog._create_sync_plist()

        assert result is False


class TestCreateWatchdogPlist:
    """Tests for _create_watchdog_plist function."""

    def test_create_watchdog_plist_success(self, temp_log_dir):
        """Should create watchdog plist file."""
        watchdog_plist = temp_log_dir / "com.nextdns-blocker.watchdog.plist"

        with patch.object(watchdog, "get_watchdog_plist_path", return_value=watchdog_plist):
            with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                result = watchdog._create_watchdog_plist()

        assert result is True
        assert watchdog_plist.exists()

    def test_create_watchdog_plist_correct_content(self, temp_log_dir):
        """Should create plist with correct label and args."""
        import plistlib

        watchdog_plist = temp_log_dir / "com.nextdns-blocker.watchdog.plist"

        with patch.object(watchdog, "get_watchdog_plist_path", return_value=watchdog_plist):
            with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                with patch.object(watchdog, "get_executable_args", return_value=["/usr/bin/test"]):
                    watchdog._create_watchdog_plist()

        parsed = plistlib.loads(watchdog_plist.read_bytes())
        assert parsed["Label"] == watchdog.LAUNCHD_WATCHDOG_LABEL
        assert parsed["ProgramArguments"] == ["/usr/bin/test", "watchdog", "check"]
        assert parsed["StartInterval"] == 60

    def test_create_watchdog_plist_failure(self, temp_log_dir):
        """Should return False when write fails."""
        watchdog_plist = temp_log_dir / "test.plist"

        with patch.object(watchdog, "get_watchdog_plist_path", return_value=watchdog_plist):
            with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                with patch.object(watchdog, "_write_plist_file", return_value=False):
                    result = watchdog._create_watchdog_plist()

        assert result is False


class TestInstallLaunchdCleanup:
    """Tests for cleanup behavior in _install_launchd_jobs."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_install_unloads_sync_when_watchdog_fails(
        self, runner, mock_audit_log_file, temp_log_dir
    ):
        """Should unload sync job when watchdog load fails."""
        load_results = [True, False]  # sync succeeds, watchdog fails
        load_call_count = [0]

        def mock_load(plist_path):
            result = load_results[load_call_count[0]]
            load_call_count[0] += 1
            return result

        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "get_launch_agents_dir", return_value=temp_log_dir):
                with patch.object(watchdog, "get_log_dir", return_value=temp_log_dir):
                    with patch.object(watchdog, "load_launchd_job", side_effect=mock_load):
                        with patch("subprocess.run") as mock_run:
                            result = runner.invoke(watchdog.cmd_install)

                            # Should have called unload for sync
                            unload_calls = [
                                c for c in mock_run.call_args_list if "unload" in str(c)
                            ]
                            assert len(unload_calls) >= 1
                            assert result.exit_code == 1
                            assert "watchdog" in result.output


class TestUninstallLaunchdFeedback:
    """Tests for feedback in _uninstall_launchd_jobs."""

    @pytest.fixture
    def runner(self):
        """Create Click CLI test runner."""
        from click.testing import CliRunner

        return CliRunner()

    def test_uninstall_shows_warning_on_sync_failure(
        self, runner, mock_audit_log_file, temp_log_dir
    ):
        """Should show warning when sync unload fails."""
        sync_plist = temp_log_dir / "sync.plist"
        watchdog_plist = temp_log_dir / "watchdog.plist"
        sync_plist.write_text("<plist></plist>")
        watchdog_plist.write_text("<plist></plist>")

        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "get_sync_plist_path", return_value=sync_plist):
                with patch.object(watchdog, "get_watchdog_plist_path", return_value=watchdog_plist):
                    with patch.object(watchdog, "unload_launchd_job", side_effect=[False, True]):
                        result = runner.invoke(watchdog.cmd_uninstall)

                        assert "warning" in result.output
                        assert "sync" in result.output

    def test_uninstall_shows_warning_on_both_failure(
        self, runner, mock_audit_log_file, temp_log_dir
    ):
        """Should show warning when both unloads fail."""
        sync_plist = temp_log_dir / "sync.plist"
        watchdog_plist = temp_log_dir / "watchdog.plist"

        with patch.object(watchdog, "is_macos", return_value=True):
            with patch.object(watchdog, "get_sync_plist_path", return_value=sync_plist):
                with patch.object(watchdog, "get_watchdog_plist_path", return_value=watchdog_plist):
                    with patch.object(watchdog, "unload_launchd_job", return_value=False):
                        result = runner.invoke(watchdog.cmd_uninstall)

                        assert "warning" in result.output
                        assert "both" in result.output
