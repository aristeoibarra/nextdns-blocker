"""Schedule evaluation for time-based domain blocking."""

from datetime import datetime, time, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo

from .common import WEEKDAY_TO_DAY


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
        except KeyError as e:
            raise ValueError(f"Invalid timezone: {timezone_str}") from e

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
        # Validate input type and presence
        if time_str is None:
            raise ValueError("Invalid time format: None")
        if not isinstance(time_str, str):
            raise ValueError(f"Invalid time format: expected string, got {type(time_str).__name__}")
        if not time_str:
            raise ValueError("Invalid time format: empty string")

        # Validate format before splitting
        if ":" not in time_str:
            raise ValueError(f"Invalid time format: {time_str}")

        parts = time_str.split(":")
        if len(parts) != 2:
            raise ValueError(f"Invalid time format: {time_str}")

        # Validate that parts are ASCII digits only (isdigit accepts Unicode digits)
        hour_part, minute_part = parts[0], parts[1]
        if not hour_part or not minute_part:
            raise ValueError(f"Invalid time format: {time_str}")
        if not (hour_part.isascii() and hour_part.isdigit()):
            raise ValueError(f"Invalid time format: {time_str}")
        if not (minute_part.isascii() and minute_part.isdigit()):
            raise ValueError(f"Invalid time format: {time_str}")

        hours = int(hour_part)
        minutes = int(minute_part)

        if not (0 <= hours <= 23) or not (0 <= minutes <= 59):
            raise ValueError(f"Invalid time format: {time_str}")

        return time(hours, minutes)

    def is_time_in_range(self, current: time, start: time, end: time) -> bool:
        """
        Check if current time is within a time range.

        Handles overnight ranges (e.g., 22:00 - 02:00) where start > end.
        For same-day ranges, start must be <= end (e.g., 09:00 - 17:00).

        Note: When start == end, this represents a single point in time,
        so current must exactly match to be "in range".

        Args:
            current: Current time to check
            start: Range start time
            end: Range end time

        Returns:
            True if current is within range
        """
        if start <= end:
            # Normal range (e.g., 09:00 - 17:00) or single point (start == end)
            return start <= current <= end
        else:
            # Overnight range (e.g., 22:00 - 02:00)
            # Current is in range if it's after start OR before/at end
            return current >= start or current <= end

    def _check_overnight_yesterday(self, now: datetime, schedule: dict[str, Any]) -> bool:
        """
        Check if current time falls within an overnight schedule that started yesterday.

        Overnight schedules are time ranges where the end time is before the start time,
        indicating the range spans midnight. For example:
        - Schedule: Friday 22:00 - 02:00
        - This means Friday 22:00 to Saturday 02:00

        When it's Saturday 01:00, we need to check if Friday had an overnight schedule
        that extends into Saturday morning.

        Algorithm:
        1. Get yesterday's day name (e.g., if today is Saturday, yesterday is Friday)
        2. For each schedule block that includes yesterday:
           a. Check if any time range is an overnight range (start > end)
           b. If so, check if current time is in the "after midnight" portion (≤ end)
        3. Return True if we're in any such overnight window

        Example:
            now = Saturday 01:00
            schedule has Friday with 22:00-02:00
            → yesterday_day = "friday"
            → start=22:00, end=02:00, start > end (overnight)
            → current_time=01:00 ≤ end=02:00
            → Return True (still in Friday's window)

        Args:
            now: Current datetime with timezone
            schedule: Schedule configuration containing 'available_hours'

        Returns:
            True if current time is within yesterday's overnight window
        """
        yesterday = now - timedelta(days=1)
        yesterday_day = WEEKDAY_TO_DAY[yesterday.weekday()]
        current_time = now.time()

        for block in schedule.get("available_hours", []):
            days = [d.lower() for d in block.get("days", [])]
            if yesterday_day not in days:
                continue

            for time_range in block.get("time_ranges", []):
                start = self.parse_time(time_range["start"])
                end = self.parse_time(time_range["end"])

                # Only check overnight ranges (where start > end indicates midnight crossing)
                if start > end:
                    # Current time is in the "after midnight" portion if ≤ end
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
        current_day = WEEKDAY_TO_DAY[now.weekday()]
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

    def should_allow(self, schedule: Optional[dict[str, Any]]) -> bool:
        """
        Determine if a domain should be in the allowlist based on its schedule.

        This is the inverse logic of should_block, used for allowlist entries.
        - No schedule = always in allowlist (return True)
        - Has schedule = only in allowlist during available_hours

        Args:
            schedule: Schedule configuration (the 'schedule' field from allowlist config)

        Returns:
            True if domain should be in allowlist, False if not
        """
        # No schedule = always in allowlist
        if not schedule or "available_hours" not in schedule:
            return True

        # Has schedule = only allow during available hours (inverse of should_block)
        # should_block returns True when OUTSIDE available hours
        # so we return the opposite: True when INSIDE available hours
        return not self.should_block(schedule)

    def should_allow_domain(self, domain_config: dict[str, Any]) -> bool:
        """
        Determine if a domain should be in the allowlist based on its config.

        This is a convenience wrapper that extracts the schedule from domain_config.

        Args:
            domain_config: Allowlist domain configuration containing schedule

        Returns:
            True if domain should be in allowlist, False if not
        """
        return self.should_allow(domain_config.get("schedule"))

    def get_blocking_status(self, domain_config: dict[str, Any]) -> dict[str, Any]:
        """
        Get the current blocking status for a domain.

        Args:
            domain_config: Domain configuration containing schedule

        Returns:
            Dictionary with:
                - 'domain': Domain name
                - 'currently_blocked': Whether the domain is currently blocked
                - 'has_schedule': Whether the domain has a schedule defined
        """
        schedule = domain_config.get("schedule")
        has_schedule = schedule is not None and "available_hours" in schedule

        return {
            "domain": domain_config.get("domain", "unknown"),
            "currently_blocked": self.should_block(schedule),
            "has_schedule": has_schedule,
        }
