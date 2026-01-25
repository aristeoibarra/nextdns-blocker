"""Protection module for addiction safety features.

This module provides:
- Locked categories/services that cannot be easily removed
- Unlock request system with configurable delay
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional, cast
from uuid import uuid4

from . import database as db
from .common import (
    audit_log,
    ensure_naive_datetime,
    get_log_dir,
    read_secure_file,
    write_secure_file,
)
from .types import (
    ItemType,
    UnlockRequest,
)

logger = logging.getLogger(__name__)

# Default unlock delay in hours
DEFAULT_UNLOCK_DELAY_HOURS = 48

# Minimum unlock delay (prevent bypassing with delay=0)
MIN_UNLOCK_DELAY_HOURS = 24


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
                    if isinstance(domain, str):
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
    - Changing unblock_delay: "never" to something else (ANY other value)
    - Removing the locked field entirely

    Args:
        old_config: Current configuration
        new_config: Proposed new configuration

    Returns:
        List of error messages for locked items being weakened
    """
    errors = []

    # Check nextdns.categories
    old_categories = {
        c["id"]: c
        for c in old_config.get("nextdns", {}).get("categories", [])
        if isinstance(c, dict) and "id" in c
    }
    new_categories = {
        c["id"]: c
        for c in new_config.get("nextdns", {}).get("categories", [])
        if isinstance(c, dict) and "id" in c
    }

    for cat_id, old_cat in old_categories.items():
        if not is_locked(old_cat):
            continue
        new_cat = new_categories.get(cat_id)
        if new_cat and not is_locked(new_cat):
            errors.append(
                f"Cannot weaken protection for category '{cat_id}'. It is marked as locked."
            )
        # Check if unblock_delay was weakened from "never" to something else
        if new_cat:
            old_delay = old_cat.get("unblock_delay")
            new_delay = new_cat.get("unblock_delay")
            if old_delay == "never" and new_delay != "never":
                errors.append(
                    f"Cannot change unblock_delay for category '{cat_id}' from 'never' to '{new_delay}'. "
                    f"Use 'ndb protection unlock-request {cat_id}' to request modification "
                    f"with a {DEFAULT_UNLOCK_DELAY_HOURS}h delay."
                )

    # Check nextdns.services
    old_services = {
        s["id"]: s
        for s in old_config.get("nextdns", {}).get("services", [])
        if isinstance(s, dict) and "id" in s
    }
    new_services = {
        s["id"]: s
        for s in new_config.get("nextdns", {}).get("services", [])
        if isinstance(s, dict) and "id" in s
    }

    for svc_id, old_svc in old_services.items():
        if not is_locked(old_svc):
            continue
        new_svc = new_services.get(svc_id)
        if new_svc and not is_locked(new_svc):
            errors.append(
                f"Cannot weaken protection for service '{svc_id}'. It is marked as locked."
            )
        # Check if unblock_delay was weakened from "never" to something else
        if new_svc:
            old_delay = old_svc.get("unblock_delay")
            new_delay = new_svc.get("unblock_delay")
            if old_delay == "never" and new_delay != "never":
                errors.append(
                    f"Cannot change unblock_delay for service '{svc_id}' from 'never' to '{new_delay}'. "
                    f"Use 'ndb protection unlock-request {svc_id}' to request modification "
                    f"with a {DEFAULT_UNLOCK_DELAY_HOURS}h delay."
                )

    # Check blocklist domains for unblock_delay weakening
    old_blocklist = {
        d.get("domain"): d for d in old_config.get("blocklist", []) if isinstance(d, dict)
    }
    new_blocklist = {
        d.get("domain"): d for d in new_config.get("blocklist", []) if isinstance(d, dict)
    }

    for domain, old_entry in old_blocklist.items():
        if not domain:
            continue
        old_delay = old_entry.get("unblock_delay")
        if old_delay != "never":
            continue
        new_entry = new_blocklist.get(domain)
        if new_entry:
            new_delay = new_entry.get("unblock_delay")
            if new_delay != "never":
                errors.append(
                    f"Cannot change unblock_delay for domain '{domain}' from 'never' to '{new_delay}'. "
                    f"Use 'ndb protection unlock-request {domain}' to request modification "
                    f"with a {DEFAULT_UNLOCK_DELAY_HOURS}h delay."
                )

    return errors


# =============================================================================
# UNLOCK REQUESTS (SQLite-backed)
# =============================================================================


def create_unlock_request(
    item_type: str,
    item_id: str,
    delay_hours: int = DEFAULT_UNLOCK_DELAY_HOURS,
    reason: Optional[str] = None,
) -> UnlockRequest:
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
    now = datetime.now()
    execute_at = now + timedelta(hours=delay_hours)

    db.add_unlock_request(
        request_id=request_id,
        item_type=item_type,
        item_id=item_id,
        created_at=now.isoformat(),
        execute_at=execute_at.isoformat(),
        delay_hours=delay_hours,
        reason=reason,
    )

    audit_log("UNLOCK_REQUEST", f"{item_type}:{item_id} scheduled for {execute_at.isoformat()}")

    return {
        "id": request_id,
        "item_type": cast(ItemType, item_type),
        "item_id": item_id,
        "created_at": now.isoformat(),
        "execute_at": execute_at.isoformat(),
        "delay_hours": delay_hours,
        "reason": reason,
        "status": "pending",
    }


def cancel_unlock_request(request_id: str) -> bool:
    """Cancel a pending unlock request.

    Args:
        request_id: ID of the request to cancel (can be partial)

    Returns:
        True if request was found and cancelled
    """
    # Find request by partial ID
    pending = get_pending_unlock_requests()
    for req in pending:
        if req.get("id", "").startswith(request_id):
            item_type = req.get("item_type", "unknown")
            item_id = req.get("item_id", "unknown")

            # Delete from database
            conn = db.get_connection()
            conn.execute("DELETE FROM unlock_requests WHERE id = ?", (req["id"],))
            conn.commit()

            audit_log("UNLOCK_CANCEL", f"{item_type}:{item_id}")
            return True

    return False


def get_pending_unlock_requests() -> list[UnlockRequest]:
    """Get all pending unlock requests."""
    rows = db.get_unlock_requests("pending")
    return [_row_to_unlock_request(r) for r in rows]


def get_executable_unlock_requests() -> list[UnlockRequest]:
    """Get unlock requests that are ready to execute."""
    now = datetime.now().isoformat()
    rows = db.get_executable_unlock_requests(before=now)
    return [_row_to_unlock_request(r) for r in rows]


def _row_to_unlock_request(row: dict[str, Any]) -> UnlockRequest:
    """Convert a database row to an UnlockRequest TypedDict."""
    return {
        "id": row["id"],
        "item_type": cast(ItemType, row["item_type"]),
        "item_id": row["item_id"],
        "created_at": row["created_at"],
        "execute_at": row["execute_at"],
        "delay_hours": row["delay_hours"],
        "reason": row.get("reason"),
        "status": row["status"],
    }


def execute_unlock_request(request_id: str, config_path: Path) -> bool:
    """Execute an unlock request by modifying the config.

    Args:
        request_id: ID of the request to execute
        config_path: Path to config.json

    Returns:
        True if successfully executed
    """
    request = db.get_unlock_request(request_id)
    if not request or request.get("status") != "pending":
        return False

    # Check if delay has passed
    try:
        execute_at = ensure_naive_datetime(datetime.fromisoformat(request["execute_at"]))
    except (ValueError, KeyError) as e:
        logger.error(f"Invalid execute_at in request {request_id}: {e}")
        return False

    if datetime.now() < execute_at:
        logger.warning(f"Request {request_id} not yet executable")
        return False

    item_type = request["item_type"]
    item_id = request["item_id"]

    # Load config and remove the locked item
    try:
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)

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
        db.update_unlock_request_status(request_id, "executed", datetime.now().isoformat())

        audit_log("UNLOCK_EXECUTE", f"{item_type}:{item_id}")
        return True

    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Failed to execute unlock request: {e}")
        return False


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

    return errors


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


def get_pin_removal_request() -> Optional[UnlockRequest]:
    """Get pending PIN removal request if exists."""
    pending = get_pending_unlock_requests()
    for req in pending:
        if req.get("item_type") == "pin" and req.get("item_id") == "protection":
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

# Commands that require PIN protection
DANGEROUS_COMMANDS = {"unblock", "pause", "edit", "disable"}


def can_execute_dangerous_command(command_name: str) -> tuple[bool, str]:
    """
    Unified check for dangerous command execution.

    This function checks PIN protection layer.

    Args:
        command_name: Name of the command to check

    Returns:
        Tuple of (can_execute, reason)
        Reasons: "ok", "pin_required", "pin_locked_out"
    """
    # PIN protection
    if is_pin_enabled():
        if command_name in DANGEROUS_COMMANDS:
            if is_pin_locked_out():
                return False, "pin_locked_out"
            if not is_pin_session_valid():
                return False, "pin_required"

    return True, "ok"


def get_all_config_validation_errors(
    old_config: dict[str, Any], new_config: dict[str, Any]
) -> list[str]:
    """
    Run all protection validation checks on a config change.

    This is a convenience function that runs all validation checks
    and returns a combined list of errors.

    Args:
        old_config: Current configuration
        new_config: Proposed new configuration

    Returns:
        Combined list of all validation errors
    """
    errors = []

    # Run all validators
    errors.extend(validate_no_locked_removal(old_config, new_config))
    errors.extend(validate_no_locked_weakening(old_config, new_config))

    return errors
