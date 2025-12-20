"""Tests for NextDNSClient class."""

from collections import deque
from unittest.mock import patch

import pytest
import requests
import responses

from nextdns_blocker.client import (
    API_URL,
    RATE_LIMIT_REQUESTS,
    RATE_LIMIT_WINDOW,
    NextDNSClient,
    RateLimiter,
)


@pytest.fixture
def client():
    """Create a NextDNSClient instance for testing."""
    return NextDNSClient("testapikey12345", "testprofile")


@pytest.fixture
def mock_denylist():
    """Sample denylist response."""
    return {"data": [{"id": "example.com", "active": True}, {"id": "blocked.com", "active": True}]}


class TestGetDenylist:
    """Tests for get_denylist method."""

    @responses.activate
    def test_get_denylist_success(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        result = client.get_denylist()
        assert result == mock_denylist["data"]

    @responses.activate
    def test_get_denylist_empty(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        result = client.get_denylist()
        assert result == []

    @responses.activate
    @patch("nextdns_blocker.client.time.sleep")
    def test_get_denylist_timeout(self, mock_sleep, client):
        # All retry attempts timeout
        for _ in range(4):
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/testprofile/denylist",
                body=requests.exceptions.Timeout(),
            )
        result = client.get_denylist()
        assert result is None

    @responses.activate
    def test_get_denylist_server_error(self, client):
        responses.add(responses.GET, f"{API_URL}/profiles/testprofile/denylist", status=500)
        result = client.get_denylist()
        assert result is None


class TestFindDomain:
    """Tests for find_domain method."""

    @responses.activate
    def test_find_domain_exists(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        result = client.find_domain("example.com")
        assert result == "example.com"

    @responses.activate
    def test_find_domain_not_found(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        result = client.find_domain("notfound.com")
        assert result is None

    @responses.activate
    def test_find_domain_api_error(self, client):
        responses.add(responses.GET, f"{API_URL}/profiles/testprofile/denylist", status=500)
        result = client.find_domain("example.com")
        assert result is None


class TestBlock:
    """Tests for block method."""

    @responses.activate
    def test_block_new_domain(self, client):
        # First call: get denylist (domain not found)
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # Second call: add to denylist
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"success": True},
            status=200,
        )
        result = client.block("newdomain.com")
        assert result is True

    @responses.activate
    def test_block_already_blocked(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        # Domain already exists, no POST should be made
        result = client.block("example.com")
        assert result is True
        assert len(responses.calls) == 1  # Only GET, no POST

    @responses.activate
    def test_block_api_error(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(responses.POST, f"{API_URL}/profiles/testprofile/denylist", status=500)
        result = client.block("newdomain.com")
        assert result is False


class TestUnblock:
    """Tests for unblock method."""

    @responses.activate
    def test_unblock_existing_domain(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/denylist/example.com",
            json={"success": True},
            status=200,
        )
        result = client.unblock("example.com")
        assert result is True

    @responses.activate
    def test_unblock_not_found(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # Domain not in denylist, should return True (already unblocked)
        result = client.unblock("notfound.com")
        assert result is True
        assert len(responses.calls) == 1  # Only GET, no DELETE

    @responses.activate
    def test_unblock_api_error(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        responses.add(
            responses.DELETE, f"{API_URL}/profiles/testprofile/denylist/example.com", status=500
        )
        result = client.unblock("example.com")
        assert result is False


class TestRequestRetry:
    """Tests for retry logic in request method."""

    @responses.activate
    @patch("nextdns_blocker.client.time.sleep")
    def test_retry_on_timeout(self, mock_sleep, client):
        # First two calls timeout, third succeeds
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            body=requests.exceptions.Timeout(),
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            body=requests.exceptions.Timeout(),
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        result = client.get_denylist()
        assert result == []
        assert len(responses.calls) == 3
        # Verify backoff was called (not actual sleep)
        assert mock_sleep.call_count == 2

    @responses.activate
    @patch("nextdns_blocker.client.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep, client):
        # All calls timeout (1 original + 3 retries = 4 total)
        for _ in range(4):
            responses.add(
                responses.GET,
                f"{API_URL}/profiles/testprofile/denylist",
                body=requests.exceptions.Timeout(),
            )
        result = client.get_denylist()
        assert result is None
        assert len(responses.calls) == 4
        # Verify backoff was called for all retries
        assert mock_sleep.call_count == 3


class TestHeaders:
    """Tests for API headers."""

    @responses.activate
    def test_api_key_header(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        client.get_denylist()
        assert responses.calls[0].request.headers["X-Api-Key"] == "testapikey12345"

    @responses.activate
    def test_content_type_header(self, client):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        client.get_denylist()
        assert responses.calls[0].request.headers["Content-Type"] == "application/json"


class TestDenylistCache:
    """Tests for denylist caching functionality."""

    @responses.activate
    def test_cache_hit(self, client, mock_denylist):
        """Second call should use cache, not make API request."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        # First call populates cache
        result1 = client.get_denylist()
        assert result1 == mock_denylist["data"]
        assert len(responses.calls) == 1

        # Second call should use cache
        result2 = client.get_denylist()
        assert result2 == mock_denylist["data"]
        assert len(responses.calls) == 1  # No new API call

    @responses.activate
    def test_cache_bypass(self, client, mock_denylist):
        """use_cache=False should bypass cache."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        # First call populates cache
        client.get_denylist()
        assert len(responses.calls) == 1

        # Second call with use_cache=False should make API request
        client.get_denylist(use_cache=False)
        assert len(responses.calls) == 2

    @responses.activate
    def test_find_domain_uses_cache(self, client, mock_denylist):
        """find_domain should use cache for subsequent calls."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        # First call populates cache
        result1 = client.find_domain("example.com")
        assert result1 == "example.com"
        assert len(responses.calls) == 1

        # Second call should use cache
        result2 = client.find_domain("blocked.com")
        assert result2 == "blocked.com"
        assert len(responses.calls) == 1  # No new API call

    @responses.activate
    def test_refresh_cache(self, client, mock_denylist):
        """refresh_cache should invalidate and refetch."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # First call
        client.get_denylist()
        assert len(responses.calls) == 1

        # Refresh should make new API call
        client.refresh_cache()
        assert len(responses.calls) == 2


class TestIsBlocked:
    """Tests for is_blocked convenience method."""

    @responses.activate
    def test_is_blocked_true(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        assert client.is_blocked("example.com") is True

    @responses.activate
    def test_is_blocked_false(self, client, mock_denylist):
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        assert client.is_blocked("notblocked.com") is False


class TestOptimisticCacheUpdates:
    """Tests for optimistic cache updates after block/unblock."""

    @responses.activate
    def test_block_updates_cache(self, client):
        """After blocking, cache should contain the domain."""
        # Initial denylist
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"data": []},
            status=200,
        )
        # Block request
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/testprofile/denylist",
            json={"id": "newdomain.com"},
            status=200,
        )

        # Verify not blocked initially
        assert client.find_domain("newdomain.com") is None

        # Block the domain
        client.block("newdomain.com")

        # Cache should now contain the domain (no new API call needed)
        # The cache contains() check uses the optimistically updated set
        assert client._cache.contains("newdomain.com") is True

    @responses.activate
    def test_unblock_updates_cache(self, client, mock_denylist):
        """After unblocking, cache should not contain the domain."""
        # Initial denylist
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/testprofile/denylist",
            json=mock_denylist,
            status=200,
        )
        # Unblock request
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/testprofile/denylist/example.com",
            json={},
            status=200,
        )

        # Verify blocked initially
        assert client.find_domain("example.com") == "example.com"

        # Unblock the domain
        client.unblock("example.com")

        # Cache should no longer contain the domain
        assert client._cache.contains("example.com") is False


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_init_default_values(self):
        """RateLimiter initializes with default values."""
        limiter = RateLimiter()
        assert limiter.max_requests == RATE_LIMIT_REQUESTS
        assert limiter.window_seconds == RATE_LIMIT_WINDOW
        assert len(limiter._requests) == 0

    def test_init_custom_values(self):
        """RateLimiter initializes with custom values."""
        limiter = RateLimiter(max_requests=10, window_seconds=30)
        assert limiter.max_requests == 10
        assert limiter.window_seconds == 30

    def test_acquire_under_limit(self):
        """acquire() returns 0 when under the rate limit."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        for _ in range(5):
            waited = limiter.acquire()
            assert waited == 0
        assert len(limiter._requests) == 5

    def test_acquire_at_limit_waits(self):
        """acquire() waits when rate limit is reached."""
        limiter = RateLimiter(max_requests=2, window_seconds=1)

        # Fill up the rate limit
        limiter.acquire()
        limiter.acquire()

        # Next acquire should wait using Condition.wait
        with patch.object(limiter._condition, "wait") as mock_wait:
            limiter.acquire()
            # Should have called wait
            assert mock_wait.called

    def test_expired_requests_cleaned(self):
        """Expired requests are removed from the window."""
        import time

        limiter = RateLimiter(max_requests=2, window_seconds=60)

        # Add old timestamp (expired) - using time.monotonic() since that's what RateLimiter uses
        old_time = time.monotonic() - 120  # 2 minutes ago
        limiter._requests = deque([old_time])

        # acquire() should clean up expired and allow request
        waited = limiter.acquire()
        assert waited == 0
        assert len(limiter._requests) == 1
        # The old expired request should be gone, only new one remains
        assert limiter._requests[0] > old_time

    def test_sliding_window_behavior(self):
        """Rate limiter uses sliding window correctly."""
        import time

        limiter = RateLimiter(max_requests=3, window_seconds=60)

        now = time.monotonic()

        # Simulate 2 requests from 30 seconds ago (still valid)
        limiter._requests = deque([now - 30, now - 25])

        # Should allow 1 more request without waiting
        waited = limiter.acquire()
        assert waited == 0
        assert len(limiter._requests) == 3

    def test_multiple_acquires_track_timestamps(self):
        """Each acquire adds a timestamp to the list."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)

        for i in range(5):
            limiter.acquire()
            assert len(limiter._requests) == i + 1
