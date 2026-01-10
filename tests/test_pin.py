"""Tests for PIN protection functionality."""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from nextdns_blocker.protection import (
    PIN_LOCKOUT_MINUTES,
    PIN_MAX_ATTEMPTS,
    PIN_MIN_LENGTH,
    _clear_pin_attempts,
    _hash_pin,
    _record_failed_attempt,
    create_pin_session,
    get_failed_attempts_count,
    get_lockout_remaining,
    get_pin_session_remaining,
    is_pin_enabled,
    is_pin_locked_out,
    is_pin_session_valid,
    remove_pin,
    set_pin,
    verify_pin,
)


class TestPinHashing:
    """Tests for PIN hashing functions."""

    def test_hash_pin_returns_hex_and_salt(self):
        """Should return hash hex string and salt bytes."""
        hash_hex, salt = _hash_pin("1234")
        assert isinstance(hash_hex, str)
        assert len(hash_hex) == 64  # SHA256 hex length
        assert isinstance(salt, bytes)
        assert len(salt) == 32

    def test_hash_pin_with_same_salt_produces_same_hash(self):
        """Should produce same hash with same salt."""
        _, salt = _hash_pin("test")
        hash1, _ = _hash_pin("test", salt)
        hash2, _ = _hash_pin("test", salt)
        assert hash1 == hash2

    def test_hash_pin_different_pins_different_hashes(self):
        """Should produce different hashes for different PINs."""
        _, salt = _hash_pin("1234")
        hash1, _ = _hash_pin("1234", salt)
        hash2, _ = _hash_pin("5678", salt)
        assert hash1 != hash2


class TestPinEnabled:
    """Tests for PIN enabled state."""

    def test_is_pin_enabled_no_file(self, tmp_path):
        """Should return False when no PIN file exists."""
        pin_file = tmp_path / ".pin_hash"
        with patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file):
            assert is_pin_enabled() is False

    def test_is_pin_enabled_empty_file(self, tmp_path):
        """Should return False when PIN file is empty."""
        pin_file = tmp_path / ".pin_hash"
        pin_file.write_text("")
        with patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file):
            assert is_pin_enabled() is False

    def test_is_pin_enabled_with_content(self, tmp_path):
        """Should return True when PIN file has content."""
        pin_file = tmp_path / ".pin_hash"
        pin_file.write_text("somesalt:somehash")
        with patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file):
            assert is_pin_enabled() is True


class TestSetPin:
    """Tests for setting PIN."""

    def test_set_pin_creates_file(self, tmp_path):
        """Should create PIN hash file."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            result = set_pin("1234")
            assert result is True
            assert pin_file.exists()
            content = pin_file.read_text()
            assert ":" in content  # salt:hash format

    def test_set_pin_too_short_raises_error(self, tmp_path):
        """Should raise ValueError for PIN shorter than minimum."""
        pin_file = tmp_path / ".pin_hash"
        with patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file):
            with pytest.raises(ValueError, match=f"at least {PIN_MIN_LENGTH}"):
                set_pin("12")  # Too short

    def test_set_pin_clears_session_and_attempts(self, tmp_path):
        """Should clear session and attempts when setting new PIN."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        # Create existing session and attempts
        session_file.write_text((datetime.now() + timedelta(minutes=30)).isoformat())
        attempts_file.write_text(json.dumps([datetime.now().isoformat()]))

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("newpin")
            assert not session_file.exists()
            assert not attempts_file.exists()


class TestVerifyPin:
    """Tests for PIN verification."""

    def test_verify_pin_correct(self, tmp_path):
        """Should return True for correct PIN."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("testpin")
            result = verify_pin("testpin")
            assert result is True

    def test_verify_pin_incorrect(self, tmp_path):
        """Should return False for incorrect PIN."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("testpin")
            result = verify_pin("wrongpin")
            assert result is False

    def test_verify_pin_no_pin_set_returns_true(self, tmp_path):
        """Should return True when no PIN is set."""
        pin_file = tmp_path / ".pin_hash"
        with patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file):
            assert verify_pin("anypin") is True

    def test_verify_pin_creates_session_on_success(self, tmp_path):
        """Should create session after successful verification."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("testpin")
            # Clear session created by set_pin
            if session_file.exists():
                session_file.unlink()
            verify_pin("testpin")
            assert session_file.exists()


class TestPinSession:
    """Tests for PIN session management."""

    def test_is_pin_session_valid_no_pin(self, tmp_path):
        """Should return True when no PIN is enabled."""
        pin_file = tmp_path / ".pin_hash"
        with patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file):
            assert is_pin_session_valid() is True

    def test_is_pin_session_valid_active_session(self, tmp_path):
        """Should return True when session is active."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"

        pin_file.write_text("salt:hash")
        future_time = datetime.now() + timedelta(minutes=20)
        session_file.write_text(future_time.isoformat())

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
        ):
            assert is_pin_session_valid() is True

    def test_is_pin_session_valid_expired_session(self, tmp_path):
        """Should return False and clean up when session is expired."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"

        pin_file.write_text("salt:hash")
        past_time = datetime.now() - timedelta(minutes=5)
        session_file.write_text(past_time.isoformat())

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
        ):
            assert is_pin_session_valid() is False
            assert not session_file.exists()

    def test_create_pin_session(self, tmp_path):
        """Should create session file with future expiration."""
        session_file = tmp_path / ".pin_session"

        with patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file):
            expires = create_pin_session()
            assert session_file.exists()
            assert expires > datetime.now()

    def test_get_pin_session_remaining(self, tmp_path):
        """Should return remaining session time."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"

        pin_file.write_text("salt:hash")
        future_time = datetime.now() + timedelta(minutes=15, seconds=30)
        session_file.write_text(future_time.isoformat())

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
        ):
            remaining = get_pin_session_remaining()
            assert remaining is not None
            assert "m" in remaining


class TestPinLockout:
    """Tests for PIN lockout (brute force protection)."""

    def test_is_pin_locked_out_no_attempts(self, tmp_path):
        """Should return False when no failed attempts."""
        attempts_file = tmp_path / ".pin_attempts"
        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            assert is_pin_locked_out() is False

    def test_is_pin_locked_out_max_attempts_reached(self, tmp_path):
        """Should return True when max attempts reached."""
        attempts_file = tmp_path / ".pin_attempts"

        # Create max attempts within lockout window
        attempts = [datetime.now().isoformat() for _ in range(PIN_MAX_ATTEMPTS)]
        attempts_file.write_text(json.dumps(attempts))

        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            assert is_pin_locked_out() is True

    def test_is_pin_locked_out_old_attempts_ignored(self, tmp_path):
        """Should ignore attempts outside lockout window."""
        attempts_file = tmp_path / ".pin_attempts"

        # Create old attempts outside lockout window
        old_time = datetime.now() - timedelta(minutes=PIN_LOCKOUT_MINUTES + 5)
        attempts = [old_time.isoformat() for _ in range(PIN_MAX_ATTEMPTS)]
        attempts_file.write_text(json.dumps(attempts))

        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            assert is_pin_locked_out() is False

    def test_record_failed_attempt(self, tmp_path):
        """Should record failed attempt."""
        attempts_file = tmp_path / ".pin_attempts"

        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            count = _record_failed_attempt()
            assert count == 1
            assert attempts_file.exists()

    def test_get_failed_attempts_count(self, tmp_path):
        """Should return correct count of failed attempts."""
        attempts_file = tmp_path / ".pin_attempts"

        attempts = [datetime.now().isoformat() for _ in range(2)]
        attempts_file.write_text(json.dumps(attempts))

        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            assert get_failed_attempts_count() == 2

    def test_clear_pin_attempts(self, tmp_path):
        """Should remove attempts file."""
        attempts_file = tmp_path / ".pin_attempts"
        attempts_file.write_text("[]")

        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            _clear_pin_attempts()
            assert not attempts_file.exists()

    def test_get_lockout_remaining(self, tmp_path):
        """Should return remaining lockout time."""
        attempts_file = tmp_path / ".pin_attempts"

        # Create max attempts
        attempts = [datetime.now().isoformat() for _ in range(PIN_MAX_ATTEMPTS)]
        attempts_file.write_text(json.dumps(attempts))

        with patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file):
            remaining = get_lockout_remaining()
            assert remaining is not None
            assert "m" in remaining


class TestRemovePin:
    """Tests for PIN removal."""

    def test_remove_pin_requires_verification(self, tmp_path):
        """Should require current PIN to remove."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch(
                "nextdns_blocker.protection.get_unlock_requests_file",
                return_value=tmp_path / "unlock.json",
            ),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("testpin")
            result = remove_pin("wrongpin")
            assert result is False
            assert pin_file.exists()  # PIN should still exist

    def test_remove_pin_creates_pending_request(self, tmp_path):
        """Should create pending removal request (not immediate removal)."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"
        unlock_file = tmp_path / "unlock_requests.json"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.get_unlock_requests_file", return_value=unlock_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("testpin")
            result = remove_pin("testpin")
            assert result is True
            assert pin_file.exists()  # PIN still exists (pending removal)
            assert unlock_file.exists()  # Pending request created

    def test_remove_pin_force_removes_immediately(self, tmp_path):
        """Should remove immediately when force=True."""
        pin_file = tmp_path / ".pin_hash"
        session_file = tmp_path / ".pin_session"
        attempts_file = tmp_path / ".pin_attempts"

        with (
            patch("nextdns_blocker.protection.get_pin_hash_file", return_value=pin_file),
            patch("nextdns_blocker.protection.get_pin_session_file", return_value=session_file),
            patch("nextdns_blocker.protection.get_pin_attempts_file", return_value=attempts_file),
            patch("nextdns_blocker.protection.audit_log"),
        ):
            set_pin("testpin")
            result = remove_pin("testpin", force=True)
            assert result is True
            assert not pin_file.exists()  # PIN removed immediately
