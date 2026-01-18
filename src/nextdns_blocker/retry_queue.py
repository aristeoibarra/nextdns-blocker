"""Retry queue for transient API failures.

This module provides a persistent queue for operations that fail due to
transient errors (timeouts, rate limits, server errors). Failed operations
are stored and retried on subsequent watchdog runs with exponential backoff.
"""

import contextlib
import json
import logging
import os
import secrets
import string
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, Optional

from .common import (
    SECURE_FILE_MODE,
    _lock_file,
    _unlock_file,
    audit_log,
    read_secure_file,
    write_secure_file,
)
from .config import get_data_dir

logger = logging.getLogger(__name__)

RETRY_QUEUE_FILE_NAME = "retry_queue.json"
RETRY_QUEUE_VERSION = "1.0"
LOCK_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 5
DEFAULT_INITIAL_BACKOFF = 60  # 1 minute
MAX_BACKOFF = 3600  # 1 hour max backoff


ActionType = Literal["block", "unblock", "allow", "disallow"]


@dataclass
class RetryItem:
    """An item in the retry queue."""

    id: str
    action: ActionType
    domain: str
    error_type: str
    error_msg: str
    attempt_count: int = 0
    first_attempt: str = ""  # ISO format
    last_attempt: str = ""  # ISO format
    next_retry_at: str = ""  # ISO format
    backoff_seconds: int = DEFAULT_INITIAL_BACKOFF

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now().isoformat()
        if not self.first_attempt:
            self.first_attempt = now
        if not self.last_attempt:
            self.last_attempt = now
        if not self.next_retry_at:
            next_time = datetime.now() + timedelta(seconds=self.backoff_seconds)
            self.next_retry_at = next_time.isoformat()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RetryItem":
        """Create RetryItem from dictionary."""
        return cls(
            id=data.get("id", ""),
            action=data.get("action", "block"),
            domain=data.get("domain", ""),
            error_type=data.get("error_type", ""),
            error_msg=data.get("error_msg", ""),
            attempt_count=data.get("attempt_count", 0),
            first_attempt=data.get("first_attempt", ""),
            last_attempt=data.get("last_attempt", ""),
            next_retry_at=data.get("next_retry_at", ""),
            backoff_seconds=data.get("backoff_seconds", DEFAULT_INITIAL_BACKOFF),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    def is_ready(self) -> bool:
        """Check if this item is ready to retry."""
        if not self.next_retry_at:
            return True
        try:
            next_time = datetime.fromisoformat(self.next_retry_at)
            return datetime.now() >= next_time
        except ValueError:
            return True

    def update_for_retry(self) -> None:
        """Update item after a failed retry attempt."""
        self.attempt_count += 1
        self.last_attempt = datetime.now().isoformat()
        # Exponential backoff with jitter
        self.backoff_seconds = min(self.backoff_seconds * 2, MAX_BACKOFF)
        next_time = datetime.now() + timedelta(seconds=self.backoff_seconds)
        self.next_retry_at = next_time.isoformat()


@dataclass
class RetryResult:
    """Result of processing the retry queue."""

    succeeded: list[RetryItem] = field(default_factory=list)
    failed: list[RetryItem] = field(default_factory=list)
    exhausted: list[RetryItem] = field(default_factory=list)
    skipped: int = 0  # Items not yet ready to retry


def _generate_retry_id() -> str:
    """Generate a unique retry item ID."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
    return f"ret_{timestamp}_{suffix}"


def get_retry_queue_file() -> Path:
    """Get the path to the retry queue file."""
    return get_data_dir() / RETRY_QUEUE_FILE_NAME


def _get_lock_file() -> Path:
    """Get the path to the retry queue lock file."""
    return get_data_dir() / ".retry_queue.lock"


@contextmanager
def _retry_queue_lock() -> Generator[None, None, None]:
    """Context manager for atomic retry queue operations."""
    lock_file = _get_lock_file()
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    fd = os.open(lock_file, os.O_RDWR | os.O_CREAT, SECURE_FILE_MODE)
    fd_closed = False
    try:
        f = os.fdopen(fd, "r+")
        fd_closed = True
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
            with contextlib.suppress(OSError):
                os.close(fd)
        raise


def _load_queue_data() -> dict[str, Any]:
    """Load retry queue from file."""
    queue_file = get_retry_queue_file()
    content = read_secure_file(queue_file)
    if not content:
        return {"version": RETRY_QUEUE_VERSION, "retry_entries": []}

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            logger.error(f"Invalid retry_queue.json: expected object, got {type(parsed).__name__}")
            return {"version": RETRY_QUEUE_VERSION, "retry_entries": []}
        data: dict[str, Any] = parsed
        if "retry_entries" not in data or not isinstance(data.get("retry_entries"), list):
            data["retry_entries"] = []
        return data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid retry_queue.json: {e}")
        return {"version": RETRY_QUEUE_VERSION, "retry_entries": []}


def _save_queue_data(data: dict[str, Any]) -> bool:
    """Save retry queue to file."""
    try:
        queue_file = get_retry_queue_file()
        queue_file.parent.mkdir(parents=True, exist_ok=True)
        content = json.dumps(data, indent=2, default=str)
        write_secure_file(queue_file, content)
        return True
    except OSError as e:
        logger.error(f"Failed to save retry_queue.json: {e}")
        return False


def enqueue(
    domain: str,
    action: ActionType,
    error_type: str,
    error_msg: str,
    initial_backoff: int = DEFAULT_INITIAL_BACKOFF,
) -> Optional[str]:
    """
    Add a failed operation to the retry queue.

    Args:
        domain: The domain that failed
        action: The action type (block, unblock, allow, disallow)
        error_type: Type of error (timeout, connection, rate_limit, etc.)
        error_msg: Error message for logging
        initial_backoff: Initial backoff in seconds before first retry

    Returns:
        The retry item ID, or None on failure
    """
    with _retry_queue_lock():
        data = _load_queue_data()
        entries: list[dict[str, Any]] = data.get("retry_entries", [])

        # Check if domain+action already in queue
        for entry in entries:
            if entry.get("domain") == domain and entry.get("action") == action:
                logger.debug(f"Domain {domain} ({action}) already in retry queue")
                return entry.get("id")

        item = RetryItem(
            id=_generate_retry_id(),
            action=action,
            domain=domain,
            error_type=error_type,
            error_msg=error_msg,
            backoff_seconds=initial_backoff,
        )

        entries.append(item.to_dict())
        data["retry_entries"] = entries

        if _save_queue_data(data):
            audit_log("RQ_ENQUEUE", f"{action} {domain} error={error_type}", prefix="RQ")
            logger.info(f"Added to retry queue: {action} {domain} (error: {error_type})")
            return item.id

        return None


def get_queue_items() -> list[RetryItem]:
    """Get all items in the retry queue."""
    with _retry_queue_lock():
        data = _load_queue_data()
        entries = data.get("retry_entries", [])
        return [RetryItem.from_dict(e) for e in entries]


def get_ready_items() -> list[RetryItem]:
    """Get items that are ready to retry (backoff elapsed)."""
    items = get_queue_items()
    return [item for item in items if item.is_ready()]


def remove_item(item_id: str) -> bool:
    """Remove an item from the retry queue."""
    with _retry_queue_lock():
        data = _load_queue_data()
        entries = data.get("retry_entries", [])
        original_count = len(entries)
        entries = [e for e in entries if e.get("id") != item_id]

        if len(entries) == original_count:
            return False  # Item not found

        data["retry_entries"] = entries
        return _save_queue_data(data)


def update_item(item: RetryItem) -> bool:
    """Update an item in the retry queue."""
    with _retry_queue_lock():
        data = _load_queue_data()
        entries = data.get("retry_entries", [])

        for i, entry in enumerate(entries):
            if entry.get("id") == item.id:
                entries[i] = item.to_dict()
                data["retry_entries"] = entries
                return _save_queue_data(data)

        return False  # Item not found


def clear_queue() -> int:
    """Clear all items from the retry queue. Returns count of items cleared."""
    with _retry_queue_lock():
        data = _load_queue_data()
        count = len(data.get("retry_entries", []))
        data["retry_entries"] = []
        _save_queue_data(data)
        if count > 0:
            audit_log("RQ_CLEAR", f"Cleared {count} items", prefix="RQ")
        return count


def process_queue(
    client: Any,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> RetryResult:
    """
    Process the retry queue, attempting to execute ready items.

    Args:
        client: NextDNSClient instance
        max_retries: Maximum retry attempts before giving up

    Returns:
        RetryResult with lists of succeeded, failed, and exhausted items
    """
    from .client import APIRequestResult

    result = RetryResult()
    ready_items = get_ready_items()

    for item in ready_items:
        if item.attempt_count >= max_retries:
            # Max retries exceeded
            remove_item(item.id)
            result.exhausted.append(item)
            audit_log(
                "RQ_EXHAUSTED",
                f"{item.action} {item.domain} after {item.attempt_count} attempts",
                prefix="RQ",
            )
            logger.warning(
                f"Retry exhausted for {item.action} {item.domain} after {item.attempt_count} attempts"
            )
            continue

        # Attempt the operation
        api_result: Optional[APIRequestResult] = None

        try:
            if item.action == "block":
                success, _ = client.block(item.domain)
                if not success:
                    # Get error info from a fresh request to understand the failure
                    api_result = client.request("PUT", f"/profiles/{client.profile_id}/denylist")
            elif item.action == "unblock":
                success, _ = client.unblock(item.domain)
                if not success:
                    api_result = client.request(
                        "DELETE", f"/profiles/{client.profile_id}/denylist/{item.domain}"
                    )
            elif item.action == "allow":
                success, _ = client.allow(item.domain)
                if not success:
                    api_result = client.request("PUT", f"/profiles/{client.profile_id}/allowlist")
            elif item.action == "disallow":
                success, _ = client.disallow(item.domain)
                if not success:
                    api_result = client.request(
                        "DELETE", f"/profiles/{client.profile_id}/allowlist/{item.domain}"
                    )
            else:
                logger.error(f"Unknown action type: {item.action}")
                remove_item(item.id)
                continue

            if success:
                remove_item(item.id)
                result.succeeded.append(item)
                audit_log(
                    "RQ_SUCCESS",
                    f"{item.action} {item.domain} after {item.attempt_count + 1} attempts",
                    prefix="RQ",
                )
                logger.info(
                    f"Retry succeeded for {item.action} {item.domain} "
                    f"(attempt {item.attempt_count + 1})"
                )
            else:
                # Check if still retryable
                if api_result and api_result.is_retryable:
                    item.update_for_retry()
                    item.error_type = api_result.error_type
                    item.error_msg = api_result.error_msg
                    update_item(item)
                    result.failed.append(item)
                    logger.debug(
                        f"Retry failed for {item.action} {item.domain}, "
                        f"next attempt in {item.backoff_seconds}s"
                    )
                else:
                    # Non-retryable error, remove from queue
                    remove_item(item.id)
                    result.exhausted.append(item)
                    error_info = api_result.error_type if api_result else "unknown"
                    audit_log(
                        "RQ_NONRETRYABLE",
                        f"{item.action} {item.domain} error={error_info}",
                        prefix="RQ",
                    )
                    logger.warning(
                        f"Non-retryable error for {item.action} {item.domain}: {error_info}"
                    )

        except Exception as e:
            # Unexpected error, update for retry
            logger.error(f"Unexpected error retrying {item.action} {item.domain}: {e}")
            item.update_for_retry()
            item.error_msg = str(e)
            update_item(item)
            result.failed.append(item)

    # Count items that weren't ready
    all_items = get_queue_items()
    result.skipped = len(all_items) - len(ready_items)

    return result


def get_queue_stats() -> dict[str, Any]:
    """Get statistics about the retry queue."""
    items = get_queue_items()
    ready = [i for i in items if i.is_ready()]

    by_action: dict[str, int] = {}
    by_error: dict[str, int] = {}
    total_attempts = 0

    for item in items:
        by_action[item.action] = by_action.get(item.action, 0) + 1
        by_error[item.error_type] = by_error.get(item.error_type, 0) + 1
        total_attempts += item.attempt_count

    return {
        "total": len(items),
        "ready": len(ready),
        "pending": len(items) - len(ready),
        "by_action": by_action,
        "by_error": by_error,
        "total_attempts": total_attempts,
    }
