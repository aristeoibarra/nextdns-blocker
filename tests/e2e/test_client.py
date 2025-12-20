"""E2E tests for NextDNS client module."""

from __future__ import annotations

import threading
import time
from unittest.mock import patch

import pytest
import responses

from nextdns_blocker.client import (
    API_URL,
    AllowlistCache,
    DenylistCache,
    DomainCache,
    NextDNSClient,
    RateLimiter,
)
from nextdns_blocker.exceptions import APIError, DomainValidationError


class TestRateLimiter:
    """Tests for the rate limiter."""

    def test_acquire_without_limit(self) -> None:
        """Test acquiring without hitting rate limit."""
        limiter = RateLimiter(max_requests=10, window_seconds=60)
        waited = limiter.acquire()
        assert waited == 0

    def test_acquire_with_timeout(self) -> None:
        """Test acquiring with timeout."""
        limiter = RateLimiter(max_requests=1, window_seconds=60)
        limiter.acquire()  # First request

        # Second request should timeout
        with pytest.raises(TimeoutError, match="timed out"):
            limiter.acquire(timeout=0.1)

    def test_acquire_waits_for_window(self) -> None:
        """Test that acquire waits for rate limit window."""
        limiter = RateLimiter(max_requests=1, window_seconds=1)
        limiter.acquire()

        start = time.time()
        # This should wait about 1 second
        waited = limiter.acquire(timeout=2)
        elapsed = time.time() - start

        assert waited > 0
        assert elapsed >= 0.9  # Should have waited

    def test_thread_safety(self) -> None:
        """Test rate limiter is thread-safe."""
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        results: list[float] = []
        errors: list[Exception] = []

        def acquire_and_record() -> None:
            try:
                waited = limiter.acquire(timeout=5)
                results.append(waited)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=acquire_and_record) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 5


class TestDomainCache:
    """Tests for the domain cache."""

    def test_cache_set_and_get(self) -> None:
        """Test setting and getting cache data."""
        cache = DomainCache(ttl=60)
        data = [{"id": "example.com"}]
        cache.set(data)

        result = cache.get()
        assert result == data

    def test_cache_is_valid(self) -> None:
        """Test cache validity check."""
        cache = DomainCache(ttl=60)
        assert cache.is_valid() is False

        cache.set([{"id": "example.com"}])
        assert cache.is_valid() is True

    def test_cache_expires(self) -> None:
        """Test cache expiration."""
        cache = DomainCache(ttl=1)  # 1 second TTL
        cache.set([{"id": "example.com"}])

        assert cache.is_valid() is True
        time.sleep(1.1)
        assert cache.is_valid() is False

    def test_cache_contains(self) -> None:
        """Test cache contains check."""
        cache = DomainCache(ttl=60)
        cache.set([{"id": "example.com"}])

        assert cache.contains("example.com") is True
        assert cache.contains("other.com") is False

    def test_cache_contains_expired(self) -> None:
        """Test contains returns None when expired."""
        cache = DomainCache(ttl=1)
        cache.set([{"id": "example.com"}])
        time.sleep(1.1)

        assert cache.contains("example.com") is None

    def test_cache_invalidate(self) -> None:
        """Test cache invalidation."""
        cache = DomainCache(ttl=60)
        cache.set([{"id": "example.com"}])

        assert cache.is_valid() is True
        cache.invalidate()
        assert cache.is_valid() is False

    def test_cache_add_domain(self) -> None:
        """Test adding domain to cache."""
        cache = DomainCache(ttl=60)
        cache.set([{"id": "example.com"}])
        cache.add_domain("new.com")

        assert cache.contains("new.com") is True

    def test_cache_add_domain_no_data(self) -> None:
        """Test adding domain when no cache data exists."""
        cache = DomainCache(ttl=60)
        cache.add_domain("new.com")  # Should not raise

        # Contains returns None since cache is not valid
        assert cache.contains("new.com") is None

    def test_cache_remove_domain(self) -> None:
        """Test removing domain from cache."""
        cache = DomainCache(ttl=60)
        cache.set([{"id": "example.com"}])
        cache.remove_domain("example.com")

        assert cache.contains("example.com") is False


class TestDenylistCache:
    """Tests for denylist cache."""

    def test_denylist_cache_inherits(self) -> None:
        """Test DenylistCache inherits from DomainCache."""
        cache = DenylistCache()
        assert isinstance(cache, DomainCache)


class TestAllowlistCache:
    """Tests for allowlist cache."""

    def test_allowlist_cache_inherits(self) -> None:
        """Test AllowlistCache inherits from DomainCache."""
        cache = AllowlistCache()
        assert isinstance(cache, DomainCache)


class TestNextDNSClient:
    """Tests for NextDNS API client."""

    def test_client_initialization(self) -> None:
        """Test client initialization."""
        client = NextDNSClient(
            api_key="test-key",
            profile_id="abc123",
            timeout=10,
            retries=3,
        )

        assert client.profile_id == "abc123"
        assert client.timeout == 10
        assert client.retries == 3
        # Verify headers are built correctly via _get_headers() method
        headers = client._get_headers()
        assert "X-Api-Key" in headers
        assert headers["X-Api-Key"] == "test-key"
        assert headers["Content-Type"] == "application/json"

    def test_calculate_backoff(self) -> None:
        """Test backoff calculation with jitter.

        Backoff now uses full jitter strategy: random value between 0 and
        the calculated exponential delay (capped at BACKOFF_MAX=30).
        """
        client = NextDNSClient("key", "profile")

        # Attempt 0: delay = 1 * 2^0 = 1, jitter in [0, 1]
        backoff_0 = client._calculate_backoff(0)
        assert 0 <= backoff_0 <= 1.0

        # Attempt 1: delay = 1 * 2^1 = 2, jitter in [0, 2]
        backoff_1 = client._calculate_backoff(1)
        assert 0 <= backoff_1 <= 2.0

        # Attempt 2: delay = 1 * 2^2 = 4, jitter in [0, 4]
        backoff_2 = client._calculate_backoff(2)
        assert 0 <= backoff_2 <= 4.0

        # Attempt 10: delay = 1 * 2^10 = 1024, capped at 30, jitter in [0, 30]
        backoff_10 = client._calculate_backoff(10)
        assert 0 <= backoff_10 <= 30.0

    @responses.activate
    def test_request_get_success(self) -> None:
        """Test successful GET request."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.request("GET", "/profiles/abc123/denylist")

        assert result == {"data": []}

    @responses.activate
    def test_request_post_success(self) -> None:
        """Test successful POST request."""
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/abc123/denylist",
            json={"success": True},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.request("POST", "/profiles/abc123/denylist", {"id": "example.com"})

        assert result == {"success": True}

    @responses.activate
    def test_request_delete_success(self) -> None:
        """Test successful DELETE request."""
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/abc123/denylist/example.com",
            body="",
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.request("DELETE", "/profiles/abc123/denylist/example.com")

        assert result == {"success": True}

    def test_request_unsupported_method(self) -> None:
        """Test unsupported HTTP method."""
        client = NextDNSClient("test-key", "abc123")
        result = client.request("PATCH", "/profiles/abc123/denylist")

        assert result is None

    @responses.activate
    def test_request_invalid_json_response(self) -> None:
        """Test handling of invalid JSON response."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body="not json {",
            status=200,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.request("GET", "/profiles/abc123/denylist")

        assert result is None

    @responses.activate
    def test_request_timeout_retry(self) -> None:
        """Test request retries on timeout."""
        import requests

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body=requests.exceptions.Timeout(),
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123", retries=1)
        with patch("nextdns_blocker.client.time.sleep"):  # Speed up test
            result = client.request("GET", "/profiles/abc123/denylist")

        assert result == {"data": []}

    @responses.activate
    def test_request_timeout_exhausted(self) -> None:
        """Test request fails after retries exhausted."""
        import requests

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body=requests.exceptions.Timeout(),
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body=requests.exceptions.Timeout(),
        )

        client = NextDNSClient("test-key", "abc123", retries=1)
        with patch("nextdns_blocker.client.time.sleep"):
            result = client.request("GET", "/profiles/abc123/denylist")

        assert result is None

    @responses.activate
    def test_request_http_429_triggers_retry_logic(self) -> None:
        """Test 429 triggers retry logic and eventually fails if not recovered."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"error": "rate limited"},
            status=429,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.request("GET", "/profiles/abc123/denylist")

        # With 0 retries, 429 error returns None
        assert result is None

    @responses.activate
    def test_request_http_500_triggers_retry_logic(self) -> None:
        """Test 500 triggers retry logic and eventually fails if not recovered."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"error": "server error"},
            status=500,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.request("GET", "/profiles/abc123/denylist")

        # With 0 retries, 500 error returns None
        assert result is None

    @responses.activate
    def test_request_http_400_no_retry(self) -> None:
        """Test request doesn't retry on 400 client error."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"error": "bad request"},
            status=400,
        )

        client = NextDNSClient("test-key", "abc123", retries=3)
        result = client.request("GET", "/profiles/abc123/denylist")

        assert result is None
        assert len(responses.calls) == 1  # Only one call, no retries

    @responses.activate
    def test_request_connection_error_retry(self) -> None:
        """Test request retries on connection error."""
        import requests

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body=requests.exceptions.ConnectionError(),
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123", retries=1)
        with patch("nextdns_blocker.client.time.sleep"):
            result = client.request("GET", "/profiles/abc123/denylist")

        assert result == {"data": []}

    @responses.activate
    def test_request_or_raise_success(self) -> None:
        """Test request_or_raise on success."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.request_or_raise("GET", "/profiles/abc123/denylist")

        assert result == {"data": []}

    @responses.activate
    def test_request_or_raise_failure(self) -> None:
        """Test request_or_raise raises on failure."""
        import requests

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body=requests.exceptions.ConnectionError(),
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        with pytest.raises(APIError, match="API request failed"):
            client.request_or_raise("GET", "/profiles/abc123/denylist")


class TestNextDNSClientDenylist:
    """Tests for denylist operations."""

    @responses.activate
    def test_get_denylist(self) -> None:
        """Test getting denylist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.get_denylist()

        assert result == [{"id": "example.com"}]

    @responses.activate
    def test_get_denylist_uses_cache(self) -> None:
        """Test get_denylist uses cache."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        client.get_denylist()  # First call
        client.get_denylist()  # Second call should use cache

        assert len(responses.calls) == 1  # Only one API call

    @responses.activate
    def test_get_denylist_failure(self) -> None:
        """Test get_denylist handles failure."""
        import requests

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            body=requests.exceptions.ConnectionError(),
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.get_denylist()

        assert result is None

    @responses.activate
    def test_find_domain(self) -> None:
        """Test finding domain in denylist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.find_domain("example.com")

        assert result == "example.com"

    @responses.activate
    def test_find_domain_not_found(self) -> None:
        """Test finding domain that's not in denylist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "other.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.find_domain("example.com")

        assert result is None

    @responses.activate
    def test_is_blocked(self) -> None:
        """Test is_blocked."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")

        assert client.is_blocked("example.com") is True
        assert client.is_blocked("other.com") is False

    @responses.activate
    def test_block_domain(self) -> None:
        """Test blocking a domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/abc123/denylist",
            json={"success": True},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.block("example.com")

        assert result is True

    @responses.activate
    def test_block_already_blocked(self) -> None:
        """Test blocking already blocked domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.block("example.com")

        assert result is True
        # Only GET call, no POST
        assert len(responses.calls) == 1

    def test_block_invalid_domain(self) -> None:
        """Test blocking invalid domain."""
        client = NextDNSClient("test-key", "abc123")

        with pytest.raises(DomainValidationError):
            client.block("not-a-valid-domain!")

    @responses.activate
    def test_block_failure(self) -> None:
        """Test block failure."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/abc123/denylist",
            json={"error": "failed"},
            status=500,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.block("example.com")

        assert result is False

    @responses.activate
    def test_unblock_domain(self) -> None:
        """Test unblocking a domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/abc123/denylist/example.com",
            body="",
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.unblock("example.com")

        assert result is True

    @responses.activate
    def test_unblock_not_blocked(self) -> None:
        """Test unblocking domain that's not blocked."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.unblock("example.com")

        assert result is True
        # Only GET call, no DELETE
        assert len(responses.calls) == 1

    def test_unblock_invalid_domain(self) -> None:
        """Test unblocking invalid domain."""
        client = NextDNSClient("test-key", "abc123")

        with pytest.raises(DomainValidationError):
            client.unblock("not-a-valid-domain!")

    @responses.activate
    def test_unblock_failure(self) -> None:
        """Test unblock failure."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/abc123/denylist/example.com",
            json={"error": "failed"},
            status=500,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.unblock("example.com")

        assert result is False

    @responses.activate
    def test_refresh_cache(self) -> None:
        """Test cache refresh."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/denylist",
            json={"data": [{"id": "example.com"}, {"id": "new.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        client.get_denylist()  # Populate cache
        result = client.refresh_cache()  # Force refresh

        assert result is True
        assert len(responses.calls) == 2  # Two API calls


class TestNextDNSClientAllowlist:
    """Tests for allowlist operations."""

    @responses.activate
    def test_get_allowlist(self) -> None:
        """Test getting allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.get_allowlist()

        assert result == [{"id": "example.com"}]

    @responses.activate
    def test_get_allowlist_uses_cache(self) -> None:
        """Test get_allowlist uses cache."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        client.get_allowlist()  # First call
        client.get_allowlist()  # Second call should use cache

        assert len(responses.calls) == 1

    @responses.activate
    def test_get_allowlist_failure(self) -> None:
        """Test get_allowlist handles failure."""
        import requests

        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            body=requests.exceptions.ConnectionError(),
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.get_allowlist()

        assert result is None

    @responses.activate
    def test_find_in_allowlist(self) -> None:
        """Test finding domain in allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.find_in_allowlist("example.com")

        assert result == "example.com"

    @responses.activate
    def test_find_in_allowlist_not_found(self) -> None:
        """Test finding domain not in allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.find_in_allowlist("example.com")

        assert result is None

    @responses.activate
    def test_is_allowed(self) -> None:
        """Test is_allowed."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")

        assert client.is_allowed("example.com") is True
        assert client.is_allowed("other.com") is False

    @responses.activate
    def test_allow_domain(self) -> None:
        """Test allowing a domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"success": True},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.allow("example.com")

        assert result is True

    @responses.activate
    def test_allow_already_allowed(self) -> None:
        """Test allowing already allowed domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.allow("example.com")

        assert result is True
        assert len(responses.calls) == 1

    def test_allow_invalid_domain(self) -> None:
        """Test allowing invalid domain."""
        client = NextDNSClient("test-key", "abc123")

        with pytest.raises(DomainValidationError):
            client.allow("not-a-valid-domain!")

    @responses.activate
    def test_allow_failure(self) -> None:
        """Test allow failure."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": []},
            status=200,
        )
        responses.add(
            responses.POST,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"error": "failed"},
            status=500,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.allow("example.com")

        assert result is False

    @responses.activate
    def test_disallow_domain(self) -> None:
        """Test disallowing a domain."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/abc123/allowlist/example.com",
            body="",
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.disallow("example.com")

        assert result is True

    @responses.activate
    def test_disallow_not_in_list(self) -> None:
        """Test disallowing domain not in allowlist."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": []},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        result = client.disallow("example.com")

        assert result is True
        assert len(responses.calls) == 1

    def test_disallow_invalid_domain(self) -> None:
        """Test disallowing invalid domain."""
        client = NextDNSClient("test-key", "abc123")

        with pytest.raises(DomainValidationError):
            client.disallow("not-a-valid-domain!")

    @responses.activate
    def test_disallow_failure(self) -> None:
        """Test disallow failure."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )
        responses.add(
            responses.DELETE,
            f"{API_URL}/profiles/abc123/allowlist/example.com",
            json={"error": "failed"},
            status=500,
        )

        client = NextDNSClient("test-key", "abc123", retries=0)
        result = client.disallow("example.com")

        assert result is False

    @responses.activate
    def test_refresh_allowlist_cache(self) -> None:
        """Test allowlist cache refresh."""
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{API_URL}/profiles/abc123/allowlist",
            json={"data": [{"id": "example.com"}, {"id": "new.com"}]},
            status=200,
        )

        client = NextDNSClient("test-key", "abc123")
        client.get_allowlist()  # Populate cache
        result = client.refresh_allowlist_cache()

        assert result is True
        assert len(responses.calls) == 2
