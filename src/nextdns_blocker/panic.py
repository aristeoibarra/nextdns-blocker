"""Panic mode state management for NextDNS Blocker.

Panic mode provides an emergency lockdown that:
- Immediately blocks all configured domains
- Hides dangerous commands from the CLI
- Prevents unblocks and schedule overrides
- Cannot be disabled (must wait for expiration)
"""

import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from .common import (
    audit_log,
    ensure_naive_datetime,
    get_log_dir,
    read_secure_file,
    write_secure_file,
)

logger = logging.getLogger(__name__)

# Minimum panic duration in minutes (covers typical craving window)
MIN_PANIC_DURATION_MINUTES = 15

# Commands to hide during panic mode (top-level commands)
# Note: "allow" is included because allowlist has highest priority in NextDNS
# and could bypass all blocks during panic mode (security risk)
DANGEROUS_COMMANDS = frozenset(
    {
        "unblock",
        "pause",
        "resume",
        "disallow",
        "allow",
    }
)

# Subcommands to hide during panic mode (parent -> {subcommands})
DANGEROUS_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "config": frozenset({"edit"}),
    "pending": frozenset({"cancel"}),
    "watchdog": frozenset({"disable"}),
}

# Duration parsing pattern (Nm, Nh, Nd)
DURATION_PATTERN = re.compile(r"^(\d+)([mhd])$", re.IGNORECASE)


def get_panic_file() -> Path:
    """Get the panic state file path."""
    return get_log_dir() / ".panic"


def _get_panic_info() -> tuple[bool, Optional[datetime]]:
    """
    Get panic state information.

    Returns:
        Tuple of (is_panic_active, panic_until_datetime).
        If not active or error, returns (False, None).

    Note:
        Uses missing_ok=True for unlink to handle race conditions where
        another process may have already cleaned up the file.
    """
    panic_file = get_panic_file()
    content = read_secure_file(panic_file)
    if not content:
        return False, None

    try:
        panic_until = ensure_naive_datetime(datetime.fromisoformat(content))
        if datetime.now() < panic_until:
            return True, panic_until
        # Expired, clean up
        panic_file.unlink(missing_ok=True)
        return False, None
    except ValueError:
        # Invalid content, clean up
        logger.warning(f"Invalid panic file content, removing: {content[:50]}")
        panic_file.unlink(missing_ok=True)
        return False, None


def is_panic_mode() -> bool:
    """Check if panic mode is currently active."""
    active, _ = _get_panic_info()
    return active


def get_panic_remaining() -> Optional[str]:
    """
    Get remaining panic time as human-readable string.

    Returns:
        Human-readable remaining time (e.g., "2h 15m"), or None if not active.
    """
    active, panic_until = _get_panic_info()
    if not active or panic_until is None:
        return None

    remaining = panic_until - datetime.now()
    # Use max(0, ...) to handle any microsecond-level timing edge cases
    # where remaining could be slightly negative due to timing between checks
    total_seconds = max(0, int(remaining.total_seconds()))

    if total_seconds <= 0:
        return "< 1m"

    total_mins = total_seconds // 60
    hours = total_mins // 60
    mins = total_mins % 60

    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m" if mins > 0 else "< 1m"


def get_panic_until() -> Optional[datetime]:
    """Get the datetime when panic mode expires."""
    _, panic_until = _get_panic_info()
    return panic_until


def set_panic(minutes: int) -> datetime:
    """
    Activate panic mode for specified minutes.

    Args:
        minutes: Duration in minutes (minimum MIN_PANIC_DURATION_MINUTES)

    Returns:
        The datetime when panic mode will expire

    Raises:
        ValueError: If minutes is less than minimum
    """
    if minutes < MIN_PANIC_DURATION_MINUTES:
        raise ValueError(f"Minimum panic duration is {MIN_PANIC_DURATION_MINUTES} minutes")

    panic_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
    write_secure_file(get_panic_file(), panic_until.isoformat())
    audit_log("PANIC_ACTIVATE", f"{minutes} minutes until {panic_until.isoformat()}")
    return panic_until


def extend_panic(minutes: int) -> Optional[datetime]:
    """
    Extend panic mode expiration.

    Args:
        minutes: Additional minutes to add

    Returns:
        New expiration datetime, or None if panic mode not active
    """
    active, current_until = _get_panic_info()
    if not active or current_until is None:
        return None

    new_until = current_until + timedelta(minutes=minutes)
    write_secure_file(get_panic_file(), new_until.isoformat())
    audit_log("PANIC_EXTEND", f"+{minutes} minutes, new expiry: {new_until.isoformat()}")
    return new_until


def try_activate_or_extend(minutes: int) -> tuple[datetime, bool]:
    """
    Try to activate panic mode or extend if already active with longer duration.

    Args:
        minutes: Duration in minutes

    Returns:
        Tuple of (expiration_datetime, was_extended)
        was_extended is True if this extended an existing panic, False if new activation

    Raises:
        ValueError: If minutes is less than minimum or less than current remaining time
    """
    if minutes < MIN_PANIC_DURATION_MINUTES:
        raise ValueError(f"Minimum panic duration is {MIN_PANIC_DURATION_MINUTES} minutes")

    active, current_until = _get_panic_info()

    if not active or current_until is None:
        # New activation
        return set_panic(minutes), False

    # Already active - check if new duration would extend
    new_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)

    if new_until <= current_until:
        # Would shorten - not allowed
        remaining_mins = int((current_until - datetime.now()).total_seconds() // 60)
        raise ValueError(
            f"Panic mode already active ({remaining_mins}m remaining). "
            f"Can only extend, not shorten. Use: panic extend <duration>"
        )

    # Extend to new time
    write_secure_file(get_panic_file(), new_until.isoformat())
    audit_log(
        "PANIC_EXTEND",
        f"Extended to {minutes} minutes, new expiry: {new_until.isoformat()}",
    )
    return new_until, True


def parse_duration(duration_str: str) -> int:
    """
    Parse duration string to minutes.

    Supports formats: Nm (minutes), Nh (hours), Nd (days)
    Examples: "30m", "2h", "1d"

    Args:
        duration_str: Duration string

    Returns:
        Duration in minutes

    Raises:
        ValueError: If format is invalid
    """
    match = DURATION_PATTERN.match(duration_str.strip())
    if not match:
        raise ValueError(
            f"Invalid duration format: {duration_str}. "
            f"Use Nm (minutes), Nh (hours), or Nd (days). Examples: 30m, 2h, 1d"
        )

    value = int(match.group(1))
    unit = match.group(2).lower()

    # Validate value is positive
    if value <= 0:
        raise ValueError(f"Duration must be a positive number, got: {value}")

    if unit == "m":
        return value
    elif unit == "h":
        return value * 60
    elif unit == "d":
        return value * 60 * 24

    # Should never reach here due to regex
    raise ValueError(f"Unknown unit: {unit}")


def is_command_hidden(command_name: str) -> bool:
    """
    Check if a top-level command should be hidden during panic mode.

    Args:
        command_name: Command name (e.g., "unblock", "pause")

    Returns:
        True if command should be hidden during panic mode
    """
    if not is_panic_mode():
        return False
    return command_name in DANGEROUS_COMMANDS


def is_subcommand_hidden(parent_command: str, subcommand: str) -> bool:
    """
    Check if a subcommand should be hidden during panic mode.

    Args:
        parent_command: Parent command name (e.g., "config", "pending")
        subcommand: Subcommand name (e.g., "edit", "cancel")

    Returns:
        True if subcommand should be hidden during panic mode
    """
    if not is_panic_mode():
        return False

    hidden_subs = DANGEROUS_SUBCOMMANDS.get(parent_command, frozenset())
    return subcommand in hidden_subs
