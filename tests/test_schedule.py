"""Tests for ScheduleEvaluator class."""

from datetime import datetime, time
from unittest.mock import patch

import pytest

from nextdns_blocker.scheduler import ScheduleEvaluator


class TestParseTime:
    """Tests for parse_time method."""

    def test_parse_valid_time(self):
        evaluator = ScheduleEvaluator()
        assert evaluator.parse_time("09:00") == time(9, 0)
        assert evaluator.parse_time("23:59") == time(23, 59)
        assert evaluator.parse_time("00:00") == time(0, 0)

    def test_parse_time_with_leading_zeros(self):
        evaluator = ScheduleEvaluator()
        assert evaluator.parse_time("01:05") == time(1, 5)

    def test_parse_invalid_time_no_colon(self):
        evaluator = ScheduleEvaluator()
        with pytest.raises(ValueError, match="Invalid time"):
            evaluator.parse_time("0900")

    def test_parse_invalid_time_empty(self):
        evaluator = ScheduleEvaluator()
        with pytest.raises(ValueError, match="Invalid time"):
            evaluator.parse_time("")

    def test_parse_invalid_time_none(self):
        evaluator = ScheduleEvaluator()
        with pytest.raises(ValueError, match="Invalid time"):
            evaluator.parse_time(None)

    def test_parse_invalid_hour(self):
        evaluator = ScheduleEvaluator()
        with pytest.raises(ValueError, match="Invalid time"):
            evaluator.parse_time("25:00")

    def test_parse_invalid_minute(self):
        evaluator = ScheduleEvaluator()
        with pytest.raises(ValueError, match="Invalid time"):
            evaluator.parse_time("12:60")

    def test_parse_invalid_format(self):
        evaluator = ScheduleEvaluator()
        with pytest.raises(ValueError, match="Invalid time"):
            evaluator.parse_time("abc:def")


class TestIsTimeInRange:
    """Tests for is_time_in_range method."""

    def test_time_within_normal_range(self):
        evaluator = ScheduleEvaluator()
        current = time(12, 0)
        start = time(9, 0)
        end = time(17, 0)
        assert evaluator.is_time_in_range(current, start, end) is True

    def test_time_at_start_boundary(self):
        evaluator = ScheduleEvaluator()
        current = time(9, 0)
        start = time(9, 0)
        end = time(17, 0)
        assert evaluator.is_time_in_range(current, start, end) is True

    def test_time_at_end_boundary(self):
        evaluator = ScheduleEvaluator()
        current = time(17, 0)
        start = time(9, 0)
        end = time(17, 0)
        assert evaluator.is_time_in_range(current, start, end) is True

    def test_time_outside_range(self):
        evaluator = ScheduleEvaluator()
        current = time(8, 0)
        start = time(9, 0)
        end = time(17, 0)
        assert evaluator.is_time_in_range(current, start, end) is False

    def test_overnight_range_before_midnight(self):
        evaluator = ScheduleEvaluator()
        current = time(23, 0)
        start = time(22, 0)
        end = time(2, 0)
        assert evaluator.is_time_in_range(current, start, end) is True

    def test_overnight_range_after_midnight(self):
        evaluator = ScheduleEvaluator()
        current = time(1, 0)
        start = time(22, 0)
        end = time(2, 0)
        assert evaluator.is_time_in_range(current, start, end) is True

    def test_overnight_range_outside(self):
        evaluator = ScheduleEvaluator()
        current = time(12, 0)
        start = time(22, 0)
        end = time(2, 0)
        assert evaluator.is_time_in_range(current, start, end) is False


class TestShouldBlock:
    """Tests for should_block method."""

    def _mock_datetime(self, year, month, day, hour, minute):
        """Helper to create a mock datetime with timezone."""
        try:
            from zoneinfo import ZoneInfo
        except ImportError:
            from backports.zoneinfo import ZoneInfo
        tz = ZoneInfo("America/Mexico_City")
        return datetime(year, month, day, hour, minute, tzinfo=tz)

    def test_should_not_block_during_available_hours(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Wednesday at 10:00 (within 09:00-17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 10, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is False

    def test_should_block_before_available_hours(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Wednesday at 08:00 (before 09:00)
        mock_now = self._mock_datetime(2025, 11, 26, 8, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is True

    def test_should_block_after_available_hours(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Wednesday at 18:00 (after 17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 18, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is True

    def test_should_not_block_weekend(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Saturday at 15:00 (within 10:00-22:00)
        mock_now = self._mock_datetime(2025, 11, 29, 15, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is False

    def test_should_block_null_schedule(self, always_blocked_config):
        evaluator = ScheduleEvaluator()
        assert evaluator.should_block(always_blocked_config["schedule"]) is True

    def test_should_block_empty_schedule(self):
        evaluator = ScheduleEvaluator()
        assert evaluator.should_block({}) is True

    def test_should_block_no_available_hours(self):
        evaluator = ScheduleEvaluator()
        assert evaluator.should_block({"other_key": "value"}) is True

    def test_overnight_schedule_friday_night(self, overnight_schedule_config):
        evaluator = ScheduleEvaluator()
        # Friday at 23:00 (within 22:00-02:00)
        mock_now = self._mock_datetime(2025, 11, 28, 23, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(overnight_schedule_config["schedule"]) is False

    def test_overnight_schedule_saturday_early(self, overnight_schedule_config):
        evaluator = ScheduleEvaluator()
        # Saturday at 01:00 (still within Saturday's 22:00-02:00 window from previous night)
        mock_now = self._mock_datetime(2025, 11, 29, 1, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            # Saturday is in the days list, so 01:00 should be within the 22:00-02:00 range
            assert evaluator.should_block(overnight_schedule_config["schedule"]) is False


class TestTimezone:
    """Tests for timezone handling."""

    def test_valid_timezone(self):
        evaluator = ScheduleEvaluator("America/New_York")
        assert str(evaluator.tz) == "America/New_York"

    def test_default_timezone(self):
        evaluator = ScheduleEvaluator()
        assert str(evaluator.tz) == "UTC"

    def test_invalid_timezone(self):
        with pytest.raises(ValueError, match="Invalid timezone"):
            ScheduleEvaluator("Invalid/Timezone")

    def test_utc_timezone(self):
        evaluator = ScheduleEvaluator("UTC")
        assert str(evaluator.tz) == "UTC"


class TestGetCurrentTime:
    """Tests for _get_current_time method."""

    def test_returns_timezone_aware_datetime(self):
        evaluator = ScheduleEvaluator("UTC")
        current = evaluator._get_current_time()
        assert current.tzinfo is not None
        assert str(current.tzinfo) == "UTC"

    def test_respects_configured_timezone(self):
        evaluator = ScheduleEvaluator("America/New_York")
        current = evaluator._get_current_time()
        assert str(current.tzinfo) == "America/New_York"

    def test_returns_datetime_instance(self):
        evaluator = ScheduleEvaluator()
        current = evaluator._get_current_time()
        assert isinstance(current, datetime)


class TestShouldBlockDomain:
    """Tests for should_block_domain convenience wrapper."""

    def _mock_datetime(self, year, month, day, hour, minute):
        """Helper to create a mock datetime with timezone."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        return datetime(year, month, day, hour, minute, tzinfo=tz)

    def test_should_block_domain_with_schedule(self, sample_domain_config):
        """Test should_block_domain extracts schedule correctly."""
        evaluator = ScheduleEvaluator()
        # Wednesday at 10:00 (within 09:00-17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 10, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = evaluator.should_block_domain(sample_domain_config)
            assert result is False

    def test_should_block_domain_no_schedule(self):
        """Test should_block_domain with no schedule key."""
        evaluator = ScheduleEvaluator()
        domain_config = {"domain": "example.com"}
        result = evaluator.should_block_domain(domain_config)
        assert result is True  # No schedule = always blocked

    def test_should_block_domain_null_schedule(self, always_blocked_config):
        """Test should_block_domain with null schedule."""
        evaluator = ScheduleEvaluator()
        result = evaluator.should_block_domain(always_blocked_config)
        assert result is True

    def test_should_block_domain_outside_hours(self, sample_domain_config):
        """Test should_block_domain outside available hours."""
        evaluator = ScheduleEvaluator()
        # Wednesday at 08:00 (before 09:00)
        mock_now = self._mock_datetime(2025, 11, 26, 8, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            result = evaluator.should_block_domain(sample_domain_config)
            assert result is True


class TestGetBlockingStatus:
    """Tests for get_blocking_status method."""

    def _mock_datetime(self, year, month, day, hour, minute):
        """Helper to create a mock datetime with timezone."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("UTC")
        return datetime(year, month, day, hour, minute, tzinfo=tz)

    def test_status_includes_domain(self, sample_domain_config):
        """Test that status includes domain name."""
        evaluator = ScheduleEvaluator()
        status = evaluator.get_blocking_status(sample_domain_config)
        assert "domain" in status
        assert status["domain"] == "example.com"

    def test_status_includes_has_schedule_true(self, sample_domain_config):
        """Test has_schedule is True when schedule defined."""
        evaluator = ScheduleEvaluator()
        status = evaluator.get_blocking_status(sample_domain_config)
        assert "has_schedule" in status
        assert status["has_schedule"] is True

    def test_status_includes_has_schedule_false(self, always_blocked_config):
        """Test has_schedule is False when no schedule."""
        evaluator = ScheduleEvaluator()
        status = evaluator.get_blocking_status(always_blocked_config)
        assert status["has_schedule"] is False

    def test_status_includes_currently_blocked(self, sample_domain_config):
        """Test currently_blocked reflects schedule evaluation."""
        evaluator = ScheduleEvaluator()
        # Wednesday at 10:00 (within 09:00-17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 10, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            status = evaluator.get_blocking_status(sample_domain_config)
            assert "currently_blocked" in status
            assert status["currently_blocked"] is False

    def test_status_blocked_outside_hours(self, sample_domain_config):
        """Test currently_blocked is True outside available hours."""
        evaluator = ScheduleEvaluator()
        # Wednesday at 20:00 (after 17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 20, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            status = evaluator.get_blocking_status(sample_domain_config)
            assert status["currently_blocked"] is True

    def test_status_with_unknown_domain(self):
        """Test status with missing domain field."""
        evaluator = ScheduleEvaluator()
        config = {"schedule": None}
        status = evaluator.get_blocking_status(config)
        assert status["domain"] == "unknown"

    def test_status_returns_dict(self, sample_domain_config):
        """Test get_blocking_status returns a dictionary."""
        evaluator = ScheduleEvaluator()
        status = evaluator.get_blocking_status(sample_domain_config)
        assert isinstance(status, dict)
        assert len(status) == 3  # domain, currently_blocked, has_schedule


class TestShouldAllow:
    """Tests for should_allow method (inverse of should_block for allowlist)."""

    def _mock_datetime(self, year, month, day, hour, minute):
        """Create a mock datetime for testing."""
        from zoneinfo import ZoneInfo

        tz = ZoneInfo("America/Mexico_City")
        return datetime(year, month, day, hour, minute, tzinfo=tz)

    def test_should_allow_no_schedule(self):
        """Test that no schedule means always allow (True)."""
        evaluator = ScheduleEvaluator()
        assert evaluator.should_allow(None) is True
        assert evaluator.should_allow({}) is True
        assert evaluator.should_allow({"other_key": "value"}) is True

    def test_should_allow_empty_available_hours(self):
        """Test that empty available_hours means never allow (no available hours defined)."""
        evaluator = ScheduleEvaluator()
        schedule = {"available_hours": []}
        # Empty available_hours = no hours available = never in allowlist
        # This is consistent with blocklist behavior where empty = always blocked
        assert evaluator.should_allow(schedule) is False

    def test_should_allow_during_available_hours(self):
        """Test should_allow returns True during available hours."""
        evaluator = ScheduleEvaluator("America/Mexico_City")
        schedule = {
            "available_hours": [
                {
                    "days": ["wednesday"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        }
        # Wednesday at 10:00 - within available hours
        mock_now = self._mock_datetime(2025, 11, 26, 10, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_allow(schedule) is True

    def test_should_not_allow_outside_available_hours(self):
        """Test should_allow returns False outside available hours."""
        evaluator = ScheduleEvaluator("America/Mexico_City")
        schedule = {
            "available_hours": [
                {
                    "days": ["wednesday"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        }
        # Wednesday at 20:00 - outside available hours
        mock_now = self._mock_datetime(2025, 11, 26, 20, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_allow(schedule) is False

    def test_should_allow_overnight_range(self):
        """Test should_allow with overnight range (e.g., 20:00-02:00)."""
        evaluator = ScheduleEvaluator("America/Mexico_City")
        schedule = {
            "available_hours": [
                {
                    "days": ["friday", "saturday"],
                    "time_ranges": [{"start": "20:00", "end": "02:00"}],
                }
            ]
        }
        # Friday at 23:00 - within overnight range
        mock_now = self._mock_datetime(2025, 11, 28, 23, 0)  # Friday
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_allow(schedule) is True

        # Saturday at 01:00 - still within Friday's overnight range
        mock_now = self._mock_datetime(2025, 11, 29, 1, 0)  # Saturday early
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_allow(schedule) is True

    def test_should_allow_domain_wrapper(self):
        """Test should_allow_domain extracts schedule from config."""
        evaluator = ScheduleEvaluator()
        config = {"domain": "youtube.com", "schedule": None}
        assert evaluator.should_allow_domain(config) is True

        config_with_no_schedule_key = {"domain": "youtube.com"}
        assert evaluator.should_allow_domain(config_with_no_schedule_key) is True

    def test_should_allow_inverse_of_should_block(self):
        """Test that should_allow is inverse of should_block when schedule exists."""
        evaluator = ScheduleEvaluator("America/Mexico_City")
        schedule = {
            "available_hours": [
                {
                    "days": ["wednesday"],
                    "time_ranges": [{"start": "09:00", "end": "17:00"}],
                }
            ]
        }
        # Wednesday at 10:00 - within available hours
        mock_now = self._mock_datetime(2025, 11, 26, 10, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            should_block = evaluator.should_block(schedule)
            should_allow = evaluator.should_allow(schedule)
            # should_block=False means available, should_allow=True means in allowlist
            assert should_block is False
            assert should_allow is True

        # Wednesday at 20:00 - outside available hours
        mock_now = self._mock_datetime(2025, 11, 26, 20, 0)
        with patch("nextdns_blocker.scheduler.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            should_block = evaluator.should_block(schedule)
            should_allow = evaluator.should_allow(schedule)
            # should_block=True means blocked, should_allow=False means not in allowlist
            assert should_block is True
            assert should_allow is False
