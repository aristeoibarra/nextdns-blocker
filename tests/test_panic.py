"""Tests for panic mode functionality."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from nextdns_blocker.panic import (
    MIN_PANIC_DURATION_MINUTES,
    extend_panic,
    get_panic_remaining,
    get_panic_until,
    is_panic_mode,
    parse_duration,
    set_panic,
    try_activate_or_extend,
)


class TestPanicState:
    """Tests for panic state management."""

    def test_is_panic_mode_no_file(self, tmp_path):
        """Should return False when no panic file exists."""
        panic_file = tmp_path / ".panic"
        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            assert is_panic_mode() is False

    def test_is_panic_mode_active(self, tmp_path):
        """Should return True when panic is active."""
        panic_file = tmp_path / ".panic"
        future_time = datetime.now() + timedelta(hours=2)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            assert is_panic_mode() is True

    def test_is_panic_mode_expired(self, tmp_path):
        """Should return False and clean up when panic has expired."""
        panic_file = tmp_path / ".panic"
        past_time = datetime.now() - timedelta(minutes=5)
        panic_file.write_text(past_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            assert is_panic_mode() is False
            assert not panic_file.exists()

    def test_is_panic_mode_invalid_content(self, tmp_path):
        """Should return False when panic file has invalid content."""
        panic_file = tmp_path / ".panic"
        panic_file.write_text("not_a_valid_datetime")

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            assert is_panic_mode() is False
            assert not panic_file.exists()


class TestPanicRemaining:
    """Tests for panic remaining time."""

    def test_get_panic_remaining_no_file(self, tmp_path):
        """Should return None when no panic file exists."""
        panic_file = tmp_path / ".panic"
        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            assert get_panic_remaining() is None

    def test_get_panic_remaining_active_hours(self, tmp_path):
        """Should return remaining time with hours when panic is active."""
        panic_file = tmp_path / ".panic"
        future_time = datetime.now() + timedelta(hours=2, minutes=30)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            remaining = get_panic_remaining()
            assert remaining is not None
            assert "2h" in remaining
            assert "m" in remaining

    def test_get_panic_remaining_active_minutes_only(self, tmp_path):
        """Should return minutes only when less than an hour remains."""
        panic_file = tmp_path / ".panic"
        future_time = datetime.now() + timedelta(minutes=45)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            remaining = get_panic_remaining()
            assert remaining is not None
            assert "h" not in remaining
            assert "m" in remaining

    def test_get_panic_remaining_less_than_minute(self, tmp_path):
        """Should return '< 1m' when less than a minute remains."""
        panic_file = tmp_path / ".panic"
        future_time = datetime.now() + timedelta(seconds=30)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            remaining = get_panic_remaining()
            assert remaining == "< 1m"


class TestSetPanic:
    """Tests for panic activation."""

    def test_set_panic_creates_file(self, tmp_path):
        """Should create panic file with ISO timestamp."""
        panic_file = tmp_path / ".panic"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=log_dir),
            patch("nextdns_blocker.panic.audit_log"),
        ):
            result = set_panic(30)
            assert panic_file.exists()
            assert isinstance(result, datetime)
            # Verify content is valid ISO format
            content = panic_file.read_text()
            datetime.fromisoformat(content)

    def test_set_panic_minimum_duration(self, tmp_path):
        """Should reject durations below minimum."""
        panic_file = tmp_path / ".panic"

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            with pytest.raises(ValueError) as exc_info:
                set_panic(5)  # Less than 15 minutes minimum
            assert str(MIN_PANIC_DURATION_MINUTES) in str(exc_info.value)

    def test_set_panic_exact_minimum(self, tmp_path):
        """Should accept exact minimum duration."""
        panic_file = tmp_path / ".panic"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=log_dir),
            patch("nextdns_blocker.panic.audit_log"),
        ):
            result = set_panic(MIN_PANIC_DURATION_MINUTES)
            assert panic_file.exists()
            assert isinstance(result, datetime)


class TestExtendPanic:
    """Tests for panic extension."""

    def test_extend_panic_not_active(self, tmp_path):
        """Should return None when panic not active."""
        panic_file = tmp_path / ".panic"
        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            result = extend_panic(30)
            assert result is None

    def test_extend_panic_adds_time(self, tmp_path):
        """Should add time to existing expiration."""
        panic_file = tmp_path / ".panic"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        original_time = datetime.now() + timedelta(hours=1)
        panic_file.write_text(original_time.isoformat())

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=log_dir),
            patch("nextdns_blocker.panic.audit_log"),
        ):
            result = extend_panic(30)
            assert result is not None
            # New time should be ~30 minutes after original
            expected = original_time + timedelta(minutes=30)
            assert abs((result - expected).total_seconds()) < 2


class TestTryActivateOrExtend:
    """Tests for activate or extend functionality."""

    def test_new_activation(self, tmp_path):
        """Should activate panic mode when not active."""
        panic_file = tmp_path / ".panic"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=log_dir),
            patch("nextdns_blocker.panic.audit_log"),
        ):
            result, was_extended = try_activate_or_extend(60)
            assert was_extended is False
            assert panic_file.exists()

    def test_extend_with_longer_duration(self, tmp_path):
        """Should extend when new duration is longer than remaining."""
        panic_file = tmp_path / ".panic"
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        # Set panic to expire in 30 minutes
        original_time = datetime.now() + timedelta(minutes=30)
        panic_file.write_text(original_time.isoformat())

        with (
            patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file),
            patch("nextdns_blocker.panic.get_log_dir", return_value=log_dir),
            patch("nextdns_blocker.panic.audit_log"),
        ):
            # Try to set 2 hours (longer than 30 minutes)
            result, was_extended = try_activate_or_extend(120)
            assert was_extended is True

    def test_reject_shorter_duration(self, tmp_path):
        """Should reject when new duration would shorten panic."""
        panic_file = tmp_path / ".panic"

        # Set panic to expire in 2 hours
        future_time = datetime.now() + timedelta(hours=2)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            with pytest.raises(ValueError) as exc_info:
                try_activate_or_extend(30)  # 30 minutes is less than 2 hours remaining
            assert "extend" in str(exc_info.value).lower()


class TestParseDuration:
    """Tests for duration string parsing."""

    def test_parse_minutes(self):
        """Should parse Nm format."""
        assert parse_duration("30m") == 30
        assert parse_duration("15m") == 15
        assert parse_duration("90m") == 90

    def test_parse_hours(self):
        """Should parse Nh format."""
        assert parse_duration("1h") == 60
        assert parse_duration("2h") == 120
        assert parse_duration("24h") == 1440

    def test_parse_days(self):
        """Should parse Nd format."""
        assert parse_duration("1d") == 1440
        assert parse_duration("7d") == 10080

    def test_parse_case_insensitive(self):
        """Should accept uppercase units."""
        assert parse_duration("30M") == 30
        assert parse_duration("2H") == 120
        assert parse_duration("1D") == 1440

    def test_parse_invalid_format(self):
        """Should raise ValueError for invalid format."""
        with pytest.raises(ValueError):
            parse_duration("30")  # Missing unit
        with pytest.raises(ValueError):
            parse_duration("abc")  # Not a number
        with pytest.raises(ValueError):
            parse_duration("30x")  # Invalid unit
        with pytest.raises(ValueError):
            parse_duration("")  # Empty string

    def test_parse_with_whitespace(self):
        """Should handle leading/trailing whitespace."""
        assert parse_duration("  30m  ") == 30
        assert parse_duration("\t2h\n") == 120


class TestGetPanicUntil:
    """Tests for get_panic_until function."""

    def test_no_panic(self, tmp_path):
        """Should return None when no panic active."""
        panic_file = tmp_path / ".panic"
        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            assert get_panic_until() is None

    def test_active_panic(self, tmp_path):
        """Should return expiration datetime when panic active."""
        panic_file = tmp_path / ".panic"
        future_time = datetime.now() + timedelta(hours=2)
        panic_file.write_text(future_time.isoformat())

        with patch("nextdns_blocker.panic.get_panic_file", return_value=panic_file):
            result = get_panic_until()
            assert result is not None
            # Allow 1 second tolerance for test execution time
            assert abs((result - future_time).total_seconds()) < 1


class TestDangerousCommands:
    """Tests for DANGEROUS_COMMANDS constant."""

    def test_allow_in_dangerous_commands(self):
        """Allow command should be in DANGEROUS_COMMANDS to prevent security holes."""
        from nextdns_blocker.panic import DANGEROUS_COMMANDS

        assert "allow" in DANGEROUS_COMMANDS

    def test_disallow_in_dangerous_commands(self):
        """Disallow command should be in DANGEROUS_COMMANDS."""
        from nextdns_blocker.panic import DANGEROUS_COMMANDS

        assert "disallow" in DANGEROUS_COMMANDS

    def test_unblock_in_dangerous_commands(self):
        """Unblock command should be in DANGEROUS_COMMANDS."""
        from nextdns_blocker.panic import DANGEROUS_COMMANDS

        assert "unblock" in DANGEROUS_COMMANDS

    def test_pause_in_dangerous_commands(self):
        """Pause command should be in DANGEROUS_COMMANDS."""
        from nextdns_blocker.panic import DANGEROUS_COMMANDS

        assert "pause" in DANGEROUS_COMMANDS

    def test_resume_in_dangerous_commands(self):
        """Resume command should be in DANGEROUS_COMMANDS."""
        from nextdns_blocker.panic import DANGEROUS_COMMANDS

        assert "resume" in DANGEROUS_COMMANDS
