"""Tests for CLI commands using Click CliRunner."""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import responses
from click.testing import CliRunner

from nextdns_blocker.cli import (
    clear_pause,
    get_pause_remaining,
    is_paused,
    main,
    set_pause,
)
from nextdns_blocker.client import API_URL, NextDNSClient
from nextdns_blocker.common import (
    audit_log,
    read_secure_file,
    write_secure_file,
)
from nextdns_blocker.exceptions import ConfigurationError, DomainValidationError

# Helper for skipping Unix-specific tests on Windows
is_windows = sys.platform == "win32"
skip_on_windows = pytest.mark.skipif(
    is_windows, reason="Unix permissions not applicable on Windows"
)


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_log_dir():
    """Create temporary log directory for pause file tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        yield log_dir


@pytest.fixture
def mock_pause_file(temp_log_dir):
    """Mock the pause file location by patching the getter function."""
    pause_file = temp_log_dir / ".paused"
    with patch("nextdns_blocker.cli.get_pause_file", return_value=pause_file):
        with patch("nextdns_blocker.cli.get_log_dir", return_value=temp_log_dir):
            yield pause_file


@pytest.fixture
def mock_client():
    """Create a mock NextDNS client."""
    return MagicMock(spec=NextDNSClient)


class TestPauseFunctions:
    """Tests for pause/resume functionality."""

    def test_is_paused_no_file(self, mock_pause_file):
        """Test is_paused returns False when no pause file exists."""
        assert is_paused() is False

    def test_is_paused_active(self, mock_pause_file):
        """Test is_paused returns True when pause is active."""
        future_time = datetime.now() + timedelta(minutes=30)
        mock_pause_file.write_text(future_time.isoformat())
        assert is_paused() is True

    def test_is_paused_expired(self, mock_pause_file):
        """Test is_paused returns False and cleans up when pause expired."""
        past_time = datetime.now() - timedelta(minutes=5)
        mock_pause_file.write_text(past_time.isoformat())
        assert is_paused() is False
        assert not mock_pause_file.exists()

    def test_get_pause_remaining_no_file(self, mock_pause_file):
        """Test get_pause_remaining returns None when no pause file."""
        assert get_pause_remaining() is None

    def test_get_pause_remaining_active(self, mock_pause_file):
        """Test get_pause_remaining returns time string when paused."""
        future_time = datetime.now() + timedelta(minutes=15)
        mock_pause_file.write_text(future_time.isoformat())
        remaining = get_pause_remaining()
        assert remaining is not None
        assert "min" in remaining

    def test_get_pause_remaining_less_than_minute(self, mock_pause_file):
        """Test get_pause_remaining shows '< 1 min' for short remaining time."""
        future_time = datetime.now() + timedelta(seconds=30)
        mock_pause_file.write_text(future_time.isoformat())
        remaining = get_pause_remaining()
        assert remaining == "< 1 min"

    def test_set_pause(self, mock_pause_file):
        """Test set_pause creates pause file correctly."""
        with patch("nextdns_blocker.cli.audit_log"):
            pause_until = set_pause(30)
        assert mock_pause_file.exists()
        assert pause_until > datetime.now()

    def test_clear_pause_when_paused(self, mock_pause_file):
        """Test clear_pause removes pause file."""
        future_time = datetime.now() + timedelta(minutes=30)
        mock_pause_file.write_text(future_time.isoformat())
        with patch("nextdns_blocker.cli.audit_log"):
            result = clear_pause()
        assert result is True
        assert not mock_pause_file.exists()

    def test_clear_pause_when_not_paused(self, mock_pause_file):
        """Test clear_pause returns False when not paused."""
        with patch("nextdns_blocker.cli.audit_log"):
            result = clear_pause()
        assert result is False


class TestPauseCommand:
    """Tests for pause CLI command."""

    def test_pause_default(self, runner, mock_pause_file):
        """Test pause command with default duration."""
        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["pause"])
        assert result.exit_code == 0
        assert "30 minutes" in result.output

    def test_pause_custom_duration(self, runner, mock_pause_file):
        """Test pause command with custom duration."""
        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["pause", "60"])
        assert result.exit_code == 0
        assert "60 minutes" in result.output

    def test_pause_invalid_minutes(self, runner):
        """Test pause with invalid minutes."""
        result = runner.invoke(main, ["pause", "abc"])
        assert result.exit_code == 2
        assert "not a valid integer" in result.output

    def test_pause_negative_minutes(self, runner):
        """Test pause with negative minutes."""
        result = runner.invoke(main, ["pause", "-5"])
        assert result.exit_code == 2


class TestResumeCommand:
    """Tests for resume CLI command."""

    def test_resume_when_paused(self, runner, mock_pause_file):
        """Test resume command when system is paused."""
        future_time = datetime.now() + timedelta(minutes=30)
        mock_pause_file.write_text(future_time.isoformat())
        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["resume"])
        assert result.exit_code == 0
        assert "resumed" in result.output

    def test_resume_when_not_paused(self, runner, mock_pause_file):
        """Test resume command when system is not paused."""
        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["resume"])
        assert result.exit_code == 0
        assert "not" in result.output.lower() and "paused" in result.output.lower()


class TestUnblockCommand:
    """Tests for unblock CLI command."""

    @responses.activate
    def test_unblock_success(self, runner, mock_pause_file, tmp_path):
        """Test successful unblock command."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/denylist/example.com",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com", "schedule": null}], "allowlist": []}'
        )

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["unblock", "example.com", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "Unblocked" in result.output

    def test_unblock_invalid_domain(self, runner, mock_pause_file, tmp_path):
        """Test unblock command fails for invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        result = runner.invoke(main, ["unblock", "invalid domain!", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Invalid domain" in result.output

    def test_unblock_no_domain(self, runner):
        """Test unblock without domain argument."""
        result = runner.invoke(main, ["unblock"])
        assert result.exit_code == 2
        assert "Missing argument" in result.output


class TestSyncCommand:
    """Tests for sync CLI command."""

    @responses.activate
    def test_sync_skips_when_paused(self, runner, mock_pause_file, tmp_path):
        """Test sync skips execution when paused."""
        future_time = datetime.now() + timedelta(minutes=30)
        mock_pause_file.write_text(future_time.isoformat())

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        result = runner.invoke(main, ["sync", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Paused" in result.output or "paused" in result.output.lower()

    @responses.activate
    def test_sync_dry_run(self, runner, mock_pause_file, tmp_path):
        """Test sync with dry-run flag."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        result = runner.invoke(main, ["sync", "--dry-run", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    @responses.activate
    def test_sync_verbose(self, runner, mock_pause_file, tmp_path):
        """Test sync with verbose flag."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "test.com", "active": True}]},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        result = runner.invoke(main, ["sync", "-v", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0

    @responses.activate
    def test_sync_blocks_domain(self, runner, mock_pause_file, tmp_path):
        """Test sync blocks domains that should be blocked."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "block-me.com", "schedule": null}], "allowlist": []}'
        )

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["sync", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0


class TestStatusCommand:
    """Tests for status CLI command."""

    @responses.activate
    def test_status_shows_domains(self, runner, mock_pause_file, tmp_path):
        """Test status command shows domains."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com", "schedule": null}], "allowlist": []}'
        )

        result = runner.invoke(main, ["status", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "example.com" in result.output

    def test_status_shows_pause_state(self, runner, mock_pause_file, tmp_path):
        """Test status command shows pause state."""
        future_time = datetime.now() + timedelta(minutes=30)
        mock_pause_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.cli.load_config") as mock_config:
            with patch("nextdns_blocker.cli.load_domains") as mock_domains:
                with patch("nextdns_blocker.cli.NextDNSClient") as mock_client_cls:
                    mock_config.return_value = {
                        "api_key": "test",
                        "profile_id": "testprofile",
                        "timeout": 10,
                        "retries": 3,
                        "timezone": "UTC",
                        "script_dir": str(tmp_path),
                    }
                    mock_domains.return_value = ([], [])
                    mock_client = MagicMock()
                    mock_client_cls.return_value = mock_client

                    result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "ACTIVE" in result.output or "Pause" in result.output

    def test_status_shows_scheduler_status_macos(self, runner, mock_pause_file, tmp_path):
        """Test status command shows scheduler status on macOS."""
        with patch("nextdns_blocker.cli.load_config") as mock_config:
            with patch("nextdns_blocker.cli.load_domains") as mock_domains:
                with patch("nextdns_blocker.cli.NextDNSClient") as mock_client_cls:
                    with patch("nextdns_blocker.cli.is_macos", return_value=True):
                        with patch("nextdns_blocker.cli.is_launchd_job_loaded", return_value=True):
                            mock_config.return_value = {
                                "api_key": "test",
                                "profile_id": "testprofile",
                                "timeout": 10,
                                "retries": 3,
                                "timezone": "UTC",
                                "script_dir": str(tmp_path),
                            }
                            mock_domains.return_value = ([], [])
                            mock_client = MagicMock()
                            mock_client_cls.return_value = mock_client

                            result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "Scheduler:" in result.output
        assert "sync:" in result.output
        assert "watchdog:" in result.output

    def test_status_shows_scheduler_not_running(self, runner, mock_pause_file, tmp_path):
        """Test status command shows scheduler not running."""
        with patch("nextdns_blocker.cli.load_config") as mock_config:
            with patch("nextdns_blocker.cli.load_domains") as mock_domains:
                with patch("nextdns_blocker.cli.NextDNSClient") as mock_client_cls:
                    with patch("nextdns_blocker.cli.is_macos", return_value=True):
                        with patch("nextdns_blocker.cli.is_launchd_job_loaded", return_value=False):
                            mock_config.return_value = {
                                "api_key": "test",
                                "profile_id": "testprofile",
                                "timeout": 10,
                                "retries": 3,
                                "timezone": "UTC",
                                "script_dir": str(tmp_path),
                            }
                            mock_domains.return_value = ([], [])
                            mock_client = MagicMock()
                            mock_client_cls.return_value = mock_client

                            result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert "NOT RUNNING" in result.output
        assert "watchdog install" in result.output


class TestHealthCommand:
    """Tests for health CLI command."""

    @patch("nextdns_blocker.cli.NextDNSClient")
    def test_health_all_ok(self, mock_client_cls, runner, mock_pause_file, tmp_path):
        """Test health command when everything is healthy."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        mock_client = mock_client_cls.return_value
        mock_client.get_denylist.return_value = []  # Successful API call

        with patch("nextdns_blocker.cli.get_log_dir", return_value=mock_pause_file.parent):
            result = runner.invoke(main, ["health", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "HEALTHY" in result.output

    @patch("nextdns_blocker.cli.NextDNSClient")
    def test_health_api_failure(self, mock_client_cls, runner, mock_pause_file, tmp_path):
        """Test health command when API fails."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=badkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        mock_client = mock_client_cls.return_value
        mock_client.get_denylist.return_value = None  # API failure

        with patch("nextdns_blocker.cli.get_log_dir", return_value=mock_pause_file.parent):
            result = runner.invoke(main, ["health", "--config-dir", str(tmp_path)])

        # API failure causes exit code 1
        assert result.exit_code == 1


class TestStatsCommand:
    """Tests for stats CLI command."""

    def test_stats_no_audit_file(self, runner, temp_log_dir):
        """Test stats with no audit log file."""
        with patch(
            "nextdns_blocker.cli.get_audit_log_file", return_value=temp_log_dir / "audit.log"
        ):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "Statistics" in result.output

    def test_stats_with_audit_data(self, runner, temp_log_dir):
        """Test stats with audit log data."""
        audit_file = temp_log_dir / "audit.log"
        audit_file.write_text(
            "2025-01-01 10:00:00 | BLOCK | example.com\n"
            "2025-01-01 11:00:00 | BLOCK | test.com\n"
            "2025-01-01 12:00:00 | UNBLOCK | example.com\n"
        )

        with patch("nextdns_blocker.cli.get_audit_log_file", return_value=audit_file):
            result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0
        assert "BLOCK" in result.output


class TestMainCLI:
    """Tests for main CLI entry point."""

    def test_main_no_args(self, runner):
        """Test main with no arguments prints usage."""
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output

    def test_main_unknown_command(self, runner):
        """Test main with unknown command."""
        result = runner.invoke(main, ["unknown"])
        assert result.exit_code == 2
        assert "No such command" in result.output

    def test_main_version(self, runner):
        """Test main with --version flag."""
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "nextdns-blocker" in result.output

    def test_main_config_error(self, runner):
        """Test main handles configuration error."""
        with patch("nextdns_blocker.cli.load_config") as mock_config:
            mock_config.side_effect = ConfigurationError("Missing API key")
            result = runner.invoke(main, ["status"])
        assert result.exit_code == 1
        assert "Missing API key" in result.output


class TestDomainValidationInClient:
    """Tests for domain validation in client methods."""

    @responses.activate
    def test_block_validates_domain(self):
        """Test that block method validates domain format."""
        client = NextDNSClient("testkey12345", "testprofile")

        with pytest.raises(DomainValidationError):
            client.block("invalid domain!")

    @responses.activate
    def test_unblock_validates_domain(self):
        """Test that unblock method validates domain format."""
        client = NextDNSClient("testkey12345", "testprofile")

        with pytest.raises(DomainValidationError):
            client.unblock("invalid domain!")


class TestAuditLog:
    """Tests for audit_log function."""

    def test_audit_log_creates_file(self, temp_log_dir):
        """Test audit_log creates log file if not exists."""
        audit_file = temp_log_dir / "audit.log"
        with patch("nextdns_blocker.common.get_audit_log_file", return_value=audit_file):
            with patch("nextdns_blocker.common.get_log_dir", return_value=temp_log_dir):
                audit_log("TEST_ACTION", "test detail")
        assert audit_file.exists()

    def test_audit_log_writes_entry(self, temp_log_dir):
        """Test audit_log writes correct format."""
        audit_file = temp_log_dir / "audit.log"
        with patch("nextdns_blocker.common.get_audit_log_file", return_value=audit_file):
            with patch("nextdns_blocker.common.get_log_dir", return_value=temp_log_dir):
                audit_log("BLOCK", "example.com")
        content = audit_file.read_text()
        assert "BLOCK" in content
        assert "example.com" in content


class TestWriteSecureFile:
    """Tests for write_secure_file function."""

    def test_write_secure_file_creates_file(self, temp_log_dir):
        """Test write_secure_file creates file with content."""
        test_file = temp_log_dir / "test.txt"
        write_secure_file(test_file, "test content")
        assert test_file.exists()
        assert test_file.read_text() == "test content"

    @skip_on_windows
    def test_write_secure_file_permissions(self, temp_log_dir):
        """Test write_secure_file sets secure permissions."""
        test_file = temp_log_dir / "test.txt"
        write_secure_file(test_file, "content")
        mode = test_file.stat().st_mode & 0o777
        assert mode == 0o600


class TestReadSecureFile:
    """Tests for read_secure_file function."""

    def test_read_secure_file_exists(self, temp_log_dir):
        """Test read_secure_file reads existing file."""
        test_file = temp_log_dir / "test.txt"
        test_file.write_text("  content  ")
        result = read_secure_file(test_file)
        assert result == "content"

    def test_read_secure_file_not_exists(self, temp_log_dir):
        """Test read_secure_file returns None for missing file."""
        test_file = temp_log_dir / "nonexistent.txt"
        result = read_secure_file(test_file)
        assert result is None


class TestAllowCommand:
    """Tests for allow CLI command."""

    @patch("nextdns_blocker.cli.NextDNSClient")
    @patch("nextdns_blocker.cli.audit_log")
    def test_allow_success(self, mock_audit, mock_client_cls, runner, mock_pause_file, tmp_path):
        """Test successful allow command."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        mock_client = mock_client_cls.return_value
        mock_client.is_blocked.return_value = False
        mock_client.allow.return_value = True

        result = runner.invoke(main, ["allow", "aws.amazon.com", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

    def test_allow_invalid_domain(self, runner, mock_pause_file, tmp_path):
        """Test allow with invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        result = runner.invoke(main, ["allow", "invalid domain!", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Invalid domain" in result.output


class TestDisallowCommand:
    """Tests for disallow CLI command."""

    @responses.activate
    def test_disallow_success(self, runner, mock_pause_file, tmp_path):
        """Test successful disallow command."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/allowlist/aws.amazon.com",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(
                main, ["disallow", "aws.amazon.com", "--config-dir", str(tmp_path)]
            )

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

    def test_disallow_invalid_domain(self, runner, mock_pause_file, tmp_path):
        """Test disallow with invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        result = runner.invoke(main, ["disallow", "invalid domain!", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Invalid domain" in result.output


class TestUpdateCommand:
    """Tests for update CLI command."""

    def test_update_help(self, runner):
        """Should show help for update command."""
        result = runner.invoke(main, ["update", "--help"])
        assert result.exit_code == 0
        assert "update" in result.output.lower()

    def test_update_already_latest(self, runner):
        """Should show message when already on latest version."""
        from nextdns_blocker import __version__

        mock_response = MagicMock()
        mock_response.read.return_value = f'{{"info": {{"version": "{__version__}"}}}}'.encode()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = runner.invoke(main, ["update"])

        assert result.exit_code == 0
        assert "already" in result.output.lower() or "latest" in result.output.lower()

    def test_update_new_version_available_decline(self, runner):
        """Should not upgrade when user declines."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "99.0.0"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            result = runner.invoke(main, ["update"], input="n\n")

        assert result.exit_code == 0
        assert "99.0.0" in result.output

    def test_update_new_version_with_yes_flag(self, runner):
        """Should skip confirmation with -y flag."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "99.0.0"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("subprocess.run", return_value=mock_subprocess):
                result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "99.0.0" in result.output

    def test_update_pypi_error(self, runner):
        """Should handle PyPI connection error."""
        import urllib.error

        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Network error"),
        ):
            result = runner.invoke(main, ["update"])

        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_update_pip_failure(self, runner):
        """Should handle pip upgrade failure."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "99.0.0"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 1
        mock_subprocess.stderr = "pip error"

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("subprocess.run", return_value=mock_subprocess):
                result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 1


class TestVerboseFlag:
    """Tests for verbose flag functionality."""

    def test_verbose_flag_exists(self, runner):
        """Should accept verbose flag."""
        result = runner.invoke(main, ["--help"])
        assert "-v" in result.output or "--verbose" in result.output


class TestSetupLogging:
    """Tests for setup_logging function."""

    def _cleanup_handlers(self, logger):
        """Close and remove all handlers to prevent Windows file locking issues."""
        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

    def test_setup_logging_verbose(self, temp_log_dir):
        """Should set DEBUG level when verbose=True."""
        import logging

        from nextdns_blocker.cli import setup_logging

        # Clear existing handlers
        root_logger = logging.getLogger()
        self._cleanup_handlers(root_logger)

        try:
            with patch("nextdns_blocker.cli.ensure_log_dir"):
                with patch(
                    "nextdns_blocker.cli.get_app_log_file",
                    return_value=temp_log_dir / "app.log",
                ):
                    setup_logging(verbose=True)

            assert root_logger.level == logging.DEBUG
        finally:
            self._cleanup_handlers(root_logger)

    def test_setup_logging_not_verbose(self, temp_log_dir):
        """Should set INFO level when verbose=False."""
        import logging

        from nextdns_blocker.cli import setup_logging

        # Clear existing handlers
        root_logger = logging.getLogger()
        self._cleanup_handlers(root_logger)

        try:
            with patch("nextdns_blocker.cli.ensure_log_dir"):
                with patch(
                    "nextdns_blocker.cli.get_app_log_file",
                    return_value=temp_log_dir / "app.log",
                ):
                    setup_logging(verbose=False)

            assert root_logger.level == logging.INFO
        finally:
            self._cleanup_handlers(root_logger)

    def test_setup_logging_no_duplicate_handlers(self, temp_log_dir):
        """Should not add duplicate handlers on multiple calls."""
        import logging

        from nextdns_blocker.cli import setup_logging

        # Clear existing handlers
        root_logger = logging.getLogger()
        self._cleanup_handlers(root_logger)

        try:
            with patch("nextdns_blocker.cli.ensure_log_dir"):
                with patch(
                    "nextdns_blocker.cli.get_app_log_file",
                    return_value=temp_log_dir / "app.log",
                ):
                    setup_logging(verbose=False)
                    initial_count = len(root_logger.handlers)
                    setup_logging(verbose=True)
                    final_count = len(root_logger.handlers)

            assert final_count == initial_count
        finally:
            self._cleanup_handlers(root_logger)


class TestPauseInfoEdgeCases:
    """Tests for _get_pause_info edge cases."""

    def test_pause_info_invalid_format(self, mock_pause_file):
        """Should return not paused for invalid date format."""
        mock_pause_file.write_text("invalid-date-format")
        assert is_paused() is False


class TestUpdateCommandEdgeCases:
    """Additional tests for update command edge cases."""

    def test_update_invalid_version_format(self, runner):
        """Should handle invalid version format gracefully."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "not.a.version.99"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("subprocess.run", return_value=mock_subprocess):
                result = runner.invoke(main, ["update", "-y"])

        # Should still work even with unusual version format
        assert result.exit_code == 0

    def test_update_subprocess_exception(self, runner):
        """Should handle subprocess exception during upgrade."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "99.0.0"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("subprocess.run", side_effect=OSError("subprocess error")):
                result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_update_uses_pipx_when_installed_via_pipx(self, runner, tmp_path):
        """Should use pipx upgrade when installed via pipx."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "99.0.0"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        # Create pipx venv directory to simulate pipx installation
        pipx_venv = tmp_path / ".local" / "pipx" / "venvs" / "nextdns-blocker"
        pipx_venv.mkdir(parents=True)

        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("nextdns_blocker.cli.Path.home", return_value=tmp_path):
                with patch("subprocess.run", return_value=mock_subprocess) as mock_run:
                    # Mock get_executable_path to return a non-homebrew path
                    with patch(
                        "nextdns_blocker.cli.get_executable_path",
                        return_value=str(pipx_venv / "bin" / "nextdns-blocker"),
                    ):
                        result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "pipx" in result.output.lower()
        # Verify pipx upgrade was called (search through all calls since detect_shell may call ps)
        pipx_call_found = False
        for call in mock_run.call_args_list:
            args = call[0][0] if call[0] else []
            if args and args[0] == "pipx" and args[1] == "upgrade":
                pipx_call_found = True
                break
        assert pipx_call_found, f"pipx upgrade not found in calls: {mock_run.call_args_list}"

    def test_update_uses_pip_when_not_pipx(self, runner, tmp_path):
        """Should use pip when not installed via pipx."""
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"info": {"version": "99.0.0"}}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        # tmp_path won't have pipx venv, so it should use pip
        with patch("urllib.request.urlopen", return_value=mock_response):
            with patch("nextdns_blocker.cli.Path.home", return_value=tmp_path):
                with patch("subprocess.run", return_value=mock_subprocess) as mock_run:
                    # Mock get_executable_path to return a non-homebrew path
                    with patch(
                        "nextdns_blocker.cli.get_executable_path",
                        return_value="/usr/local/bin/nextdns-blocker",
                    ):
                        result = runner.invoke(main, ["update", "-y"])

        assert result.exit_code == 0
        assert "pip" in result.output.lower()
        # Verify pip was called (search through all calls since detect_shell may call ps)
        pip_call_found = False
        for call in mock_run.call_args_list:
            args = call[0][0] if call[0] else []
            if args and "pip" in str(args):
                pip_call_found = True
                break
        assert pip_call_found, f"pip not found in calls: {mock_run.call_args_list}"


class TestStatsCommandEdgeCases:
    """Additional tests for stats command edge cases."""

    def test_stats_read_error(self, runner, temp_log_dir):
        """Should handle read error gracefully."""
        audit_file = temp_log_dir / "audit.log"

        # Create file then make it unreadable by simulating error
        with patch("nextdns_blocker.cli.get_audit_log_file", return_value=audit_file):
            with patch("builtins.open", side_effect=OSError("Permission denied")):
                result = runner.invoke(main, ["stats"])

        assert result.exit_code == 0


class TestFixCommand:
    """Tests for fix CLI command."""

    def test_fix_help(self, runner):
        """Should show help for fix command."""
        result = runner.invoke(main, ["fix", "--help"])
        assert result.exit_code == 0
        assert "Fix common issues" in result.output

    def test_fix_config_error(self, runner, tmp_path):
        """Should fail when config is missing."""
        with patch("nextdns_blocker.cli.load_config", side_effect=ConfigurationError("No config")):
            result = runner.invoke(main, ["fix"])

        assert result.exit_code == 1
        assert "FAILED" in result.output
        assert "init" in result.output

    def test_fix_success_pipx(self, runner, tmp_path):
        """Should complete successfully with pipx installation."""
        # Create pipx executable
        pipx_bin = tmp_path / ".local" / "bin"
        pipx_bin.mkdir(parents=True)
        pipx_exe = pipx_bin / "nextdns-blocker"
        pipx_exe.touch()

        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        with patch("nextdns_blocker.cli.load_config"):
            with patch("shutil.which", return_value=None):
                with patch("nextdns_blocker.cli.Path.home", return_value=tmp_path):
                    with patch("nextdns_blocker.cli.is_macos", return_value=True):
                        with patch("nextdns_blocker.cli.is_windows", return_value=False):
                            with patch(
                                "nextdns_blocker.platform_utils.is_windows", return_value=False
                            ):
                                with patch("subprocess.run", return_value=mock_subprocess):
                                    result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Fix complete" in result.output
        assert "pipx" in result.output

    def test_fix_success_system(self, runner, tmp_path):
        """Should complete successfully with system installation."""
        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 0

        with patch("nextdns_blocker.cli.load_config"):
            with patch("shutil.which", return_value="/usr/local/bin/nextdns-blocker"):
                with patch("nextdns_blocker.cli.is_macos", return_value=True):
                    with patch("subprocess.run", return_value=mock_subprocess):
                        result = runner.invoke(main, ["fix"])

        assert result.exit_code == 0
        assert "Fix complete" in result.output
        assert "system" in result.output

    def test_fix_scheduler_failure(self, runner, tmp_path):
        """Should fail when scheduler installation fails."""
        mock_subprocess = MagicMock()
        mock_subprocess.returncode = 1
        mock_subprocess.stderr = "install error"

        with patch("nextdns_blocker.cli.load_config"):
            with patch("shutil.which", return_value="/usr/bin/nextdns-blocker"):
                with patch("nextdns_blocker.cli.is_macos", return_value=True):
                    with patch("subprocess.run", return_value=mock_subprocess):
                        result = runner.invoke(main, ["fix"])

        assert result.exit_code == 1
        assert "Scheduler: FAILED" in result.output


class TestSyncCommandEdgeCases:
    """Additional tests for sync command edge cases."""

    @responses.activate
    def test_sync_sends_discord_notification(self, runner, mock_pause_file, tmp_path):
        """Should send Discord notification when configured."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )
        responses.add(
            responses.POST,
            "https://discord.com/api/webhooks/test",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text(
            "NEXTDNS_API_KEY=testkey12345\n"
            "NEXTDNS_PROFILE_ID=testprofile\n"
            "DISCORD_WEBHOOK=https://discord.com/api/webhooks/test\n"
        )
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["sync", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0


class TestHealthCommandEdgeCases:
    """Additional tests for health command edge cases."""

    def test_health_config_error(self, runner, mock_pause_file, tmp_path):
        """Should handle configuration error."""
        # Missing .env file
        result = runner.invoke(main, ["health", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1

    @patch("nextdns_blocker.cli.NextDNSClient")
    def test_health_missing_domains_file(self, mock_client_cls, runner, mock_pause_file, tmp_path):
        """Should show warning for missing config.json."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        # No config.json file

        mock_client = mock_client_cls.return_value
        mock_client.get_denylist.return_value = []

        with patch("nextdns_blocker.cli.get_log_dir", return_value=mock_pause_file.parent):
            result = runner.invoke(main, ["health", "--config-dir", str(tmp_path)])

        # Should fail due to missing config.json
        assert result.exit_code == 1


class TestStatusCommandEdgeCases:
    """Additional tests for status command edge cases."""

    def test_status_config_error(self, runner, mock_pause_file, tmp_path):
        """Should handle configuration error."""
        result = runner.invoke(main, ["status", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1

    @responses.activate
    def test_status_with_protected_domains(self, runner, mock_pause_file, tmp_path):
        """Should show protected domains in status."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": [{"id": "protected.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/allowlist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")
        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "protected.com", "protected": true}], "allowlist": []}'
        )

        result = runner.invoke(main, ["status", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "protected.com" in result.output


class TestValidateCommand:
    """Tests for validate CLI command."""

    def test_validate_valid_config(self, runner, tmp_path):
        """Should validate a correct configuration successfully."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com"}, {"domain": "test.org"}], "allowlist": []}'
        )

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "Configuration OK" in result.output
        assert "2 domains" in result.output

    def test_validate_with_protected_domains(self, runner, tmp_path):
        """Should count protected domains."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com", "protected": true}, '
            '{"domain": "test.org", "protected": true}], "allowlist": []}'
        )

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "2 protected" in result.output

    def test_validate_with_allowlist(self, runner, tmp_path):
        """Should count allowlist entries."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com"}], '
            '"allowlist": [{"domain": "allowed.com"}, {"domain": "safe.org"}]}'
        )

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "2 entries" in result.output

    def test_validate_with_schedules(self, runner, tmp_path):
        """Should validate and count schedules."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com", "schedule": {'
            '"available_hours": [{"days": ["monday"], "time_ranges": [{"start": "09:00", "end": "17:00"}]}]'
            "}}]}"
        )

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "schedule" in result.output.lower()

    def test_validate_missing_domains_file(self, runner, tmp_path):
        """Should fail when config.json is missing."""
        # No config.json file created

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "not found" in result.output.lower() or "failed" in result.output.lower()

    def test_validate_invalid_json(self, runner, tmp_path):
        """Should fail on invalid JSON syntax."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text("{invalid json}")

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "invalid" in result.output.lower() or "error" in result.output.lower()

    def test_validate_invalid_domain_format(self, runner, tmp_path):
        """Should fail on invalid domain format."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text('{"blocklist": [{"domain": "invalid domain.com"}]}')

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "invalid" in result.output.lower()

    def test_validate_invalid_schedule_time(self, runner, tmp_path):
        """Should fail on invalid schedule time format."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com", "schedule": {'
            '"available_hours": [{"days": ["monday"], "time_ranges": [{"start": "25:00", "end": "17:00"}]}]'
            "}}]}"
        )

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "invalid" in result.output.lower() or "error" in result.output.lower()

    def test_validate_denylist_allowlist_conflict(self, runner, tmp_path):
        """Should fail when domain is in both denylist and allowlist."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text(
            '{"blocklist": [{"domain": "example.com"}], "allowlist": [{"domain": "example.com"}]}'
        )

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "conflict" in result.output.lower() or "both" in result.output.lower()

    def test_validate_json_output(self, runner, tmp_path):
        """Should output JSON when --json flag is used."""
        import json

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text('{"blocklist": [{"domain": "example.com"}], "allowlist": []}')

        result = runner.invoke(main, ["validate", "--json", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        # Should be valid JSON
        output = json.loads(result.output)
        assert output["valid"] is True
        assert "checks" in output
        assert "summary" in output

    def test_validate_json_output_with_errors(self, runner, tmp_path):
        """Should output JSON with errors when validation fails."""
        import json

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text('{"blocklist": [{"domain": "invalid domain"}]}')

        result = runner.invoke(main, ["validate", "--json", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        output = json.loads(result.output)
        assert output["valid"] is False
        assert len(output["errors"]) > 0

    def test_validate_empty_domains(self, runner, tmp_path):
        """Should fail when no domains are configured."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=testkey12345\nNEXTDNS_PROFILE_ID=testprofile\n")

        domains_file = tmp_path / "config.json"
        domains_file.write_text('{"blocklist": []}')

        result = runner.invoke(main, ["validate", "--config-dir", str(tmp_path)])

        assert result.exit_code == 1
        assert "no domains" in result.output.lower()


class TestUninstallCommand:
    """Tests for the uninstall command."""

    def test_uninstall_help(self, runner):
        """Test that uninstall --help works."""
        result = runner.invoke(main, ["uninstall", "--help"])
        assert result.exit_code == 0
        assert "Completely remove NextDNS Blocker" in result.output
        assert "--yes" in result.output

    def test_uninstall_cancelled(self, runner):
        """Test that uninstall can be cancelled."""
        result = runner.invoke(main, ["uninstall"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    @patch("nextdns_blocker.watchdog._uninstall_launchd_jobs")
    @patch("nextdns_blocker.cli.is_macos", return_value=True)
    @patch("nextdns_blocker.config.get_data_dir")
    @patch("nextdns_blocker.config.get_config_dir")
    def test_uninstall_macos(
        self, mock_config_dir, mock_data_dir, mock_is_macos, mock_uninstall, runner, tmp_path
    ):
        """Test uninstall on macOS."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / ".env").write_text("TEST=1")

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        (data_dir / "logs").mkdir()

        mock_config_dir.return_value = config_dir
        mock_data_dir.return_value = data_dir

        result = runner.invoke(main, ["uninstall", "-y"])

        assert result.exit_code == 0
        assert "complete" in result.output.lower()
        mock_uninstall.assert_called_once()
        assert not config_dir.exists()
        assert not data_dir.exists()

    @patch("nextdns_blocker.watchdog._uninstall_windows_tasks")
    @patch("nextdns_blocker.cli.is_windows", return_value=True)
    @patch("nextdns_blocker.cli.is_macos", return_value=False)
    @patch("nextdns_blocker.config.get_data_dir")
    @patch("nextdns_blocker.config.get_config_dir")
    def test_uninstall_windows(
        self,
        mock_config_dir,
        mock_data_dir,
        mock_is_macos,
        mock_is_windows,
        mock_uninstall,
        runner,
        tmp_path,
    ):
        """Test uninstall on Windows."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / ".env").write_text("TEST=1")

        mock_config_dir.return_value = config_dir
        mock_data_dir.return_value = config_dir  # Same dir on Windows

        result = runner.invoke(main, ["uninstall", "-y"])

        assert result.exit_code == 0
        assert "complete" in result.output.lower()
        mock_uninstall.assert_called_once()

    @patch("nextdns_blocker.watchdog._uninstall_cron_jobs")
    @patch("nextdns_blocker.cli.is_windows", return_value=False)
    @patch("nextdns_blocker.cli.is_macos", return_value=False)
    @patch("nextdns_blocker.config.get_data_dir")
    @patch("nextdns_blocker.config.get_config_dir")
    def test_uninstall_linux(
        self,
        mock_config_dir,
        mock_data_dir,
        mock_is_macos,
        mock_is_windows,
        mock_uninstall,
        runner,
        tmp_path,
    ):
        """Test uninstall on Linux."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        mock_config_dir.return_value = config_dir
        mock_data_dir.return_value = data_dir

        result = runner.invoke(main, ["uninstall", "-y"])

        assert result.exit_code == 0
        assert "complete" in result.output.lower()
        mock_uninstall.assert_called_once()
        assert not config_dir.exists()
        assert not data_dir.exists()

    @patch("nextdns_blocker.watchdog._uninstall_launchd_jobs")
    @patch("nextdns_blocker.cli.is_macos", return_value=True)
    @patch("nextdns_blocker.config.get_data_dir")
    @patch("nextdns_blocker.config.get_config_dir")
    def test_uninstall_already_removed(
        self, mock_config_dir, mock_data_dir, mock_is_macos, mock_uninstall, runner, tmp_path
    ):
        """Test uninstall when directories already removed."""
        config_dir = tmp_path / "nonexistent_config"
        data_dir = tmp_path / "nonexistent_data"

        mock_config_dir.return_value = config_dir
        mock_data_dir.return_value = data_dir

        result = runner.invoke(main, ["uninstall", "-y"])

        assert result.exit_code == 0
        assert "Already removed" in result.output

    @patch("nextdns_blocker.watchdog._uninstall_launchd_jobs", side_effect=OSError("Job error"))
    @patch("nextdns_blocker.cli.is_macos", return_value=True)
    @patch("nextdns_blocker.config.get_data_dir")
    @patch("nextdns_blocker.config.get_config_dir")
    def test_uninstall_watchdog_error_continues(
        self, mock_config_dir, mock_data_dir, mock_is_macos, mock_uninstall, runner, tmp_path
    ):
        """Test uninstall continues even if watchdog uninstall fails."""
        config_dir = tmp_path / "config"
        config_dir.mkdir()

        mock_config_dir.return_value = config_dir
        mock_data_dir.return_value = config_dir

        result = runner.invoke(main, ["uninstall", "-y"])

        assert result.exit_code == 0
        assert "Warning" in result.output
        assert "complete" in result.output.lower()
