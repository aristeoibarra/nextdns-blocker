"""Tests for CLI commands using Click CliRunner."""

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
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/test_profile/denylist/example.com",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "example.com", "schedule": null}], "allowlist": []}'
        )

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["unblock", "example.com", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "Unblocked" in result.output

    def test_unblock_invalid_domain(self, runner, mock_pause_file, tmp_path):
        """Test unblock command fails for invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
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
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")

        result = runner.invoke(main, ["sync", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Paused" in result.output or "paused" in result.output.lower()

    @responses.activate
    def test_sync_dry_run(self, runner, mock_pause_file, tmp_path):
        """Test sync with dry-run flag."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        result = runner.invoke(main, ["sync", "--dry-run", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "DRY RUN" in result.output

    @responses.activate
    def test_sync_verbose(self, runner, mock_pause_file, tmp_path):
        """Test sync with verbose flag."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": [{"id": "test.com", "active": True}]},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        result = runner.invoke(main, ["sync", "-v", "--config-dir", str(tmp_path)])
        assert result.exit_code == 0

    @responses.activate
    def test_sync_blocks_domain(self, runner, mock_pause_file, tmp_path):
        """Test sync blocks domains that should be blocked."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "block-me.com", "schedule": null}], "allowlist": []}'
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
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": [{"id": "example.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/allowlist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "example.com", "schedule": null}], "allowlist": []}'
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
                        "profile_id": "test_profile",
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


class TestHealthCommand:
    """Tests for health CLI command."""

    @responses.activate
    def test_health_all_ok(self, runner, mock_pause_file, tmp_path):
        """Test health command when everything is healthy."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

        with patch("nextdns_blocker.cli.get_log_dir", return_value=mock_pause_file.parent):
            result = runner.invoke(main, ["health", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "HEALTHY" in result.output

    @responses.activate
    def test_health_api_failure(self, runner, mock_pause_file, tmp_path):
        """Test health command when API fails."""
        responses.add(responses.GET, f"{API_URL}/profiles/test_profile/denylist", status=401)

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=bad_key\nNEXTDNS_PROFILE_ID=test_profile\n")
        domains_file = tmp_path / "domains.json"
        domains_file.write_text(
            '{"domains": [{"domain": "test.com", "schedule": null}], "allowlist": []}'
        )

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
        client = NextDNSClient("test_key", "test_profile")

        with pytest.raises(DomainValidationError):
            client.block("invalid domain!")

    @responses.activate
    def test_unblock_validates_domain(self):
        """Test that unblock method validates domain format."""
        client = NextDNSClient("test_key", "test_profile")

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


class TestSyncWithDomainsUrl:
    """Tests for sync command with --domains-url flag."""

    @responses.activate
    def test_sync_with_domains_url_flag(self, runner, mock_pause_file, tmp_path):
        """Test sync uses --domains-url flag to fetch remote domains."""
        remote_url = "https://example.com/domains.json"

        responses.add(
            responses.GET,
            remote_url,
            json={"domains": [{"domain": "remote.com"}], "allowlist": []},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/test_profile/denylist",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")

        with patch(
            "nextdns_blocker.config.get_domains_cache_file", return_value=tmp_path / "cache.json"
        ):
            result = runner.invoke(
                main,
                ["sync", "--config-dir", str(tmp_path), "--domains-url", remote_url, "--dry-run"],
            )

        assert result.exit_code == 0


class TestAllowCommand:
    """Tests for allow CLI command."""

    @responses.activate
    def test_allow_success(self, runner, mock_pause_file, tmp_path):
        """Test successful allow command."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/test_profile/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/test_profile/allowlist",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(main, ["allow", "aws.amazon.com", "--config-dir", str(tmp_path)])

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

    def test_allow_invalid_domain(self, runner, mock_pause_file, tmp_path):
        """Test allow with invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")

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
            f"{API_URL}/profiles/test_profile/allowlist",
            json={"data": [{"id": "aws.amazon.com", "active": True}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/test_profile/allowlist/aws.amazon.com",
            json={"success": True},
            status=200,
        )

        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")

        with patch("nextdns_blocker.cli.audit_log"):
            result = runner.invoke(
                main, ["disallow", "aws.amazon.com", "--config-dir", str(tmp_path)]
            )

        assert result.exit_code == 0
        assert "allowlist" in result.output.lower()

    def test_disallow_invalid_domain(self, runner, mock_pause_file, tmp_path):
        """Test disallow with invalid domain."""
        env_file = tmp_path / ".env"
        env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test_profile\n")

        result = runner.invoke(main, ["disallow", "invalid domain!", "--config-dir", str(tmp_path)])
        assert result.exit_code == 1
        assert "Invalid domain" in result.output
