"""NextDNS API client with caching and rate limiting."""

import json
import logging
from datetime import datetime
from time import sleep
from typing import Any, Optional

import requests

from .common import validate_domain
from .config import DEFAULT_RETRIES, DEFAULT_TIMEOUT
from .exceptions import DomainValidationError

# =============================================================================
# CONSTANTS
# =============================================================================

API_URL = "https://api.nextdns.io"

# Rate limiting and backoff settings
RATE_LIMIT_REQUESTS = 30  # Max requests per minute
RATE_LIMIT_WINDOW = 60  # Window in seconds
BACKOFF_BASE = 1.0  # Base delay for exponential backoff (seconds)
BACKOFF_MAX = 30.0  # Maximum backoff delay (seconds)
CACHE_TTL = 60  # Denylist cache TTL in seconds

logger = logging.getLogger(__name__)


# =============================================================================
# RATE LIMITER
# =============================================================================


class RateLimiter:
    """Simple rate limiter using sliding window algorithm."""

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
        self.requests: list[float] = []

    def acquire(self) -> float:
        """
        Acquire permission to make a request, waiting if necessary.

        Returns:
            Time waited in seconds (0 if no wait was needed)
        """
        now = datetime.now().timestamp()
        waited = 0.0

        # Remove expired timestamps
        cutoff = now - self.window_seconds
        self.requests = [ts for ts in self.requests if ts > cutoff]

        # Check if we need to wait
        if len(self.requests) >= self.max_requests:
            # Wait until the oldest request expires
            wait_time = self.requests[0] - cutoff
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f}s")
                sleep(wait_time)
                waited = wait_time
                now = datetime.now().timestamp()

        self.requests.append(now)
        return waited


# =============================================================================
# CACHES
# =============================================================================


class DomainCache:
    """Base cache class for domain lists to reduce API calls."""

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

    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        return self._data is not None and (datetime.now().timestamp() - self._timestamp) < self.ttl

    def get(self) -> Optional[list[dict[str, Any]]]:
        """Get cached data if valid."""
        if self.is_valid():
            return self._data
        return None

    def set(self, data: list[dict[str, Any]]) -> None:
        """Update cache with new data."""
        self._data = data
        self._domains = {entry.get("id", "") for entry in data}
        self._timestamp = datetime.now().timestamp()

    def contains(self, domain: str) -> Optional[bool]:
        """
        Check if domain is in cache.

        Returns:
            True/False if cache is valid, None if cache is invalid
        """
        if not self.is_valid():
            return None
        return domain in self._domains

    def invalidate(self) -> None:
        """Invalidate the cache."""
        self._data = None
        self._domains = set()
        self._timestamp = 0

    def add_domain(self, domain: str) -> None:
        """Add a domain to the cache (for optimistic updates)."""
        if self._data is not None:
            self._domains.add(domain)

    def remove_domain(self, domain: str) -> None:
        """Remove a domain from the cache (for optimistic updates)."""
        self._domains.discard(domain)


class DenylistCache(DomainCache):
    """Cache for denylist to reduce API calls."""

    pass


class AllowlistCache(DomainCache):
    """Cache for allowlist to reduce API calls."""

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
        self.headers: dict[str, str] = {"X-Api-Key": api_key, "Content-Type": "application/json"}
        self._rate_limiter = RateLimiter()
        self._cache = DenylistCache()
        self._allowlist_cache = AllowlistCache()

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = BACKOFF_BASE * (2**attempt)
        return min(delay, BACKOFF_MAX)

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

        for attempt in range(self.retries + 1):
            # Apply rate limiting
            self._rate_limiter.acquire()

            try:
                if method == "GET":
                    response = requests.get(url, headers=self.headers, timeout=self.timeout)
                elif method == "POST":
                    response = requests.post(
                        url, headers=self.headers, json=data, timeout=self.timeout
                    )
                elif method == "DELETE":
                    response = requests.delete(url, headers=self.headers, timeout=self.timeout)
                else:
                    logger.error(f"Unsupported HTTP method: {method}")
                    return None

                response.raise_for_status()

                # Handle empty responses
                if not response.text:
                    return {"success": True}

                # Parse JSON with error handling
                try:
                    return response.json()
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
                    sleep(backoff)
                    continue
                logger.error(f"API timeout after {self.retries} retries: {method} {endpoint}")
                return None
            except requests.exceptions.HTTPError as e:
                # Retry on 429 (rate limit) and 5xx errors
                status_code = e.response.status_code if e.response else 0
                if status_code == 429 or (500 <= status_code < 600):
                    if attempt < self.retries:
                        backoff = self._calculate_backoff(attempt)
                        logger.warning(
                            f"HTTP {status_code} for {method} {endpoint}, "
                            f"retry {attempt + 1}/{self.retries} after {backoff:.1f}s"
                        )
                        sleep(backoff)
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
                    sleep(backoff)
                    continue
                logger.error(f"API request error for {method} {endpoint}: {e}")
                return None

        return None

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

        data = result.get("data", [])
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

        data = result.get("data", [])
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
