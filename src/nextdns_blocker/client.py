"""NextDNS API client with caching and rate limiting."""

import json
import logging
import os
import random
import threading
import time
from collections import deque
from typing import Any, Optional

import requests

from .common import safe_int, validate_domain
from .config import DEFAULT_RETRIES, DEFAULT_TIMEOUT
from .exceptions import APIError, DomainValidationError

# =============================================================================
# CONSTANTS
# =============================================================================

API_URL = "https://api.nextdns.io"

# Rate limiting and backoff settings (configurable via environment variables)
# Minimum bounds enforced to prevent misconfiguration:
# - RATE_LIMIT_REQUESTS: Max 1000 to prevent API abuse, min 1 to ensure limit exists
# - RATE_LIMIT_WINDOW: Max 3600s (1 hour) for reasonable window, min 1s to prevent division issues
_raw_rate_limit_requests = safe_int(os.environ.get("RATE_LIMIT_REQUESTS"), 30)
RATE_LIMIT_REQUESTS = min(1000, max(1, _raw_rate_limit_requests))

_raw_rate_limit_window = safe_int(os.environ.get("RATE_LIMIT_WINDOW"), 60)
RATE_LIMIT_WINDOW = min(3600, max(1, _raw_rate_limit_window))

BACKOFF_BASE = 1.0  # Base delay for exponential backoff (seconds)
BACKOFF_MAX = 30.0  # Maximum backoff delay (seconds)

_raw_cache_ttl = safe_int(os.environ.get("CACHE_TTL"), 60)
CACHE_TTL = min(3600, max(1, _raw_cache_ttl))  # 1-3600 seconds TTL

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITER
# =============================================================================


class RateLimiter:
    """Thread-safe rate limiter using sliding window algorithm."""

    def __init__(
        self, max_requests: int = RATE_LIMIT_REQUESTS, window_seconds: int = RATE_LIMIT_WINDOW
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # Use deque for O(1) popleft operations when removing expired timestamps
        self._requests: deque[float] = deque()
        self._condition = threading.Condition()

    def acquire(self, timeout: Optional[float] = None) -> float:
        """
        Acquire permission to make a request, waiting if necessary.

        Uses time.monotonic() for accurate interval measurement that is not
        affected by system clock changes.

        Args:
            timeout: Maximum time to wait in seconds (None for no timeout)

        Returns:
            Time waited in seconds (0 if no wait was needed)

        Raises:
            TimeoutError: If timeout is reached while waiting for rate limit
        """
        total_waited = 0.0
        deadline = None if timeout is None else time.monotonic() + timeout

        with self._condition:
            while True:
                now = time.monotonic()

                # Check if we've exceeded the timeout
                if deadline is not None and now >= deadline:
                    raise TimeoutError("Rate limiter acquire timed out")

                # Remove expired timestamps from the front (O(1) per removal with deque)
                cutoff = now - self.window_seconds
                while self._requests and self._requests[0] <= cutoff:
                    self._requests.popleft()

                # Check if we can proceed
                if len(self._requests) < self.max_requests:
                    self._requests.append(now)
                    return total_waited

                # Calculate wait time until oldest request expires
                wait_time = self._requests[0] - cutoff
                if wait_time <= 0:
                    # Oldest request already expired, try again
                    continue

                # Apply timeout constraint if set
                if deadline is not None:
                    remaining = deadline - now
                    wait_time = min(wait_time, remaining)

                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")

                # Wait with Condition - releases lock during wait, reacquires before returning
                # This is thread-safe: other threads can check/modify while we wait
                wait_start = time.monotonic()
                self._condition.wait(timeout=wait_time)
                # Track actual time waited (handles spurious wakeups correctly)
                actual_waited = time.monotonic() - wait_start
                total_waited += actual_waited


# =============================================================================
# CACHES
# =============================================================================


class DomainCache:
    """Thread-safe cache class for domain lists to reduce API calls.

    Uses time.monotonic() for cache expiration to ensure accurate timing
    that is not affected by system clock changes.
    """

    def __init__(self, ttl: int = CACHE_TTL) -> None:
        """
        Initialize the cache.

        Args:
            ttl: Time to live in seconds
        """
        self.ttl = ttl
        self._data: Optional[list[dict[str, Any]]] = None
        self._domains: set[str] = set()
        self._timestamp: float = 0
        self._lock = threading.Lock()

    def _is_valid_unlocked(self) -> bool:
        """Check if cache is still valid (internal, must hold lock)."""
        return self._data is not None and (time.monotonic() - self._timestamp) < self.ttl

    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        with self._lock:
            return self._is_valid_unlocked()

    def get(self) -> Optional[list[dict[str, Any]]]:
        """Get cached data if valid."""
        with self._lock:
            if self._is_valid_unlocked():
                return self._data
            return None

    def set(self, data: list[dict[str, Any]]) -> None:
        """Update cache with new data."""
        with self._lock:
            self._data = data
            # Filter out entries without valid id to prevent false positives
            self._domains = {str(entry["id"]) for entry in data if entry.get("id")}
            self._timestamp = time.monotonic()

    def contains(self, domain: str) -> Optional[bool]:
        """
        Check if domain is in cache.

        This method uses a 3-state return to distinguish between:
        - True: Domain is definitely in the cached list
        - False: Domain is definitely NOT in the cached list
        - None: Cache is expired/invalid, lookup result is unknown

        This allows callers to handle cache misses appropriately (e.g., by
        fetching fresh data from the API when None is returned).

        Args:
            domain: Domain name to check

        Returns:
            True if domain is in cache, False if not in cache,
            None if cache is invalid/expired and lookup cannot be performed
        """
        with self._lock:
            if self._data is None or (time.monotonic() - self._timestamp) >= self.ttl:
                return None
            return domain in self._domains

    def invalidate(self) -> None:
        """Invalidate the cache."""
        with self._lock:
            self._data = None
            self._domains.clear()  # More efficient than creating new set
            self._timestamp = 0

    def add_domain(self, domain: str) -> None:
        """
        Add a domain to the cache (for optimistic updates).

        Thread-safe: uses set for _domains to prevent duplicates,
        and checks before appending to _data list.
        """
        with self._lock:
            if self._data is not None:
                # Use set.add which handles duplicates automatically
                if domain not in self._domains:
                    self._domains.add(domain)
                    self._data.append({"id": domain, "active": True})

    def remove_domain(self, domain: str) -> None:
        """Remove a domain from the cache (for optimistic updates)."""
        with self._lock:
            self._domains.discard(domain)
            # Keep _data in sync with _domains
            if self._data is not None:
                self._data = [entry for entry in self._data if entry.get("id") != domain]


class DenylistCache(DomainCache):
    """Cache for denylist (blocked domains) to reduce API calls.

    This specialized cache is used for storing blocked domains fetched from
    the NextDNS API. It inherits all functionality from DomainCache.

    The separate class allows for:
    - Type-safe distinction between denylist and allowlist caches
    - Future extensibility for denylist-specific behavior
    - Clear semantic meaning in code that handles both lists

    Example:
        cache = DenylistCache(ttl=60)
        cache.set([{"id": "example.com", "active": True}])
        is_blocked = cache.contains("example.com")
    """

    pass


class AllowlistCache(DomainCache):
    """Cache for allowlist (allowed domains) to reduce API calls.

    This specialized cache is used for storing allowed domains fetched from
    the NextDNS API. It inherits all functionality from DomainCache.

    The separate class allows for:
    - Type-safe distinction between denylist and allowlist caches
    - Future extensibility for allowlist-specific behavior
    - Clear semantic meaning in code that handles both lists

    Example:
        cache = AllowlistCache(ttl=60)
        cache.set([{"id": "trusted.com", "active": True}])
        is_allowed = cache.contains("trusted.com")
    """

    pass


# =============================================================================
# NEXTDNS CLIENT
# =============================================================================


class NextDNSClient:
    """Client for interacting with the NextDNS API with caching and rate limiting."""

    def __init__(
        self,
        api_key: str,
        profile_id: str,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        """
        Initialize the NextDNS client.

        Args:
            api_key: NextDNS API key
            profile_id: NextDNS profile ID
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
        """
        self.profile_id = profile_id
        self.timeout = timeout
        self.retries = retries
        self._api_key = api_key  # Store privately to avoid accidental exposure
        self._rate_limiter = RateLimiter()
        self._cache = DenylistCache()
        self._allowlist_cache = AllowlistCache()

    def _get_headers(self) -> dict[str, str]:
        """
        Build request headers dynamically.

        Headers are constructed on-demand rather than stored as an instance
        variable to prevent accidental exposure of the API key in logs,
        stack traces, or object serialization.

        Returns:
            Dict with required API headers
        """
        return {"X-Api-Key": self._api_key, "Content-Type": "application/json"}

    def _redacted_headers(self) -> dict[str, str]:
        """Return headers with API key fully redacted for safe logging."""
        return {
            "X-Api-Key": "***REDACTED***",
            "Content-Type": "application/json",
        }

    def __repr__(self) -> str:
        """Return a safe string representation without exposing API key."""
        return f"NextDNSClient(profile_id={self.profile_id!r}, timeout={self.timeout}, retries={self.retries})"

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Uses "full jitter" strategy to prevent thundering herd problem
        when multiple clients retry simultaneously.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds (with random jitter between 0 and calculated delay)
        """
        delay = BACKOFF_BASE * (2**attempt)
        capped_delay = min(delay, BACKOFF_MAX)
        # Full jitter: random value between 0 and capped_delay
        return random.uniform(0, capped_delay)

    def request(
        self, method: str, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> Optional[dict[str, Any]]:
        """
        Make an HTTP request to the NextDNS API with retry logic and exponential backoff.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            data: Optional request body for POST requests

        Returns:
            Response JSON as dict, or None if request failed
        """
        url = f"{API_URL}{endpoint}"

        # Validate HTTP method
        method_upper = method.upper()
        valid_methods = ("GET", "POST", "DELETE", "PUT", "PATCH")
        if method_upper not in valid_methods:
            raise ValueError(
                f"Unsupported HTTP method: {method}. Valid methods: {', '.join(valid_methods)}"
            )

        for attempt in range(self.retries + 1):
            # Apply rate limiting
            self._rate_limiter.acquire()

            try:
                # Use requests.request() for all methods to reduce code duplication
                response = requests.request(
                    method=method_upper,
                    url=url,
                    headers=self._get_headers(),
                    json=data if method_upper in ("POST", "PUT", "PATCH") else None,
                    timeout=self.timeout,
                )

                response.raise_for_status()

                # Handle empty responses - expected for DELETE (204 No Content)
                # and some POST operations
                if not response.text or not response.text.strip():
                    # 204 No Content is explicitly expected to be empty
                    if response.status_code == 204:
                        return {"success": True}
                    # For other success codes, log but still treat as success
                    # since raise_for_status() already validated the status
                    if response.status_code in (200, 201, 202):
                        logger.debug(
                            f"Empty response body for {method} {endpoint} "
                            f"(status: {response.status_code})"
                        )
                        return {"success": True}
                    # Unexpected empty response for other status codes
                    logger.warning(
                        f"Unexpected empty response for {method} {endpoint} "
                        f"(status: {response.status_code})"
                    )
                    return {"success": True}

                # Parse JSON with error handling
                try:
                    result: dict[str, Any] = response.json()
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response for {method} {endpoint}: {e}")
                    return None

            except requests.exceptions.Timeout:
                if attempt < self.retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Request timeout for {method} {endpoint}, "
                        f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(f"API timeout after {self.retries} retries: {method} {endpoint}")
                return None
            except requests.exceptions.HTTPError as e:
                # Retry on 429 (rate limit) and 5xx errors
                # Use getattr for safer access in case response is malformed
                status_code = getattr(e.response, "status_code", 0) if e.response else 0
                if status_code == 429 or (500 <= status_code < 600):
                    if attempt < self.retries:
                        backoff = self._calculate_backoff(attempt)
                        logger.warning(
                            f"HTTP {status_code} for {method} {endpoint}, "
                            f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                        )
                        time.sleep(backoff)
                        continue
                logger.error(f"API HTTP error for {method} {endpoint}: {e}")
                return None
            except requests.exceptions.RequestException as e:
                if attempt < self.retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Request error for {method} {endpoint}, "
                        f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(f"API request error for {method} {endpoint}: {e}")
                return None

        return None

    def request_or_raise(
        self, method: str, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the NextDNS API, raising APIError on failure.

        This is an alternative to request() that raises an exception instead
        of returning None on failure, useful when errors should be propagated.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            data: Optional request body for POST requests

        Returns:
            Response JSON as dict

        Raises:
            APIError: If the request fails after all retries
        """
        result = self.request(method, endpoint, data)
        if result is None:
            raise APIError(f"API request failed: {method} {endpoint}")
        return result

    # -------------------------------------------------------------------------
    # DENYLIST METHODS
    # -------------------------------------------------------------------------

    def get_denylist(self, use_cache: bool = True) -> Optional[list[dict[str, Any]]]:
        """
        Fetch the current denylist from NextDNS.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            List of blocked domains, or None if request failed
        """
        # Check cache first
        if use_cache:
            cached = self._cache.get()
            if cached is not None:
                logger.debug("Using cached denylist")
                return cached

        result = self.request("GET", f"/profiles/{self.profile_id}/denylist")
        if result is None:
            logger.warning("Failed to fetch denylist from API")
            return None

        data: list[dict[str, Any]] = result.get("data", [])
        self._cache.set(data)
        return data

    def find_domain(self, domain: str, use_cache: bool = True) -> Optional[str]:
        """
        Find a domain in the denylist.

        Args:
            domain: Domain name to find
            use_cache: Whether to use cached data if available

        Returns:
            Domain name if found, None otherwise
        """
        # Quick cache check
        if use_cache:
            cached_result = self._cache.contains(domain)
            if cached_result is not None:
                return domain if cached_result else None

        denylist = self.get_denylist(use_cache=use_cache)
        if denylist is None:
            return None

        for entry in denylist:
            if entry.get("id") == domain:
                return domain
        return None

    def is_blocked(self, domain: str) -> bool:
        """
        Check if a domain is currently blocked.

        Args:
            domain: Domain name to check

        Returns:
            True if blocked, False otherwise
        """
        return self.find_domain(domain) is not None

    def block(self, domain: str) -> bool:
        """
        Add a domain to the denylist.

        Args:
            domain: Domain name to block

        Returns:
            True if successful, False otherwise

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        # Check if already blocked (using cache for efficiency)
        if self.find_domain(domain):
            logger.debug(f"Domain already blocked: {domain}")
            return True

        result = self.request(
            "POST", f"/profiles/{self.profile_id}/denylist", {"id": domain, "active": True}
        )

        if result is not None:
            # Optimistic cache update
            self._cache.add_domain(domain)
            logger.info(f"Blocked: {domain}")
            return True

        logger.error(f"Failed to block: {domain}")
        return False

    def unblock(self, domain: str) -> bool:
        """
        Remove a domain from the denylist.

        Args:
            domain: Domain name to unblock

        Returns:
            True if successful (including if domain wasn't blocked), False on error

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if not self.find_domain(domain):
            logger.debug(f"Domain not in denylist: {domain}")
            return True

        result = self.request("DELETE", f"/profiles/{self.profile_id}/denylist/{domain}")

        if result is not None:
            # Optimistic cache update
            self._cache.remove_domain(domain)
            logger.info(f"Unblocked: {domain}")
            return True

        logger.error(f"Failed to unblock: {domain}")
        return False

    def refresh_cache(self) -> bool:
        """
        Force refresh the denylist cache.

        Returns:
            True if successful, False otherwise
        """
        self._cache.invalidate()
        return self.get_denylist(use_cache=False) is not None

    # -------------------------------------------------------------------------
    # ALLOWLIST METHODS
    # -------------------------------------------------------------------------

    def get_allowlist(self, use_cache: bool = True) -> Optional[list[dict[str, Any]]]:
        """
        Fetch the current allowlist from NextDNS.

        Args:
            use_cache: Whether to use cached data if available

        Returns:
            List of allowed domains, or None if request failed
        """
        if use_cache:
            cached = self._allowlist_cache.get()
            if cached is not None:
                logger.debug("Using cached allowlist")
                return cached

        result = self.request("GET", f"/profiles/{self.profile_id}/allowlist")
        if result is None:
            logger.warning("Failed to fetch allowlist from API")
            return None

        data: list[dict[str, Any]] = result.get("data", [])
        self._allowlist_cache.set(data)
        return data

    def find_in_allowlist(self, domain: str, use_cache: bool = True) -> Optional[str]:
        """
        Find a domain in the allowlist.

        Args:
            domain: Domain name to find
            use_cache: Whether to use cached data if available

        Returns:
            Domain name if found, None otherwise
        """
        if use_cache:
            cached_result = self._allowlist_cache.contains(domain)
            if cached_result is not None:
                return domain if cached_result else None

        allowlist = self.get_allowlist(use_cache=use_cache)
        if allowlist is None:
            return None

        for entry in allowlist:
            if entry.get("id") == domain:
                return domain
        return None

    def is_allowed(self, domain: str) -> bool:
        """
        Check if a domain is currently in the allowlist.

        Args:
            domain: Domain name to check

        Returns:
            True if in allowlist, False otherwise
        """
        return self.find_in_allowlist(domain) is not None

    def allow(self, domain: str) -> bool:
        """
        Add a domain to the allowlist.

        Args:
            domain: Domain name to allow

        Returns:
            True if successful, False otherwise

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if self.find_in_allowlist(domain):
            logger.debug(f"Domain already in allowlist: {domain}")
            return True

        result = self.request(
            "POST", f"/profiles/{self.profile_id}/allowlist", {"id": domain, "active": True}
        )

        if result is not None:
            self._allowlist_cache.add_domain(domain)
            logger.info(f"Added to allowlist: {domain}")
            return True

        logger.error(f"Failed to add to allowlist: {domain}")
        return False

    def disallow(self, domain: str) -> bool:
        """
        Remove a domain from the allowlist.

        Args:
            domain: Domain name to remove from allowlist

        Returns:
            True if successful, False otherwise

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if not self.find_in_allowlist(domain):
            logger.debug(f"Domain not in allowlist: {domain}")
            return True

        result = self.request("DELETE", f"/profiles/{self.profile_id}/allowlist/{domain}")

        if result is not None:
            self._allowlist_cache.remove_domain(domain)
            logger.info(f"Removed from allowlist: {domain}")
            return True

        logger.error(f"Failed to remove from allowlist: {domain}")
        return False

    def refresh_allowlist_cache(self) -> bool:
        """
        Force refresh the allowlist cache.

        Returns:
            True if successful, False otherwise
        """
        self._allowlist_cache.invalidate()
        return self.get_allowlist(use_cache=False) is not None
