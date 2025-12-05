"""Schedule evaluation for time-based domain blocking."""

from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .common import DAYS_MAP


class ScheduleEvaluator:
    """Evaluates domain schedules to determine if a domain should be blocked."""

    def __init__(self, timezone_str: str = "UTC") -> None:
        """
        Initialize the schedule evaluator.

        Args:
            timezone_str: Timezone string (e.g., 'America/Mexico_City')
                         Defaults to 'UTC'

        Raises:
            ValueError: If timezone is invalid
        """
        try:
            self.tz = ZoneInfo(timezone_str)
        except KeyError:
            raise ValueError(f"Invalid timezone: {timezone_str}")

    def _get_current_time(self) -> datetime:
        """Get current time in the configured timezone."""
        return datetime.now(self.tz)

    def parse_time(self, time_str: Optional[str]) -> time:
        """
        Parse a time string (HH:MM) into a time object.

        Args:
            time_str: Time string in HH:MM format

        Returns:
            time object

        Raises:
            ValueError: If time format is invalid
        """
        if not time_str or not isinstance(time_str, str):
            raise ValueError(f"Invalid time format: {time_str}")

        if ":" not in time_str:
            raise ValueError(f"Invalid time format: {time_str}")

        try:
            parts = time_str.split(":")
            if len(parts) != 2:
                raise ValueError(f"Invalid time format: {time_str}")

            hours = int(parts[0])
            minutes = int(parts[1])

            if not (0 <= hours <= 23) or not (0 <= minutes <= 59):
                raise ValueError(f"Invalid time format: {time_str}")

            return time(hours, minutes)
        except (ValueError, TypeError):
            raise ValueError(f"Invalid time format: {time_str}")

    def is_time_in_range(self, current: time, start: time, end: time) -> bool:
        """
        Check if current time is within a time range.

        Handles overnight ranges (e.g., 22:00 - 02:00).

        Args:
            current: Current time to check
            start: Range start time
            end: Range end time

        Returns:
            True if current is within range
        """
        if start <= end:
            # Normal range (e.g., 09:00 - 17:00)
            return start <= current <= end
        else:
            # Overnight range (e.g., 22:00 - 02:00)
            return current >= start or current <= end

    def _check_overnight_yesterday(self, now: datetime, schedule: dict[str, Any]) -> bool:
        """
        Check if we're in an overnight schedule from yesterday.

        For example, if it's Saturday 01:00 and Friday had 22:00-02:00 schedule,
        we should check if we're in that overnight window.

        Args:
            now: Current datetime
            schedule: Schedule configuration

        Returns:
            True if in yesterday's overnight window
        """
        yesterday = now - timedelta(days=1)
        yesterday_day = list(DAYS_MAP.keys())[yesterday.weekday()]
        current_time = now.time()

        for block in schedule.get("available_hours", []):
            days = [d.lower() for d in block.get("days", [])]
            if yesterday_day not in days:
                continue

            for time_range in block.get("time_ranges", []):
                start = self.parse_time(time_range["start"])
                end = self.parse_time(time_range["end"])

                # Only check overnight ranges
                if start > end:
                    # We're in the "after midnight" portion
                    if current_time <= end:
                        return True

        return False

    def should_block(self, schedule: Optional[dict[str, Any]]) -> bool:
        """
        Determine if a domain should be blocked based on its schedule.

        Args:
            schedule: Schedule configuration (the 'schedule' field from domain config)

        Returns:
            True if domain should be blocked, False if available
        """
        # No schedule = always blocked
        if not schedule or "available_hours" not in schedule:
            return True

        now = self._get_current_time()
        current_day = list(DAYS_MAP.keys())[now.weekday()]
        current_time = now.time()

        # Check today's schedule
        for block in schedule.get("available_hours", []):
            days = [d.lower() for d in block.get("days", [])]
            if current_day not in days:
                continue

            for time_range in block.get("time_ranges", []):
                start = self.parse_time(time_range["start"])
                end = self.parse_time(time_range["end"])

                if self.is_time_in_range(current_time, start, end):
                    return False  # Available, don't block

        # Check if we're in yesterday's overnight window
        if self._check_overnight_yesterday(now, schedule):
            return False  # Still in yesterday's window, don't block

        return True  # Outside all available windows, block

    def should_block_domain(self, domain_config: dict[str, Any]) -> bool:
        """
        Determine if a domain should be blocked based on its config.

        This is a convenience wrapper that extracts the schedule from domain_config.

        Args:
            domain_config: Domain configuration containing schedule

        Returns:
            True if domain should be blocked, False if available
        """
        return self.should_block(domain_config.get("schedule"))

    def get_next_change(self, domain_config: dict[str, Any]) -> Optional[dict[str, Any]]:
        """
        Get information about the next schedule change for a domain.

        Args:
            domain_config: Domain configuration containing schedule

        Returns:
            Dictionary with 'action' (block/unblock) and 'time' (datetime),
            or None if no schedule
        """
        schedule = domain_config.get("schedule")
        if not schedule or "available_hours" not in schedule:
            return None

        currently_blocked = self.should_block(schedule)

        return {
            "currently_blocked": currently_blocked,
            "domain": domain_config.get("domain", "unknown"),
        }
