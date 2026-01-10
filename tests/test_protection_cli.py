"""Tests for protection CLI commands."""

import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from nextdns_blocker import protection_cli
from nextdns_blocker.protection_cli import protection


@pytest.fixture
def runner():
    """Create a CliRunner instance."""
    return CliRunner()


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config setup."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create env file
    env_file = config_dir / ".env"
    env_file.write_text("NEXTDNS_API_KEY=test\nNEXTDNS_PROFILE_ID=test123")

    # Create config.json
    config_json = config_dir / "config.json"
    config = {
        "nextdns": {
            "categories": [
                {"id": "porn", "locked": True},
                {"id": "gambling"},
            ],
            "services": [
                {"id": "tiktok", "locked": True},
            ],
        },
        "protection": {
            "unlock_delay_hours": 48,
            "auto_panic": {
                "enabled": True,
                "schedule": {"start": "23:00", "end": "06:00"},
            },
        },
    }
    config_json.write_text(json.dumps(config))

    return {
        "dir": config_dir,
        "env_file": env_file,
        "config_json": config_json,
        "config": config,
    }


class TestProtectionGroup:
    """Tests for protection command group."""

    def test_protection_help(self, runner):
        """Should show help for protection command."""
        result = runner.invoke(protection, ["--help"])
        assert result.exit_code == 0
        assert "addiction protection" in result.output.lower()


class TestProtectionStatus:
    """Tests for protection status command."""

    def test_status_shows_info(self, runner, mock_config, tmp_path):
        """Should show protection status."""
        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.return_value = {"script_dir": str(mock_config["dir"])}
            with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=False):
                with patch("nextdns_blocker.protection_cli.is_auto_panic_time", return_value=False):
                    with patch(
                        "nextdns_blocker.protection_cli.get_pending_unlock_requests",
                        return_value=[],
                    ):
                        result = runner.invoke(protection, ["status"])

        assert result.exit_code == 0
        assert "Protection Status" in result.output

    def test_status_shows_pin_enabled(self, runner, mock_config):
        """Should show PIN status when enabled."""
        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.return_value = {"script_dir": str(mock_config["dir"])}
            with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
                with patch(
                    "nextdns_blocker.protection_cli.is_pin_session_valid", return_value=True
                ):
                    with patch(
                        "nextdns_blocker.protection_cli.get_pin_session_remaining",
                        return_value="25m 30s",
                    ):
                        with patch(
                            "nextdns_blocker.protection_cli.is_auto_panic_time", return_value=False
                        ):
                            with patch(
                                "nextdns_blocker.protection_cli.get_pending_unlock_requests",
                                return_value=[],
                            ):
                                result = runner.invoke(protection, ["status"])

        assert result.exit_code == 0
        assert "enabled" in result.output

    def test_status_config_error(self, runner):
        """Should handle config error."""
        from nextdns_blocker.exceptions import ConfigurationError

        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.side_effect = ConfigurationError("Test error")
            result = runner.invoke(protection, ["status"])

        assert result.exit_code == 1
        assert "Config error" in result.output


class TestUnlockRequest:
    """Tests for unlock-request command."""

    def test_unlock_request_not_found(self, runner, mock_config):
        """Should error when item not found."""
        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.return_value = {"script_dir": str(mock_config["dir"])}
            result = runner.invoke(protection, ["unlock-request", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output

    def test_unlock_request_not_locked(self, runner, mock_config):
        """Should warn when item not locked."""
        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.return_value = {"script_dir": str(mock_config["dir"])}
            result = runner.invoke(protection, ["unlock-request", "gambling"])

        assert result.exit_code == 0
        assert "not locked" in result.output

    def test_unlock_request_already_pending(self, runner, mock_config):
        """Should warn when request already pending."""
        pending = [
            {
                "id": "abc123",
                "item_type": "category",
                "item_id": "porn",
                "execute_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            }
        ]
        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.return_value = {"script_dir": str(mock_config["dir"])}
            with patch(
                "nextdns_blocker.protection_cli.get_pending_unlock_requests",
                return_value=pending,
            ):
                result = runner.invoke(protection, ["unlock-request", "porn"])

        assert result.exit_code == 0
        assert "already pending" in result.output

    def test_unlock_request_creates_request(self, runner, mock_config):
        """Should create unlock request."""
        with patch("nextdns_blocker.protection_cli.load_config") as mock_load:
            mock_load.return_value = {"script_dir": str(mock_config["dir"])}
            with patch(
                "nextdns_blocker.protection_cli.get_pending_unlock_requests",
                return_value=[],
            ):
                with patch("nextdns_blocker.protection_cli.create_unlock_request") as mock_create:
                    mock_create.return_value = {
                        "id": "test123",
                        "execute_at": (datetime.now() + timedelta(hours=48)).isoformat(),
                    }
                    result = runner.invoke(protection, ["unlock-request", "porn"])

        assert result.exit_code == 0
        assert "created" in result.output
        mock_create.assert_called_once()


class TestCancelRequest:
    """Tests for cancel command."""

    def test_cancel_success(self, runner):
        """Should cancel request successfully."""
        with patch("nextdns_blocker.protection_cli.cancel_unlock_request", return_value=True):
            result = runner.invoke(protection, ["cancel", "abc123"])

        assert result.exit_code == 0
        assert "cancelled" in result.output

    def test_cancel_not_found(self, runner):
        """Should error when request not found."""
        with patch("nextdns_blocker.protection_cli.cancel_unlock_request", return_value=False):
            result = runner.invoke(protection, ["cancel", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.output


class TestListRequests:
    """Tests for list command."""

    def test_list_empty(self, runner):
        """Should show message when no pending requests."""
        with patch(
            "nextdns_blocker.protection_cli.get_pending_unlock_requests",
            return_value=[],
        ):
            result = runner.invoke(protection, ["list"])

        assert result.exit_code == 0
        assert "No pending" in result.output

    def test_list_with_requests(self, runner):
        """Should list pending requests."""
        pending = [
            {
                "id": "abc123",
                "item_type": "category",
                "item_id": "porn",
                "execute_at": (datetime.now() + timedelta(hours=24)).isoformat(),
            }
        ]
        with patch(
            "nextdns_blocker.protection_cli.get_pending_unlock_requests",
            return_value=pending,
        ):
            result = runner.invoke(protection, ["list"])

        assert result.exit_code == 0
        assert "abc123" in result.output
        assert "porn" in result.output


class TestPinGroup:
    """Tests for pin command group."""

    def test_pin_help(self, runner):
        """Should show help for pin command."""
        result = runner.invoke(protection, ["pin", "--help"])
        assert result.exit_code == 0
        assert "PIN protection" in result.output


class TestPinSet:
    """Tests for pin set command."""

    def test_pin_set_new(self, runner):
        """Should set new PIN when none exists."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=False):
            with patch("nextdns_blocker.protection_cli.set_pin") as mock_set:
                result = runner.invoke(protection, ["pin", "set"], input="1234\n1234\n")

        assert result.exit_code == 0
        assert "enabled" in result.output
        mock_set.assert_called_once_with("1234")

    def test_pin_set_requires_current(self, runner):
        """Should require current PIN when already set."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch("nextdns_blocker.protection_cli.verify_pin", return_value=False):
                with patch("nextdns_blocker.protection_cli.is_pin_locked_out", return_value=False):
                    with patch(
                        "nextdns_blocker.protection_cli.get_failed_attempts_count",
                        return_value=1,
                    ):
                        result = runner.invoke(protection, ["pin", "set"], input="wrong\n")

        assert result.exit_code == 1
        assert "Incorrect" in result.output

    def test_pin_set_too_short(self, runner):
        """Should error when PIN too short."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=False):
            with patch("nextdns_blocker.protection_cli.set_pin") as mock_set:
                mock_set.side_effect = ValueError("PIN must be at least 4 characters")
                result = runner.invoke(protection, ["pin", "set"], input="12\n12\n")

        assert result.exit_code == 1
        assert "Error" in result.output


class TestPinRemove:
    """Tests for pin remove command."""

    def test_pin_remove_not_enabled(self, runner):
        """Should show message when PIN not enabled."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=False):
            result = runner.invoke(protection, ["pin", "remove"])

        assert result.exit_code == 0
        assert "not enabled" in result.output

    def test_pin_remove_already_pending(self, runner):
        """Should show message when removal already pending."""
        pending = {
            "id": "abc123",
            "execute_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        }
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch(
                "nextdns_blocker.protection_cli.get_pin_removal_request", return_value=pending
            ):
                result = runner.invoke(protection, ["pin", "remove"])

        assert result.exit_code == 0
        assert "already pending" in result.output

    def test_pin_remove_success(self, runner):
        """Should create removal request."""
        pending = {
            "id": "abc123",
            "execute_at": (datetime.now() + timedelta(hours=24)).isoformat(),
        }
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch(
                "nextdns_blocker.protection_cli.get_pin_removal_request",
                side_effect=[None, pending],
            ):
                with patch("nextdns_blocker.protection_cli.is_pin_locked_out", return_value=False):
                    with patch("nextdns_blocker.protection_cli.remove_pin", return_value=True):
                        result = runner.invoke(protection, ["pin", "remove"], input="1234\n")

        assert result.exit_code == 0
        assert "scheduled" in result.output


class TestPinStatus:
    """Tests for pin status command."""

    def test_pin_status_not_enabled(self, runner):
        """Should show not enabled message."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=False):
            result = runner.invoke(protection, ["pin", "status"])

        assert result.exit_code == 0
        assert "not enabled" in result.output

    def test_pin_status_enabled_with_session(self, runner):
        """Should show session info when active."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch("nextdns_blocker.protection_cli.is_pin_session_valid", return_value=True):
                with patch(
                    "nextdns_blocker.protection_cli.get_pin_session_remaining",
                    return_value="25m 30s",
                ):
                    with patch(
                        "nextdns_blocker.protection_cli.is_pin_locked_out", return_value=False
                    ):
                        with patch(
                            "nextdns_blocker.protection_cli.get_failed_attempts_count",
                            return_value=0,
                        ):
                            with patch(
                                "nextdns_blocker.protection_cli.get_pin_removal_request",
                                return_value=None,
                            ):
                                result = runner.invoke(protection, ["pin", "status"])

        assert result.exit_code == 0
        assert "enabled" in result.output
        assert "active" in result.output

    def test_pin_status_locked_out(self, runner):
        """Should show lockout info."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch("nextdns_blocker.protection_cli.is_pin_session_valid", return_value=False):
                with patch("nextdns_blocker.protection_cli.is_pin_locked_out", return_value=True):
                    with patch(
                        "nextdns_blocker.protection_cli.get_lockout_remaining",
                        return_value="10m 30s",
                    ):
                        with patch(
                            "nextdns_blocker.protection_cli.get_pin_removal_request",
                            return_value=None,
                        ):
                            result = runner.invoke(protection, ["pin", "status"])

        assert result.exit_code == 0
        assert "LOCKED" in result.output


class TestPinVerify:
    """Tests for pin verify command."""

    def test_pin_verify_not_enabled(self, runner):
        """Should show message when PIN not enabled."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=False):
            result = runner.invoke(protection, ["pin", "verify"])

        assert result.exit_code == 0
        assert "not enabled" in result.output

    def test_pin_verify_locked_out(self, runner):
        """Should show lockout message."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch("nextdns_blocker.protection_cli.is_pin_locked_out", return_value=True):
                with patch(
                    "nextdns_blocker.protection_cli.get_lockout_remaining",
                    return_value="10m",
                ):
                    result = runner.invoke(protection, ["pin", "verify"])

        assert result.exit_code == 1
        assert "Locked out" in result.output

    def test_pin_verify_already_valid(self, runner):
        """Should show message when session already valid."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch("nextdns_blocker.protection_cli.is_pin_locked_out", return_value=False):
                with patch(
                    "nextdns_blocker.protection_cli.is_pin_session_valid", return_value=True
                ):
                    with patch(
                        "nextdns_blocker.protection_cli.get_pin_session_remaining",
                        return_value="25m",
                    ):
                        result = runner.invoke(protection, ["pin", "verify"])

        assert result.exit_code == 0
        assert "already active" in result.output

    def test_pin_verify_success(self, runner):
        """Should verify PIN successfully."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch("nextdns_blocker.protection_cli.is_pin_locked_out", return_value=False):
                with patch(
                    "nextdns_blocker.protection_cli.is_pin_session_valid", return_value=False
                ):
                    with patch("nextdns_blocker.protection_cli.verify_pin", return_value=True):
                        with patch(
                            "nextdns_blocker.protection_cli.get_pin_session_remaining",
                            return_value="30m 0s",
                        ):
                            result = runner.invoke(protection, ["pin", "verify"], input="1234\n")

        assert result.exit_code == 0
        assert "verified" in result.output

    def test_pin_verify_incorrect(self, runner):
        """Should show error for incorrect PIN."""
        with patch("nextdns_blocker.protection_cli.is_pin_enabled", return_value=True):
            with patch(
                "nextdns_blocker.protection_cli.is_pin_locked_out", side_effect=[False, False]
            ):
                with patch(
                    "nextdns_blocker.protection_cli.is_pin_session_valid", return_value=False
                ):
                    with patch("nextdns_blocker.protection_cli.verify_pin", return_value=False):
                        with patch(
                            "nextdns_blocker.protection_cli.get_failed_attempts_count",
                            return_value=1,
                        ):
                            result = runner.invoke(protection, ["pin", "verify"], input="wrong\n")

        assert result.exit_code == 1
        assert "Incorrect" in result.output


class TestRegisterProtection:
    """Tests for register_protection function."""

    def test_register_protection(self):
        """Should register protection command."""
        mock_group = MagicMock()
        protection_cli.register_protection(mock_group)
        mock_group.add_command.assert_called_once()
