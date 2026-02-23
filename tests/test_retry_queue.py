"""Tests for retry queue module with SQLite backend."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from nextdns_blocker import database as db
from nextdns_blocker.client import APIRequestResult
from nextdns_blocker.retry_queue import (
    DEFAULT_INITIAL_BACKOFF,
    DEFAULT_MAX_RETRIES,
    MAX_BACKOFF,
    RetryItem,
    RetryResult,
    _generate_retry_id,
    clear_queue,
    enqueue,
    get_queue_items,
    get_queue_stats,
    get_ready_items,
    process_queue,
    remove_item,
    update_item,
)


@pytest.fixture(autouse=True)
def use_temp_database(tmp_path: Path):
    """Use a temporary database for each test."""
    test_db_path = tmp_path / "test.db"

    # Patch the database path
    with patch.object(db, "get_db_path", return_value=test_db_path):
        # Clear thread-local connection
        if hasattr(db._local, "connection"):
            db._local.connection = None

        # Initialize fresh database
        db.init_database()

        yield

        # Close connection
        db.close_connection()


class TestRetryItem:
    """Tests for RetryItem dataclass."""

    def test_create_item(self):
        """Should create item with default values."""
        item = RetryItem(
            id="ret_test_123",
            action="block",
            domain="example.com",
            error_type="timeout",
            error_msg="Request timed out",
        )
        assert item.id == "ret_test_123"
        assert item.action == "block"
        assert item.domain == "example.com"
        assert item.error_type == "timeout"
        assert item.attempt_count == 0
        assert item.backoff_seconds == DEFAULT_INITIAL_BACKOFF
        assert item.created_at  # Should be set automatically
        assert item.next_retry_at

    def test_from_dict(self):
        """Should create item from dictionary."""
        data = {
            "id": "ret_test_456",
            "action": "unblock",
            "domain": "test.com",
            "error_type": "rate_limit",
            "error_msg": "429 Too Many Requests",
            "attempt_count": 2,
            "created_at": "2025-01-17T10:00:00",
            "next_retry_at": "2025-01-17T10:10:00",
            "backoff_seconds": 120,
        }
        item = RetryItem.from_dict(data)
        assert item.id == "ret_test_456"
        assert item.action == "unblock"
        assert item.attempt_count == 2
        assert item.backoff_seconds == 120

    def test_to_dict(self):
        """Should convert to dictionary."""
        item = RetryItem(
            id="ret_test_789",
            action="block",
            domain="example.com",
            error_type="timeout",
            error_msg="Timeout",
        )
        data = item.to_dict()
        assert data["id"] == "ret_test_789"
        assert data["action"] == "block"
        assert data["domain"] == "example.com"

    def test_is_ready_when_time_passed(self):
        """Should be ready when next_retry_at has passed."""
        past_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        item = RetryItem(
            id="ret_test",
            action="block",
            domain="example.com",
            error_type="timeout",
            error_msg="Timeout",
            next_retry_at=past_time,
        )
        assert item.is_ready() is True

    def test_is_ready_when_time_not_passed(self):
        """Should not be ready when next_retry_at is in the future."""
        future_time = (datetime.now() + timedelta(minutes=5)).isoformat()
        item = RetryItem(
            id="ret_test",
            action="block",
            domain="example.com",
            error_type="timeout",
            error_msg="Timeout",
            next_retry_at=future_time,
        )
        assert item.is_ready() is False

    def test_update_for_retry(self):
        """Should update item with exponential backoff."""
        item = RetryItem(
            id="ret_test",
            action="block",
            domain="example.com",
            error_type="timeout",
            error_msg="Timeout",
            backoff_seconds=60,
        )
        original_attempt = item.attempt_count
        item.update_for_retry()

        assert item.attempt_count == original_attempt + 1
        assert item.backoff_seconds == 120  # Doubled

    def test_update_for_retry_max_backoff(self):
        """Should not exceed MAX_BACKOFF."""
        item = RetryItem(
            id="ret_test",
            action="block",
            domain="example.com",
            error_type="timeout",
            error_msg="Timeout",
            backoff_seconds=MAX_BACKOFF,
        )
        item.update_for_retry()
        assert item.backoff_seconds == MAX_BACKOFF


class TestGenerateRetryId:
    """Tests for _generate_retry_id function."""

    def test_format(self):
        """Retry ID should match expected format."""
        retry_id = _generate_retry_id()
        assert retry_id.startswith("ret_")
        parts = retry_id.split("_")
        assert len(parts) == 4
        assert len(parts[1]) == 8  # YYYYMMDD
        assert len(parts[2]) == 6  # HHMMSS
        assert len(parts[3]) == 6  # random suffix

    def test_uniqueness(self):
        """Generated IDs should be unique."""
        ids = [_generate_retry_id() for _ in range(100)]
        assert len(set(ids)) == 100


class TestEnqueue:
    """Tests for enqueue function."""

    def test_enqueue_item(self):
        """Should enqueue an item successfully."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            item_id = enqueue(
                domain="example.com",
                action="block",
                error_type="timeout",
                error_msg="Request timed out",
            )
            assert item_id is not None
            assert item_id.startswith("ret_")

            # Verify item was saved
            items = get_queue_items()
            assert len(items) == 1
            assert items[0].domain == "example.com"
            assert items[0].action == "block"

    def test_enqueue_duplicate(self):
        """Should not duplicate items for same domain+action."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            id1 = enqueue("example.com", "block", "timeout", "Error 1")
            id2 = enqueue("example.com", "block", "timeout", "Error 2")

            assert id1 == id2  # Same ID returned
            items = get_queue_items()
            assert len(items) == 1  # Only one item


class TestQueueOperations:
    """Tests for queue operations."""

    def test_get_queue_items(self):
        """Should return all queue items."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            enqueue("example1.com", "block", "timeout", "Error")
            enqueue("example2.com", "unblock", "rate_limit", "Error")

            items = get_queue_items()
            assert len(items) == 2

    def test_get_ready_items(self):
        """Should return only ready items."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            # Add item and make it ready
            enqueue("ready.com", "block", "timeout", "Error")
            items = get_queue_items()
            items[0].next_retry_at = (datetime.now() - timedelta(minutes=5)).isoformat()
            update_item(items[0])

            # Add item with future retry time
            enqueue("not-ready.com", "block", "timeout", "Error")
            items = get_queue_items()
            for item in items:
                if item.domain == "not-ready.com":
                    item.next_retry_at = (datetime.now() + timedelta(hours=1)).isoformat()
                    update_item(item)

            ready = get_ready_items()
            assert len(ready) == 1
            assert ready[0].domain == "ready.com"

    def test_remove_item(self):
        """Should remove item from queue."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            item_id = enqueue("example.com", "block", "timeout", "Error")
            assert len(get_queue_items()) == 1

            assert item_id is not None
            result = remove_item(item_id)
            assert result is True
            assert len(get_queue_items()) == 0

    def test_remove_nonexistent_item(self):
        """Should return False for non-existent item."""
        result = remove_item("nonexistent_id")
        assert result is False

    def test_clear_queue(self):
        """Should clear all items from queue."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            enqueue("example1.com", "block", "timeout", "Error")
            enqueue("example2.com", "unblock", "rate_limit", "Error")
            assert len(get_queue_items()) == 2

            count = clear_queue()
            assert count == 2
            assert len(get_queue_items()) == 0


class TestGetQueueStats:
    """Tests for get_queue_stats function."""

    def test_empty_queue_stats(self):
        """Should return zero stats for empty queue."""
        stats = get_queue_stats()
        assert stats["total"] == 0
        assert stats["ready"] == 0
        assert stats["pending"] == 0
        assert stats["total_attempts"] == 0

    def test_queue_stats_with_items(self):
        """Should return correct stats for queue with items."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            enqueue("example1.com", "block", "timeout", "Error")
            enqueue("example2.com", "unblock", "rate_limit", "Error")

            stats = get_queue_stats()
            assert stats["total"] == 2
            assert stats["by_action"]["block"] == 1
            assert stats["by_action"]["unblock"] == 1
            assert stats["by_error"]["timeout"] == 1
            assert stats["by_error"]["rate_limit"] == 1


class TestProcessQueue:
    """Tests for process_queue function."""

    def test_process_empty_queue(self):
        """Processing empty queue should return empty result."""
        mock_client = MagicMock()
        result = process_queue(mock_client)

        assert result.succeeded == []
        assert result.failed == []
        assert result.exhausted == []

    def test_process_successful_retry(self):
        """Should process successful retry correctly."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            # Enqueue an item
            enqueue("example.com", "block", "timeout", "Error")

            # Make item ready
            items = get_queue_items()
            items[0].next_retry_at = (datetime.now() - timedelta(minutes=1)).isoformat()
            update_item(items[0])

            # Mock successful client response using *_with_result() methods
            mock_client = MagicMock()
            mock_client.block_with_result.return_value = (True, True, APIRequestResult.ok())

            result = process_queue(mock_client)

            assert len(result.succeeded) == 1
            assert result.succeeded[0].domain == "example.com"
            assert len(get_queue_items()) == 0  # Item removed

    def test_process_failed_retry_retryable(self):
        """Should keep retryable failures in queue."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            # Enqueue an item
            enqueue("example.com", "block", "timeout", "Error")

            # Make item ready
            items = get_queue_items()
            items[0].next_retry_at = (datetime.now() - timedelta(minutes=1)).isoformat()
            update_item(items[0])

            # Mock failed client response with retryable error using *_with_result() methods
            mock_client = MagicMock()
            mock_client.block_with_result.return_value = (
                False,
                False,
                APIRequestResult.timeout("Still failing"),
            )

            result = process_queue(mock_client)

            assert len(result.failed) == 1
            assert len(get_queue_items()) == 1  # Item still in queue
            # Attempt count should be incremented
            items = get_queue_items()
            assert items[0].attempt_count == 2  # Initial 1 + 1 from retry

    def test_process_exhausted_retries(self):
        """Should remove items after max retries exceeded."""
        with patch("nextdns_blocker.retry_queue.audit_log"):
            # Enqueue an item
            enqueue("example.com", "block", "timeout", "Error")

            # Make item ready with max attempts
            items = get_queue_items()
            items[0].next_retry_at = (datetime.now() - timedelta(minutes=1)).isoformat()
            items[0].attempt_count = DEFAULT_MAX_RETRIES
            update_item(items[0])

            mock_client = MagicMock()
            result = process_queue(mock_client)

            assert len(result.exhausted) == 1
            assert len(get_queue_items()) == 0  # Item removed


class TestRetryResult:
    """Tests for RetryResult dataclass."""

    def test_default_values(self):
        """Should have empty lists by default."""
        result = RetryResult()
        assert result.succeeded == []
        assert result.failed == []
        assert result.exhausted == []
        assert result.skipped == 0
