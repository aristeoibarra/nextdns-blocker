"""Pending action management for delayed unblock operations."""

import json
import logging
import secrets
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .common import (
    audit_log,
    read_secure_file,
    write_secure_file,
)
from .config import UNBLOCK_DELAY_SECONDS, get_data_dir

logger = logging.getLogger(__name__)

PENDING_FILE_NAME = "pending.json"
PENDING_VERSION = "1.0"


def get_pending_file() -> Path:
    """Get the path to the pending actions file."""
    return get_data_dir() / PENDING_FILE_NAME


def generate_action_id() -> str:
    """
    Generate a unique action ID.

    Format: pnd_{YYYYMMDD}_{HHMMSS}_{random6}
    Example: pnd_20251215_143022_a1b2c3
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"pnd_{timestamp}_{suffix}"


def _load_pending_data() -> dict[str, Any]:
    """Load pending actions from file."""
    pending_file = get_pending_file()
    content = read_secure_file(pending_file)
    if not content:
        return {"version": PENDING_VERSION, "pending_actions": []}

    try:
        data: dict[str, Any] = json.loads(content)
        # Ensure version compatibility
        if data.get("version") != PENDING_VERSION:
            logger.warning("Pending file version mismatch, migrating...")
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid pending.json: {e}")
        return {"version": PENDING_VERSION, "pending_actions": []}


def _save_pending_data(data: dict[str, Any]) -> bool:
    """Save pending actions to file."""
    try:
        pending_file = get_pending_file()
        pending_file.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, indent=2, default=str)
        write_secure_file(pending_file, content)
        return True
    except OSError as e:
        logger.error(f"Failed to save pending.json: {e}")
        return False


def create_pending_action(
    domain: str,
    delay: str,
    requested_by: str = "cli",
) -> Optional[dict[str, Any]]:
    """
    Create a new pending unblock action.

    Args:
        domain: Domain to unblock
        delay: Delay value ('24h', '4h', '30m', '0')
        requested_by: Origin of request ('cli', 'sync')

    Returns:
        Created action dict or None on failure
    """
    delay_seconds = UNBLOCK_DELAY_SECONDS.get(delay)
    if delay_seconds is None:  # 'never' or invalid
        return None

    now = datetime.now()
    execute_at = now + timedelta(seconds=delay_seconds)

    action = {
        "id": generate_action_id(),
        "action": "unblock",
        "domain": domain,
        "created_at": now.isoformat(),
        "execute_at": execute_at.isoformat(),
        "delay": delay,
        "status": "pending",
        "requested_by": requested_by,
    }

    data = _load_pending_data()

    # Check for duplicate pending action for same domain
    pending_actions: list[dict[str, Any]] = data["pending_actions"]
    for existing in pending_actions:
        if existing["domain"] == domain and existing["status"] == "pending":
            logger.warning(f"Pending action already exists for {domain}")
            return existing

    data["pending_actions"].append(action)

    if _save_pending_data(data):
        audit_log("PENDING_CREATE", f"{action['id']} {domain} delay={delay}")
        return action
    return None


def get_pending_action(action_id: str) -> Optional[dict[str, Any]]:
    """Get a pending action by ID."""
    data = _load_pending_data()
    pending_actions: list[dict[str, Any]] = data["pending_actions"]
    for action in pending_actions:
        if action["id"] == action_id:
            return action
    return None


def get_pending_actions(status: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Get all pending actions, optionally filtered by status.

    Args:
        status: Filter by status ('pending', 'executed', 'cancelled')

    Returns:
        List of matching actions
    """
    data = _load_pending_data()
    actions: list[dict[str, Any]] = data.get("pending_actions", [])
    if status:
        actions = [a for a in actions if a.get("status") == status]
    return actions


def get_pending_for_domain(domain: str) -> Optional[dict[str, Any]]:
    """Get pending action for a specific domain."""
    data = _load_pending_data()
    pending_actions: list[dict[str, Any]] = data["pending_actions"]
    for action in pending_actions:
        if action["domain"] == domain and action["status"] == "pending":
            return action
    return None


def cancel_pending_action(action_id: str) -> bool:
    """
    Cancel a pending action.

    Args:
        action_id: ID of action to cancel

    Returns:
        True if cancelled, False if not found or already executed
    """
    data = _load_pending_data()
    for i, action in enumerate(data["pending_actions"]):
        if action["id"] == action_id:
            if action["status"] != "pending":
                return False
            # Remove the action entirely
            domain = action["domain"]
            del data["pending_actions"][i]
            if _save_pending_data(data):
                audit_log("PENDING_CANCEL", f"{action_id} {domain}")
                return True
            return False
    return False


def get_ready_actions() -> list[dict[str, Any]]:
    """Get all actions that are ready to execute (execute_at <= now)."""
    now = datetime.now()
    data = _load_pending_data()
    ready = []
    for action in data["pending_actions"]:
        if action["status"] != "pending":
            continue
        try:
            execute_at = datetime.fromisoformat(action["execute_at"])
            if execute_at <= now:
                ready.append(action)
        except (ValueError, KeyError):
            logger.warning(f"Invalid action: {action.get('id')}")
    return ready


def mark_action_executed(action_id: str) -> bool:
    """Mark an action as executed and remove it from the file."""
    data = _load_pending_data()
    for i, action in enumerate(data["pending_actions"]):
        if action["id"] == action_id:
            domain = action["domain"]
            del data["pending_actions"][i]
            if _save_pending_data(data):
                audit_log("PENDING_EXECUTE", f"{action_id} {domain}")
                return True
            return False
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
    data = _load_pending_data()
    original_count = len(data["pending_actions"])

    data["pending_actions"] = [
        a for a in data["pending_actions"] if datetime.fromisoformat(a["created_at"]) > cutoff
    ]

    removed = original_count - len(data["pending_actions"])
    if removed > 0:
        _save_pending_data(data)
        logger.info(f"Cleaned up {removed} old pending actions")
    return removed
