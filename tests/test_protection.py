"""Tests for protection module."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest

from nextdns_blocker import database as db
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

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
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

    def test_create_unlock_request(self):
        """Should create an unlock request."""
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "porn", 48, "testing")

        assert request["item_type"] == "category"
        assert request["item_id"] == "porn"
        assert request["status"] == "pending"
        assert request["delay_hours"] == 48
        assert request["reason"] == "testing"

    def test_create_unlock_request_min_delay(self):
        """Should enforce minimum delay."""
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "test", 1)

        assert request["delay_hours"] >= protection.MIN_UNLOCK_DELAY_HOURS

    def test_get_pending_unlock_requests(self):
        """Should return pending requests."""
        with patch.object(protection, "audit_log"):
            protection.create_unlock_request("category", "test1")
            protection.create_unlock_request("service", "test2")

        pending = protection.get_pending_unlock_requests()
        assert len(pending) == 2

    def test_cancel_unlock_request(self):
        """Should cancel a pending request."""
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "test")
            result = protection.cancel_unlock_request(request["id"])

        assert result is True
        pending = protection.get_pending_unlock_requests()
        assert len(pending) == 0

    def test_cancel_nonexistent_request(self):
        """Should return False for nonexistent request."""
        result = protection.cancel_unlock_request("nonexistent")
        assert result is False

    def test_get_executable_unlock_requests(self):
        """Should return only executable requests."""
        # Create request with 0 delay (will be min delay)
        with patch.object(protection, "audit_log"):
            protection.create_unlock_request("category", "test", 48)

        # Not executable yet
        executable = protection.get_executable_unlock_requests()
        assert len(executable) == 0


class TestValidateProtectionConfig:
    """Tests for validate_protection_config function."""

    def test_valid_config(self):
        """Should return no errors for valid config."""
        config = {
            "unlock_delay_hours": 48,
        }
        errors = protection.validate_protection_config(config)
        assert errors == []

    def test_invalid_unlock_delay(self):
        """Should return error for invalid unlock delay."""
        config = {"unlock_delay_hours": 1}
        errors = protection.validate_protection_config(config)
        assert len(errors) == 1
        assert "unlock_delay_hours" in errors[0]

    def test_empty_config(self):
        """Should return no errors for empty config."""
        errors = protection.validate_protection_config({})
        assert errors == []


class TestExecuteUnlockRequest:
    """Tests for execute_unlock_request function."""

    @pytest.fixture(autouse=True)
    def use_temp_database(self, tmp_path: Path):
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

    def test_execute_unlock_request_success(self, tmp_path):
        """Should execute unlock request and remove item from database."""
        # Add a NextDNS category to the database
        db.set_nextdns_category("porn", locked=True)

        # Create a request that's ready to execute
        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "porn", 24)

        # Modify execute_at to be in the past using database
        conn = db.get_connection()
        past_time = (datetime.now() - timedelta(hours=1)).isoformat()
        conn.execute(
            "UPDATE unlock_requests SET execute_at = ? WHERE id = ?",
            (past_time, request["id"]),
        )
        conn.commit()

        # Execute
        with patch.object(protection, "audit_log"):
            result = protection.execute_unlock_request(request["id"])

        assert result is True

        # Verify category was removed from database
        assert db.get_nextdns_category("porn") is None

    def test_execute_unlock_request_not_ready(self, tmp_path):
        """Should not execute if delay hasn't passed."""
        # Add a NextDNS category to the database
        db.set_nextdns_category("test", locked=True)

        with patch.object(protection, "audit_log"):
            request = protection.create_unlock_request("category", "test", 48)
            result = protection.execute_unlock_request(request["id"])

        assert result is False

    def test_execute_unlock_request_not_found(self, tmp_path):
        """Should return False for nonexistent request."""
        result = protection.execute_unlock_request("nonexistent")
        assert result is False


class TestCanExecuteDangerousCommand:
    """Tests for can_execute_dangerous_command function."""

    @patch.object(protection, "is_pin_enabled", return_value=True)
    @patch.object(protection, "is_pin_locked_out", return_value=True)
    def test_blocked_during_lockout(self, mock_lockout, mock_pin):
        """Should block when PIN is locked out."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is False
        assert reason == "pin_locked_out"

    @patch.object(protection, "is_pin_enabled", return_value=True)
    @patch.object(protection, "is_pin_locked_out", return_value=False)
    @patch.object(protection, "is_pin_session_valid", return_value=False)
    def test_requires_pin(self, mock_session, mock_lockout, mock_pin):
        """Should require PIN when no valid session."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is False
        assert reason == "pin_required"

    @patch.object(protection, "is_pin_enabled", return_value=False)
    def test_allowed_no_protection(self, mock_pin):
        """Should allow when no protection enabled."""
        can_exec, reason = protection.can_execute_dangerous_command("unblock")
        assert can_exec is True
        assert reason == "ok"


class TestPinFunctions:
    """Tests for PIN-related functions."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Use a temporary database for PIN tests."""
        db_path = tmp_path / "test.db"
        with patch.object(db, "get_db_path", return_value=db_path):
            # Close any existing connection and reinitialize
            db.close_connection()
            db.init_database()
            yield tmp_path
            db.close_connection()

    def test_is_pin_enabled_false(self, mock_db):
        """Should return False when no PIN set."""
        assert protection.is_pin_enabled() is False

    def test_is_pin_enabled_true(self, mock_db):
        """Should return True when PIN is set."""
        db.set_pin_value("hash", "somehash:salt")
        assert protection.is_pin_enabled() is True

    def test_set_pin_success(self, mock_db):
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

    def test_verify_pin_correct(self, mock_db):
        """Should verify correct PIN."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.verify_pin("1234")
        assert result is True

    def test_verify_pin_incorrect(self, mock_db):
        """Should reject incorrect PIN."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.verify_pin("wrong")
        assert result is False

    def test_verify_pin_no_pin_set(self, mock_db):
        """Should return True when no PIN set."""
        result = protection.verify_pin("anything")
        assert result is True

    def test_create_pin_session(self, mock_db):
        """Should create a PIN session."""
        expires = protection.create_pin_session()
        assert isinstance(expires, datetime)
        assert expires > datetime.now()

    def test_is_pin_session_valid_no_pin(self, mock_db):
        """Should return True when no PIN enabled."""
        assert protection.is_pin_session_valid() is True

    def test_is_pin_session_valid_active(self, mock_db):
        """Should return True for active session."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            protection.verify_pin("1234")  # Creates session
            assert protection.is_pin_session_valid() is True

    def test_is_pin_session_valid_no_session(self, mock_db):
        """Should return False when no session exists."""
        db.set_pin_value("hash", "somehash:salt")
        assert protection.is_pin_session_valid() is False

    def test_get_pin_session_remaining_no_pin(self, mock_db):
        """Should return None when no PIN enabled."""
        assert protection.get_pin_session_remaining() is None

    def test_get_pin_session_remaining_active(self, mock_db):
        """Should return remaining time for active session."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            protection.verify_pin("1234")
            remaining = protection.get_pin_session_remaining()
            assert remaining is not None
            assert "m" in remaining

    def test_is_pin_locked_out_false(self, mock_db):
        """Should return False when no attempts."""
        assert protection.is_pin_locked_out() is False

    def test_get_failed_attempts_count_zero(self, mock_db):
        """Should return 0 when no attempts."""
        assert protection.get_failed_attempts_count() == 0

    def test_get_lockout_remaining_not_locked(self, mock_db):
        """Should return None when not locked out."""
        assert protection.get_lockout_remaining() is None


class TestRemovePin:
    """Tests for remove_pin function."""

    @pytest.fixture
    def mock_db(self, tmp_path):
        """Use a temporary database for PIN tests."""
        db_path = tmp_path / "test.db"
        with patch.object(db, "get_db_path", return_value=db_path):
            db.close_connection()
            db.init_database()
            yield tmp_path
            db.close_connection()

    def test_remove_pin_not_enabled(self, mock_db):
        """Should return False when PIN not enabled."""
        assert protection.remove_pin("1234") is False

    def test_remove_pin_wrong_pin(self, mock_db):
        """Should return False for wrong PIN."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.remove_pin("wrong")
        assert result is False

    def test_remove_pin_force(self, mock_db):
        """Should remove PIN immediately with force=True."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.remove_pin("1234", force=True)
        assert result is True
        assert protection.is_pin_enabled() is False

    def test_remove_pin_creates_pending(self, mock_db):
        """Should create pending removal request without force."""
        with patch.object(protection, "audit_log"):
            protection.set_pin("1234")
            result = protection.remove_pin("1234", force=False)
        assert result is True
        # PIN should still be enabled (waiting for delay)
        assert protection.is_pin_enabled() is True
