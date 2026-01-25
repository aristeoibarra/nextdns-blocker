"""Tests for pending CLI commands with SQLite backend."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from nextdns_blocker import database as db
from nextdns_blocker.pending_cli import pending_cli


@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()


@pytest.fixture(autouse=True)
def use_temp_database(tmp_path: Path):
    """Use a temporary database for each test."""
    test_db_path = tmp_path / "test.db"

    # Patch the database path
    with patch.object(db, "get_db_path", return_value=test_db_path):
        # Clear thread-local connection
        if hasattr(db._local, "connection"):
            db._local.connection = None

        # Initialize fresh database
        db.init_database()

        yield

        # Close connection
        db.close_connection()


class TestPendingList:
    """Tests for pending list command."""

    def test_list_empty(self, runner: CliRunner):
        """List with no pending actions."""
        result = runner.invoke(pending_cli, ["list"])
        assert result.exit_code == 0
        assert "No pending actions" in result.output

    def test_list_with_actions(self, runner: CliRunner):
        """List pending actions."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        created_at = datetime.now().isoformat()

        # Create action directly in database
        db.add_pending_action(
            action_id="pnd_20251215_120000_abc123",
            action="unblock",
            domain="example.com",
            created_at=created_at,
            execute_at=execute_at,
            delay="4h",
            requested_by="cli",
        )

        result = runner.invoke(pending_cli, ["list"])
        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "4h" in result.output


class TestPendingShow:
    """Tests for pending show command."""

    def test_show_action(self, runner: CliRunner):
        """Show details of pending action."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        created_at = datetime.now().isoformat()

        db.add_pending_action(
            action_id="pnd_20251215_120000_abc123",
            action="unblock",
            domain="example.com",
            created_at=created_at,
            execute_at=execute_at,
            delay="4h",
            requested_by="cli",
        )

        result = runner.invoke(pending_cli, ["show", "abc123"])
        assert result.exit_code == 0
        assert "example.com" in result.output
        assert "4h" in result.output
        assert "pending" in result.output

    def test_show_not_found(self, runner: CliRunner):
        """Show non-existent action."""
        result = runner.invoke(pending_cli, ["show", "nonexistent"])
        assert result.exit_code == 0
        assert "No action found" in result.output

    def test_show_partial_id_match(self, runner: CliRunner):
        """Show action using partial ID."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        created_at = datetime.now().isoformat()

        db.add_pending_action(
            action_id="pnd_20251215_120000_abc123",
            action="unblock",
            domain="example.com",
            created_at=created_at,
            execute_at=execute_at,
            delay="4h",
            requested_by="cli",
        )

        # Using last 6 characters
        result = runner.invoke(pending_cli, ["show", "abc123"])
        assert result.exit_code == 0
        assert "example.com" in result.output


class TestPendingCancel:
    """Tests for pending cancel command."""

    def test_cancel_action_confirmed(self, runner: CliRunner):
        """Cancel action with confirmation."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        created_at = datetime.now().isoformat()

        db.add_pending_action(
            action_id="pnd_20251215_120000_abc123",
            action="unblock",
            domain="example.com",
            created_at=created_at,
            execute_at=execute_at,
            delay="4h",
            requested_by="cli",
        )

        with (
            patch("nextdns_blocker.pending.audit_log"),
            patch("nextdns_blocker.notifications.send_notification"),
            patch("nextdns_blocker.config.load_config", return_value={}),
        ):
            result = runner.invoke(pending_cli, ["cancel", "abc123", "-y"])
            assert result.exit_code == 0
            assert "Cancelled" in result.output

    def test_cancel_action_not_found(self, runner: CliRunner):
        """Cancel non-existent action."""
        result = runner.invoke(pending_cli, ["cancel", "nonexistent", "-y"])
        assert result.exit_code == 0
        assert "No pending action found" in result.output

    def test_cancel_action_declined(self, runner: CliRunner):
        """Cancel action declined by user."""
        execute_at = (datetime.now() + timedelta(hours=2)).isoformat()
        created_at = datetime.now().isoformat()

        db.add_pending_action(
            action_id="pnd_20251215_120000_abc123",
            action="unblock",
            domain="example.com",
            created_at=created_at,
            execute_at=execute_at,
            delay="4h",
            requested_by="cli",
        )

        result = runner.invoke(pending_cli, ["cancel", "abc123"], input="n\n")
        assert result.exit_code == 0
        assert "Cancelled." in result.output

        # Verify action was not removed
        actions = db.get_pending_actions()
        assert len(actions) == 1
