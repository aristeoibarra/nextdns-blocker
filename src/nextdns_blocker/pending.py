"""Pending action management for delayed unblock operations.

Note on datetime handling:
    All datetime operations in this module use naive (timezone-unaware) datetimes
    for consistency. This means datetime.now() is used without timezone info,
    and ISO format strings are stored/parsed without timezone suffixes.
    This is intentional to avoid mixing naive and aware datetimes which would
    cause comparison errors.
"""

import logging
import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Optional

from . import database as db
from .common import audit_log
from .config import parse_duration

logger = logging.getLogger(__name__)


def generate_action_id() -> str:
    """
    Generate a unique action ID.

    Format: pnd_{YYYYMMDD}_{HHMMSS}_{random6}
    Example: pnd_20251215_143022_a1b2c3
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"pnd_{timestamp}_{suffix}"


def create_pending_action(
    domain: str,
    delay: str,
    requested_by: str = "cli",
) -> Optional[dict[str, Any]]:
    """
    Create a new pending unblock action.

    Args:
        domain: Domain to unblock
        delay: Delay value ('24h', '4h', '30m', '0', 'never').
            - If 'never' is passed, no pending action will be created and the function returns None.
        requested_by: Origin of request ('cli', 'sync')

    Returns:
        Created action dict, or None on failure or if delay is 'never'

    Note:
        Invalid delay values are logged and treated as 'never' (no action created).
    """
    # Parse delay using flexible duration parser
    try:
        delay_seconds = parse_duration(delay)
    except ValueError:
        logger.warning(f"Invalid delay value '{delay}', no pending action created")
        return None

    if delay_seconds is None:  # 'never' - valid but no action needed
        return None

    # Check for duplicate pending action for same domain
    existing = get_pending_for_domain(domain)
    if existing:
        logger.warning(f"Pending action already exists for {domain}")
        return existing

    now = datetime.now()
    execute_at = now + timedelta(seconds=delay_seconds)

    action_id = generate_action_id()

    db.add_pending_action(
        action_id=action_id,
        action="unblock",
        domain=domain,
        created_at=now.isoformat(),
        execute_at=execute_at.isoformat(),
        delay=delay,
        requested_by=requested_by,
    )

    audit_log("PENDING_CREATE", f"{action_id} {domain} delay={delay}")

    return {
        "id": action_id,
        "action": "unblock",
        "domain": domain,
        "created_at": now.isoformat(),
        "execute_at": execute_at.isoformat(),
        "delay": delay,
        "status": "pending",
        "requested_by": requested_by,
    }


def get_pending_action(action_id: str) -> Optional[dict[str, Any]]:
    """Get a pending action by ID."""
    return db.get_pending_action(action_id)


def get_pending_actions(status: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Get all pending actions, optionally filtered by status.

    Args:
        status: Filter by status ('pending', 'executed', 'cancelled')

    Returns:
        List of matching actions
    """
    if status:
        return db.get_pending_actions(status)

    # Get all actions if no status filter
    conn = db.get_connection()
    cursor = conn.execute("SELECT * FROM pending_actions ORDER BY execute_at")
    return [dict(row) for row in cursor]


def get_pending_for_domain(domain: str) -> Optional[dict[str, Any]]:
    """Get pending action for a specific domain."""
    conn = db.get_connection()
    cursor = conn.execute(
        "SELECT * FROM pending_actions WHERE domain = ? AND status = 'pending' LIMIT 1",
        (domain,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def cancel_pending_action(action_id: str) -> bool:
    """
    Cancel a pending action.

    Args:
        action_id: ID of action to cancel

    Returns:
        True if cancelled, False if not found or already executed
    """
    action = db.get_pending_action(action_id)
    if not action:
        return False

    if action.get("status") != "pending":
        return False

    domain = action.get("domain", "unknown")

    # Delete the action (we don't keep cancelled actions)
    conn = db.get_connection()
    cursor = conn.execute("DELETE FROM pending_actions WHERE id = ?", (action_id,))
    conn.commit()

    if cursor.rowcount > 0:
        audit_log("PENDING_CANCEL", f"{action_id} {domain}")
        return True
    return False


def get_ready_actions() -> list[dict[str, Any]]:
    """Get all actions that are ready to execute (execute_at <= now)."""
    now = datetime.now().isoformat()
    return db.get_executable_pending_actions(before=now)


def mark_action_executed(action_id: str) -> bool:
    """Mark an action as executed and remove it from the database."""
    action = db.get_pending_action(action_id)
    if not action:
        return False

    domain = action.get("domain", "unknown")

    # Delete the action after execution
    conn = db.get_connection()
    cursor = conn.execute("DELETE FROM pending_actions WHERE id = ?", (action_id,))
    conn.commit()

    if cursor.rowcount > 0:
        audit_log("PENDING_EXECUTE", f"{action_id} {domain}")
        return True
    return False


def cleanup_old_actions(max_age_days: int = 7) -> int:
    """
    Remove actions older than max_age_days.

    Args:
        max_age_days: Maximum age in days (default: 7)

    Returns:
        Count of removed actions
    """
    cutoff = datetime.now() - timedelta(days=max_age_days)
    cutoff_str = cutoff.isoformat()

    conn = db.get_connection()
    cursor = conn.execute(
        "DELETE FROM pending_actions WHERE created_at < ?",
        (cutoff_str,),
    )
    conn.commit()

    removed = cursor.rowcount
    if removed > 0:
        logger.info(f"Cleaned up {removed} old pending actions")
    return removed
