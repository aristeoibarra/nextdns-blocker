"""Tests for protection module."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from nextdns_blocker import protection


class TestIsLocked:
    """Tests for is_locked function."""

    def test_locked_true(self):
        """Should return True when locked is True."""
        assert protection.is_locked({"locked": True}) is True

    def test_locked_false(self):
        """Should return False when locked is False."""
        assert protection.is_locked({"locked": False}) is False

    def test_unblock_delay_never(self):
        """Should return True when unblock_delay is 'never'."""
        assert protection.is_locked({"unblock_delay": "never"}) is True

    def test_unblock_delay_other(self):
        """Should return False for other unblock_delay values."""
        assert protection.is_locked({"unblock_delay": "48h"}) is False

    def test_empty_item(self):
        """Should return False for empty item."""
        assert protection.is_locked({}) is False

    def test_both_locked_and_never(self):
        """Should return True when both locked and never are set."""
        assert protection.is_locked({"locked": True, "unblock_delay": "never"}) is True


class TestGetLockedIds:
    """Tests for get_locked_ids function."""

    def test_locked_categories(self):
        """Should return locked category IDs."""
        config = {
            "nextdns": {
                "categories": [
                    {"id": "porn", "locked": True},
                    {"id": "gambling", "locked": False},
                    {"id": "dating", "unblock_delay": "never"},
                ]
            }
        }
        locked = protection.get_locked_ids(config, "categories")
        assert locked == {"porn", "dating"}

    def test_locked_services(self):
        """Should return locked service IDs."""
        config = {
            "nextdns": {
                "services": [
                    {"id": "tiktok", "locked": True},
                    {"id": "twitter"},
                ]
            }
        }
        locked = protection.get_locked_ids(config, "services")
        assert locked == {"tiktok"}

    def test_locked_domains_in_blocklist(self):
        """Should return locked domains from blocklist."""
        config = {
            "blocklist": [
                {"domain": "bad.com", "locked": True},
                {"domain": "ok.com"},
            ]
        }
        locked = protection.get_locked_ids(config, "domains")
        assert locked == {"bad.com"}

    def test_locked_domains_in_categories(self):
        """Should return domains from locked categories."""
        config = {
            "categories": [
                {"id": "custom", "locked": True, "domains": ["a.com", "b.com"]},
                {"id": "other", "domains": ["c.com"]},
            ]
        }
        locked = protection.get_locked_ids(config, "domains")
        assert locked == {"a.com", "b.com"}

    def test_empty_config(self):
        """Should return empty set for empty config."""
        assert protection.get_locked_ids({}, "categories") == set()


class TestValidateNoLockedRemoval:
    """Tests for validate_no_locked_removal function."""

    def test_no_locked_items_removed(self):
        """Should return no errors when no locked items removed."""
        old_config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        new_config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        errors = protection.validate_no_locked_removal(old_config, new_config)
        assert errors == []

    def test_locked_category_removed(self):
        """Should return error when locked category removed."""
        old_config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        new_config = {"nextdns": {"categories": []}}
        errors = protection.validate_no_locked_removal(old_config, new_config)
        assert len(errors) == 1
        assert "porn" in errors[0]

    def test_locked_service_removed(self):
        """Should return error when locked service removed."""
        old_config = {"nextdns": {"services": [{"id": "tiktok", "locked": True}]}}
        new_config = {"nextdns": {"services": []}}
        errors = protection.validate_no_locked_removal(old_config, new_config)
        assert len(errors) == 1
        assert "tiktok" in errors[0]


class TestValidateNoLockedWeakening:
    """Tests for validate_no_locked_weakening function."""

    def test_no_weakening(self):
        """Should return no errors when no weakening."""
        old_config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        new_config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        errors = protection.validate_no_locked_weakening(old_config, new_config)
        assert errors == []

    def test_weakening_category(self):
        """Should return error when locked changed to false."""
        old_config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        new_config = {"nextdns": {"categories": [{"id": "porn", "locked": False}]}}
        errors = protection.validate_no_locked_weakening(old_config, new_config)
        assert len(errors) == 1
        assert "porn" in errors[0]

    def test_weakening_service(self):
        """Should return error when service locked changed."""
        old_config = {"nextdns": {"services": [{"id": "tiktok", "locked": True}]}}
        new_config = {"nextdns": {"services": [{"id": "tiktok"}]}}
        errors = protection.validate_no_locked_weakening(old_config, new_config)
        assert len(errors) == 1
        assert "tiktok" in errors[0]


class TestUnlockRequests:
    """Tests for unlock request functions."""

    @pytest.fixture
    def mock_log_dir(self, tmp_path):
        """Mock the log directory."""
        with patch.object(protection, "get_log_dir", return_value=tmp_path):
            yield tmp_path

    def test_create_unlock_request(self, mock_log_dir):
        """Should create an unlock request."""
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "porn", 48, "testing")

        assert request["item_type"] == "category"
        assert request["item_id"] == "porn"
        assert request["status"] == "pending"
        assert request["delay_hours"] == 48
        assert request["reason"] == "testing"

    def test_create_unlock_request_min_delay(self, mock_log_dir):
        """Should enforce minimum delay."""
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "test", 1)

        assert request["delay_hours"] >= protection.MIN_UNLOCK_DELAY_HOURS

    def test_get_pending_unlock_requests(self, mock_log_dir):
        """Should return pending requests."""
        with patch.object(protection, "audit_log"):
            protection.create_unlock_request("category", "test1")
            protection.create_unlock_request("service", "test2")

        pending = protection.get_pending_unlock_requests()
        assert len(pending) == 2

    def test_cancel_unlock_request(self, mock_log_dir):
        """Should cancel a pending request."""
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "test")
            result = protection.cancel_unlock_request(request["id"])

        assert result is True
        pending = protection.get_pending_unlock_requests()
        assert len(pending) == 0

    def test_cancel_nonexistent_request(self, mock_log_dir):
        """Should return False for nonexistent request."""
        result = protection.cancel_unlock_request("nonexistent")
        assert result is False

    def test_get_executable_unlock_requests(self, mock_log_dir):
        """Should return only executable requests."""
        # Create request with 0 delay (will be min delay)
        with patch.object(protection, "audit_log"):
            protection.create_unlock_request("category", "test", 48)

        # Not executable yet
        executable = protection.get_executable_unlock_requests()
        assert len(executable) == 0

    def test_load_unlock_requests_invalid_json(self, mock_log_dir):
        """Should handle invalid JSON gracefully."""
        requests_file = mock_log_dir / "unlock_requests.json"
        requests_file.write_text("invalid json")

        requests = protection._load_unlock_requests()
        assert requests == []


class TestAutoPanic:
    """Tests for auto-panic functions."""

    def test_is_auto_panic_time_disabled(self):
        """Should return False when disabled."""
        config = {"protection": {"auto_panic": {"enabled": False}}}
        assert protection.is_auto_panic_time(config) is False

    def test_is_auto_panic_time_no_config(self):
        """Should return False when no config."""
        assert protection.is_auto_panic_time({}) is False

    def test_is_auto_panic_time_in_schedule(self):
        """Should return True when in schedule."""
        # Test with current time in range
        now = datetime.now()
        start = (now - timedelta(hours=1)).strftime("%H:%M")
        end = (now + timedelta(hours=1)).strftime("%H:%M")

        config = {
            "protection": {
                "auto_panic": {
                    "enabled": True,
                    "schedule": {"start": start, "end": end},
                }
            }
        }
        assert protection.is_auto_panic_time(config) is True

    def test_is_auto_panic_time_outside_schedule(self):
        """Should return False when outside schedule."""
        now = datetime.now()
        start = (now + timedelta(hours=2)).strftime("%H:%M")
        end = (now + timedelta(hours=4)).strftime("%H:%M")

        config = {
            "protection": {
                "auto_panic": {
                    "enabled": True,
                    "schedule": {"start": start, "end": end},
                }
            }
        }
        assert protection.is_auto_panic_time(config) is False

    def test_is_auto_panic_time_wrong_day(self):
        """Should return False when not on active day."""
        now = datetime.now()
        start = (now - timedelta(hours=1)).strftime("%H:%M")
        end = (now + timedelta(hours=1)).strftime("%H:%M")
        # Get a day that is not today
        wrong_day = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        wrong_day.remove(
            ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"][
                now.weekday()
            ]
        )

        config = {
            "protection": {
                "auto_panic": {
                    "enabled": True,
                    "schedule": {"start": start, "end": end},
                    "days": wrong_day[:1],
                }
            }
        }
        assert protection.is_auto_panic_time(config) is False

    def test_can_disable_auto_panic_true(self):
        """Should return True when cannot_disable is False."""
        config = {"protection": {"auto_panic": {"cannot_disable": False}}}
        assert protection.can_disable_auto_panic(config) is True

    def test_can_disable_auto_panic_false(self):
        """Should return False when cannot_disable is True."""
        config = {"protection": {"auto_panic": {"cannot_disable": True}}}
        assert protection.can_disable_auto_panic(config) is False


class TestValidateProtectionConfig:
    """Tests for validate_protection_config function."""

    def test_valid_config(self):
        """Should return no errors for valid config."""
        config = {
            "unlock_delay_hours": 48,
            "auto_panic": {
                "enabled": True,
                "cannot_disable": False,
                "schedule": {"start": "23:00", "end": "06:00"},
                "days": ["monday", "tuesday"],
            },
        }
        errors = protection.validate_protection_config(config)
        assert errors == []

    def test_invalid_unlock_delay(self):
        """Should return error for invalid unlock delay."""
        config = {"unlock_delay_hours": 1}
        errors = protection.validate_protection_config(config)
        assert len(errors) == 1
        assert "unlock_delay_hours" in errors[0]

    def test_invalid_auto_panic_type(self):
        """Should return error for non-dict auto_panic."""
        config = {"auto_panic": "invalid"}
        errors = protection.validate_protection_config(config)
        assert len(errors) == 1

    def test_invalid_enabled_type(self):
        """Should return error for non-bool enabled."""
        config = {"auto_panic": {"enabled": "yes"}}
        errors = protection.validate_protection_config(config)
        assert len(errors) == 1

    def test_invalid_schedule_time(self):
        """Should return error for invalid time format."""
        config = {"auto_panic": {"schedule": {"start": "25:00"}}}
        errors = protection.validate_protection_config(config)
        assert len(errors) == 1

    def test_invalid_day_name(self):
        """Should return error for invalid day name."""
        config = {"auto_panic": {"days": ["funday"]}}
        errors = protection.validate_protection_config(config)
        assert len(errors) == 1

    def test_non_dict_protection(self):
        """Should return error for non-dict protection."""
        errors = protection.validate_protection_config("invalid")
        assert len(errors) == 1


class TestIsValidTime:
    """Tests for _is_valid_time function."""

    def test_valid_times(self):
        """Should return True for valid times."""
        assert protection._is_valid_time("00:00") is True
        assert protection._is_valid_time("23:59") is True
        assert protection._is_valid_time("12:30") is True

    def test_invalid_times(self):
        """Should return False for invalid times."""
        assert protection._is_valid_time("24:00") is False
        assert protection._is_valid_time("12:60") is False
        assert protection._is_valid_time("1:30") is False  # Missing leading zero
        assert protection._is_valid_time("invalid") is False


class TestExecuteUnlockRequest:
    """Tests for execute_unlock_request function."""

    @pytest.fixture
    def mock_log_dir(self, tmp_path):
        """Mock the log directory."""
        with patch.object(protection, "get_log_dir", return_value=tmp_path):
            yield tmp_path

    def test_execute_unlock_request_success(self, mock_log_dir, tmp_path):
        """Should execute unlock request and modify config."""
        # Create config file
        config_path = tmp_path / "config.json"
        config = {"nextdns": {"categories": [{"id": "porn", "locked": True}]}}
        config_path.write_text(json.dumps(config))

        # Create a request that's ready to execute
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "porn", 24)

        # Modify execute_at to be in the past
        requests = protection._load_unlock_requests()
        requests[0]["execute_at"] = (datetime.now() - timedelta(hours=1)).isoformat()
        protection._save_unlock_requests(requests)

        # Execute
        with patch.object(protection, "audit_log"):
            result = protection.execute_unlock_request(request["id"], config_path)

        assert result is True

        # Verify config was modified
        new_config = json.loads(config_path.read_text())
        assert new_config["nextdns"]["categories"] == []

    def test_execute_unlock_request_not_ready(self, mock_log_dir, tmp_path):
        """Should not execute if delay hasn't passed."""
        config_path = tmp_path / "config.json"
        config_path.write_text("{}")

        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "test", 48)
            result = protection.execute_unlock_request(request["id"], config_path)

        assert result is False

    def test_execute_unlock_request_not_found(self, mock_log_dir, tmp_path):
        """Should return False for nonexistent request."""
        config_path = tmp_path / "config.json"
        result = protection.execute_unlock_request("nonexistent", config_path)
        assert result is False


class TestCanExecuteDangerousCommand:
    """Tests for can_execute_dangerous_command function."""

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=True)
    def test_blocked_during_panic(self, mock_panic):
        """Should block dangerous commands during panic mode."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is False
        assert reason == "panic_mode"

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    @patch.object(protection, "is_pin_enabled", return_value=True)
    @patch.object(protection, "is_pin_locked_out", return_value=True)
    def test_blocked_during_lockout(self, mock_lockout, mock_pin, mock_panic):
        """Should block when PIN is locked out."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is False
        assert reason == "pin_locked_out"

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    @patch.object(protection, "is_pin_enabled", return_value=True)
    @patch.object(protection, "is_pin_locked_out", return_value=False)
    @patch.object(protection, "is_pin_session_valid", return_value=False)
    def test_requires_pin(self, mock_session, mock_lockout, mock_pin, mock_panic):
        """Should require PIN when no valid session."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is False
        assert reason == "pin_required"

    @patch("nextdns_blocker.panic.is_panic_mode", return_value=False)
    @patch.object(protection, "is_pin_enabled", return_value=False)
    def test_allowed_no_protection(self, mock_pin, mock_panic):
        """Should allow when no protection enabled."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is True
        assert reason == "ok"


class TestPinFunctions:
    """Tests for PIN-related functions."""

    @pytest.fixture
    def mock_log_dir(self, tmp_path):
        """Mock the log directory."""
        with patch.object(protection, "get_log_dir", return_value=tmp_path):
            yield tmp_path

    def test_is_pin_enabled_false(self, mock_log_dir):
        """Should return False when no PIN file exists."""
        assert protection.is_pin_enabled() is False

    def test_is_pin_enabled_true(self, mock_log_dir):
        """Should return True when PIN file exists."""
        pin_file = mock_log_dir / ".pin_hash"
        pin_file.write_text("somehash:salt")
        assert protection.is_pin_enabled() is True

    def test_set_pin_success(self, mock_log_dir):
        """Should set PIN successfully."""
        with patch.object(protection, "audit_log"):
            result = protection.set_pin("1234")
        assert result is True
        assert protection.is_pin_enabled() is True

    def test_set_pin_too_short(self):
        """Should raise error for short PIN."""
        with pytest.raises(ValueError):
            protection.set_pin("123")

    def test_set_pin_too_long(self):
        """Should raise error for long PIN."""
        with pytest.raises(ValueError):
            protection.set_pin("a" * 50)

    def test_verify_pin_correct(self, mock_log_dir):
        """Should verify correct PIN."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.verify_pin("1234")
        assert result is True

    def test_verify_pin_incorrect(self, mock_log_dir):
        """Should reject incorrect PIN."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.verify_pin("wrong")
        assert result is False

    def test_verify_pin_no_pin_set(self, mock_log_dir):
        """Should return True when no PIN set."""
        result = protection.verify_pin("anything")
        assert result is True

    def test_create_pin_session(self, mock_log_dir):
        """Should create a PIN session."""
        expires = protection.create_pin_session()
        assert isinstance(expires, datetime)
        assert expires > datetime.now()

    def test_is_pin_session_valid_no_pin(self, mock_log_dir):
        """Should return True when no PIN enabled."""
        assert protection.is_pin_session_valid() is True

    def test_is_pin_session_valid_active(self, mock_log_dir):
        """Should return True for active session."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            protection.verify_pin("1234")  # Creates session
            assert protection.is_pin_session_valid() is True

    def test_is_pin_session_valid_no_session(self, mock_log_dir):
        """Should return False when no session file."""
        pin_file = mock_log_dir / ".pin_hash"
        pin_file.write_text("hash:salt")
        assert protection.is_pin_session_valid() is False

    def test_get_pin_session_remaining_no_pin(self, mock_log_dir):
        """Should return None when no PIN enabled."""
        assert protection.get_pin_session_remaining() is None

    def test_get_pin_session_remaining_active(self, mock_log_dir):
        """Should return remaining time for active session."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            protection.verify_pin("1234")
            remaining = protection.get_pin_session_remaining()
            assert remaining is not None
            assert "m" in remaining

    def test_is_pin_locked_out_false(self, mock_log_dir):
        """Should return False when no attempts."""
        assert protection.is_pin_locked_out() is False

    def test_get_failed_attempts_count_zero(self, mock_log_dir):
        """Should return 0 when no attempts."""
        assert protection.get_failed_attempts_count() == 0

    def test_get_lockout_remaining_not_locked(self, mock_log_dir):
        """Should return None when not locked out."""
        assert protection.get_lockout_remaining() is None


class TestRemovePin:
    """Tests for remove_pin function."""

    @pytest.fixture
    def mock_log_dir(self, tmp_path):
        """Mock the log directory."""
        with patch.object(protection, "get_log_dir", return_value=tmp_path):
            yield tmp_path

    def test_remove_pin_not_enabled(self, mock_log_dir):
        """Should return False when PIN not enabled."""
        assert protection.remove_pin("1234") is False

    def test_remove_pin_wrong_pin(self, mock_log_dir):
        """Should return False for wrong PIN."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.remove_pin("wrong")
        assert result is False

    def test_remove_pin_force(self, mock_log_dir):
        """Should remove PIN immediately with force=True."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.remove_pin("1234", force=True)
        assert result is True
        assert protection.is_pin_enabled() is False

    def test_remove_pin_creates_pending(self, mock_log_dir):
        """Should create pending removal request without force."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.remove_pin("1234", force=False)
        assert result is True
        # PIN should still be enabled (waiting for delay)
        assert protection.is_pin_enabled() is True
