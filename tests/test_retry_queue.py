"""Tests for retry queue module."""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from nextdns_blocker.client import APIRequestResult
from nextdns_blocker.retry_queue import (
    DEFAULT_INITIAL_BACKOFF,
    DEFAULT_MAX_RETRIES,
    MAX_BACKOFF,
    RetryItem,
    RetryResult,
    _generate_retry_id,
    _load_queue_data,
    _save_queue_data,
    clear_queue,
    enqueue,
    get_queue_items,
    get_queue_stats,
    get_ready_items,
    process_queue,
    remove_item,
    update_item,
)


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
        assert item.first_attempt  # Should be set automatically
        assert item.last_attempt
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
            "first_attempt": "2025-01-17T10:00:00",
            "last_attempt": "2025-01-17T10:05:00",
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
        assert item.last_attempt  # Should be updated

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


class TestQueueDataIO:
    """Tests for queue data loading and saving."""

    def test_load_empty_file(self, tmp_path: Path):
        """Loading non-existent file returns default structure."""
        with patch(
            "nextdns_blocker.retry_queue.get_retry_queue_file",
            return_value=tmp_path / "retry_queue.json",
        ):
            data = _load_queue_data()
            assert data["version"] == "1.0"
            assert data["retry_entries"] == []

    def test_save_and_load(self, tmp_path: Path):
        """Saved data can be loaded correctly."""
        queue_file = tmp_path / "retry_queue.json"
        with patch("nextdns_blocker.retry_queue.get_retry_queue_file", return_value=queue_file):
            test_data = {
                "version": "1.0",
                "retry_entries": [{"id": "ret_123", "domain": "example.com", "action": "block"}],
            }
            assert _save_queue_data(test_data)
            loaded = _load_queue_data()
            assert loaded == test_data

    def test_load_invalid_json(self, tmp_path: Path):
        """Loading invalid JSON returns default structure."""
        queue_file = tmp_path / "retry_queue.json"
        queue_file.write_text("invalid json {")
        with patch("nextdns_blocker.retry_queue.get_retry_queue_file", return_value=queue_file):
            data = _load_queue_data()
            assert data["version"] == "1.0"
            assert data["retry_entries"] == []


class TestEnqueue:
    """Tests for enqueue function."""

    def test_enqueue_item(self, tmp_path: Path):
        """Should enqueue an item successfully."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
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

    def test_enqueue_duplicate(self, tmp_path: Path):
        """Should not duplicate items for same domain+action."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            id1 = enqueue("example.com", "block", "timeout", "Error 1")
            id2 = enqueue("example.com", "block", "timeout", "Error 2")

            assert id1 == id2  # Same ID returned
            items = get_queue_items()
            assert len(items) == 1  # Only one item


class TestQueueOperations:
    """Tests for queue operations."""

    def test_get_queue_items(self, tmp_path: Path):
        """Should return all queue items."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            enqueue("example1.com", "block", "timeout", "Error")
            enqueue("example2.com", "unblock", "rate_limit", "Error")

            items = get_queue_items()
            assert len(items) == 2

    def test_get_ready_items(self, tmp_path: Path):
        """Should return only ready items."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            # Add item with past retry time
            enqueue("ready.com", "block", "timeout", "Error")

            # Modify to have future retry time
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

    def test_remove_item(self, tmp_path: Path):
        """Should remove item from queue."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            item_id = enqueue("example.com", "block", "timeout", "Error")
            assert len(get_queue_items()) == 1

            result = remove_item(item_id)
            assert result is True
            assert len(get_queue_items()) == 0

    def test_remove_nonexistent_item(self, tmp_path: Path):
        """Should return False for non-existent item."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
        ):
            result = remove_item("nonexistent_id")
            assert result is False

    def test_clear_queue(self, tmp_path: Path):
        """Should clear all items from queue."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            enqueue("example1.com", "block", "timeout", "Error")
            enqueue("example2.com", "unblock", "rate_limit", "Error")
            assert len(get_queue_items()) == 2

            count = clear_queue()
            assert count == 2
            assert len(get_queue_items()) == 0


class TestGetQueueStats:
    """Tests for get_queue_stats function."""

    def test_empty_queue_stats(self, tmp_path: Path):
        """Should return zero stats for empty queue."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
        ):
            stats = get_queue_stats()
            assert stats["total"] == 0
            assert stats["ready"] == 0
            assert stats["pending"] == 0
            assert stats["total_attempts"] == 0

    def test_queue_stats_with_items(self, tmp_path: Path):
        """Should return correct stats for queue with items."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
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

    def test_process_empty_queue(self, tmp_path: Path):
        """Processing empty queue should return empty result."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
        ):
            mock_client = MagicMock()
            result = process_queue(mock_client)

            assert result.succeeded == []
            assert result.failed == []
            assert result.exhausted == []

    def test_process_successful_retry(self, tmp_path: Path):
        """Should process successful retry correctly."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            # Enqueue an item
            enqueue("example.com", "block", "timeout", "Error")

            # Make item ready
            items = get_queue_items()
            items[0].next_retry_at = (datetime.now() - timedelta(minutes=1)).isoformat()
            update_item(items[0])

            # Mock successful client response
            mock_client = MagicMock()
            mock_client.block.return_value = (True, True)

            result = process_queue(mock_client)

            assert len(result.succeeded) == 1
            assert result.succeeded[0].domain == "example.com"
            assert len(get_queue_items()) == 0  # Item removed

    def test_process_failed_retry_retryable(self, tmp_path: Path):
        """Should keep retryable failures in queue."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
            # Enqueue an item
            enqueue("example.com", "block", "timeout", "Error")

            # Make item ready
            items = get_queue_items()
            items[0].next_retry_at = (datetime.now() - timedelta(minutes=1)).isoformat()
            update_item(items[0])

            # Mock failed client response with retryable error
            mock_client = MagicMock()
            mock_client.block.return_value = (False, False)
            mock_client.request.return_value = APIRequestResult.timeout("Still failing")

            result = process_queue(mock_client)

            assert len(result.failed) == 1
            assert len(get_queue_items()) == 1  # Item still in queue
            # Attempt count should be incremented
            items = get_queue_items()
            assert items[0].attempt_count == 1

    def test_process_exhausted_retries(self, tmp_path: Path):
        """Should remove items after max retries exceeded."""
        queue_file = tmp_path / "retry_queue.json"
        lock_file = tmp_path / ".retry_queue.lock"
        with (
            patch(
                "nextdns_blocker.retry_queue.get_retry_queue_file",
                return_value=queue_file,
            ),
            patch("nextdns_blocker.retry_queue._get_lock_file", return_value=lock_file),
            patch("nextdns_blocker.retry_queue.audit_log"),
        ):
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
