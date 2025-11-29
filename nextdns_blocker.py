#!/usr/bin/env python3
"""NextDNS Domain Controller - Manages domain blocking with per-domain scheduling."""

import os
import re
import sys
import logging
import json
import fcntl
from pathlib import Path
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, time as dt_time, timedelta
from time import sleep

import requests

# Timezone support: use zoneinfo (Python 3.9+) with fallback
try:
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 fallback
    from backports.zoneinfo import ZoneInfo  # type: ignore

# Import shared utilities
from common import (
    LOG_DIR,
    AUDIT_LOG_FILE,
    SECURE_FILE_MODE,
    ensure_log_dir,
    audit_log,
    write_secure_file,
    read_secure_file,
)

# Import notification module
from notifications import NotificationManager


# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

PAUSE_FILE = LOG_DIR / ".paused"
APP_LOG_FILE = LOG_DIR / "app.log"
API_URL = "https://api.nextdns.io"

# Default configuration values
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_TIMEZONE = "UTC"
DEFAULT_PAUSE_MINUTES = 30

# Rate limiting and backoff settings
RATE_LIMIT_REQUESTS = 30  # Max requests per minute
RATE_LIMIT_WINDOW = 60  # Window in seconds
BACKOFF_BASE = 1.0  # Base delay for exponential backoff (seconds)
BACKOFF_MAX = 30.0  # Maximum backoff delay (seconds)
CACHE_TTL = 60  # Denylist cache TTL in seconds

# Domain validation constants (RFC 1035)
MAX_DOMAIN_LENGTH = 253
MAX_LABEL_LENGTH = 63

# Domain validation pattern (RFC 1035 compliant, no trailing dot)
# Each label: starts/ends with alphanumeric, middle can have hyphens, max 63 chars
# Full domain: labels separated by dots, no trailing dot, max 253 chars
DOMAIN_PATTERN = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
    r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
)

# Time format pattern (HH:MM, 24-hour format)
TIME_PATTERN = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')

# URL pattern for DOMAINS_URL validation (stricter validation)
# Requires: scheme, valid hostname (at least domain.tld), optional path
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+' # domain labels
    r'[a-zA-Z]{2,}'  # TLD (at least 2 chars)
    r'(?::\d{1,5})?'  # optional port
    r'(?:/[^\s]*)?$',  # optional path
    re.IGNORECASE
)

# Valid day names for schedules
VALID_DAYS = frozenset({
    'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
})

# Day name to weekday number mapping (Monday=0, Sunday=6)
DAYS_MAP: Dict[str, int] = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6
}

# Ensure log directory exists before setting up logging
ensure_log_dir()

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(APP_LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class NextDNSBlockerError(Exception):
    """Base exception for NextDNS Blocker."""
    pass


class ConfigurationError(NextDNSBlockerError):
    """Raised when configuration is invalid or missing."""
    pass


class DomainValidationError(NextDNSBlockerError):
    """Raised when domain validation fails."""
    pass


class APIError(NextDNSBlockerError):
    """Raised when API request fails."""
    pass


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def validate_domain(domain: str) -> bool:
    """
    Validate a domain name according to RFC 1035.

    Args:
        domain: Domain name to validate

    Returns:
        True if valid, False otherwise
    """
    if not domain or len(domain) > MAX_DOMAIN_LENGTH:
        return False
    # Reject trailing dots (FQDN notation not supported)
    if domain.endswith('.'):
        return False
    return DOMAIN_PATTERN.match(domain) is not None


def validate_time_format(time_str: str) -> bool:
    """
    Validate a time string in HH:MM format.

    Args:
        time_str: Time string to validate

    Returns:
        True if valid HH:MM format, False otherwise
    """
    if not time_str or not isinstance(time_str, str):
        return False
    return TIME_PATTERN.match(time_str) is not None


def validate_url(url: str) -> bool:
    """
    Validate a URL string (must be http or https).

    Args:
        url: URL string to validate

    Returns:
        True if valid URL format, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    return URL_PATTERN.match(url) is not None


def parse_env_value(value: str) -> str:
    """
    Parse .env value, handling quotes and whitespace.

    Args:
        value: Raw value from .env file

    Returns:
        Cleaned value with quotes removed
    """
    value = value.strip()
    if len(value) >= 2:
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
    return value


def safe_int(value: Optional[str], default: int, name: str = "value") -> int:
    """
    Safely convert a string to int with validation.

    Args:
        value: String value to convert (can be None)
        default: Default value if conversion fails or value is None
        name: Name of the value for error messages

    Returns:
        Converted integer or default value

    Raises:
        ConfigurationError: If value is not a valid positive integer
    """
    if value is None:
        return default

    try:
        result = int(value)
        if result < 0:
            raise ConfigurationError(f"{name} must be a positive integer, got: {value}")
        return result
    except ValueError:
        raise ConfigurationError(f"{name} must be a valid integer, got: {value}")


# =============================================================================
# PAUSE MANAGEMENT
# =============================================================================

def is_paused() -> bool:
    """
    Check if the blocker is currently paused.

    Uses file locking to prevent race conditions when checking/removing
    expired pause files across multiple concurrent processes.

    Returns:
        True if paused and pause hasn't expired, False otherwise
    """
    try:
        with open(PAUSE_FILE, 'r+') as f:
            # Acquire exclusive lock to prevent race conditions
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                content = f.read().strip()
                if not content:
                    return False

                pause_until = datetime.fromisoformat(content)
                if datetime.now() < pause_until:
                    return True

                # Pause expired - truncate file while we hold the lock
                f.seek(0)
                f.truncate()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        # Remove empty file outside the lock
        _remove_pause_file()
        return False
    except FileNotFoundError:
        return False
    except (OSError, ValueError):
        return False


def get_pause_remaining() -> Optional[str]:
    """
    Get remaining pause time as a human-readable string.

    Returns:
        String like "5 min" or "< 1 min", or None if not paused
    """
    content = read_secure_file(PAUSE_FILE)
    if not content:
        return None

    try:
        pause_until = datetime.fromisoformat(content)
        remaining = pause_until - datetime.now()

        if remaining.total_seconds() <= 0:
            _remove_pause_file()
            return None

        mins = int(remaining.total_seconds() // 60)
        return f"{mins} min" if mins > 0 else "< 1 min"
    except ValueError:
        return None


def _remove_pause_file() -> None:
    """Remove the pause file safely."""
    try:
        PAUSE_FILE.unlink(missing_ok=True)
    except OSError:
        pass


def set_pause(minutes: int) -> datetime:
    """
    Set the blocker to pause for specified minutes.

    Args:
        minutes: Number of minutes to pause

    Returns:
        DateTime when pause will end
    """
    pause_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
    write_secure_file(PAUSE_FILE, pause_until.isoformat())
    audit_log("PAUSE", f"{minutes} minutes until {pause_until.isoformat()}")
    return pause_until


def clear_pause() -> bool:
    """
    Clear the pause state.

    Returns:
        True if pause was cleared, False if wasn't paused
    """
    if PAUSE_FILE.exists():
        _remove_pause_file()
        audit_log("RESUME", "Manual resume")
        return True
    return False


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

def validate_domain_config(config: Dict[str, Any], index: int) -> List[str]:
    """
    Validate a single domain configuration entry.

    Args:
        config: Domain configuration dictionary
        index: Index in the domains array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: List[str] = []

    # Check domain field exists and is valid
    if 'domain' not in config:
        return [f"#{index}: Missing 'domain' field"]

    domain = config['domain']
    if not domain or not isinstance(domain, str) or not domain.strip():
        return [f"#{index}: Empty or invalid domain"]

    domain = domain.strip()
    if not validate_domain(domain):
        return [f"#{index}: Invalid domain format '{domain}'"]

    # Check schedule if present
    schedule = config.get('schedule')
    if schedule is None:
        return errors

    if not isinstance(schedule, dict):
        return [f"'{domain}': schedule must be a dictionary"]

    if 'available_hours' not in schedule:
        return errors

    hours = schedule['available_hours']
    if not isinstance(hours, list):
        return [f"'{domain}': available_hours must be a list"]

    # Validate each schedule block
    for block_idx, block in enumerate(hours):
        if not isinstance(block, dict):
            errors.append(f"'{domain}': schedule block #{block_idx} must be a dictionary")
            continue

        # Validate days
        for day in block.get('days', []):
            if isinstance(day, str) and day.lower() not in VALID_DAYS:
                errors.append(f"'{domain}': invalid day '{day}'")

        # Validate time ranges
        for tr_idx, time_range in enumerate(block.get('time_ranges', [])):
            if not isinstance(time_range, dict):
                errors.append(f"'{domain}': time_range #{tr_idx} must be a dictionary")
                continue
            for key in ['start', 'end']:
                if key not in time_range:
                    errors.append(f"'{domain}': missing '{key}' in time_range")
                elif not validate_time_format(time_range[key]):
                    errors.append(
                        f"'{domain}': invalid time format '{time_range[key]}' "
                        f"for '{key}' (expected HH:MM)"
                    )

    return errors


def load_domains(script_dir: str, domains_url: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load domain configurations from URL or local file.

    Args:
        script_dir: Directory containing the script (for local domains.json)
        domains_url: Optional URL to fetch domains from

    Returns:
        List of validated domain configurations

    Raises:
        ConfigurationError: If loading or validation fails
    """
    config = None

    if domains_url:
        try:
            response = requests.get(domains_url, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            config = response.json()
            logger.info(f"Loaded domains from URL: {domains_url}")
        except requests.exceptions.RequestException as e:
            raise ConfigurationError(f"Failed to load domains from URL: {e}")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON from URL: {e}")
    else:
        json_file = Path(script_dir) / 'domains.json'
        if not json_file.exists():
            raise ConfigurationError(f"Config file not found: {json_file}")

        try:
            with open(json_file, 'r') as f:
                config = json.load(f)
            logger.info("Loaded domains from local file")
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in domains.json: {e}")

    # Validate structure
    if not isinstance(config, dict):
        raise ConfigurationError("Config must be a JSON object with 'domains' array")

    domains = config.get('domains', [])
    if not domains:
        raise ConfigurationError("No domains configured")

    # Validate each domain
    all_errors: List[str] = []
    for idx, domain_config in enumerate(domains):
        all_errors.extend(validate_domain_config(domain_config, idx))

    if all_errors:
        for error in all_errors:
            logger.error(error)
        raise ConfigurationError(f"Domain validation failed: {len(all_errors)} error(s)")

    return domains


def load_config() -> Dict[str, Any]:
    """
    Load configuration from .env file and environment variables.

    Returns:
        Configuration dictionary with all settings

    Raises:
        ConfigurationError: If required configuration is missing
    """
    script_dir = Path(__file__).parent.absolute()
    env_file = script_dir / '.env'

    if env_file.exists():
        with open(env_file, 'r', encoding='utf-8-sig') as f:  # utf-8-sig handles BOM
            for line_num, line in enumerate(f, 1):
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Validate line format
                if '=' not in line:
                    logger.warning(f".env line {line_num}: missing '=' separator, skipping")
                    continue

                key, value = line.split('=', 1)
                key = key.strip()

                if not key:
                    logger.warning(f".env line {line_num}: empty key, skipping")
                    continue

                os.environ[key] = parse_env_value(value)

    # Build configuration with validated values
    config: Dict[str, Any] = {
        'api_key': os.getenv('NEXTDNS_API_KEY'),
        'profile_id': os.getenv('NEXTDNS_PROFILE_ID'),
        'timezone': os.getenv('TIMEZONE', DEFAULT_TIMEZONE),
        'domains_url': os.getenv('DOMAINS_URL'),
        'timeout': safe_int(os.getenv('API_TIMEOUT'), DEFAULT_TIMEOUT, 'API_TIMEOUT'),
        'retries': safe_int(os.getenv('API_RETRIES'), DEFAULT_RETRIES, 'API_RETRIES'),
        'script_dir': str(script_dir),
        # Notification settings (all optional)
        'NOTIFICATION_EMAIL_ENABLED': os.getenv('NOTIFICATION_EMAIL_ENABLED', ''),
        'NOTIFICATION_EMAIL_SMTP_HOST': os.getenv('NOTIFICATION_EMAIL_SMTP_HOST', ''),
        'NOTIFICATION_EMAIL_SMTP_PORT': os.getenv('NOTIFICATION_EMAIL_SMTP_PORT', '587'),
        'NOTIFICATION_EMAIL_SMTP_USER': os.getenv('NOTIFICATION_EMAIL_SMTP_USER', ''),
        'NOTIFICATION_EMAIL_SMTP_PASSWORD': os.getenv('NOTIFICATION_EMAIL_SMTP_PASSWORD', ''),
        'NOTIFICATION_EMAIL_FROM': os.getenv('NOTIFICATION_EMAIL_FROM', ''),
        'NOTIFICATION_EMAIL_TO': os.getenv('NOTIFICATION_EMAIL_TO', ''),
        'NOTIFICATION_EMAIL_USE_TLS': os.getenv('NOTIFICATION_EMAIL_USE_TLS', 'true'),
        'NOTIFICATION_TELEGRAM_ENABLED': os.getenv('NOTIFICATION_TELEGRAM_ENABLED', ''),
        'NOTIFICATION_TELEGRAM_BOT_TOKEN': os.getenv('NOTIFICATION_TELEGRAM_BOT_TOKEN', ''),
        'NOTIFICATION_TELEGRAM_CHAT_ID': os.getenv('NOTIFICATION_TELEGRAM_CHAT_ID', ''),
        'NOTIFICATION_DISCORD_ENABLED': os.getenv('NOTIFICATION_DISCORD_ENABLED', ''),
        'NOTIFICATION_DISCORD_WEBHOOK_URL': os.getenv('NOTIFICATION_DISCORD_WEBHOOK_URL', ''),
        'NOTIFICATION_SLACK_ENABLED': os.getenv('NOTIFICATION_SLACK_ENABLED', ''),
        'NOTIFICATION_SLACK_WEBHOOK_URL': os.getenv('NOTIFICATION_SLACK_WEBHOOK_URL', ''),
    }

    # Validate required fields
    if not config['api_key']:
        raise ConfigurationError("Missing NEXTDNS_API_KEY in .env or environment")

    if not config['profile_id']:
        raise ConfigurationError("Missing NEXTDNS_PROFILE_ID in .env or environment")

    # Validate timezone early to fail fast
    try:
        ZoneInfo(config['timezone'])
    except KeyError:
        raise ConfigurationError(
            f"Invalid TIMEZONE '{config['timezone']}'. "
            f"See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        )

    # Validate DOMAINS_URL if provided
    if config['domains_url'] and not validate_url(config['domains_url']):
        raise ConfigurationError(
            f"Invalid DOMAINS_URL '{config['domains_url']}'. "
            f"Must be a valid http:// or https:// URL"
        )

    return config


# =============================================================================
# NEXTDNS API CLIENT
# =============================================================================

class RateLimiter:
    """Simple rate limiter using sliding window algorithm."""

    def __init__(
        self,
        max_requests: int = RATE_LIMIT_REQUESTS,
        window_seconds: int = RATE_LIMIT_WINDOW
    ) -> None:
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum requests allowed in the window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: List[float] = []

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


class DenylistCache:
    """Cache for denylist to reduce API calls."""

    def __init__(self, ttl: int = CACHE_TTL) -> None:
        """
        Initialize the cache.

        Args:
            ttl: Time to live in seconds
        """
        self.ttl = ttl
        self._data: Optional[List[Dict[str, Any]]] = None
        self._domains: Set[str] = set()
        self._timestamp: float = 0

    def is_valid(self) -> bool:
        """Check if cache is still valid."""
        return (
            self._data is not None and
            (datetime.now().timestamp() - self._timestamp) < self.ttl
        )

    def get(self) -> Optional[List[Dict[str, Any]]]:
        """Get cached denylist if valid."""
        if self.is_valid():
            return self._data
        return None

    def set(self, data: List[Dict[str, Any]]) -> None:
        """Update cache with new data."""
        self._data = data
        self._domains = {entry.get("id", "") for entry in data}
        self._timestamp = datetime.now().timestamp()

    def contains(self, domain: str) -> Optional[bool]:
        """
        Check if domain is in cached denylist.

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


class NextDNSClient:
    """Client for interacting with the NextDNS API with caching and rate limiting."""

    def __init__(
        self,
        api_key: str,
        profile_id: str,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        notification_manager: Optional[NotificationManager] = None
    ) -> None:
        """
        Initialize the NextDNS client.

        Args:
            api_key: NextDNS API key
            profile_id: NextDNS profile ID
            timeout: Request timeout in seconds
            retries: Number of retry attempts for failed requests
            notification_manager: Optional notification manager for sending alerts
        """
        self.profile_id = profile_id
        self.timeout = timeout
        self.retries = retries
        self.headers: Dict[str, str] = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json"
        }
        self._rate_limiter = RateLimiter()
        self._cache = DenylistCache()
        self._notifications = notification_manager

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay.

        Args:
            attempt: Current attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        delay = BACKOFF_BASE * (2 ** attempt)
        return min(delay, BACKOFF_MAX)

    def request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
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
                    response = requests.get(
                        url, headers=self.headers, timeout=self.timeout
                    )
                elif method == "POST":
                    response = requests.post(
                        url, headers=self.headers, json=data, timeout=self.timeout
                    )
                elif method == "DELETE":
                    response = requests.delete(
                        url, headers=self.headers, timeout=self.timeout
                    )
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
                logger.error(
                    f"API timeout after {self.retries} retries: {method} {endpoint}"
                )
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

    def get_denylist(self, use_cache: bool = True) -> Optional[List[Dict[str, Any]]]:
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
            "POST",
            f"/profiles/{self.profile_id}/denylist",
            {"id": domain, "active": True}
        )

        if result is not None:
            # Optimistic cache update
            self._cache.add_domain(domain)
            logger.info(f"Blocked: {domain}")
            # Send notification
            if self._notifications:
                self._notifications.notify_block(domain)
            return True

        logger.error(f"Failed to block: {domain}")
        # Send error notification
        if self._notifications:
            self._notifications.notify_error(
                f"Failed to block domain: {domain}",
                context="NextDNS API request failed"
            )
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

        result = self.request(
            "DELETE",
            f"/profiles/{self.profile_id}/denylist/{domain}"
        )

        if result is not None:
            # Optimistic cache update
            self._cache.remove_domain(domain)
            logger.info(f"Unblocked: {domain}")
            # Send notification
            if self._notifications:
                self._notifications.notify_unblock(domain)
            return True

        logger.error(f"Failed to unblock: {domain}")
        # Send error notification
        if self._notifications:
            self._notifications.notify_error(
                f"Failed to unblock domain: {domain}",
                context="NextDNS API request failed"
            )
        return False

    def refresh_cache(self) -> bool:
        """
        Force refresh the denylist cache.

        Returns:
            True if successful, False otherwise
        """
        self._cache.invalidate()
        return self.get_denylist(use_cache=False) is not None


# =============================================================================
# SCHEDULE EVALUATOR
# =============================================================================

class ScheduleEvaluator:
    """Evaluates whether a domain should be blocked based on its schedule."""

    def __init__(self, timezone: str = DEFAULT_TIMEZONE) -> None:
        """
        Initialize the schedule evaluator.

        Args:
            timezone: Timezone for schedule evaluation (e.g., 'UTC', 'America/New_York')

        Raises:
            ValueError: If timezone is invalid
        """
        try:
            self.tz = ZoneInfo(timezone)
        except KeyError:
            raise ValueError(f"Invalid timezone: {timezone}")

    def parse_time(self, time_str: str) -> dt_time:
        """
        Parse a time string in HH:MM format.

        Args:
            time_str: Time string to parse

        Returns:
            dt_time object

        Raises:
            ValueError: If time string is invalid
        """
        if not time_str or ':' not in time_str:
            raise ValueError(f"Invalid time format: {time_str}")

        try:
            hour, minute = map(int, time_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError(f"Time out of range: {time_str}")
            return dt_time(hour, minute)
        except (ValueError, AttributeError) as e:
            raise ValueError(f"Invalid time: {time_str}") from e

    def is_time_in_range(
        self,
        current: dt_time,
        start: dt_time,
        end: dt_time
    ) -> bool:
        """
        Check if current time is within a range (supports overnight ranges).

        For normal ranges (start < end), checks: start <= current <= end
        For overnight ranges (start > end), checks: current >= start OR current < end

        Note: End time uses exclusive comparison for overnight ranges to avoid
        ambiguity at midnight boundaries (e.g., 22:00-02:00 includes 01:59 but not 02:00).

        Args:
            current: Current time to check
            start: Range start time
            end: Range end time

        Returns:
            True if current is within range
        """
        if start <= end:
            # Normal range (e.g., 09:00 - 17:00): inclusive on both ends
            return start <= current <= end
        # Overnight range (e.g., 22:00 - 02:00)
        # current >= start (evening part) OR current < end (morning part, exclusive)
        return current >= start or current < end

    def should_block(self, schedule: Optional[Dict[str, Any]]) -> bool:
        """
        Determine if a domain should be blocked based on its schedule.

        Args:
            schedule: Domain schedule configuration, or None for always blocked

        Returns:
            True if domain should be blocked, False if it should be available
        """
        # No schedule means always blocked
        if not schedule or 'available_hours' not in schedule:
            return True

        now = datetime.now(self.tz)
        current_day = now.weekday()
        current_time = now.time()

        for block in schedule['available_hours']:
            try:
                days = [DAYS_MAP[d.lower()] for d in block.get('days', [])]
            except KeyError:
                # Invalid day name, default to blocked
                return True

            if current_day not in days:
                continue

            for time_range in block.get('time_ranges', []):
                try:
                    start = self.parse_time(time_range['start'])
                    end = self.parse_time(time_range['end'])
                    if self.is_time_in_range(current_time, start, end):
                        return False  # Domain is available
                except (KeyError, ValueError):
                    # Invalid time range, default to blocked
                    return True

        # No matching schedule found, block the domain
        return True


# =============================================================================
# CLI COMMAND HANDLERS
# =============================================================================

def get_protected_domains(domains: List[Dict[str, Any]]) -> List[str]:
    """
    Extract domains marked as protected from config.

    Args:
        domains: List of domain configurations

    Returns:
        List of protected domain names
    """
    return [d['domain'] for d in domains if d.get('protected', False)]


def cmd_pause(minutes: int = DEFAULT_PAUSE_MINUTES) -> int:
    """
    Handle the 'pause' command.

    Args:
        minutes: Number of minutes to pause

    Returns:
        Exit code (0 for success)
    """
    pause_until = set_pause(minutes)
    print(f"\n  Blocking paused for {minutes} minutes")
    print(f"  Resumes at: {pause_until.strftime('%H:%M')}")
    print("  Use 'resume' to resume immediately\n")
    return 0


def cmd_resume() -> int:
    """
    Handle the 'resume' command.

    Returns:
        Exit code (0 for success)
    """
    if clear_pause():
        print("\n  Blocking resumed\n")
    else:
        print("\n  Blocking is not paused\n")
    return 0


def cmd_unblock(
    target: str,
    client: NextDNSClient,
    protected_domains: List[str]
) -> int:
    """
    Handle the 'unblock' command.

    Args:
        target: Domain to unblock
        client: NextDNS API client
        protected_domains: List of protected domain names

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    target = target.lower().strip()

    if not validate_domain(target):
        print(f"\n  Invalid domain: {target}\n")
        return 1

    if target in protected_domains:
        print(f"\n  '{target}' is marked as protected in domains.json")
        print("  Remove 'protected: true' from config to unblock it\n")
        return 1

    try:
        if client.unblock(target):
            audit_log("MANUAL_UNBLOCK", target)
            print(f"\n  Unblocked: {target}\n")
            return 0
        else:
            print(f"\n  Failed to unblock: {target}\n")
            return 1
    except DomainValidationError as e:
        print(f"\n  Error: {e}\n")
        return 1


def cmd_sync(
    client: NextDNSClient,
    domains: List[Dict[str, Any]],
    protected_domains: List[str],
    timezone: str,
    dry_run: bool = False,
    verbose: bool = False
) -> int:
    """
    Handle the 'sync' command - synchronize domain blocking with schedules.

    Args:
        client: NextDNS API client
        domains: List of domain configurations
        protected_domains: List of protected domain names
        timezone: Timezone for schedule evaluation
        dry_run: If True, only show what would be done without making changes
        verbose: If True, show detailed output

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Check if paused (skip check in dry-run mode to show what would happen)
    if not dry_run and is_paused():
        remaining = get_pause_remaining()
        logger.info(f"Skipped sync - paused ({remaining} remaining)")
        if verbose:
            print(f"\n  Skipped sync - paused ({remaining} remaining)\n")
        return 0

    try:
        scheduler = ScheduleEvaluator(timezone)
    except ValueError as e:
        logger.error(f"Invalid timezone '{timezone}': {e}")
        print(f"\n  Error: Invalid timezone '{timezone}'")
        print("  Check TIMEZONE in .env (e.g., 'UTC', 'America/New_York')\n")
        return 1

    if dry_run:
        print(f"\n  DRY RUN MODE - No changes will be made")
        print(f"  Timezone: {timezone}")
        now = datetime.now(scheduler.tz)
        print(f"  Current time: {now.strftime('%A %H:%M')} ({timezone})\n")

    blocked_count = 0
    unblocked_count = 0
    unchanged_count = 0

    # Protected domains - always ensure they're blocked
    for protected in protected_domains:
        is_blocked = client.find_domain(protected) is not None
        if not is_blocked:
            if dry_run:
                print(f"  [WOULD BLOCK] {protected} (protected, currently unblocked)")
                blocked_count += 1
            else:
                audit_log("PROTECTED_REBLOCK", protected)
                try:
                    if client.block(protected):
                        blocked_count += 1
                        if verbose:
                            print(f"  [BLOCKED] {protected} (protected)")
                except DomainValidationError as e:
                    logger.error(f"Invalid protected domain: {e}")
        elif verbose or dry_run:
            if dry_run:
                print(f"  [OK] {protected} (protected, already blocked)")
            unchanged_count += 1

    # Scheduled domains
    for domain_config in domains:
        domain = domain_config['domain']

        # Skip protected domains (already handled)
        if domain in protected_domains:
            continue

        should_block = scheduler.should_block(domain_config.get('schedule'))
        is_blocked = client.find_domain(domain) is not None

        if dry_run:
            status = "blocked" if is_blocked else "open"
            action = "should be blocked" if should_block else "should be open"
            if should_block and not is_blocked:
                print(f"  [WOULD BLOCK] {domain} (currently {status}, {action})")
                blocked_count += 1
            elif not should_block and is_blocked:
                print(f"  [WOULD UNBLOCK] {domain} (currently {status}, {action})")
                unblocked_count += 1
            else:
                print(f"  [OK] {domain} (currently {status}, {action})")
                unchanged_count += 1
        else:
            try:
                if should_block and not is_blocked:
                    if client.block(domain):
                        blocked_count += 1
                        if verbose:
                            print(f"  [BLOCKED] {domain}")
                elif not should_block and is_blocked:
                    if client.unblock(domain):
                        unblocked_count += 1
                        if verbose:
                            print(f"  [UNBLOCKED] {domain}")
                elif verbose:
                    status = "blocked" if is_blocked else "open"
                    print(f"  [OK] {domain} ({status})")
                    unchanged_count += 1
            except DomainValidationError as e:
                logger.error(f"Invalid domain in config: {e}")

    # Summary
    if dry_run:
        print(f"\n  Summary (DRY RUN):")
        print(f"    Would block:   {blocked_count}")
        print(f"    Would unblock: {unblocked_count}")
        print(f"    Unchanged:     {unchanged_count}")
        print()
    elif verbose:
        print(f"\n  Summary:")
        print(f"    Blocked:   {blocked_count}")
        print(f"    Unblocked: {unblocked_count}")
        print(f"    Unchanged: {unchanged_count}")
        print()

    logger.info(f"Sync complete: {blocked_count} blocked, {unblocked_count} unblocked")
    return 0


def cmd_status(
    client: NextDNSClient,
    domains: List[Dict[str, Any]],
    protected_domains: List[str]
) -> int:
    """
    Handle the 'status' command - display current blocking status.

    Args:
        client: NextDNS API client
        domains: List of domain configurations
        protected_domains: List of protected domain names

    Returns:
        Exit code (0 for success)
    """
    pause_remaining = get_pause_remaining()
    if pause_remaining:
        print(f"\n  PAUSED ({pause_remaining} remaining)")

    if protected_domains:
        print("\n  protected")
        print("  ---------")
        for protected in protected_domains:
            status = "blocked" if client.find_domain(protected) else "WARNING: not blocked"
            print(f"    {protected:<30} {status}")

    print("\n  scheduled")
    print("  ---------")
    for domain_config in domains:
        domain = domain_config['domain']
        if domain in protected_domains:
            continue
        status = "blocked" if client.find_domain(domain) else "open"
        print(f"    {domain:<30} {status}")
    print()

    return 0


def cmd_health(client: NextDNSClient, config: Dict[str, Any]) -> int:
    """
    Handle the 'health' command - perform health checks.

    Args:
        client: NextDNS API client
        config: Configuration dictionary

    Returns:
        Exit code (0 for healthy, 1 for unhealthy)
    """
    print("\n  NextDNS Blocker Health Check")
    print("  " + "=" * 30)

    all_healthy = True
    checks: List[tuple] = []

    # Check 1: Configuration
    config_ok = bool(config.get('api_key') and config.get('profile_id'))
    checks.append(("Configuration", config_ok, "API key and profile ID set"))

    # Check 2: Timezone
    try:
        ZoneInfo(config.get('timezone', 'UTC'))  # Validate timezone
        tz_ok = True
        tz_msg = f"Timezone: {config.get('timezone', 'UTC')}"
    except Exception:
        tz_ok = False
        tz_msg = f"Invalid timezone: {config.get('timezone')}"
    checks.append(("Timezone", tz_ok, tz_msg))

    # Check 3: API connectivity
    try:
        denylist = client.get_denylist(use_cache=False)
        api_ok = denylist is not None
        api_msg = f"API responding, {len(denylist or [])} domains in denylist"
    except Exception as e:
        api_ok = False
        api_msg = f"API error: {e}"
    checks.append(("API Connection", api_ok, api_msg))

    # Check 4: Pause state
    paused = is_paused()
    pause_remaining = get_pause_remaining()
    if paused:
        pause_msg = f"PAUSED ({pause_remaining} remaining)"
    else:
        pause_msg = "Not paused"
    checks.append(("Pause State", True, pause_msg))  # Info only, not a failure

    # Check 5: Log directory
    log_dir_ok = LOG_DIR.exists() and os.access(LOG_DIR, os.W_OK)
    checks.append(("Log Directory", log_dir_ok, str(LOG_DIR)))

    # Check 6: Cache status
    cache_valid = client._cache.is_valid()
    cache_msg = "Valid" if cache_valid else "Empty/Expired"
    checks.append(("Cache Status", True, cache_msg))  # Info only

    # Print results
    print()
    for name, status, msg in checks:
        icon = "OK" if status else "FAIL"
        status_str = f"[{icon}]"
        print(f"  {status_str:<8} {name:<18} {msg}")
        if not status and name not in ("Pause State", "Cache Status"):
            all_healthy = False

    # Summary
    print()
    if all_healthy:
        print("  Status: HEALTHY")
    else:
        print("  Status: UNHEALTHY")
    print()

    return 0 if all_healthy else 1


def get_stats() -> Dict[str, Any]:
    """
    Get statistics from audit log.

    Returns:
        Dictionary with statistics
    """
    stats = {
        "total_blocks": 0,
        "total_unblocks": 0,
        "total_pauses": 0,
        "last_sync": None,
        "last_action": None
    }

    if not AUDIT_LOG_FILE.exists():
        return stats

    try:
        with open(AUDIT_LOG_FILE, 'r') as f:
            lines = f.readlines()

        for line in lines:
            # Use word boundaries to match actions correctly
            # BLOCK, PROTECTED_REBLOCK count as blocks
            # UNBLOCK, MANUAL_UNBLOCK count as unblocks
            if "| BLOCK |" in line or "| PROTECTED_REBLOCK |" in line:
                stats["total_blocks"] += 1
            elif "UNBLOCK |" in line:
                stats["total_unblocks"] += 1
            elif "| PAUSE |" in line:
                stats["total_pauses"] += 1

        if lines:
            # Get last action timestamp
            last_line = lines[-1].strip()
            if "|" in last_line:
                stats["last_action"] = last_line.split("|")[0].strip()

    except OSError:
        pass

    return stats


def cmd_stats() -> int:
    """
    Handle the 'stats' command - show usage statistics.

    Returns:
        Exit code (0 for success)
    """
    stats = get_stats()

    print("\n  NextDNS Blocker Statistics")
    print("  " + "=" * 28)
    print()
    print(f"  Total blocks:     {stats['total_blocks']}")
    print(f"  Total unblocks:   {stats['total_unblocks']}")
    print(f"  Total pauses:     {stats['total_pauses']}")
    print()
    if stats['last_action']:
        print(f"  Last action:      {stats['last_action']}")
    print()

    return 0


def print_usage() -> None:
    """Print CLI usage information."""
    print("\nUsage:")
    print("  sync [options]    - Sync domain blocking with schedules")
    print("    --dry-run       - Show what would be done without making changes")
    print("    --verbose, -v   - Show detailed output")
    print("  status            - Show current blocking status")
    print("  health            - Perform health checks")
    print("  stats             - Show usage statistics")
    print("  unblock <domain>  - Manually unblock a domain")
    print("  pause [minutes]   - Pause all blocking (default: 30 min)")
    print("  resume            - Resume blocking immediately")
    print()
    print("Examples:")
    print("  ./blocker.bin sync --dry-run    # Preview sync changes")
    print("  ./blocker.bin sync -v           # Sync with verbose output")
    print("  ./blocker.bin health            # Check system health")
    print("  ./blocker.bin pause 60          # Pause for 60 minutes")
    print()


def main() -> int:
    """
    Main entry point for the NextDNS Blocker CLI.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    if len(sys.argv) < 2:
        print_usage()
        return 1

    action = sys.argv[1].lower()

    # Commands that don't need full config
    if action == "pause":
        if len(sys.argv) > 2:
            try:
                minutes = int(sys.argv[2])
                if minutes <= 0:
                    print("\n  Error: pause duration must be a positive number\n")
                    return 1
            except ValueError:
                print(f"\n  Error: '{sys.argv[2]}' is not a valid number\n")
                return 1
        else:
            minutes = DEFAULT_PAUSE_MINUTES
        return cmd_pause(minutes)

    if action == "resume":
        return cmd_resume()

    # Load configuration for other commands
    try:
        config = load_config()
    except ConfigurationError as e:
        logger.error(str(e))
        print(f"\n  Configuration error: {e}\n")
        return 1

    # Initialize notification manager early (after config is loaded)
    try:
        notification_manager = NotificationManager(config)
    except Exception as e:
        logger.warning(f"Failed to initialize notification manager: {e}")
        notification_manager = None

    try:
        domains = load_domains(config['script_dir'], config.get('domains_url'))
    except ConfigurationError as e:
        logger.error(str(e))
        print(f"\n  Configuration error: {e}\n")
        if notification_manager:
            notification_manager.notify_error(str(e), context="Domain configuration loading")
        return 1

    client = NextDNSClient(
        config['api_key'],
        config['profile_id'],
        timeout=config['timeout'],
        retries=config['retries'],
        notification_manager=notification_manager
    )
    protected_domains = get_protected_domains(domains)

    if action == "unblock":
        if len(sys.argv) < 3:
            print("\n  Usage: unblock <domain>\n")
            return 1
        return cmd_unblock(sys.argv[2], client, protected_domains)

    if action == "sync":
        # Parse sync options
        dry_run = "--dry-run" in sys.argv
        verbose = "--verbose" in sys.argv or "-v" in sys.argv
        return cmd_sync(
            client, domains, protected_domains, config['timezone'],
            dry_run=dry_run, verbose=verbose
        )

    if action == "status":
        return cmd_status(client, domains, protected_domains)

    if action == "health":
        return cmd_health(client, config)

    if action == "stats":
        return cmd_stats()

    # Unknown action
    audit_log(f"UNKNOWN_{action}", "")
    print_usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())
