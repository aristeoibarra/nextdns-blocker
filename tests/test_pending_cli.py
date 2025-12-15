"""Tests for pending CLI commands."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nextdns_blocker.pending_cli import pending_cli


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture
def pending_file(tmp_path: Path):
    """Create temporary pending file."""
    return tmp_path / "pending.json"


class TestPendingList:
    """Tests for pending list command."""

    def test_list_empty(self, runner: CliRunner, pending_file: Path):
        """List with no pending actions."""
        pending_file.write_text(json.dumps({"version": "1.0", "pending_actions": []}))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = runner.invoke(pending_cli, ["list"])
            assert result.exit_code == 0
            assert "No pending actions" in result.output

    def test_list_with_actions(self, runner: CliRunner, pending_file: Path):
        """List pending actions."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {
                    "id": "pnd_20251215_120000_abc123",
                    "domain": "example.com",
                    "delay": "4h",
                    "status": "pending",
                    "execute_at": execute_at,
                }
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = runner.invoke(pending_cli, ["list"])
            assert result.exit_code == 0
            assert "example.com" in result.output
            assert "4h" in result.output


class TestPendingShow:
    """Tests for pending show command."""

    def test_show_action(self, runner: CliRunner, pending_file: Path):
        """Show details of pending action."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        created_at = datetime.now().isoformat()
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {
                    "id": "pnd_20251215_120000_abc123",
                    "action": "unblock",
                    "domain": "example.com",
                    "delay": "4h",
                    "status": "pending",
                    "execute_at": execute_at,
                    "created_at": created_at,
                    "requested_by": "cli",
                }
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = runner.invoke(pending_cli, ["show", "abc123"])
            assert result.exit_code == 0
            assert "example.com" in result.output
            assert "4h" in result.output
            assert "pending" in result.output

    def test_show_not_found(self, runner: CliRunner, pending_file: Path):
        """Show non-existent action."""
        pending_file.write_text(json.dumps({"version": "1.0", "pending_actions": []}))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = runner.invoke(pending_cli, ["show", "nonexistent"])
            assert result.exit_code == 0
            assert "No action found" in result.output

    def test_show_partial_id_match(self, runner: CliRunner, pending_file: Path):
        """Show action using partial ID."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {
                    "id": "pnd_20251215_120000_abc123",
                    "action": "unblock",
                    "domain": "example.com",
                    "delay": "4h",
                    "status": "pending",
                    "execute_at": execute_at,
                    "created_at": datetime.now().isoformat(),
                }
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            # Using last 6 characters
            result = runner.invoke(pending_cli, ["show", "abc123"])
            assert result.exit_code == 0
            assert "example.com" in result.output


class TestPendingCancel:
    """Tests for pending cancel command."""

    def test_cancel_action_confirmed(self, runner: CliRunner, pending_file: Path):
        """Cancel action with confirmation."""
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {
                    "id": "pnd_20251215_120000_abc123",
                    "domain": "example.com",
                    "status": "pending",
                    "execute_at": (datetime.now() + timedelta(hours=2)).isoformat(),
                }
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with (
            patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file),
            patch("nextdns_blocker.pending.audit_log"),
            patch("nextdns_blocker.notifications.send_discord_notification"),
            patch("nextdns_blocker.config.load_config", return_value={}),
        ):
            result = runner.invoke(pending_cli, ["cancel", "abc123", "-y"])
            assert result.exit_code == 0
            assert "Cancelled" in result.output

    def test_cancel_action_not_found(self, runner: CliRunner, pending_file: Path):
        """Cancel non-existent action."""
        pending_file.write_text(json.dumps({"version": "1.0", "pending_actions": []}))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = runner.invoke(pending_cli, ["cancel", "nonexistent", "-y"])
            assert result.exit_code == 0
            assert "No pending action found" in result.output

    def test_cancel_action_declined(self, runner: CliRunner, pending_file: Path):
        """Cancel action declined by user."""
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {
                    "id": "pnd_20251215_120000_abc123",
                    "domain": "example.com",
                    "status": "pending",
                    "execute_at": (datetime.now() + timedelta(hours=2)).isoformat(),
                }
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = runner.invoke(pending_cli, ["cancel", "abc123"], input="n\n")
            assert result.exit_code == 0
            assert "Cancelled." in result.output

            # Verify action was not removed
            data = json.loads(pending_file.read_text())
            assert len(data["pending_actions"]) == 1
