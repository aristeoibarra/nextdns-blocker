"""Protection module for addiction safety features.

This module provides:
- Locked categories/services that cannot be easily removed
- Unlock request system with configurable delay
- Auto-panic mode for scheduled protection periods
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

from .common import audit_log, get_log_dir, read_secure_file, write_secure_file

logger = logging.getLogger(__name__)

# Default unlock delay in hours
DEFAULT_UNLOCK_DELAY_HOURS = 48

# Minimum unlock delay (prevent bypassing with delay=0)
MIN_UNLOCK_DELAY_HOURS = 24


def get_unlock_requests_file() -> Path:
    """Get the unlock requests state file path."""
    return get_log_dir() / "unlock_requests.json"


def _load_unlock_requests() -> list[dict[str, Any]]:
    """Load pending unlock requests from file."""
    requests_file = get_unlock_requests_file()
    content = read_secure_file(requests_file)
    if not content:
        return []
    try:
        data = json.loads(content)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        logger.warning("Invalid unlock requests file, resetting")
        return []


def _save_unlock_requests(requests: list[dict[str, Any]]) -> None:
    """Save unlock requests to file."""
    write_secure_file(get_unlock_requests_file(), json.dumps(requests, indent=2))


def is_locked(item: dict[str, Any]) -> bool:
    """Check if an item (category/service/domain) is locked.

    An item is considered locked if:
    - It has "locked": true
    - It has "unblock_delay": "never"
    """
    if item.get("locked") is True:
        return True
    if item.get("unblock_delay") == "never":
        return True
    return False


def get_locked_ids(config: dict[str, Any], item_type: str) -> set[str]:
    """Get set of locked IDs for a given type.

    Args:
        config: Full config dictionary
        item_type: One of 'categories', 'services', 'domains'

    Returns:
        Set of locked item IDs
    """
    locked = set()

    if item_type == "categories":
        # Check nextdns.categories
        nextdns = config.get("nextdns", {})
        for cat in nextdns.get("categories", []):
            if is_locked(cat):
                locked.add(cat.get("id", ""))

    elif item_type == "services":
        # Check nextdns.services
        nextdns = config.get("nextdns", {})
        for svc in nextdns.get("services", []):
            if is_locked(svc):
                locked.add(svc.get("id", ""))

    elif item_type == "domains":
        # Check blocklist
        for domain in config.get("blocklist", []):
            if is_locked(domain):
                locked.add(domain.get("domain", ""))
        # Check categories (custom domain groups)
        for cat in config.get("categories", []):
            if is_locked(cat):
                for domain in cat.get("domains", []):
                    locked.add(domain)

    return locked


def validate_no_locked_removal(old_config: dict[str, Any], new_config: dict[str, Any]) -> list[str]:
    """Validate that no locked items are being removed.

    Args:
        old_config: Current configuration
        new_config: Proposed new configuration

    Returns:
        List of error messages for locked items being removed
    """
    errors = []

    for item_type in ["categories", "services", "domains"]:
        old_locked = get_locked_ids(old_config, item_type)
        new_ids = set()

        if item_type == "categories":
            for cat in new_config.get("nextdns", {}).get("categories", []):
                new_ids.add(cat.get("id", ""))
        elif item_type == "services":
            for svc in new_config.get("nextdns", {}).get("services", []):
                new_ids.add(svc.get("id", ""))
        elif item_type == "domains":
            for domain in new_config.get("blocklist", []):
                new_ids.add(domain.get("domain", ""))
            for cat in new_config.get("categories", []):
                for domain in cat.get("domains", []):
                    new_ids.add(domain)

        removed_locked = old_locked - new_ids
        for item_id in removed_locked:
            errors.append(
                f"Cannot remove locked {item_type[:-1]} '{item_id}'. "
                f"Use 'ndb protection unlock-request {item_id}' to request removal "
                f"with a {DEFAULT_UNLOCK_DELAY_HOURS}h delay."
            )

    return errors


def validate_no_locked_weakening(
    old_config: dict[str, Any], new_config: dict[str, Any]
) -> list[str]:
    """Validate that locked items are not being weakened.

    Weakening includes:
    - Changing locked: true to locked: false
    - Changing unblock_delay: "never" to something else
    - Removing the locked field entirely

    Args:
        old_config: Current configuration
        new_config: Proposed new configuration

    Returns:
        List of error messages for locked items being weakened
    """
    errors = []

    # Check nextdns.categories
    old_categories = {c["id"]: c for c in old_config.get("nextdns", {}).get("categories", [])}
    new_categories = {c["id"]: c for c in new_config.get("nextdns", {}).get("categories", [])}

    for cat_id, old_cat in old_categories.items():
        if not is_locked(old_cat):
            continue
        new_cat = new_categories.get(cat_id)
        if new_cat and not is_locked(new_cat):
            errors.append(
                f"Cannot weaken protection for category '{cat_id}'. It is marked as locked."
            )

    # Check nextdns.services
    old_services = {s["id"]: s for s in old_config.get("nextdns", {}).get("services", [])}
    new_services = {s["id"]: s for s in new_config.get("nextdns", {}).get("services", [])}

    for svc_id, old_svc in old_services.items():
        if not is_locked(old_svc):
            continue
        new_svc = new_services.get(svc_id)
        if new_svc and not is_locked(new_svc):
            errors.append(
                f"Cannot weaken protection for service '{svc_id}'. It is marked as locked."
            )

    return errors


def create_unlock_request(
    item_type: str,
    item_id: str,
    delay_hours: int = DEFAULT_UNLOCK_DELAY_HOURS,
    reason: Optional[str] = None,
) -> dict[str, Any]:
    """Create a pending unlock request.

    Args:
        item_type: Type of item ('category', 'service', 'domain')
        item_id: ID of the item to unlock
        delay_hours: Hours until the request can be executed
        reason: Optional reason for the request

    Returns:
        The created unlock request
    """
    # Enforce minimum delay
    delay_hours = max(delay_hours, MIN_UNLOCK_DELAY_HOURS)

    request_id = str(uuid4())[:12]
    execute_at = datetime.now() + timedelta(hours=delay_hours)

    request = {
        "id": request_id,
        "item_type": item_type,
        "item_id": item_id,
        "created_at": datetime.now().isoformat(),
        "execute_at": execute_at.isoformat(),
        "delay_hours": delay_hours,
        "reason": reason,
        "status": "pending",
    }

    requests = _load_unlock_requests()
    requests.append(request)
    _save_unlock_requests(requests)

    audit_log("UNLOCK_REQUEST", f"{item_type}:{item_id} scheduled for {execute_at.isoformat()}")

    return request


def cancel_unlock_request(request_id: str) -> bool:
    """Cancel a pending unlock request.

    Args:
        request_id: ID of the request to cancel (can be partial)

    Returns:
        True if request was found and cancelled
    """
    requests = _load_unlock_requests()

    for i, req in enumerate(requests):
        if req["id"].startswith(request_id) and req["status"] == "pending":
            requests[i]["status"] = "cancelled"
            requests[i]["cancelled_at"] = datetime.now().isoformat()
            _save_unlock_requests(requests)
            audit_log("UNLOCK_CANCEL", f"{req['item_type']}:{req['item_id']}")
            return True

    return False


def get_pending_unlock_requests() -> list[dict[str, Any]]:
    """Get all pending unlock requests."""
    requests = _load_unlock_requests()
    return [r for r in requests if r["status"] == "pending"]


def get_executable_unlock_requests() -> list[dict[str, Any]]:
    """Get unlock requests that are ready to execute."""
    now = datetime.now()
    requests = _load_unlock_requests()

    executable = []
    for req in requests:
        if req["status"] != "pending":
            continue
        execute_at = datetime.fromisoformat(req["execute_at"])
        if now >= execute_at:
            executable.append(req)

    return executable


def execute_unlock_request(request_id: str, config_path: Path) -> bool:
    """Execute an unlock request by modifying the config.

    Args:
        request_id: ID of the request to execute
        config_path: Path to config.json

    Returns:
        True if successfully executed
    """
    requests = _load_unlock_requests()

    request = None
    for req in requests:
        if req["id"] == request_id and req["status"] == "pending":
            request = req
            break

    if not request:
        return False

    # Check if delay has passed
    execute_at = datetime.fromisoformat(request["execute_at"])
    if datetime.now() < execute_at:
        logger.warning(f"Request {request_id} not yet executable")
        return False

    # Load config and remove the locked item
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

        item_type = request["item_type"]
        item_id = request["item_id"]

        if item_type == "category":
            categories = config.get("nextdns", {}).get("categories", [])
            config["nextdns"]["categories"] = [c for c in categories if c.get("id") != item_id]
        elif item_type == "service":
            services = config.get("nextdns", {}).get("services", [])
            config["nextdns"]["services"] = [s for s in services if s.get("id") != item_id]

        # Write updated config
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        # Mark request as executed
        for i, req in enumerate(requests):
            if req["id"] == request_id:
                requests[i]["status"] = "executed"
                requests[i]["executed_at"] = datetime.now().isoformat()
                break

        _save_unlock_requests(requests)
        audit_log("UNLOCK_EXECUTE", f"{item_type}:{item_id}")

        return True

    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to execute unlock request: {e}")
        return False


# =============================================================================
# AUTO-PANIC MODE
# =============================================================================


def is_auto_panic_time(config: dict[str, Any]) -> bool:
    """Check if current time falls within auto-panic schedule.

    Args:
        config: Config dictionary with protection.auto_panic settings

    Returns:
        True if auto-panic should be active now
    """
    protection = config.get("protection", {})
    auto_panic = protection.get("auto_panic", {})

    if not auto_panic.get("enabled", False):
        return False

    schedule = auto_panic.get("schedule", {})
    start_str = schedule.get("start", "23:00")
    end_str = schedule.get("end", "06:00")

    # Parse times
    start_h, start_m = map(int, start_str.split(":"))
    end_h, end_m = map(int, end_str.split(":"))

    start_mins = start_h * 60 + start_m
    end_mins = end_h * 60 + end_m

    now = datetime.now()
    current_mins = now.hour * 60 + now.minute

    # Check if today is in the active days
    days = auto_panic.get("days", [])
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    current_day = day_names[now.weekday()]

    if days and current_day not in days:
        return False

    # Handle overnight ranges (e.g., 23:00 - 06:00)
    if start_mins > end_mins:
        # Overnight: active if current >= start OR current < end
        return current_mins >= start_mins or current_mins < end_mins
    else:
        # Same day: active if start <= current < end
        return start_mins <= current_mins < end_mins


def can_disable_auto_panic(config: dict[str, Any]) -> bool:
    """Check if auto-panic can be disabled.

    Args:
        config: Config dictionary

    Returns:
        True if auto-panic can be disabled (cannot_disable is False or not set)
    """
    protection = config.get("protection", {})
    auto_panic = protection.get("auto_panic", {})
    return not auto_panic.get("cannot_disable", False)


def validate_protection_config(protection: dict[str, Any]) -> list[str]:
    """Validate the protection section of config.

    Args:
        protection: The protection config dict

    Returns:
        List of validation errors
    """
    errors = []

    if not isinstance(protection, dict):
        return ["'protection' must be an object"]

    # Validate unlock_delay_hours
    delay = protection.get("unlock_delay_hours")
    if delay is not None:
        if not isinstance(delay, int) or delay < MIN_UNLOCK_DELAY_HOURS:
            errors.append(
                f"protection.unlock_delay_hours must be an integer >= {MIN_UNLOCK_DELAY_HOURS}"
            )

    # Validate auto_panic
    auto_panic = protection.get("auto_panic")
    if auto_panic is not None:
        if not isinstance(auto_panic, dict):
            errors.append("protection.auto_panic must be an object")
        else:
            # Validate enabled
            if "enabled" in auto_panic and not isinstance(auto_panic["enabled"], bool):
                errors.append("protection.auto_panic.enabled must be a boolean")

            # Validate cannot_disable
            if "cannot_disable" in auto_panic and not isinstance(
                auto_panic["cannot_disable"], bool
            ):
                errors.append("protection.auto_panic.cannot_disable must be a boolean")

            # Validate schedule
            schedule = auto_panic.get("schedule")
            if schedule is not None:
                if not isinstance(schedule, dict):
                    errors.append("protection.auto_panic.schedule must be an object")
                else:
                    for key in ["start", "end"]:
                        time_val = schedule.get(key)
                        if time_val is not None:
                            if not isinstance(time_val, str):
                                errors.append(
                                    f"protection.auto_panic.schedule.{key} must be a string"
                                )
                            elif not _is_valid_time(time_val):
                                errors.append(
                                    f"protection.auto_panic.schedule.{key} must be HH:MM format"
                                )

            # Validate days
            days = auto_panic.get("days")
            if days is not None:
                valid_days = {
                    "monday",
                    "tuesday",
                    "wednesday",
                    "thursday",
                    "friday",
                    "saturday",
                    "sunday",
                }
                if not isinstance(days, list):
                    errors.append("protection.auto_panic.days must be an array")
                else:
                    for day in days:
                        if day.lower() not in valid_days:
                            errors.append(f"protection.auto_panic.days: invalid day '{day}'")

    return errors


def _is_valid_time(time_str: str) -> bool:
    """Validate HH:MM time format."""
    import re

    if not re.match(r"^\d{2}:\d{2}$", time_str):
        return False
    try:
        h, m = map(int, time_str.split(":"))
        return 0 <= h <= 23 and 0 <= m <= 59
    except ValueError:
        return False


# =============================================================================
# PIN PROTECTION
# =============================================================================

# PIN configuration
PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 32
PIN_SESSION_DURATION_MINUTES = 30
PIN_MAX_ATTEMPTS = 3
PIN_LOCKOUT_MINUTES = 15
PIN_HASH_ITERATIONS = 600_000  # OWASP recommendation for PBKDF2-SHA256

# Delay for PIN removal (hours) - prevents impulsive disabling
PIN_REMOVAL_DELAY_HOURS = 24


def get_pin_hash_file() -> Path:
    """Get the PIN hash file path."""
    return get_log_dir() / ".pin_hash"


def get_pin_session_file() -> Path:
    """Get the PIN session file path."""
    return get_log_dir() / ".pin_session"


def get_pin_attempts_file() -> Path:
    """Get the PIN failed attempts file path."""
    return get_log_dir() / ".pin_attempts"


def is_pin_enabled() -> bool:
    """Check if PIN protection is enabled."""
    pin_file = get_pin_hash_file()
    content = read_secure_file(pin_file)
    return content is not None and len(content) > 0


def _hash_pin(pin: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """
    Hash a PIN using PBKDF2-SHA256.

    Args:
        pin: The PIN to hash
        salt: Optional salt (generated if not provided)

    Returns:
        Tuple of (hash_hex, salt_bytes)
    """
    import hashlib
    import secrets

    if salt is None:
        salt = secrets.token_bytes(32)

    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        PIN_HASH_ITERATIONS,
    )

    return hash_bytes.hex(), salt


def set_pin(pin: str) -> bool:
    """
    Set or update the PIN.

    Args:
        pin: The new PIN (must be PIN_MIN_LENGTH to PIN_MAX_LENGTH chars)

    Returns:
        True if PIN was set successfully

    Raises:
        ValueError: If PIN doesn't meet requirements
    """
    if len(pin) < PIN_MIN_LENGTH:
        raise ValueError(f"PIN must be at least {PIN_MIN_LENGTH} characters")
    if len(pin) > PIN_MAX_LENGTH:
        raise ValueError(f"PIN must be at most {PIN_MAX_LENGTH} characters")

    hash_hex, salt = _hash_pin(pin)

    # Store as: salt_hex:hash_hex
    content = f"{salt.hex()}:{hash_hex}"
    write_secure_file(get_pin_hash_file(), content)

    # Clear any existing session and attempts
    _clear_pin_session()
    _clear_pin_attempts()

    audit_log("PIN_SET", "PIN protection enabled")
    return True


def verify_pin(pin: str) -> bool:
    """
    Verify a PIN against the stored hash.

    Args:
        pin: The PIN to verify

    Returns:
        True if PIN is correct, False otherwise
    """
    if not is_pin_enabled():
        return True  # No PIN = always valid

    # Check if locked out
    if is_pin_locked_out():
        audit_log("PIN_LOCKED_OUT", "Verification attempted during lockout")
        return False

    content = read_secure_file(get_pin_hash_file())
    if not content or ":" not in content:
        return False

    try:
        salt_hex, stored_hash = content.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        computed_hash, _ = _hash_pin(pin, salt)

        if computed_hash == stored_hash:
            _clear_pin_attempts()
            create_pin_session()
            audit_log("PIN_VERIFIED", "PIN verification successful")
            return True
        else:
            _record_failed_attempt()
            audit_log("PIN_FAILED", "Incorrect PIN entered")
            return False
    except (ValueError, TypeError) as e:
        logger.warning(f"PIN verification error: {e}")
        return False


def remove_pin(current_pin: str, force: bool = False) -> bool:
    """
    Remove PIN protection.

    Note: This creates a pending removal request with delay unless force=True.
    force=True should only be used by the pending action executor.

    Args:
        current_pin: Current PIN for verification
        force: If True, remove immediately (used by pending executor)

    Returns:
        True if removal initiated/completed successfully
    """
    if not is_pin_enabled():
        return False

    if not verify_pin(current_pin):
        return False

    if force:
        # Immediate removal (called by pending action executor)
        pin_file = get_pin_hash_file()
        if pin_file.exists():
            pin_file.unlink()
        _clear_pin_session()
        _clear_pin_attempts()
        audit_log("PIN_REMOVED", "PIN protection disabled")
        return True

    # Create pending removal request
    request = create_unlock_request(
        item_type="pin",
        item_id="protection",
        delay_hours=PIN_REMOVAL_DELAY_HOURS,
        reason="PIN removal requested",
    )

    audit_log("PIN_REMOVE_REQUESTED", f"Scheduled for {request['execute_at']}")
    return True


def get_pin_removal_request() -> Optional[dict[str, Any]]:
    """Get pending PIN removal request if exists."""
    pending = get_pending_unlock_requests()
    for req in pending:
        if req["item_type"] == "pin" and req["item_id"] == "protection":
            return req
    return None


def cancel_pin_removal() -> bool:
    """Cancel pending PIN removal request."""
    request = get_pin_removal_request()
    if request:
        return cancel_unlock_request(request["id"])
    return False


# =============================================================================
# PIN SESSION MANAGEMENT
# =============================================================================


def create_pin_session() -> datetime:
    """
    Create a new PIN session.

    Returns:
        Session expiration datetime
    """
    expires = datetime.now() + timedelta(minutes=PIN_SESSION_DURATION_MINUTES)
    write_secure_file(get_pin_session_file(), expires.isoformat())
    return expires


def is_pin_session_valid() -> bool:
    """Check if current PIN session is still valid."""
    if not is_pin_enabled():
        return True  # No PIN = always valid

    content = read_secure_file(get_pin_session_file())
    if not content:
        return False

    try:
        expires = datetime.fromisoformat(content)
        if datetime.now() < expires:
            return True
        # Expired, clean up
        _clear_pin_session()
        return False
    except ValueError:
        _clear_pin_session()
        return False


def _clear_pin_session() -> None:
    """Clear the current PIN session."""
    session_file = get_pin_session_file()
    if session_file.exists():
        session_file.unlink(missing_ok=True)


def get_pin_session_remaining() -> Optional[str]:
    """
    Get remaining session time as human-readable string.

    Returns:
        Human-readable remaining time, or None if no valid session
    """
    if not is_pin_enabled():
        return None

    content = read_secure_file(get_pin_session_file())
    if not content:
        return None

    try:
        expires = datetime.fromisoformat(content)
        remaining = expires - datetime.now()
        if remaining.total_seconds() <= 0:
            return None

        mins = int(remaining.total_seconds() // 60)
        secs = int(remaining.total_seconds() % 60)
        return f"{mins}m {secs}s"
    except ValueError:
        return None


# =============================================================================
# PIN LOCKOUT (BRUTE FORCE PROTECTION)
# =============================================================================


def _record_failed_attempt() -> int:
    """
    Record a failed PIN attempt.

    Returns:
        Current number of failed attempts
    """
    content = read_secure_file(get_pin_attempts_file())
    attempts = []

    if content:
        try:
            attempts = json.loads(content)
        except json.JSONDecodeError:
            attempts = []

    # Add new attempt
    attempts.append(datetime.now().isoformat())

    # Keep only attempts within lockout window
    cutoff = datetime.now() - timedelta(minutes=PIN_LOCKOUT_MINUTES)
    attempts = [a for a in attempts if datetime.fromisoformat(a) > cutoff]

    write_secure_file(get_pin_attempts_file(), json.dumps(attempts))

    return len(attempts)


def _clear_pin_attempts() -> None:
    """Clear failed PIN attempts."""
    attempts_file = get_pin_attempts_file()
    if attempts_file.exists():
        attempts_file.unlink(missing_ok=True)


def get_failed_attempts_count() -> int:
    """Get current number of failed attempts in lockout window."""
    content = read_secure_file(get_pin_attempts_file())
    if not content:
        return 0

    try:
        attempts = json.loads(content)
        cutoff = datetime.now() - timedelta(minutes=PIN_LOCKOUT_MINUTES)
        valid_attempts = [a for a in attempts if datetime.fromisoformat(a) > cutoff]
        return len(valid_attempts)
    except (json.JSONDecodeError, ValueError):
        return 0


def is_pin_locked_out() -> bool:
    """Check if PIN entry is locked out due to too many failed attempts."""
    return get_failed_attempts_count() >= PIN_MAX_ATTEMPTS


def get_lockout_remaining() -> Optional[str]:
    """
    Get remaining lockout time.

    Returns:
        Human-readable remaining time, or None if not locked out
    """
    if not is_pin_locked_out():
        return None

    content = read_secure_file(get_pin_attempts_file())
    if not content:
        return None

    try:
        attempts = json.loads(content)
        if not attempts:
            return None

        # Find oldest attempt in current window
        oldest = min(datetime.fromisoformat(a) for a in attempts)
        lockout_ends = oldest + timedelta(minutes=PIN_LOCKOUT_MINUTES)
        remaining = lockout_ends - datetime.now()

        if remaining.total_seconds() <= 0:
            return None

        mins = int(remaining.total_seconds() // 60)
        secs = int(remaining.total_seconds() % 60)
        return f"{mins}m {secs}s"
    except (json.JSONDecodeError, ValueError):
        return None


# =============================================================================
# UNIFIED PROTECTION CHECK
# =============================================================================


def can_execute_dangerous_command(command_name: str) -> tuple[bool, str]:
    """
    Unified check for dangerous command execution.

    This function checks all protection layers in order:
    1. Panic mode (absolute block - commands are hidden)
    2. PIN protection (requires verification)

    Args:
        command_name: Name of the command to check

    Returns:
        Tuple of (can_execute, reason)
        Reasons: "ok", "panic_mode", "pin_required", "pin_locked_out"
    """
    from .panic import DANGEROUS_COMMANDS, DANGEROUS_SUBCOMMANDS, is_panic_mode

    # 1. Panic mode has absolute priority
    if is_panic_mode():
        if command_name in DANGEROUS_COMMANDS:
            return False, "panic_mode"
        # Check subcommands
        for _parent, subs in DANGEROUS_SUBCOMMANDS.items():
            if command_name in subs:
                return False, "panic_mode"

    # 2. PIN protection
    if is_pin_enabled():
        if command_name in DANGEROUS_COMMANDS:
            if is_pin_locked_out():
                return False, "pin_locked_out"
            if not is_pin_session_valid():
                return False, "pin_required"

    return True, "ok"
