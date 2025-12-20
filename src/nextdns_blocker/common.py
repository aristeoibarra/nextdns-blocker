"""Common utilities shared between NextDNS Blocker modules."""

import contextlib
import logging
import os
import re
import stat
import time
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Optional

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)


# =============================================================================
# CROSS-PLATFORM FILE LOCKING
# =============================================================================

# File locking abstraction for cross-platform support
try:
    import fcntl

    def _lock_file(f: IO[Any], exclusive: bool = True, timeout: Optional[float] = None) -> None:
        """
        Acquire file lock (Unix implementation).

        Args:
            f: File object to lock
            exclusive: If True, acquire exclusive lock; otherwise shared lock
            timeout: Maximum seconds to wait for lock (None = wait indefinitely)

        Raises:
            TimeoutError: If timeout is reached while waiting for lock
            OSError: If lock acquisition fails for other reasons
        """
        lock_type = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH

        if timeout is None:
            # Blocking lock
            fcntl.flock(f.fileno(), lock_type)
        else:
            # Non-blocking with timeout
            deadline = time.monotonic() + timeout
            sleep_interval = 0.01  # Start with 10ms
            max_sleep = 0.1  # Max 100ms between retries

            while True:
                try:
                    fcntl.flock(f.fileno(), lock_type | fcntl.LOCK_NB)
                    return  # Lock acquired
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Failed to acquire file lock within {timeout}s")
                    time.sleep(sleep_interval)
                    sleep_interval = min(sleep_interval * 2, max_sleep)

    def _unlock_file(f: IO[Any]) -> None:
        """Release file lock (Unix implementation)."""
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    _HAS_FCNTL = True

except ImportError:
    # Windows fallback using msvcrt
    # Note: msvcrt.locking() differs from Unix fcntl.flock():
    # - Uses LK_NBLCK (non-blocking) which fails immediately if lock unavailable
    # - Locks only 1 byte at current position (sufficient for our append-only logs)
    # - Does not support shared locks (exclusive parameter is ignored)
    # This is acceptable for our use case since concurrent access is rare and
    # the audit log uses append-only writes.
    try:
        import msvcrt

        def _lock_file(f: IO[Any], exclusive: bool = True, timeout: Optional[float] = None) -> None:
            """
            Acquire file lock (Windows implementation using msvcrt.locking).

            Args:
                f: File object to lock
                exclusive: Ignored on Windows (always exclusive)
                timeout: Maximum seconds to wait for lock (None = wait indefinitely)

            Raises:
                TimeoutError: If timeout is reached while waiting for lock
                OSError: If lock acquisition fails for other reasons
            """
            import time

            if timeout is None:
                # Keep trying indefinitely with a reasonable default timeout
                timeout = 30.0  # 30 second default for "indefinite" on Windows

            deadline = time.monotonic() + timeout
            sleep_interval = 0.01  # Start with 10ms
            max_sleep = 0.1  # Max 100ms between retries

            while True:
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)  # type: ignore[attr-defined]
                    return  # Lock acquired
                except OSError as e:
                    # Windows lock contention errors:
                    # errno 36 = EDEADLOCK (resource busy)
                    # errno 13 = EACCES (permission denied / lock held by another process)
                    # errno 33 = ELOCK (lock violation on some Windows versions)
                    if e.errno not in (13, 33, 36):
                        raise
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"Failed to acquire file lock within {timeout}s")
                    time.sleep(sleep_interval)
                    sleep_interval = min(sleep_interval * 2, max_sleep)

        def _unlock_file(f: IO[Any]) -> None:
            """Release file lock (Windows implementation)."""
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
            except OSError as e:
                # errno 22 = EINVAL (already unlocked or invalid)
                # errno 9 = EBADF (bad file descriptor)
                if e.errno not in (9, 22):
                    logger.warning(f"Unexpected error unlocking file: {e}")
                # Otherwise silently ignore - file already unlocked or closed

        _HAS_FCNTL = False

    except ImportError:
        # No locking available - use no-op functions
        def _lock_file(f: IO[Any], exclusive: bool = True, timeout: Optional[float] = None) -> None:
            """No-op file lock (fallback when no locking available)."""
            pass

        def _unlock_file(f: IO[Any]) -> None:
            """No-op file unlock (fallback when no locking available)."""
            pass

        _HAS_FCNTL = False
        logger.warning("File locking not available on this platform")


# =============================================================================
# SHARED CONSTANTS
# =============================================================================

APP_NAME = "nextdns-blocker"


# Use functions for dynamic path resolution (XDG support)
def get_log_dir() -> Path:
    """Get the log directory path using XDG conventions."""
    return Path(user_data_dir(APP_NAME)) / "logs"


def get_audit_log_file() -> Path:
    """Get the audit log file path."""
    return get_log_dir() / "audit.log"


# Secure file permissions (owner read/write only)
# Note: On Windows, Unix file mode bits (0o600) are largely ignored by the OS.
# Files are created with default Windows ACLs based on the parent directory
# permissions and the user's default ACL. The file is still only accessible
# by the creating user in typical configurations, but the exact permissions
# depend on Windows security settings rather than these mode bits.
# For truly restrictive permissions on Windows, use SetFileSecurity() or icacls.
SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600

# Domain validation constants (RFC 1035)
MAX_DOMAIN_LENGTH = 253
MAX_LABEL_LENGTH = 63

# Domain validation pattern (RFC 1035 compliant, no trailing dot)
DOMAIN_PATTERN = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*"
    r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$"
)

# Time format pattern (HH:MM, 24-hour format)
TIME_PATTERN = re.compile(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$")

# URL pattern for DOMAINS_URL validation (port captured for additional validation)
URL_PATTERN = re.compile(
    r"^https?://"  # http:// or https://
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"  # domain labels
    r"[a-zA-Z]{2,}"  # TLD (at least 2 chars)
    r"(?::(\d{1,5}))?"  # optional port (captured for validation)
    r"(?:/[^\s]*)?$",  # optional path
    re.IGNORECASE,
)

# Valid day names for schedules
VALID_DAYS = frozenset(
    {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
)

# Day name to weekday number mapping (Monday=0, Sunday=6)
DAYS_MAP = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

# Weekday number to day name mapping (inverse of DAYS_MAP)
# This provides O(1) lookup by weekday index without relying on dict key order
WEEKDAY_TO_DAY = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


# =============================================================================
# DIRECTORY MANAGEMENT
# =============================================================================


def ensure_log_dir() -> None:
    """Ensure log directory exists. Called lazily when needed."""
    get_log_dir().mkdir(parents=True, exist_ok=True)


def ensure_naive_datetime(dt: datetime) -> datetime:
    """
    Ensure a datetime is naive (timezone-unaware) for consistent comparisons.

    This function centralizes the handling of naive vs aware datetimes throughout
    the codebase. All datetime comparisons should use naive datetimes to avoid
    TypeError when comparing aware and naive datetimes.

    Args:
        dt: A datetime object (can be naive or aware)

    Returns:
        A naive datetime (tzinfo stripped if present)
    """
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


# =============================================================================
# VALIDATION FUNCTIONS
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
    if domain.endswith("."):
        return False
    return DOMAIN_PATTERN.match(domain) is not None


def is_subdomain(child: str, parent: str) -> bool:
    """
    Check if child is a subdomain of parent.

    This is used to detect when an allowlist entry is a subdomain of a blocked
    domain, which is a valid configuration but worth warning about since the
    allowlist entry will override the block for that specific subdomain.

    Args:
        child: Potential subdomain (e.g., 'aws.amazon.com')
        parent: Potential parent domain (e.g., 'amazon.com')

    Returns:
        True if child is a subdomain of parent, False otherwise

    Examples:
        >>> is_subdomain("aws.amazon.com", "amazon.com")
        True
        >>> is_subdomain("a.b.c.example.com", "example.com")
        True
        >>> is_subdomain("amazon.com", "amazon.com")
        False
        >>> is_subdomain("notamazon.com", "amazon.com")
        False
    """
    if not child or not parent:
        return False

    child_lower = child.strip().lower()
    parent_lower = parent.strip().lower()

    # Same domain is not a subdomain relationship
    if child_lower == parent_lower:
        return False

    # Child must end with ".parent" to be a valid subdomain
    # This prevents partial matches like "notamazon.com" matching "amazon.com"
    return child_lower.endswith("." + parent_lower)


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

    Validates:
    - Must be http or https scheme
    - Valid domain name structure
    - Port number in valid range (1-65535) if specified

    Args:
        url: URL string to validate

    Returns:
        True if valid URL format, False otherwise
    """
    if not url or not isinstance(url, str):
        return False

    match = URL_PATTERN.match(url)
    if not match:
        return False

    # Validate port range if present
    port_str = match.group(1)
    if port_str:
        # Reject leading zeros (could indicate octal in some contexts)
        if len(port_str) > 1 and port_str.startswith("0"):
            return False
        port = int(port_str)
        if port < 1 or port > 65535:
            return False

    return True


# =============================================================================
# PARSING FUNCTIONS
# =============================================================================


def parse_env_value(value: str) -> str:
    """
    Parse .env value, handling quotes and whitespace.

    Args:
        value: Raw value from .env file

    Returns:
        Cleaned value with quotes removed

    Raises:
        ValueError: If value is None or not a string
    """
    if value is None or not isinstance(value, str):
        raise ValueError("Environment value must be a non-None string")

    value = value.strip()
    if len(value) >= 2 and (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
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
        ConfigurationError: If value is not a valid non-negative integer
    """
    from .exceptions import ConfigurationError

    if value is None:
        return default

    try:
        result = int(value)
        if result < 0:
            raise ConfigurationError(f"{name} must be a non-negative integer, got: {value}")
        return result
    except ValueError:
        raise ConfigurationError(f"{name} must be a valid integer, got: {value}")


# =============================================================================
# FILE I/O FUNCTIONS
# =============================================================================


def audit_log(action: str, detail: str = "", prefix: str = "") -> None:
    """
    Log an action to the audit log file with secure permissions and file locking.

    Args:
        action: The action being logged (e.g., 'BLOCK', 'UNBLOCK', 'PAUSE')
        detail: Additional details about the action
        prefix: Optional prefix for the log entry (e.g., 'WD' for watchdog)
    """
    try:
        ensure_log_dir()

        audit_file = get_audit_log_file()

        # Create file with secure permissions if it doesn't exist
        if not audit_file.exists():
            audit_file.touch(mode=SECURE_FILE_MODE)

        # Build log entry
        parts = [datetime.now().isoformat()]
        if prefix:
            parts.append(prefix)
        parts.extend([action, detail])
        log_entry = " | ".join(parts) + "\n"

        # Write with exclusive lock to prevent corruption from concurrent writes
        with open(audit_file, "a", encoding="utf-8") as f:
            _lock_file(f, exclusive=True)
            try:
                f.write(log_entry)
            finally:
                _unlock_file(f)

    except OSError as e:
        # Log at WARNING level to ensure audit failures are visible
        # (audit logs are security-relevant and failures should be noticed)
        logger.warning(f"Failed to write audit log: {e}")


def write_secure_file(path: Path, content: str) -> None:
    """
    Write content to a file with secure permissions (0o600).

    Args:
        path: Path to the file
        content: Content to write

    Raises:
        OSError: If file operations fail
    """
    # Resolve the path to catch symlink attacks and path traversal
    resolved_path = path.resolve()

    # Ensure log directory exists if writing to log dir
    log_dir = get_log_dir().resolve()
    if resolved_path.parent == log_dir or log_dir in resolved_path.parents:
        ensure_log_dir()
    else:
        # Create parent directories if needed for other paths
        resolved_path.parent.mkdir(parents=True, exist_ok=True)

    # Set secure permissions before writing if file exists
    if resolved_path.exists():
        os.chmod(resolved_path, SECURE_FILE_MODE)

    # Write with exclusive lock
    fd = os.open(resolved_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, SECURE_FILE_MODE)
    fd_closed = False
    try:
        # os.fdopen takes ownership of fd - it will close it when the file object closes
        f = os.fdopen(fd, "w")
        fd_closed = True  # fd is now owned by f
        try:
            _lock_file(f, exclusive=True)
            try:
                f.write(content)
                f.flush()  # Ensure data is written before unlocking
                os.fsync(f.fileno())  # Force write to disk
            finally:
                _unlock_file(f)
        finally:
            f.close()
    except OSError:
        # Only close fd if os.fdopen failed (fd not yet owned by file object)
        if not fd_closed:
            with contextlib.suppress(OSError):
                os.close(fd)
        raise


def read_secure_file(path: Path) -> Optional[str]:
    """
    Read content from a file with shared lock.

    Args:
        path: Path to the file

    Returns:
        File content or None if file doesn't exist or read fails
    """
    if not path.exists():
        return None

    try:
        with open(path, encoding="utf-8") as f:
            _lock_file(f, exclusive=False)
            try:
                return f.read().strip()
            finally:
                _unlock_file(f)
    except OSError as e:
        logger.debug(f"Failed to read secure file {path}: {e}")
        return None
