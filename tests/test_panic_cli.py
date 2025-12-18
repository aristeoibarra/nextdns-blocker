"""Tests for panic mode CLI commands using Click CliRunner."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nextdns_blocker.panic_cli import panic_cli


@pytest.fixture
def runner():
    """Create Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_panic_dir():
    """Create temporary directory for panic file tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        yield log_dir


@pytest.fixture
def mock_panic_file(temp_panic_dir):
    """Mock the panic file location."""
    panic_file = temp_panic_dir / ".panic"
    with (
        patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
        patch("nextdns_blocker.panic.get_log_dir", return_value=temp_panic_dir),
        patch("nextdns_blocker.panic_cli.is_panic_mode") as mock_is_panic,
        patch("nextdns_blocker.panic_cli.get_panic_remaining") as mock_remaining,
        patch("nextdns_blocker.panic_cli.get_panic_until") as mock_until,
    ):
        mock_is_panic.return_value = False
        mock_remaining.return_value = None
        mock_until.return_value = None
        yield panic_file


class TestPanicActivation:
    """Tests for panic mode activation."""

    def test_panic_help(self, runner):
        """Should show help when no arguments."""
        result = runner.invoke(panic_cli)
        assert result.exit_code == 0
        assert "Emergency lockdown mode" in result.output

    def test_panic_activate_success(self, runner, temp_panic_dir):
        """Should activate panic mode with valid duration using registered command."""
        panic_file = temp_panic_dir / ".panic"

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=temp_panic_dir),
            patch("nextdns_blocker.panic.audit_log"),
            patch("nextdns_blocker.panic_cli._block_all_domains", return_value=0),
        ):
            result = runner.invoke(panic_cli, ["2h"])
            assert result.exit_code == 0
            assert "PANIC MODE ACTIVATED" in result.output

    def test_panic_activate_with_activate_command(self, runner, temp_panic_dir):
        """Should activate panic mode using 'activate' subcommand."""
        panic_file = temp_panic_dir / ".panic"

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=temp_panic_dir),
            patch("nextdns_blocker.panic.audit_log"),
            patch("nextdns_blocker.panic_cli._block_all_domains", return_value=0),
        ):
            result = runner.invoke(panic_cli, ["activate", "2h"])
            assert result.exit_code == 0
            assert "PANIC MODE ACTIVATED" in result.output

    def test_panic_activate_minimum_duration_error(self, runner, temp_panic_dir):
        """Should reject duration below minimum."""
        panic_file = temp_panic_dir / ".panic"

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=temp_panic_dir),
        ):
            # Use activate subcommand for custom durations
            result = runner.invoke(panic_cli, ["activate", "5m"])
            assert result.exit_code == 1
            assert "Minimum duration" in result.output

    def test_panic_activate_invalid_duration_format(self, runner):
        """Should reject invalid duration format."""
        # Invalid durations go to Click's error handling
        result = runner.invoke(panic_cli, ["activate", "invalid"])
        assert result.exit_code == 1
        assert "Invalid duration format" in result.output


class TestPanicStatus:
    """Tests for panic status command."""

    def test_panic_status_inactive(self, runner, temp_panic_dir):
        """Should show not active when panic not active."""
        panic_file = temp_panic_dir / ".panic"

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            result = runner.invoke(panic_cli, ["status"])
            assert result.exit_code == 0
            assert "not active" in result.output

    def test_panic_status_active(self, runner, temp_panic_dir):
        """Should show status when panic active."""
        panic_file = temp_panic_dir / ".panic"
        future_time = datetime.now() + timedelta(hours=2)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            result = runner.invoke(panic_cli, ["status"])
            assert result.exit_code == 0
            assert "PANIC MODE ACTIVE" in result.output


class TestPanicExtend:
    """Tests for panic extend command."""

    def test_panic_extend_not_active(self, runner, temp_panic_dir):
        """Should error when trying to extend inactive panic."""
        panic_file = temp_panic_dir / ".panic"

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic_cli.is_panic_mode", return_value=False),
        ):
            result = runner.invoke(panic_cli, ["extend", "30m"])
            assert result.exit_code == 1
            assert "not active" in result.output

    def test_panic_extend_success(self, runner, temp_panic_dir):
        """Should extend panic when active."""
        panic_file = temp_panic_dir / ".panic"
        future_time = datetime.now() + timedelta(hours=1)
        panic_file.write_text(future_time.isoformat())

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=temp_panic_dir),
            patch("nextdns_blocker.panic.audit_log"),
            patch("nextdns_blocker.panic_cli.is_panic_mode", return_value=True),
            patch(
                "nextdns_blocker.panic_cli.extend_panic",
                return_value=future_time + timedelta(minutes=30),
            ),
            patch("nextdns_blocker.panic_cli.get_panic_remaining", return_value="1h 30m"),
        ):
            result = runner.invoke(panic_cli, ["extend", "30m"])
            assert result.exit_code == 0
            assert "extended" in result.output


class TestPanicReactivation:
    """Tests for panic reactivation behavior."""

    def test_panic_reactivate_longer_extends(self, runner, temp_panic_dir):
        """Should extend when reactivating with longer duration."""
        panic_file = temp_panic_dir / ".panic"
        # Set panic to expire in 30 minutes
        future_time = datetime.now() + timedelta(minutes=30)
        panic_file.write_text(future_time.isoformat())

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=temp_panic_dir),
            patch("nextdns_blocker.panic.audit_log"),
        ):
            # Try to activate for 2 hours (longer than 30 minutes remaining)
            result = runner.invoke(panic_cli, ["2h"])
            assert result.exit_code == 0
            assert "EXTENDED" in result.output

    def test_panic_reactivate_shorter_fails(self, runner, temp_panic_dir):
        """Should fail when reactivating with shorter duration."""
        panic_file = temp_panic_dir / ".panic"
        # Set panic to expire in 2 hours
        future_time = datetime.now() + timedelta(hours=2)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            # Try to activate for 30 minutes (shorter than 2 hours remaining)
            result = runner.invoke(panic_cli, ["30m"])
            assert result.exit_code == 1
            assert "extend" in result.output.lower()


class TestBlockAllDomains:
    """Tests for _block_all_domains helper."""

    def test_block_all_domains_success(self, temp_panic_dir):
        """Should block all unblocked domains."""
        from nextdns_blocker.panic_cli import _block_all_domains

        mock_client = MagicMock()
        mock_client.is_blocked.return_value = False
        mock_client.block.return_value = True

        mock_config = {
            "api_key": "test",
            "profile_id": "test",
            "timeout": 10,
            "retries": 3,
            "script_dir": temp_panic_dir,
            "discord_webhook_url": None,
        }

        domains = [
            {"domain": "example.com"},
            {"domain": "test.com"},
        ]

        # Patch at the source modules where imports happen
        with (
            patch("nextdns_blocker.config.load_config", return_value=mock_config),
            patch("nextdns_blocker.config.load_domains", return_value=(domains, [])),
            patch("nextdns_blocker.client.NextDNSClient", return_value=mock_client),
            patch("nextdns_blocker.common.audit_log"),
            patch("nextdns_blocker.notifications.send_discord_notification"),
        ):
            count = _block_all_domains()
            assert count == 2
            assert mock_client.block.call_count == 2

    def test_block_all_domains_already_blocked(self, temp_panic_dir):
        """Should not block already blocked domains."""
        from nextdns_blocker.panic_cli import _block_all_domains

        mock_client = MagicMock()
        mock_client.is_blocked.return_value = True  # Already blocked

        mock_config = {
            "api_key": "test",
            "profile_id": "test",
            "timeout": 10,
            "retries": 3,
            "script_dir": temp_panic_dir,
            "discord_webhook_url": None,
        }

        domains = [{"domain": "example.com"}]

        # Patch at the source modules where imports happen
        with (
            patch("nextdns_blocker.config.load_config", return_value=mock_config),
            patch("nextdns_blocker.config.load_domains", return_value=(domains, [])),
            patch("nextdns_blocker.client.NextDNSClient", return_value=mock_client),
        ):
            count = _block_all_domains()
            assert count == 0
            mock_client.block.assert_not_called()
