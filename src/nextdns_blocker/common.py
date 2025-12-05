"""Common utilities shared between NextDNS Blocker modules."""

import fcntl
import logging
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Optional

from platformdirs import user_data_dir

logger = logging.getLogger(__name__)


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

# Keep legacy constants for backwards compatibility with tests
# These are evaluated at import time but point to the same location
LOG_DIR = get_log_dir()
AUDIT_LOG_FILE = get_audit_log_file()

# Secure file permissions (owner read/write only)
SECURE_FILE_MODE = stat.S_IRUSR | stat.S_IWUSR  # 0o600

# Domain validation constants (RFC 1035)
MAX_DOMAIN_LENGTH = 253
MAX_LABEL_LENGTH = 63

# Domain validation pattern (RFC 1035 compliant, no trailing dot)
DOMAIN_PATTERN = re.compile(
    r'^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)*'
    r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?$'
)

# Time format pattern (HH:MM, 24-hour format)
TIME_PATTERN = re.compile(r'^([01]?[0-9]|2[0-3]):([0-5][0-9])$')

# URL pattern for DOMAINS_URL validation
URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+'  # domain labels
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
DAYS_MAP = {
    'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
    'friday': 4, 'saturday': 5, 'sunday': 6
}


# =============================================================================
# DIRECTORY MANAGEMENT
# =============================================================================

def ensure_log_dir() -> None:
    """Ensure log directory exists. Called lazily when needed."""
    get_log_dir().mkdir(parents=True, exist_ok=True)


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
    from .exceptions import ConfigurationError

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
        with open(audit_file, 'a') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(log_entry)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    except OSError as e:
        logger.debug(f"Failed to write audit log: {e}")


def write_secure_file(path: Path, content: str) -> None:
    """
    Write content to a file with secure permissions (0o600).

    Args:
        path: Path to the file
        content: Content to write
    """
    log_dir = get_log_dir()
    # Ensure log directory exists if writing to log dir
    if path.parent == log_dir:
        ensure_log_dir()
    else:
        # Create parent directories if needed for other paths
        path.parent.mkdir(parents=True, exist_ok=True)

    # Set secure permissions before writing if file exists
    if path.exists():
        os.chmod(path, SECURE_FILE_MODE)

    # Write with exclusive lock
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, SECURE_FILE_MODE)
    fd_owned = False
    try:
        f = os.fdopen(fd, 'w')
        fd_owned = True  # os.fdopen now owns the fd, don't close manually
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(content)
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()
    except Exception:
        if not fd_owned:
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
        with open(path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return f.read().strip()
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except OSError:
        return None
