"""Tests for pending action module with SQLite backend."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from nextdns_blocker import database as db
from nextdns_blocker.pending import (
    cancel_pending_action,
    cleanup_old_actions,
    create_pending_action,
    generate_action_id,
    get_pending_actions,
    get_pending_for_domain,
    get_ready_actions,
    mark_action_executed,
)


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


class TestGenerateActionId:
    """Tests for generate_action_id function."""

    def test_format(self):
        """Action ID should match expected format."""
        action_id = generate_action_id()
        assert action_id.startswith("pnd_")
        parts = action_id.split("_")
        assert len(parts) == 4
        # pnd, date, time, random
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 6  # random suffix

    def test_uniqueness(self):
        """Generated IDs should be unique."""
        ids = [generate_action_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestCreatePendingAction:
    """Tests for create_pending_action function."""

    def test_create_action_with_delay(self):
        """Creating action with valid delay."""
        with patch("nextdns_blocker.pending.audit_log"):
            action = create_pending_action("example.com", "4h", "cli")
            assert action is not None
            assert action["domain"] == "example.com"
            assert action["delay"] == "4h"
            assert action["status"] == "pending"
            assert action["requested_by"] == "cli"
            assert action["id"].startswith("pnd_")

    def test_create_action_never_returns_none(self):
        """Creating action with 'never' delay returns None."""
        action = create_pending_action("example.com", "never", "cli")
        assert action is None

    def test_create_action_invalid_delay(self):
        """Creating action with invalid delay returns None."""
        action = create_pending_action("example.com", "invalid", "cli")
        assert action is None

    def test_create_duplicate_returns_existing(self):
        """Creating duplicate action returns existing one."""
        with patch("nextdns_blocker.pending.audit_log"):
            action1 = create_pending_action("example.com", "4h", "cli")
            action2 = create_pending_action("example.com", "24h", "cli")
            assert action1["id"] == action2["id"]

    def test_execute_at_calculated_correctly(self):
        """Execute time is calculated correctly based on delay."""
        with patch("nextdns_blocker.pending.audit_log"):
            before = datetime.now()
            action = create_pending_action("example.com", "30m", "cli")
            after = datetime.now()

            execute_at = datetime.fromisoformat(action["execute_at"])
            expected_min = before + timedelta(minutes=30)
            expected_max = after + timedelta(minutes=30)

            assert expected_min <= execute_at <= expected_max


class TestGetPendingActions:
    """Tests for get_pending_actions function."""

    def test_get_all_actions(self):
        """Get all pending actions."""
        with patch("nextdns_blocker.pending.audit_log"):
            create_pending_action("a.com", "4h", "cli")
            create_pending_action("b.com", "4h", "cli")

            actions = get_pending_actions()
            assert len(actions) == 2

    def test_filter_by_status(self):
        """Filter actions by status."""
        with patch("nextdns_blocker.pending.audit_log"):
            action = create_pending_action("a.com", "4h", "cli")
            mark_action_executed(action["id"])

            create_pending_action("b.com", "4h", "cli")

            pending = get_pending_actions(status="pending")
            assert len(pending) == 1
            assert pending[0]["domain"] == "b.com"


class TestGetPendingForDomain:
    """Tests for get_pending_for_domain function."""

    def test_find_existing_domain(self):
        """Find pending action for domain."""
        with patch("nextdns_blocker.pending.audit_log"):
            created = create_pending_action("example.com", "4h", "cli")
            action = get_pending_for_domain("example.com")
            assert action is not None
            assert action["id"] == created["id"]

    def test_domain_not_found(self):
        """Return None for non-existent domain."""
        action = get_pending_for_domain("example.com")
        assert action is None


class TestCancelPendingAction:
    """Tests for cancel_pending_action function."""

    def test_cancel_existing_action(self):
        """Cancel existing pending action."""
        with patch("nextdns_blocker.pending.audit_log"):
            action = create_pending_action("example.com", "4h", "cli")
            result = cancel_pending_action(action["id"])
            assert result is True

            # Verify action was removed
            actions = get_pending_actions()
            assert len(actions) == 0

    def test_cancel_non_existent_action(self):
        """Cancelling non-existent action returns False."""
        result = cancel_pending_action("nonexistent")
        assert result is False


class TestGetReadyActions:
    """Tests for get_ready_actions function."""

    def test_get_ready_actions(self):
        """Get actions ready for execution."""
        with patch("nextdns_blocker.pending.audit_log"):
            # Create action with 0 delay (ready immediately)
            create_pending_action("a.com", "0", "cli")
            # Create action with future execution
            create_pending_action("b.com", "4h", "cli")

            ready = get_ready_actions()
            assert len(ready) == 1
            assert ready[0]["domain"] == "a.com"

    def test_skip_non_pending_status(self):
        """Skip actions that are not in pending status."""
        with patch("nextdns_blocker.pending.audit_log"):
            action = create_pending_action("a.com", "0", "cli")
            mark_action_executed(action["id"])

            ready = get_ready_actions()
            assert len(ready) == 0


class TestMarkActionExecuted:
    """Tests for mark_action_executed function."""

    def test_mark_executed_removes_action(self):
        """Marking action as executed removes it from database."""
        with patch("nextdns_blocker.pending.audit_log"):
            action = create_pending_action("example.com", "4h", "cli")
            result = mark_action_executed(action["id"])
            assert result is True

            actions = get_pending_actions()
            assert len(actions) == 0

    def test_mark_non_existent_action(self):
        """Marking non-existent action returns False."""
        with patch("nextdns_blocker.pending.audit_log"):
            result = mark_action_executed("nonexistent")
            assert result is False


class TestCleanupOldActions:
    """Tests for cleanup_old_actions function."""

    def test_cleanup_old_actions(self):
        """Clean up actions older than max_age_days."""
        with patch("nextdns_blocker.pending.audit_log"):
            # Create an action
            action = create_pending_action("old.com", "4h", "cli")

            # Manually update its created_at to be old
            conn = db.get_connection()
            old_time = (datetime.now() - timedelta(days=10)).isoformat()
            conn.execute(
                "UPDATE pending_actions SET created_at = ? WHERE id = ?",
                (old_time, action["id"]),
            )
            conn.commit()

            # Create a recent action
            create_pending_action("recent.com", "4h", "cli")

            removed = cleanup_old_actions(max_age_days=7)
            assert removed == 1

            actions = get_pending_actions()
            assert len(actions) == 1
            assert actions[0]["domain"] == "recent.com"
