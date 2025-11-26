"""Tests for ScheduleEvaluator class."""

import pytest
from datetime import time, datetime
from unittest.mock import patch

from nextdns_blocker import ScheduleEvaluator


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
        import pytz
        tz = pytz.timezone('America/Mexico_City')
        return tz.localize(datetime(year, month, day, hour, minute))

    def test_should_not_block_during_available_hours(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Wednesday at 10:00 (within 09:00-17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 10, 0)
        with patch('nextdns_blocker.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is False

    def test_should_block_before_available_hours(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Wednesday at 08:00 (before 09:00)
        mock_now = self._mock_datetime(2025, 11, 26, 8, 0)
        with patch('nextdns_blocker.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is True

    def test_should_block_after_available_hours(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Wednesday at 18:00 (after 17:00)
        mock_now = self._mock_datetime(2025, 11, 26, 18, 0)
        with patch('nextdns_blocker.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(sample_domain_config["schedule"]) is True

    def test_should_not_block_weekend(self, sample_domain_config):
        evaluator = ScheduleEvaluator()
        # Saturday at 15:00 (within 10:00-22:00)
        mock_now = self._mock_datetime(2025, 11, 29, 15, 0)
        with patch('nextdns_blocker.datetime') as mock_dt:
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
        with patch('nextdns_blocker.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            assert evaluator.should_block(overnight_schedule_config["schedule"]) is False

    def test_overnight_schedule_saturday_early(self, overnight_schedule_config):
        evaluator = ScheduleEvaluator()
        # Saturday at 01:00 (still within Saturday's 22:00-02:00 window from previous night)
        mock_now = self._mock_datetime(2025, 11, 29, 1, 0)
        with patch('nextdns_blocker.datetime') as mock_dt:
            mock_dt.now.return_value = mock_now
            # Saturday is in the days list, so 01:00 should be within the 22:00-02:00 range
            assert evaluator.should_block(overnight_schedule_config["schedule"]) is False


class TestTimezone:
    """Tests for timezone handling."""

    def test_valid_timezone(self):
        evaluator = ScheduleEvaluator("America/New_York")
        assert evaluator.tz.zone == "America/New_York"

    def test_default_timezone(self):
        evaluator = ScheduleEvaluator()
        assert evaluator.tz.zone == "America/Mexico_City"

    def test_invalid_timezone(self):
        with pytest.raises(ValueError, match="Invalid timezone"):
            ScheduleEvaluator("Invalid/Timezone")

    def test_utc_timezone(self):
        evaluator = ScheduleEvaluator("UTC")
        assert evaluator.tz.zone == "UTC"
