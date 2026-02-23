"""NextDNS API client with caching and rate limiting."""

import contextlib
import json
import logging
import os
import random
import re
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

import requests

from .common import safe_int, validate_domain
from .config import DEFAULT_RETRIES, DEFAULT_TIMEOUT
from .exceptions import APIError, DomainValidationError

# =============================================================================
# CIRCUIT BREAKER
# =============================================================================

CIRCUIT_BREAKER_THRESHOLD = int(os.environ.get("CIRCUIT_BREAKER_THRESHOLD", "5"))
CIRCUIT_BREAKER_TIMEOUT = int(os.environ.get("CIRCUIT_BREAKER_TIMEOUT", "60"))


class CircuitBreaker:
    """Simple circuit breaker for API calls.

    States:
        closed: Normal operation, requests pass through.
        open: Too many failures, requests fail immediately.
        half-open: After timeout, allow one request to test recovery.
    """

    def __init__(
        self,
        threshold: int = CIRCUIT_BREAKER_THRESHOLD,
        timeout: int = CIRCUIT_BREAKER_TIMEOUT,
    ) -> None:
        self._threshold = threshold
        self._timeout = timeout
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._state = "closed"
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "open":
                if time.time() - self._last_failure_time >= self._timeout:
                    self._state = "half-open"
            return self._state

    def record_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = "closed"

    def record_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._threshold:
                self._state = "open"
                logging.getLogger(__name__).warning(
                    "Circuit breaker opened after %d failures", self._failure_count
                )

    def allow_request(self) -> bool:
        state = self.state
        if state == "closed":
            return True
        if state == "half-open":
            return True
        return False


# =============================================================================
# API RESULT CLASS
# =============================================================================


@dataclass
class BatchResult:
    """Result of a batch operation on multiple domains.

    Attributes:
        succeeded: List of domains that were processed successfully
        failed: List of tuples (domain, error_message) for failed operations
        skipped: List of domains that were skipped (already existed/didn't exist)
    """

    succeeded: list[str]
    failed: list[tuple[str, str]]
    skipped: list[str]

    @property
    def total(self) -> int:
        """Total number of domains processed."""
        return len(self.succeeded) + len(self.failed) + len(self.skipped)

    @property
    def success_count(self) -> int:
        """Number of successfully processed domains."""
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        """Number of failed domains."""
        return len(self.failed)

    @property
    def all_succeeded(self) -> bool:
        """True if all domains were processed successfully (no failures)."""
        return len(self.failed) == 0


@dataclass
class APIRequestResult:
    """Result of an API request with error context.

    This class provides structured error information instead of just returning
    None on failure, enabling better debugging and smarter retry logic.

    Attributes:
        success: Whether the request completed successfully
        data: Response data if successful, None otherwise
        error_type: Type of error (empty string if successful)
        error_msg: Human-readable error message
        status_code: HTTP status code if available
        retry_after: Seconds to wait before retrying (for rate limiting)
    """

    success: bool
    data: Optional[dict[str, Any]] = None
    error_type: str = ""
    error_msg: str = ""
    status_code: Optional[int] = None
    retry_after: Optional[int] = None

    # Error type constants
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    PARSE_ERROR = "parse_error"
    UNKNOWN = "unknown"

    @classmethod
    def ok(cls, data: Optional[dict[str, Any]] = None) -> "APIRequestResult":
        """Create a successful result."""
        return cls(success=True, data=data or {"success": True})

    @classmethod
    def timeout(cls, msg: str = "Request timed out") -> "APIRequestResult":
        """Create a timeout error result."""
        return cls(success=False, error_type=cls.TIMEOUT, error_msg=msg)

    @classmethod
    def connection_error(cls, msg: str = "Connection failed") -> "APIRequestResult":
        """Create a connection error result."""
        return cls(success=False, error_type=cls.CONNECTION, error_msg=msg)

    @classmethod
    def http_error(
        cls, status_code: int, msg: str, retry_after: Optional[int] = None
    ) -> "APIRequestResult":
        """Create an HTTP error result with appropriate error type."""
        if status_code == 401 or status_code == 403:
            error_type = cls.AUTH
        elif status_code == 429:
            error_type = cls.RATE_LIMIT
        elif 500 <= status_code < 600:
            error_type = cls.SERVER_ERROR
        else:
            error_type = cls.CLIENT_ERROR

        return cls(
            success=False,
            error_type=error_type,
            error_msg=msg,
            status_code=status_code,
            retry_after=retry_after,
        )

    @classmethod
    def parse_error(cls, msg: str = "Invalid JSON response") -> "APIRequestResult":
        """Create a parse error result."""
        return cls(success=False, error_type=cls.PARSE_ERROR, error_msg=msg)

    @property
    def is_retryable(self) -> bool:
        """Check if this error type is typically retryable."""
        return self.error_type in (
            self.TIMEOUT,
            self.CONNECTION,
            self.RATE_LIMIT,
            self.SERVER_ERROR,
        )


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
                # Safety check: if deque is empty after cleanup, we can proceed
                if not self._requests:
                    self._requests.append(now)
                    return total_waited

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
        """Get cached data if valid. Returns a copy to prevent external modification."""
        with self._lock:
            if self._is_valid_unlocked():
                # Return a shallow copy to prevent callers from modifying cache data
                return list(self._data) if self._data else None
            return None

    def set(self, data: list[dict[str, Any]]) -> None:
        """Update cache with new data."""
        with self._lock:
            self._data = data
            # Filter out entries without valid id to prevent false positives
            # Also validate each entry is a dict to handle malformed API responses
            self._domains = {
                str(entry["id"]) for entry in data if isinstance(entry, dict) and entry.get("id")
            }
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
        self._session = requests.Session()
        self._session.verify = True
        self._rate_limiter = RateLimiter()
        self._cache = DenylistCache()
        self._allowlist_cache = AllowlistCache()
        self._circuit_breaker = CircuitBreaker()

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

    def close(self) -> None:
        """Close the underlying HTTP session."""
        self._session.close()

    def __enter__(self) -> "NextDNSClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

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
    ) -> APIRequestResult:
        """
        Make an HTTP request to the NextDNS API with retry logic and exponential backoff.

        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path
            data: Optional request body for POST requests

        Returns:
            APIRequestResult with success status and data or error details
        """
        url = f"{API_URL}{endpoint}"

        # Validate HTTP method
        method_upper = method.upper()
        valid_methods = ("GET", "POST", "DELETE", "PUT", "PATCH")
        if method_upper not in valid_methods:
            raise ValueError(
                f"Unsupported HTTP method: {method}. Valid methods: {', '.join(valid_methods)}"
            )

        # Circuit breaker check
        if not self._circuit_breaker.allow_request():
            logger.warning("Circuit breaker is open, rejecting %s %s", method_upper, endpoint)
            return APIRequestResult.http_error(
                503, "Circuit breaker open - too many recent failures"
            )

        last_error: Optional[APIRequestResult] = None

        for attempt in range(self.retries + 1):
            # Apply rate limiting with timeout to prevent indefinite blocking
            try:
                self._rate_limiter.acquire(timeout=float(self.timeout * 2))
            except TimeoutError:
                # Rate limiter timeout - treat as retryable
                last_error = APIRequestResult.timeout("Rate limiter acquire timed out")
                if attempt < self.retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Rate limiter timeout for {method} {endpoint}, "
                        f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(
                    f"Rate limiter timeout after {self.retries} retries: {method} {endpoint}"
                )
                return last_error

            try:
                # Use session for connection pooling and reuse
                response = self._session.request(
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
                        self._circuit_breaker.record_success()
                        return APIRequestResult.ok()
                    # For other success codes, log but still treat as success
                    # since raise_for_status() already validated the status
                    if response.status_code in (200, 201, 202):
                        logger.debug(
                            f"Empty response body for {method} {endpoint} "
                            f"(status: {response.status_code})"
                        )
                        self._circuit_breaker.record_success()
                        return APIRequestResult.ok()
                    # Unexpected empty response for other status codes
                    logger.warning(
                        f"Unexpected empty response for {method} {endpoint} "
                        f"(status: {response.status_code})"
                    )
                    self._circuit_breaker.record_success()
                    return APIRequestResult.ok()

                # Parse JSON with error handling
                try:
                    result_data: dict[str, Any] = response.json()
                    self._circuit_breaker.record_success()
                    return APIRequestResult.ok(result_data)
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response for {method} {endpoint}: {e}")
                    return APIRequestResult.parse_error(f"Invalid JSON: {e}")

            except requests.exceptions.Timeout:
                last_error = APIRequestResult.timeout(f"Request timed out after {self.timeout}s")
                if attempt < self.retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Request timeout for {method} {endpoint}, "
                        f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(f"API timeout after {self.retries} retries: {method} {endpoint}")
                self._circuit_breaker.record_failure()
                return last_error

            except requests.exceptions.HTTPError as e:
                # Use getattr for safer access in case response is malformed
                status_code = 0
                if e.response is not None:
                    status_code = getattr(e.response, "status_code", 0)
                # Fallback: extract status code from error message (e.g., "429 Client Error")
                if status_code == 0:
                    match = re.search(r"^(\d{3})\s", str(e))
                    if match:
                        status_code = int(match.group(1))
                retry_after = None
                if status_code == 429 and e.response:
                    # Try to get Retry-After header
                    retry_after_str = e.response.headers.get("Retry-After")
                    if retry_after_str:
                        with contextlib.suppress(ValueError):
                            retry_after = int(retry_after_str)

                last_error = APIRequestResult.http_error(
                    status_code=status_code,
                    msg=str(e),
                    retry_after=retry_after,
                )

                # Retry on 408 (request timeout), 429 (rate limit) and 5xx errors
                if status_code in (408, 429) or (500 <= status_code < 600):
                    if attempt < self.retries:
                        # Use Retry-After header if available, otherwise use calculated backoff
                        if retry_after is not None and retry_after > 0:
                            backoff = float(retry_after)
                            logger.warning(
                                f"HTTP {status_code} for {method} {endpoint}, "
                                f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s (Retry-After)"
                            )
                        else:
                            backoff = self._calculate_backoff(attempt)
                            logger.warning(
                                f"HTTP {status_code} for {method} {endpoint}, "
                                f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                            )
                        time.sleep(backoff)
                        continue
                logger.error(f"API HTTP error for {method} {endpoint}: {e}")
                self._circuit_breaker.record_failure()
                return last_error

            except requests.exceptions.RequestException as e:
                last_error = APIRequestResult.connection_error(str(e))
                if attempt < self.retries:
                    backoff = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Request error for {method} {endpoint}, "
                        f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                    )
                    time.sleep(backoff)
                    continue
                logger.error(f"API request error for {method} {endpoint}: {e}")
                self._circuit_breaker.record_failure()
                return last_error

        # Should not reach here, but return last error if we do
        return last_error or APIRequestResult(
            success=False, error_type=APIRequestResult.UNKNOWN, error_msg="Unknown error"
        )

    def request_or_raise(
        self, method: str, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> dict[str, Any]:
        """
        Make an HTTP request to the NextDNS API, raising APIError on failure.

        This is an alternative to request() that raises an exception instead
        of returning an error result, useful when errors should be propagated.

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
        if not result.success:
            raise APIError(
                f"API request failed: {method} {endpoint} - {result.error_type}: {result.error_msg}"
            )
        return result.data or {"success": True}

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
        if not result.success:
            logger.warning(f"Failed to fetch denylist from API: {result.error_msg}")
            return None

        data: list[dict[str, Any]] = (result.data or {}).get("data", [])
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

    def block(self, domain: str) -> tuple[bool, bool]:
        """
        Add a domain to the denylist.

        Args:
            domain: Domain name to block

        Returns:
            Tuple of (success, was_added):
            - success: True if operation completed without error
            - was_added: True if domain was actually added, False if already existed

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        # Check if already blocked (using cache for efficiency)
        if self.find_domain(domain):
            logger.debug(f"Domain already blocked: {domain}")
            return (True, False)  # Success but not added (already exists)

        result = self.request(
            "POST", f"/profiles/{self.profile_id}/denylist", {"id": domain, "active": True}
        )

        if result.success:
            # Optimistic cache update
            self._cache.add_domain(domain)
            logger.info(f"Blocked: {domain}")
            return (True, True)  # Success and was added

        logger.error(f"Failed to block: {domain} - {result.error_msg}")
        return (False, False)  # Failed

    def unblock(self, domain: str) -> tuple[bool, bool]:
        """
        Remove a domain from the denylist.

        Args:
            domain: Domain name to unblock

        Returns:
            Tuple of (success, was_removed):
            - success: True if operation completed without error
            - was_removed: True if domain was actually removed, False if didn't exist

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if not self.find_domain(domain):
            logger.debug(f"Domain not in denylist: {domain}")
            return (True, False)  # Success but not removed (didn't exist)

        result = self.request("DELETE", f"/profiles/{self.profile_id}/denylist/{domain}")

        if result.success:
            # Optimistic cache update
            self._cache.remove_domain(domain)
            logger.info(f"Unblocked: {domain}")
            return (True, True)  # Success and was removed

        logger.error(f"Failed to unblock: {domain} - {result.error_msg}")
        return (False, False)  # Failed

    def block_with_result(self, domain: str) -> tuple[bool, bool, APIRequestResult]:
        """
        Add a domain to the denylist, returning full error context.

        This method is useful when the caller needs to know if the error
        is retryable (e.g., for retry queue integration).

        Args:
            domain: Domain name to block

        Returns:
            Tuple of (success, was_added, api_result):
            - success: True if operation completed without error
            - was_added: True if domain was actually added, False if already existed
            - api_result: Full APIRequestResult with error context if failed

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if self.find_domain(domain):
            logger.debug(f"Domain already blocked: {domain}")
            return (True, False, APIRequestResult.ok())

        result = self.request(
            "PUT",
            f"/profiles/{self.profile_id}/denylist",
            {"id": domain, "active": True},
        )

        if result.success:
            self._cache.add_domain(domain)
            logger.info(f"Blocked: {domain}")
            return (True, True, result)

        logger.error(f"Failed to block: {domain} - {result.error_msg}")
        return (False, False, result)

    def unblock_with_result(self, domain: str) -> tuple[bool, bool, APIRequestResult]:
        """
        Remove a domain from the denylist, returning full error context.

        This method is useful when the caller needs to know if the error
        is retryable (e.g., for retry queue integration).

        Args:
            domain: Domain name to unblock

        Returns:
            Tuple of (success, was_removed, api_result):
            - success: True if operation completed without error
            - was_removed: True if domain was actually removed, False if didn't exist
            - api_result: Full APIRequestResult with error context if failed

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if not self.find_domain(domain):
            logger.debug(f"Domain not in denylist: {domain}")
            return (True, False, APIRequestResult.ok())

        result = self.request("DELETE", f"/profiles/{self.profile_id}/denylist/{domain}")

        if result.success:
            self._cache.remove_domain(domain)
            logger.info(f"Unblocked: {domain}")
            return (True, True, result)

        logger.error(f"Failed to unblock: {domain} - {result.error_msg}")
        return (False, False, result)

    def refresh_cache(self) -> bool:
        """
        Force refresh the denylist cache.

        Returns:
            True if successful, False otherwise
        """
        self._cache.invalidate()
        return self.get_denylist(use_cache=False) is not None

    def find_domains_batch(self, domains: list[str], use_cache: bool = True) -> dict[str, bool]:
        """
        Check multiple domains against the denylist in a single operation.

        This is more efficient than calling find_domain() for each domain,
        as it fetches the denylist once and checks all domains against it.

        Args:
            domains: List of domain names to check
            use_cache: Whether to use cached denylist if available

        Returns:
            Dict mapping domain -> is_blocked (True if in denylist)
        """
        if not domains:
            return {}

        denylist = self.get_denylist(use_cache=use_cache)
        if denylist is None:
            return dict.fromkeys(domains, False)

        blocked_set = {str(entry.get("id")) for entry in denylist if entry.get("id")}
        return {d: d in blocked_set for d in domains}

    def block_domains_batch(self, domains: list[str]) -> BatchResult:
        """
        Block multiple domains in a single batch operation.

        Validates all domains first, then attempts to block each one.
        Uses a single denylist fetch to check existing blocks.

        Args:
            domains: List of domain names to block

        Returns:
            BatchResult with succeeded, failed, and skipped domains
        """
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        skipped: list[str] = []

        if not domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Validate all domains first
        valid_domains: list[str] = []
        for domain in domains:
            if not validate_domain(domain):
                failed.append((domain, f"Invalid domain: {domain}"))
            else:
                valid_domains.append(domain)

        if not valid_domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Fetch denylist once to check existing blocks
        existing_blocks = self.find_domains_batch(valid_domains)

        # Process each domain
        for domain in valid_domains:
            if existing_blocks.get(domain, False):
                skipped.append(domain)
                logger.debug(f"Domain already blocked: {domain}")
                continue

            result = self.request(
                "POST",
                f"/profiles/{self.profile_id}/denylist",
                {"id": domain, "active": True},
            )

            if result.success:
                self._cache.add_domain(domain)
                succeeded.append(domain)
                logger.info(f"Blocked: {domain}")
            else:
                failed.append((domain, result.error_msg))
                logger.error(f"Failed to block: {domain} - {result.error_msg}")

        return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

    def unblock_domains_batch(self, domains: list[str]) -> BatchResult:
        """
        Unblock multiple domains in a single batch operation.

        Validates all domains first, then attempts to unblock each one.
        Uses a single denylist fetch to check which domains are actually blocked.

        Args:
            domains: List of domain names to unblock

        Returns:
            BatchResult with succeeded, failed, and skipped domains
        """
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        skipped: list[str] = []

        if not domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Validate all domains first
        valid_domains: list[str] = []
        for domain in domains:
            if not validate_domain(domain):
                failed.append((domain, f"Invalid domain: {domain}"))
            else:
                valid_domains.append(domain)

        if not valid_domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Fetch denylist once to check existing blocks
        existing_blocks = self.find_domains_batch(valid_domains)

        # Process each domain
        for domain in valid_domains:
            if not existing_blocks.get(domain, False):
                skipped.append(domain)
                logger.debug(f"Domain not in denylist: {domain}")
                continue

            result = self.request("DELETE", f"/profiles/{self.profile_id}/denylist/{domain}")

            if result.success:
                self._cache.remove_domain(domain)
                succeeded.append(domain)
                logger.info(f"Unblocked: {domain}")
            else:
                failed.append((domain, result.error_msg))
                logger.error(f"Failed to unblock: {domain} - {result.error_msg}")

        return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

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
        if not result.success:
            logger.warning(f"Failed to fetch allowlist from API: {result.error_msg}")
            return None

        data: list[dict[str, Any]] = (result.data or {}).get("data", [])
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

    def allow(self, domain: str) -> tuple[bool, bool]:
        """
        Add a domain to the allowlist.

        Args:
            domain: Domain name to allow

        Returns:
            Tuple of (success, was_added):
            - success: True if operation completed without error
            - was_added: True if domain was actually added, False if already existed

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if self.find_in_allowlist(domain):
            logger.debug(f"Domain already in allowlist: {domain}")
            return (True, False)  # Success but not added (already exists)

        result = self.request(
            "POST", f"/profiles/{self.profile_id}/allowlist", {"id": domain, "active": True}
        )

        if result.success:
            self._allowlist_cache.add_domain(domain)
            logger.info(f"Added to allowlist: {domain}")
            return (True, True)  # Success and was added

        logger.error(f"Failed to add to allowlist: {domain} - {result.error_msg}")
        return (False, False)  # Failed

    def disallow(self, domain: str) -> tuple[bool, bool]:
        """
        Remove a domain from the allowlist.

        Args:
            domain: Domain name to remove from allowlist

        Returns:
            Tuple of (success, was_removed):
            - success: True if operation completed without error
            - was_removed: True if domain was actually removed, False if didn't exist

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if not self.find_in_allowlist(domain):
            logger.debug(f"Domain not in allowlist: {domain}")
            return (True, False)  # Success but not removed (didn't exist)

        result = self.request("DELETE", f"/profiles/{self.profile_id}/allowlist/{domain}")

        if result.success:
            self._allowlist_cache.remove_domain(domain)
            logger.info(f"Removed from allowlist: {domain}")
            return (True, True)  # Success and was removed

        logger.error(f"Failed to remove from allowlist: {domain} - {result.error_msg}")
        return (False, False)  # Failed

    def allow_with_result(self, domain: str) -> tuple[bool, bool, APIRequestResult]:
        """
        Add a domain to the allowlist, returning full error context.

        Args:
            domain: Domain name to allow

        Returns:
            Tuple of (success, was_added, api_result):
            - success: True if operation completed without error
            - was_added: True if domain was actually added, False if already existed
            - api_result: Full APIRequestResult with error context if failed

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if self.find_in_allowlist(domain):
            logger.debug(f"Domain already in allowlist: {domain}")
            return (True, False, APIRequestResult.ok())

        result = self.request(
            "POST", f"/profiles/{self.profile_id}/allowlist", {"id": domain, "active": True}
        )

        if result.success:
            self._allowlist_cache.add_domain(domain)
            logger.info(f"Added to allowlist: {domain}")
            return (True, True, result)

        logger.error(f"Failed to add to allowlist: {domain} - {result.error_msg}")
        return (False, False, result)

    def disallow_with_result(self, domain: str) -> tuple[bool, bool, APIRequestResult]:
        """
        Remove a domain from the allowlist, returning full error context.

        Args:
            domain: Domain name to remove from allowlist

        Returns:
            Tuple of (success, was_removed, api_result):
            - success: True if operation completed without error
            - was_removed: True if domain was actually removed, False if didn't exist
            - api_result: Full APIRequestResult with error context if failed

        Raises:
            DomainValidationError: If domain is invalid
        """
        if not validate_domain(domain):
            raise DomainValidationError(f"Invalid domain: {domain}")

        if not self.find_in_allowlist(domain):
            logger.debug(f"Domain not in allowlist: {domain}")
            return (True, False, APIRequestResult.ok())

        result = self.request("DELETE", f"/profiles/{self.profile_id}/allowlist/{domain}")

        if result.success:
            self._allowlist_cache.remove_domain(domain)
            logger.info(f"Removed from allowlist: {domain}")
            return (True, True, result)

        logger.error(f"Failed to remove from allowlist: {domain} - {result.error_msg}")
        return (False, False, result)

    def refresh_allowlist_cache(self) -> bool:
        """
        Force refresh the allowlist cache.

        Returns:
            True if successful, False otherwise
        """
        self._allowlist_cache.invalidate()
        return self.get_allowlist(use_cache=False) is not None

    def find_in_allowlist_batch(
        self, domains: list[str], use_cache: bool = True
    ) -> dict[str, bool]:
        """
        Check multiple domains against the allowlist in a single operation.

        This is more efficient than calling find_in_allowlist() for each domain,
        as it fetches the allowlist once and checks all domains against it.

        Args:
            domains: List of domain names to check
            use_cache: Whether to use cached allowlist if available

        Returns:
            Dict mapping domain -> is_allowed (True if in allowlist)
        """
        if not domains:
            return {}

        allowlist = self.get_allowlist(use_cache=use_cache)
        if allowlist is None:
            return dict.fromkeys(domains, False)

        allowed_set = {str(entry.get("id")) for entry in allowlist if entry.get("id")}
        return {d: d in allowed_set for d in domains}

    def allow_domains_batch(self, domains: list[str]) -> BatchResult:
        """
        Add multiple domains to the allowlist in a single batch operation.

        Validates all domains first, then attempts to allow each one.
        Uses a single allowlist fetch to check existing entries.

        Args:
            domains: List of domain names to allow

        Returns:
            BatchResult with succeeded, failed, and skipped domains
        """
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        skipped: list[str] = []

        if not domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Validate all domains first
        valid_domains: list[str] = []
        for domain in domains:
            if not validate_domain(domain):
                failed.append((domain, f"Invalid domain: {domain}"))
            else:
                valid_domains.append(domain)

        if not valid_domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Fetch allowlist once to check existing entries
        existing_allowed = self.find_in_allowlist_batch(valid_domains)

        # Process each domain
        for domain in valid_domains:
            if existing_allowed.get(domain, False):
                skipped.append(domain)
                logger.debug(f"Domain already in allowlist: {domain}")
                continue

            result = self.request(
                "POST",
                f"/profiles/{self.profile_id}/allowlist",
                {"id": domain, "active": True},
            )

            if result.success:
                self._allowlist_cache.add_domain(domain)
                succeeded.append(domain)
                logger.info(f"Added to allowlist: {domain}")
            else:
                failed.append((domain, result.error_msg))
                logger.error(f"Failed to add to allowlist: {domain} - {result.error_msg}")

        return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

    def disallow_domains_batch(self, domains: list[str]) -> BatchResult:
        """
        Remove multiple domains from the allowlist in a single batch operation.

        Validates all domains first, then attempts to remove each one.
        Uses a single allowlist fetch to check which domains are actually allowed.

        Args:
            domains: List of domain names to remove from allowlist

        Returns:
            BatchResult with succeeded, failed, and skipped domains
        """
        succeeded: list[str] = []
        failed: list[tuple[str, str]] = []
        skipped: list[str] = []

        if not domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Validate all domains first
        valid_domains: list[str] = []
        for domain in domains:
            if not validate_domain(domain):
                failed.append((domain, f"Invalid domain: {domain}"))
            else:
                valid_domains.append(domain)

        if not valid_domains:
            return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

        # Fetch allowlist once to check existing entries
        existing_allowed = self.find_in_allowlist_batch(valid_domains)

        # Process each domain
        for domain in valid_domains:
            if not existing_allowed.get(domain, False):
                skipped.append(domain)
                logger.debug(f"Domain not in allowlist: {domain}")
                continue

            result = self.request("DELETE", f"/profiles/{self.profile_id}/allowlist/{domain}")

            if result.success:
                self._allowlist_cache.remove_domain(domain)
                succeeded.append(domain)
                logger.info(f"Removed from allowlist: {domain}")
            else:
                failed.append((domain, result.error_msg))
                logger.error(f"Failed to remove from allowlist: {domain} - {result.error_msg}")

        return BatchResult(succeeded=succeeded, failed=failed, skipped=skipped)

    # -------------------------------------------------------------------------
    # PARENTAL CONTROL METHODS
    # -------------------------------------------------------------------------

    def get_parental_control(self) -> Optional[dict[str, Any]]:
        """
        Fetch the current Parental Control configuration from NextDNS.

        Returns:
            Parental Control config dict, or None if request failed.
            The dict contains:
            - safeSearch: bool
            - youtubeRestrictedMode: bool
            - blockBypass: bool
            - categories: list of active category objects
            - services: list of active service objects
        """
        result = self.request("GET", f"/profiles/{self.profile_id}/parentalControl")
        if not result.success:
            logger.warning(f"Failed to fetch parental control config from API: {result.error_msg}")
            return None
        # API returns {"data": {...}}, unwrap it
        data: dict[str, Any] = (result.data or {}).get("data", result.data or {})
        return data

    def update_parental_control(
        self,
        safe_search: Optional[bool] = None,
        youtube_restricted_mode: Optional[bool] = None,
        block_bypass: Optional[bool] = None,
    ) -> bool:
        """
        Update Parental Control global settings.

        Only provided parameters will be updated. Pass None to leave unchanged.

        Args:
            safe_search: Enable SafeSearch on search engines
            youtube_restricted_mode: Enable YouTube restricted mode
            block_bypass: Block VPNs, proxies, and alternative DNS

        Returns:
            True if successful, False otherwise
        """
        data: dict[str, Any] = {}

        if safe_search is not None:
            data["safeSearch"] = safe_search
        if youtube_restricted_mode is not None:
            data["youtubeRestrictedMode"] = youtube_restricted_mode
        if block_bypass is not None:
            data["blockBypass"] = block_bypass

        if not data:
            logger.debug("No parental control settings to update")
            return True

        result = self.request("PATCH", f"/profiles/{self.profile_id}/parentalControl", data)

        if result.success:
            logger.info(f"Updated parental control settings: {list(data.keys())}")
            return True

        logger.error(f"Failed to update parental control settings: {result.error_msg}")
        return False

    def get_parental_control_categories(self) -> Optional[list[dict[str, Any]]]:
        """
        Get list of active Parental Control categories.

        Returns:
            List of category objects with 'id' and 'active' fields,
            or None if request failed
        """
        config = self.get_parental_control()
        if config is None:
            return None
        categories: list[dict[str, Any]] = config.get("categories", [])
        return categories

    def get_parental_control_services(self) -> Optional[list[dict[str, Any]]]:
        """
        Get list of active Parental Control services.

        Returns:
            List of service objects with 'id' and 'active' fields,
            or None if request failed
        """
        config = self.get_parental_control()
        if config is None:
            return None
        services: list[dict[str, Any]] = config.get("services", [])
        return services

    def is_category_active(self, category_id: str) -> Optional[bool]:
        """
        Check if a Parental Control category is currently active.

        Args:
            category_id: The category ID (e.g., 'gambling', 'porn')

        Returns:
            True if active, False if not active, None if request failed
        """
        categories = self.get_parental_control_categories()
        if categories is None:
            return None

        for cat in categories:
            if cat.get("id") == category_id:
                is_active: bool = cat.get("active", False)
                return is_active
        return False

    def is_service_active(self, service_id: str) -> Optional[bool]:
        """
        Check if a Parental Control service is currently active.

        Args:
            service_id: The service ID (e.g., 'tiktok', 'netflix')

        Returns:
            True if active, False if not active, None if request failed
        """
        services = self.get_parental_control_services()
        if services is None:
            return None

        for svc in services:
            if svc.get("id") == service_id:
                is_active: bool = svc.get("active", False)
                return is_active
        return False

    def service_exists(self, service_id: str) -> Optional[bool]:
        """
        Check if a Parental Control service exists in the profile.

        Args:
            service_id: The service ID (e.g., 'tiktok', 'netflix')

        Returns:
            True if exists, False if not, None if request failed
        """
        services = self.get_parental_control_services()
        if services is None:
            return None

        return any(svc.get("id") == service_id for svc in services)

    def add_category(self, category_id: str, active: bool = True) -> bool:
        """
        Add/activate a category in Parental Control.

        Uses PATCH to set the active state. NextDNS parental control categories
        are predefined and cannot be added/removed, only activated/deactivated.

        Args:
            category_id: The category ID (e.g., 'gambling', 'porn')
            active: Whether the category should be active (blocking)

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "PATCH",
            f"/profiles/{self.profile_id}/parentalControl/categories/{category_id}",
            {"active": active},
        )

        if result.success:
            status = "activated" if active else "deactivated"
            logger.info(f"Parental control category {status}: {category_id}")
            return True

        logger.error(
            f"Failed to update parental control category: {category_id} - {result.error_msg}"
        )
        return False

    def remove_category(self, category_id: str) -> bool:
        """
        Deactivate a category in Parental Control.

        Uses PATCH to set active=False. NextDNS parental control categories
        are predefined and cannot be removed, only deactivated.

        Args:
            category_id: The category ID to deactivate

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "PATCH",
            f"/profiles/{self.profile_id}/parentalControl/categories/{category_id}",
            {"active": False},
        )

        if result.success:
            logger.info(f"Deactivated parental control category: {category_id}")
            return True

        logger.error(
            f"Failed to deactivate parental control category: {category_id} - {result.error_msg}"
        )
        return False

    def add_service(self, service_id: str, active: bool = True) -> bool:
        """
        Add a service to Parental Control.

        Uses POST to add the service. Unlike categories which are predefined,
        services must be added before they can be controlled.

        Args:
            service_id: The service ID (e.g., 'tiktok', 'netflix')
            active: Whether the service should be active (blocking)

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "POST",
            f"/profiles/{self.profile_id}/parentalControl/services",
            {"id": service_id, "active": active},
        )

        if result.success:
            status = "activated" if active else "deactivated"
            logger.info(f"Parental control service {status}: {service_id}")
            return True

        logger.error(f"Failed to add parental control service: {service_id} - {result.error_msg}")
        return False

    def remove_service(self, service_id: str) -> bool:
        """
        Remove a service from Parental Control.

        Uses DELETE to remove the service entirely.

        Args:
            service_id: The service ID to remove

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "DELETE",
            f"/profiles/{self.profile_id}/parentalControl/services/{service_id}",
        )

        if result.success:
            logger.info(f"Removed parental control service: {service_id}")
            return True

        logger.error(
            f"Failed to remove parental control service: {service_id} - {result.error_msg}"
        )
        return False

    def activate_category(self, category_id: str) -> bool:
        """
        Activate a Parental Control category (start blocking).

        Uses PATCH to set active=True. NextDNS parental control categories
        are predefined and cannot be added/removed, only activated/deactivated.

        Args:
            category_id: The category ID to activate

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "PATCH",
            f"/profiles/{self.profile_id}/parentalControl/categories/{category_id}",
            {"active": True},
        )
        if result.success:
            logger.info(f"Parental control category activated: {category_id}")
            return True
        logger.error(
            f"Failed to activate parental control category: {category_id} - {result.error_msg}"
        )
        return False

    def deactivate_category(self, category_id: str) -> bool:
        """
        Deactivate a Parental Control category (stop blocking).

        Uses PATCH to set active=False. NextDNS parental control categories
        are predefined and cannot be added/removed, only activated/deactivated.

        Args:
            category_id: The category ID to deactivate

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "PATCH",
            f"/profiles/{self.profile_id}/parentalControl/categories/{category_id}",
            {"active": False},
        )
        if result.success:
            logger.info(f"Parental control category deactivated: {category_id}")
            return True
        logger.error(
            f"Failed to deactivate parental control category: {category_id} - {result.error_msg}"
        )
        return False

    def activate_service(self, service_id: str) -> bool:
        """
        Activate a Parental Control service (start blocking).

        First tries PATCH for existing services. If service doesn't exist (404),
        falls back to POST to add it.

        Args:
            service_id: The service ID to activate

        Returns:
            True if successful, False otherwise
        """
        # First try PATCH for existing services
        result = self.request(
            "PATCH",
            f"/profiles/{self.profile_id}/parentalControl/services/{service_id}",
            {"active": True},
        )
        if result.success:
            logger.info(f"Parental control service activated: {service_id}")
            return True

        # If PATCH failed (likely 404 for new service), try POST to add it
        logger.debug(f"PATCH failed for {service_id}, trying POST to add service")
        result = self.request(
            "POST",
            f"/profiles/{self.profile_id}/parentalControl/services",
            {"id": service_id, "active": True},
        )
        if result.success:
            logger.info(f"Parental control service added and activated: {service_id}")
            return True

        logger.error(
            f"Failed to activate parental control service: {service_id} - {result.error_msg}"
        )
        return False

    def deactivate_service(self, service_id: str) -> bool:
        """
        Deactivate a Parental Control service (stop blocking).

        Uses PATCH to deactivate the service. Services in NextDNS are predefined
        (like categories), so we just activate/deactivate them.

        Args:
            service_id: The service ID to deactivate

        Returns:
            True if successful, False otherwise
        """
        result = self.request(
            "PATCH",
            f"/profiles/{self.profile_id}/parentalControl/services/{service_id}",
            {"active": False},
        )
        if result.success:
            logger.info(f"Parental control service deactivated: {service_id}")
            return True
        logger.error(
            f"Failed to deactivate parental control service: {service_id} - {result.error_msg}"
        )
        return False
