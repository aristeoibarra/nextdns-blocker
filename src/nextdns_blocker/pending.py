"""Pending action management for delayed unblock operations.

Note on datetime handling:
    All datetime operations in this module use naive (timezone-unaware) datetimes
    for consistency. This means datetime.now() is used without timezone info,
    and ISO format strings are stored/parsed without timezone suffixes.
    This is intentional to avoid mixing naive and aware datetimes which would
    cause comparison errors.
"""

import contextlib
import json
import logging
import os
import secrets
import shutil
import string
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .common import (
    SECURE_FILE_MODE,
    _lock_file,
    _unlock_file,
    audit_log,
    ensure_naive_datetime,
    read_secure_file,
    write_secure_file,
)
from .config import UNBLOCK_DELAY_SECONDS, VALID_UNBLOCK_DELAYS, get_data_dir

logger = logging.getLogger(__name__)

PENDING_FILE_NAME = "pending.json"
PENDING_VERSION = "1.0"
MAX_BACKUP_FILES = 3  # Keep last N backup files
LOCK_TIMEOUT_SECONDS = 10.0  # Maximum time to wait for file lock


def get_pending_file() -> Path:
    """Get the path to the pending actions file."""
    return get_data_dir() / PENDING_FILE_NAME


def _get_lock_file() -> Path:
    """Get the path to the pending lock file."""
    return get_data_dir() / ".pending.lock"


@contextmanager
def _pending_file_lock() -> Generator[None, None, None]:
    """
    Context manager for atomic pending file operations.

    Uses a separate lock file to ensure read-modify-write operations
    are atomic across multiple processes.

    Raises:
        TimeoutError: If lock cannot be acquired within LOCK_TIMEOUT_SECONDS
        OSError: If file operations fail
    """
    lock_file = _get_lock_file()
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    # Create lock file if it doesn't exist
    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, SECURE_FILE_MODE)
    fd_closed = False
    try:
        f = os.fdopen(fd, "r+")
        fd_closed = True  # fd is now owned by f
        try:
            _lock_file(f, exclusive=True, timeout=LOCK_TIMEOUT_SECONDS)
            try:
                yield
            finally:
                _unlock_file(f)
        finally:
            f.close()
    except OSError:
        if not fd_closed:
            # Use suppress to handle case where fd might already be invalid
            with contextlib.suppress(OSError):
                os.close(fd)
        raise


def _create_backup(file_path: Path) -> Optional[Path]:
    """
    Create a backup of a file before overwriting due to corruption.

    Args:
        file_path: Path to the file to backup

    Returns:
        Path to backup file, or None if backup failed
    """
    if not file_path.exists():
        return None

    try:
        # Include microseconds to avoid collision in rapid successive operations
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_path = file_path.with_suffix(f".{timestamp}.bak")
        shutil.copy2(file_path, backup_path)
        logger.info(f"Created backup: {backup_path}")

        # Clean up old backups (keep only MAX_BACKUP_FILES)
        backup_pattern = f"{file_path.stem}.*.bak"
        backups = sorted(file_path.parent.glob(backup_pattern), reverse=True)
        for old_backup in backups[MAX_BACKUP_FILES:]:
            try:
                old_backup.unlink()
                logger.debug(f"Removed old backup: {old_backup}")
            except OSError as e:
                logger.debug(f"Could not remove old backup {old_backup}: {e}")

        return backup_path
    except OSError as e:
        logger.warning(f"Failed to create backup of {file_path}: {e}")
        return None


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
    """
    Load pending actions from file.

    Returns:
        dict containing 'version' and 'pending_actions' list.
        Returns empty structure if file doesn't exist or is corrupted.
    """
    pending_file = get_pending_file()
    content = read_secure_file(pending_file)
    if not content:
        return {"version": PENDING_VERSION, "pending_actions": []}

    try:
        parsed = json.loads(content)
        # Validate that parsed data is a dict
        if not isinstance(parsed, dict):
            logger.error(f"Invalid pending.json: expected object, got {type(parsed).__name__}")
            _create_backup(pending_file)
            return {"version": PENDING_VERSION, "pending_actions": []}
        data: dict[str, Any] = parsed
        # Ensure version compatibility
        if data.get("version") != PENDING_VERSION:
            logger.warning("Pending file version mismatch, migrating...")
        # Validate pending_actions is a list
        if "pending_actions" not in data or not isinstance(data.get("pending_actions"), list):
            logger.warning("Missing or invalid 'pending_actions' in pending.json, resetting")
            data["pending_actions"] = []
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid pending.json: {e}")
        # Log content preview for debugging (truncated for safety)
        content_preview = content[:200] + "..." if len(content) > 200 else content
        logger.warning(f"Corrupted content preview: {content_preview!r}")

        # Create backup before resetting to preserve data for recovery
        backup_path = _create_backup(pending_file)
        if backup_path:
            logger.warning(
                f"Corrupted file backed up to: {backup_path}. "
                f"Any pending actions have been lost - check backup for manual recovery."
            )
        else:
            logger.error(
                "Failed to create backup of corrupted pending.json. " "Pending actions may be lost."
            )
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
        delay: Delay value ('24h', '4h', '30m', '0', 'never').
            - If 'never' is passed, no pending action will be created and the function returns None.
        requested_by: Origin of request ('cli', 'sync')

    Returns:
        Created action dict, or None on failure or if delay is 'never'

    Note:
        Invalid delay values are logged and treated as 'never' (no action created).
    """
    # Validate delay is a known value
    if delay not in VALID_UNBLOCK_DELAYS:
        logger.warning(f"Invalid delay value '{delay}', no pending action created")
        return None

    delay_seconds = UNBLOCK_DELAY_SECONDS.get(delay)
    if delay_seconds is None:  # 'never' - valid but no action needed
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

    # Use file lock for atomic read-modify-write operation
    with _pending_file_lock():
        data = _load_pending_data()

        # Check for duplicate pending action for same domain
        pending_actions: list[dict[str, Any]] = data["pending_actions"]
        for existing in pending_actions:
            if existing.get("domain") == domain and existing.get("status") == "pending":
                logger.warning(f"Pending action already exists for {domain}")
                return existing

        data["pending_actions"].append(action)

        if _save_pending_data(data):
            audit_log("PENDING_CREATE", f"{action['id']} {domain} delay={delay}")
            return action
    return None


def get_pending_action(action_id: str) -> Optional[dict[str, Any]]:
    """Get a pending action by ID (thread-safe with shared lock)."""
    with _pending_file_lock():
        data = _load_pending_data()
        pending_actions: list[dict[str, Any]] = data.get("pending_actions", [])
        for action in pending_actions:
            if action.get("id") == action_id:
                return action
        return None


def get_pending_actions(status: Optional[str] = None) -> list[dict[str, Any]]:
    """
    Get all pending actions, optionally filtered by status (thread-safe).

    Args:
        status: Filter by status ('pending', 'executed', 'cancelled')

    Returns:
        List of matching actions
    """
    with _pending_file_lock():
        data = _load_pending_data()
        actions: list[dict[str, Any]] = data.get("pending_actions", [])
        if status:
            actions = [a for a in actions if a.get("status") == status]
        return actions


def get_pending_for_domain(domain: str) -> Optional[dict[str, Any]]:
    """Get pending action for a specific domain (thread-safe)."""
    with _pending_file_lock():
        data = _load_pending_data()
        pending_actions: list[dict[str, Any]] = data.get("pending_actions", [])
        for action in pending_actions:
            if action.get("domain") == domain and action.get("status") == "pending":
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
    # Use file lock for atomic read-modify-write operation
    with _pending_file_lock():
        data = _load_pending_data()
        for i, action in enumerate(data["pending_actions"]):
            if action.get("id") == action_id:
                if action.get("status") != "pending":
                    return False
                # Remove the action entirely
                domain = action.get("domain", "unknown")
                del data["pending_actions"][i]
                if _save_pending_data(data):
                    audit_log("PENDING_CANCEL", f"{action_id} {domain}")
                    return True
                return False
        return False


def get_ready_actions() -> list[dict[str, Any]]:
    """Get all actions that are ready to execute (execute_at <= now, thread-safe)."""
    now = datetime.now()
    with _pending_file_lock():
        data = _load_pending_data()
        ready = []
        for action in data["pending_actions"]:
            if action.get("status") != "pending":
                continue
            try:
                execute_at_str = action.get("execute_at", "")
                if execute_at_str:
                    execute_at = ensure_naive_datetime(datetime.fromisoformat(execute_at_str))
                    if execute_at <= now:
                        ready.append(action)
            except (ValueError, KeyError):
                logger.warning(f"Invalid action: {action.get('id')}")
        return ready


def mark_action_executed(action_id: str) -> bool:
    """Mark an action as executed and remove it from the file."""
    # Use file lock for atomic read-modify-write operation
    with _pending_file_lock():
        data = _load_pending_data()
        for i, action in enumerate(data["pending_actions"]):
            if action.get("id") == action_id:
                domain = action.get("domain", "unknown")
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
        Count of removed actions, or 0 if cleanup failed
    """
    try:
        cutoff = datetime.now() - timedelta(days=max_age_days)

        # Use file lock for atomic read-modify-write operation
        with _pending_file_lock():
            data = _load_pending_data()
            original_count = len(data["pending_actions"])

            new_actions = []
            for a in data["pending_actions"]:
                try:
                    created_at = ensure_naive_datetime(datetime.fromisoformat(a["created_at"]))
                    if created_at > cutoff:
                        new_actions.append(a)
                except (ValueError, KeyError):
                    logger.warning(f"Invalid created_at in action: {a.get('id')}")
                    # Keep malformed actions to avoid data loss
                    new_actions.append(a)
            data["pending_actions"] = new_actions

            removed = original_count - len(data["pending_actions"])
            if removed > 0:
                if _save_pending_data(data):
                    logger.info(f"Cleaned up {removed} old pending actions")
                else:
                    logger.warning("Failed to save after cleanup")
                    return 0
            return removed
    except OSError as e:
        logger.error(f"Cleanup failed due to I/O error: {e}")
        return 0
