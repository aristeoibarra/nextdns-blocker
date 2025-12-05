"""Tests for watchdog.py - Cron watchdog functionality."""

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


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_disabled_file(temp_log_dir):
    """Mock the DISABLED_FILE path by patching the getter function."""
    disabled_file = temp_log_dir / ".watchdog_disabled"
    with patch.object(watchdog, "get_disabled_file", return_value=disabled_file):
        with patch.object(watchdog, "DISABLED_FILE", disabled_file):
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
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate = MagicMock()

        with patch("subprocess.Popen", return_value=mock_process):
            result = watchdog.set_crontab("*/5 * * * * job\n")
            assert result is True

    def test_set_crontab_failure(self):
        """Should return False on failure."""
        mock_process = MagicMock()
        mock_process.returncode = 1
        mock_process.communicate = MagicMock()

        with patch("subprocess.Popen", return_value=mock_process):
            result = watchdog.set_crontab("*/5 * * * * job\n")
            assert result is False

    def test_set_crontab_error(self):
        """Should return False on error."""
        with patch("subprocess.Popen", side_effect=OSError("error")):
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

        with patch.object(watchdog, "get_crontab", return_value=crontab):
            result = runner.invoke(watchdog.cmd_status)
            assert result.exit_code == 0
            assert "ok" in result.output
            assert "active" in result.output

    def test_cmd_status_missing_crons(self, runner, mock_disabled_file):
        """Should show missing status when cron jobs absent."""
        with patch.object(watchdog, "get_crontab", return_value=""):
            result = runner.invoke(watchdog.cmd_status)
            assert result.exit_code == 0
            assert "missing" in result.output
            assert "compromised" in result.output

    def test_cmd_status_disabled(self, runner, mock_disabled_file):
        """Should show disabled status when watchdog disabled."""
        mock_disabled_file.write_text("permanent")
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"

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
        with patch.object(watchdog, "get_crontab", return_value=""):
            with patch.object(watchdog, "set_crontab", return_value=True):
                result = runner.invoke(watchdog.cmd_install)
                assert result.exit_code == 0
                assert "cron installed" in result.output

    def test_cmd_install_failure(self, runner):
        """Should return error when cron install fails."""
        with patch.object(watchdog, "get_crontab", return_value=""):
            with patch.object(watchdog, "set_crontab", return_value=False):
                result = runner.invoke(watchdog.cmd_install)
                assert result.exit_code == 1
                assert "failed" in result.output

    def test_cmd_install_preserves_existing(self, runner, mock_audit_log_file):
        """Should preserve existing cron jobs."""
        existing_cron = "0 * * * * other_job\n"
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
        with patch.object(watchdog, "get_crontab", return_value=crontab):
            with patch.object(watchdog, "set_crontab", return_value=True):
                result = runner.invoke(watchdog.cmd_uninstall)
                assert result.exit_code == 0
                assert "removed" in result.output

    def test_cmd_uninstall_failure(self, runner):
        """Should return error when uninstall fails."""
        with patch.object(watchdog, "get_crontab", return_value=""):
            with patch.object(watchdog, "set_crontab", return_value=False):
                result = runner.invoke(watchdog.cmd_uninstall)
                assert result.exit_code == 1

    def test_cmd_uninstall_preserves_other_jobs(self, runner, mock_audit_log_file):
        """Should preserve non-blocker cron jobs."""
        crontab = "0 * * * * other_job\n*/2 * * * * nextdns-blocker sync\n"
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
        with patch.object(watchdog, "get_crontab", return_value=""):
            result = runner.invoke(watchdog.main, ["status"])
            assert result.exit_code == 0

    def test_main_check_command(self, runner, mock_disabled_file):
        """Should run check command."""
        crontab = "*/2 * * * * nextdns-blocker sync\n* * * * * nextdns-blocker watchdog check\n"
        with patch.object(watchdog, "get_crontab", return_value=crontab):
            result = runner.invoke(watchdog.main, ["check"])
            assert result.exit_code == 0

    def test_main_install_command(self, runner, mock_audit_log_file):
        """Should run install command."""
        with patch.object(watchdog, "get_crontab", return_value=""):
            with patch.object(watchdog, "set_crontab", return_value=True):
                result = runner.invoke(watchdog.main, ["install"])
                assert result.exit_code == 0

    def test_main_uninstall_command(self, runner, mock_audit_log_file):
        """Should run uninstall command."""
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
