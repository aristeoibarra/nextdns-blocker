"""Tests for pending action module."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from nextdns_blocker.pending import (
    _load_pending_data,
    _save_pending_data,
    cancel_pending_action,
    cleanup_old_actions,
    create_pending_action,
    generate_action_id,
    get_pending_actions,
    get_pending_for_domain,
    get_ready_actions,
    mark_action_executed,
)


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


class TestPendingDataIO:
    """Tests for pending data loading and saving."""

    def test_load_empty_file(self, tmp_path: Path):
        """Loading non-existent file returns default structure."""
        with patch(
            "nextdns_blocker.pending.get_pending_file", return_value=tmp_path / "pending.json"
        ):
            data = _load_pending_data()
            assert data["version"] == "1.0"
            assert data["pending_actions"] == []

    def test_save_and_load(self, tmp_path: Path):
        """Saved data can be loaded correctly."""
        pending_file = tmp_path / "pending.json"
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            test_data = {
                "version": "1.0",
                "pending_actions": [
                    {"id": "test_123", "domain": "example.com", "status": "pending"}
                ],
            }
            assert _save_pending_data(test_data)
            loaded = _load_pending_data()
            assert loaded == test_data

    def test_load_invalid_json(self, tmp_path: Path):
        """Loading invalid JSON returns default structure."""
        pending_file = tmp_path / "pending.json"
        pending_file.write_text("invalid json {")
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            data = _load_pending_data()
            assert data["version"] == "1.0"
            assert data["pending_actions"] == []


class TestCreatePendingAction:
    """Tests for create_pending_action function."""

    def test_create_action_with_delay(self, tmp_path: Path):
        """Creating action with valid delay."""
        pending_file = tmp_path / "pending.json"
        with (
            patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file),
            patch("nextdns_blocker.pending.audit_log"),
        ):
            action = create_pending_action("example.com", "4h", "cli")
            assert action is not None
            assert action["domain"] == "example.com"
            assert action["delay"] == "4h"
            assert action["status"] == "pending"
            assert action["requested_by"] == "cli"
            assert action["id"].startswith("pnd_")

    def test_create_action_never_returns_none(self, tmp_path: Path):
        """Creating action with 'never' delay returns None."""
        pending_file = tmp_path / "pending.json"
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            action = create_pending_action("example.com", "never", "cli")
            assert action is None

    def test_create_action_invalid_delay(self, tmp_path: Path):
        """Creating action with invalid delay returns None."""
        pending_file = tmp_path / "pending.json"
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            action = create_pending_action("example.com", "invalid", "cli")
            assert action is None

    def test_create_duplicate_returns_existing(self, tmp_path: Path):
        """Creating duplicate action returns existing one."""
        pending_file = tmp_path / "pending.json"
        with (
            patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file),
            patch("nextdns_blocker.pending.audit_log"),
        ):
            action1 = create_pending_action("example.com", "4h", "cli")
            action2 = create_pending_action("example.com", "24h", "cli")
            assert action1["id"] == action2["id"]

    def test_execute_at_calculated_correctly(self, tmp_path: Path):
        """Execute time is calculated correctly based on delay."""
        pending_file = tmp_path / "pending.json"
        with (
            patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file),
            patch("nextdns_blocker.pending.audit_log"),
        ):
            before = datetime.now()
            action = create_pending_action("example.com", "30m", "cli")
            after = datetime.now()

            execute_at = datetime.fromisoformat(action["execute_at"])
            expected_min = before + timedelta(minutes=30)
            expected_max = after + timedelta(minutes=30)

            assert expected_min <= execute_at <= expected_max


class TestGetPendingActions:
    """Tests for get_pending_actions function."""

    def test_get_all_actions(self, tmp_path: Path):
        """Get all pending actions."""
        pending_file = tmp_path / "pending.json"
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "1", "domain": "a.com", "status": "pending"},
                {"id": "2", "domain": "b.com", "status": "executed"},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            actions = get_pending_actions()
            assert len(actions) == 2

    def test_filter_by_status(self, tmp_path: Path):
        """Filter actions by status."""
        pending_file = tmp_path / "pending.json"
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "1", "domain": "a.com", "status": "pending"},
                {"id": "2", "domain": "b.com", "status": "executed"},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            pending = get_pending_actions(status="pending")
            assert len(pending) == 1
            assert pending[0]["id"] == "1"


class TestGetPendingForDomain:
    """Tests for get_pending_for_domain function."""

    def test_find_existing_domain(self, tmp_path: Path):
        """Find pending action for domain."""
        pending_file = tmp_path / "pending.json"
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "1", "domain": "example.com", "status": "pending"},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            action = get_pending_for_domain("example.com")
            assert action is not None
            assert action["id"] == "1"

    def test_domain_not_found(self, tmp_path: Path):
        """Return None for non-existent domain."""
        pending_file = tmp_path / "pending.json"
        test_data = {"version": "1.0", "pending_actions": []}
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            action = get_pending_for_domain("example.com")
            assert action is None


class TestCancelPendingAction:
    """Tests for cancel_pending_action function."""

    def test_cancel_existing_action(self, tmp_path: Path):
        """Cancel existing pending action."""
        pending_file = tmp_path / "pending.json"
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "test_123", "domain": "example.com", "status": "pending"},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with (
            patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file),
            patch("nextdns_blocker.pending.audit_log"),
        ):
            result = cancel_pending_action("test_123")
            assert result is True

            # Verify action was removed
            actions = get_pending_actions()
            assert len(actions) == 0

    def test_cancel_non_existent_action(self, tmp_path: Path):
        """Cancelling non-existent action returns False."""
        pending_file = tmp_path / "pending.json"
        test_data = {"version": "1.0", "pending_actions": []}
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            result = cancel_pending_action("nonexistent")
            assert result is False


class TestGetReadyActions:
    """Tests for get_ready_actions function."""

    def test_get_ready_actions(self, tmp_path: Path):
        """Get actions ready for execution."""
        pending_file = tmp_path / "pending.json"
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        future_time = (datetime.now() + timedelta(hours=1)).isoformat()
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "1", "domain": "a.com", "status": "pending", "execute_at": past_time},
                {"id": "2", "domain": "b.com", "status": "pending", "execute_at": future_time},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            ready = get_ready_actions()
            assert len(ready) == 1
            assert ready[0]["id"] == "1"

    def test_skip_non_pending_status(self, tmp_path: Path):
        """Skip actions that are not in pending status."""
        pending_file = tmp_path / "pending.json"
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "1", "domain": "a.com", "status": "executed", "execute_at": past_time},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            ready = get_ready_actions()
            assert len(ready) == 0


class TestMarkActionExecuted:
    """Tests for mark_action_executed function."""

    def test_mark_executed_removes_action(self, tmp_path: Path):
        """Marking action as executed removes it from file."""
        pending_file = tmp_path / "pending.json"
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {"id": "test_123", "domain": "example.com", "status": "pending"},
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with (
            patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file),
            patch("nextdns_blocker.pending.audit_log"),
        ):
            result = mark_action_executed("test_123")
            assert result is True

            actions = get_pending_actions()
            assert len(actions) == 0


class TestCleanupOldActions:
    """Tests for cleanup_old_actions function."""

    def test_cleanup_old_actions(self, tmp_path: Path):
        """Clean up actions older than max_age_days."""
        pending_file = tmp_path / "pending.json"
        old_time = (datetime.now() - timedelta(days=10)).isoformat()
        recent_time = (datetime.now() - timedelta(days=1)).isoformat()
        test_data = {
            "version": "1.0",
            "pending_actions": [
                {
                    "id": "1",
                    "domain": "old.com",
                    "status": "pending",
                    "created_at": old_time,
                    "execute_at": old_time,
                },
                {
                    "id": "2",
                    "domain": "recent.com",
                    "status": "pending",
                    "created_at": recent_time,
                    "execute_at": recent_time,
                },
            ],
        }
        pending_file.write_text(json.dumps(test_data))
        with patch("nextdns_blocker.pending.get_pending_file", return_value=pending_file):
            removed = cleanup_old_actions(max_age_days=7)
            assert removed == 1

            actions = get_pending_actions()
            assert len(actions) == 1
            assert actions[0]["domain"] == "recent.com"
