"""Retry queue for transient API failures.

This module provides a persistent queue for operations that fail due to
transient errors (timeouts, rate limits, server errors). Failed operations
are stored and retried on subsequent watchdog runs with exponential backoff.
"""

import logging
import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, Optional

from . import database as db
from .common import audit_log

logger = logging.getLogger(__name__)

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
    created_at: str = ""  # ISO format
    next_retry_at: str = ""  # ISO format
    backoff_seconds: int = DEFAULT_INITIAL_BACKOFF

    def __post_init__(self) -> None:
        """Set timestamps if not provided."""
        now = datetime.now().isoformat()
        if not self.created_at:
            self.created_at = now
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
            created_at=data.get("created_at", ""),
            next_retry_at=data.get("next_retry_at", ""),
            backoff_seconds=data.get("backoff_seconds", DEFAULT_INITIAL_BACKOFF),
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "action": self.action,
            "domain": self.domain,
            "error_type": self.error_type,
            "error_msg": self.error_msg,
            "attempt_count": self.attempt_count,
            "created_at": self.created_at,
            "next_retry_at": self.next_retry_at,
            "backoff_seconds": self.backoff_seconds,
        }

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
        # Exponential backoff with cap
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
    # Check if domain+action already in queue
    conn = db.get_connection()
    cursor = conn.execute(
        "SELECT id FROM retry_queue WHERE domain = ? AND action = ?",
        (domain, action),
    )
    existing = cursor.fetchone()
    if existing:
        logger.debug(f"Domain {domain} ({action}) already in retry queue")
        return str(existing["id"])

    item_id = _generate_retry_id()
    now = datetime.now()
    next_retry = now + timedelta(seconds=initial_backoff)

    db.add_retry_entry(
        entry_id=item_id,
        domain=domain,
        action=action,
        error_type=error_type,
        error_msg=error_msg,
        created_at=now.isoformat(),
        next_retry_at=next_retry.isoformat(),
        attempt_count=1,
        backoff_seconds=initial_backoff,
    )

    audit_log("RQ_ENQUEUE", f"{action} {domain} error={error_type}", prefix="RQ")
    logger.info(f"Added to retry queue: {action} {domain} (error: {error_type})")
    return item_id


def get_queue_items() -> list[RetryItem]:
    """Get all items in the retry queue."""
    conn = db.get_connection()
    cursor = conn.execute("SELECT * FROM retry_queue ORDER BY next_retry_at")
    return [RetryItem.from_dict(dict(row)) for row in cursor]


def get_ready_items() -> list[RetryItem]:
    """Get items that are ready to retry (backoff elapsed)."""
    now = datetime.now().isoformat()
    rows = db.get_retryable_entries(before=now)
    return [RetryItem.from_dict(row) for row in rows]


def remove_item(item_id: str) -> bool:
    """Remove an item from the retry queue."""
    return db.remove_retry_entry(item_id)


def update_item(item: RetryItem) -> None:
    """Update an item in the retry queue."""
    conn = db.get_connection()
    conn.execute(
        """
        UPDATE retry_queue SET
            attempt_count = ?,
            next_retry_at = ?,
            backoff_seconds = ?,
            error_type = ?,
            error_msg = ?
        WHERE id = ?
        """,
        (
            item.attempt_count,
            item.next_retry_at,
            item.backoff_seconds,
            item.error_type,
            item.error_msg,
            item.id,
        ),
    )
    conn.commit()


def clear_queue() -> int:
    """Clear all items from the retry queue. Returns count of items cleared."""
    count = db.clear_retry_queue()
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

        # Attempt the operation using *_with_result() methods to get error context
        # without making extra API calls
        success = False
        api_result: Optional[APIRequestResult] = None

        try:
            if item.action == "block":
                success, _, api_result = client.block_with_result(item.domain)
            elif item.action == "unblock":
                success, _, api_result = client.unblock_with_result(item.domain)
            elif item.action == "allow":
                success, _, api_result = client.allow_with_result(item.domain)
            elif item.action == "disallow":
                success, _, api_result = client.disallow_with_result(item.domain)
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
            logger.error(
                f"Unexpected error retrying {item.action} {item.domain}: {e}", exc_info=True
            )
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
