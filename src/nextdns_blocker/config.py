"""Configuration loading and validation for NextDNS Blocker."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Optional

# Timezone support: use zoneinfo (Python 3.9+)
from zoneinfo import ZoneInfo

from platformdirs import user_config_dir, user_data_dir

from .common import (
    APP_NAME,
    NEXTDNS_CATEGORIES,
    NEXTDNS_SERVICES,
    VALID_DAYS,
    get_log_dir,
    parse_env_value,
    safe_int,
    validate_category_id,
    validate_domain,
    validate_time_format,
)
from .exceptions import ConfigurationError

# Re-export get_log_dir for backward compatibility
__all__ = ["get_log_dir"]

# =============================================================================
# CREDENTIAL VALIDATION PATTERNS
# =============================================================================

# NextDNS API key pattern: alphanumeric with optional underscores/hyphens
# Minimum 8 characters for flexibility with test keys
API_KEY_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{8,}$")

# NextDNS Profile ID pattern: alphanumeric, typically 6 characters like "abc123"
PROFILE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{4,30}$")

# Discord Webhook pattern: Stricter validation
# - Webhook ID: 17-20 digit snowflake (Discord uses snowflakes as IDs)
# - Token: 60-100 character alphanumeric with underscores/hyphens/dots
#   (extended range to accommodate Discord's varying token lengths)
DISCORD_WEBHOOK_PATTERN = re.compile(
    r"^https://discord\.com/api/webhooks/\d{17,20}/[a-zA-Z0-9_.-]{60,100}$"
)

# =============================================================================
# UNBLOCK DELAY SETTINGS
# =============================================================================

# Legacy valid unblock_delay values (kept for backward compatibility messages)
VALID_UNBLOCK_DELAYS = frozenset({"never", "24h", "4h", "30m", "0"})

# Legacy mapping of unblock_delay strings to seconds (None for 'never' = cannot unblock)
# Kept for backward compatibility - new code should use parse_duration()
UNBLOCK_DELAY_SECONDS: dict[str, Optional[int]] = {
    "never": None,
    "24h": 24 * 60 * 60,
    "4h": 4 * 60 * 60,
    "30m": 30 * 60,
    "0": 0,
}

# Flexible duration pattern: number followed by unit (m=minutes, h=hours, d=days)
DURATION_PATTERN = re.compile(r"^(\d+)([mhd])$")

# Duration unit multipliers (to seconds)
DURATION_MULTIPLIERS = {"m": 60, "h": 3600, "d": 86400}


def parse_duration(value: str) -> Optional[int]:
    """
    Parse flexible duration string to seconds.

    Supports:
    - "never": Cannot unblock (returns None)
    - "0": Immediate unblock (returns 0)
    - "{n}m": n minutes (e.g., "30m", "45m", "90m")
    - "{n}h": n hours (e.g., "1h", "2h", "24h")
    - "{n}d": n days (e.g., "1d", "7d")

    Args:
        value: Duration string like "30m", "2h", "1d", or "never"/"0"

    Returns:
        Seconds as int, or None for "never"

    Raises:
        ValueError: If duration format is invalid
    """
    if not value or not isinstance(value, str):
        raise ValueError("Duration must be a non-empty string")

    value = value.strip().lower()

    if value == "never":
        return None
    if value == "0":
        return 0

    match = DURATION_PATTERN.match(value)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{value}'. "
            f"Expected: 'never', '0', or number with unit (e.g., '30m', '2h', '1d')"
        )

    amount = int(match.group(1))
    unit = match.group(2)

    if amount == 0:
        return 0

    return amount * DURATION_MULTIPLIERS[unit]


def validate_api_key(api_key: str) -> bool:
    """
    Validate NextDNS API key format.

    Args:
        api_key: API key string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not api_key or not isinstance(api_key, str):
        return False
    return API_KEY_PATTERN.match(api_key.strip()) is not None


def validate_profile_id(profile_id: str) -> bool:
    """
    Validate NextDNS Profile ID format.

    Args:
        profile_id: Profile ID string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not profile_id or not isinstance(profile_id, str):
        return False
    return PROFILE_ID_PATTERN.match(profile_id.strip()) is not None


def validate_discord_webhook(url: str) -> bool:
    """
    Validate Discord Webhook URL format.

    Args:
        url: Webhook URL string to validate

    Returns:
        True if valid format, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    return DISCORD_WEBHOOK_PATTERN.match(url.strip()) is not None


def validate_unblock_delay(delay: str) -> bool:
    """
    Validate unblock_delay value using flexible duration parser.

    Supports flexible durations like "30m", "2h", "1d", "never", "0".

    Args:
        delay: Delay string to validate

    Returns:
        True if valid, False otherwise
    """
    if not delay or not isinstance(delay, str):
        return False
    try:
        parse_duration(delay)
        return True
    except ValueError:
        return False


def parse_unblock_delay_seconds(delay: str) -> Optional[int]:
    """
    Convert unblock_delay string to seconds using flexible duration parser.

    Supports flexible durations like "30m", "2h", "1d", "never", "0".

    Args:
        delay: Delay string (e.g., "30m", "2h", "1d", "never", "0")

    Returns:
        Number of seconds, or None for 'never' (cannot unblock)

    Raises:
        ValueError: If duration format is invalid
    """
    return parse_duration(delay)


# =============================================================================
# CONSTANTS
# =============================================================================

# APP_NAME is imported from common.py to avoid duplication
DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_TIMEZONE = "UTC"
DEFAULT_PAUSE_MINUTES = 30

logger = logging.getLogger(__name__)


# =============================================================================
# XDG DIRECTORY FUNCTIONS
# =============================================================================


def get_config_dir(override: Optional[Path] = None) -> Path:
    """
    Get the configuration directory path.

    Resolution order:
    1. Override path if provided
    2. Current working directory if .env AND config.json exist
    3. XDG config directory (~/.config/nextdns-blocker on Linux,
       ~/Library/Application Support/nextdns-blocker on macOS)

    Args:
        override: Optional path to use instead of auto-detection

    Returns:
        Path to the configuration directory
    """
    if override:
        return Path(override)

    # Require .env AND config.json to use CWD (fixes #124)
    # This avoids false positives from unrelated .env files
    cwd = Path.cwd()
    has_env = (cwd / ".env").exists()
    has_config = (cwd / "config.json").exists()
    if has_env and has_config:
        return cwd

    return Path(user_config_dir(APP_NAME))


def get_data_dir() -> Path:
    """
    Get the data directory path for logs and state files.

    Returns:
        Path to the data directory (~/.local/share/nextdns-blocker on Linux,
        ~/Library/Application Support/nextdns-blocker on macOS)
    """
    return Path(user_data_dir(APP_NAME))


# =============================================================================
# SCHEDULE VALIDATION
# =============================================================================


def validate_schedule(schedule: dict[str, Any], prefix: str) -> list[str]:
    """
    Validate a schedule configuration.

    Args:
        schedule: Schedule configuration dictionary with available_hours
        prefix: Prefix for error messages (e.g., "'example.com'" or "allowlist 'example.com'")

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    if not isinstance(schedule, dict):
        return [f"{prefix}: schedule must be a dictionary"]

    if "available_hours" not in schedule:
        return errors

    hours = schedule["available_hours"]
    if not isinstance(hours, list):
        return [f"{prefix}: available_hours must be a list"]

    # Collect all time ranges per day for overlap detection
    day_time_ranges: dict[str, list[tuple[int, int, int]]] = (
        {}
    )  # day -> [(start_mins, end_mins, block_idx)]

    # Validate each schedule block
    for block_idx, block in enumerate(hours):
        if not isinstance(block, dict):
            errors.append(f"{prefix}: schedule block #{block_idx} must be a dictionary")
            continue

        # Validate days
        block_days = []
        for day in block.get("days", []):
            if isinstance(day, str):
                day_lower = day.lower()
                if day_lower not in VALID_DAYS:
                    errors.append(f"{prefix}: invalid day '{day}'")
                else:
                    block_days.append(day_lower)

        # Validate time ranges
        for tr_idx, time_range in enumerate(block.get("time_ranges", [])):
            if not isinstance(time_range, dict):
                errors.append(f"{prefix}: time_range #{tr_idx} must be a dictionary")
                continue

            start_valid = True
            end_valid = True
            for key in ["start", "end"]:
                if key not in time_range:
                    errors.append(f"{prefix}: missing '{key}' in time_range")
                    if key == "start":
                        start_valid = False
                    else:
                        end_valid = False
                elif not validate_time_format(time_range[key]):
                    errors.append(
                        f"{prefix}: invalid time format '{time_range[key]}' "
                        f"for '{key}' (expected HH:MM)"
                    )
                    if key == "start":
                        start_valid = False
                    else:
                        end_valid = False

            # Collect time ranges for overlap detection (only if both start and end are valid)
            if start_valid and end_valid:
                start_h, start_m = map(int, time_range["start"].split(":"))
                end_h, end_m = map(int, time_range["end"].split(":"))
                start_mins = start_h * 60 + start_m
                end_mins = end_h * 60 + end_m

                for day in block_days:
                    if day not in day_time_ranges:
                        day_time_ranges[day] = []
                    day_time_ranges[day].append((start_mins, end_mins, block_idx))

    # Check for overlapping time ranges on the same day
    for day, ranges in day_time_ranges.items():
        if len(ranges) < 2:
            continue

        # Sort by start time
        sorted_ranges = sorted(ranges, key=lambda x: x[0])

        for i in range(len(sorted_ranges) - 1):
            start1, end1, block1 = sorted_ranges[i]
            start2, end2, block2 = sorted_ranges[i + 1]

            # Handle overnight ranges (end < start means it crosses midnight)
            is_overnight1 = end1 < start1
            is_overnight2 = end2 < start2

            # For non-overnight ranges, check simple overlap
            if not is_overnight1 and not is_overnight2:
                if start2 < end1:  # Overlap detected
                    logger.warning(
                        f"{prefix}: overlapping time ranges on {day} "
                        f"(block #{block1} and #{block2})"
                    )

    return errors


# =============================================================================
# DOMAIN CONFIG VALIDATION
# =============================================================================


def validate_domain_config(config: dict[str, Any], index: int) -> list[str]:
    """
    Validate a single domain configuration entry.

    Args:
        config: Domain configuration dictionary
        index: Index in the domains array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check domain field exists and is valid
    if "domain" not in config:
        return [f"#{index}: Missing 'domain' field"]

    domain = config["domain"]
    if not domain or not isinstance(domain, str) or not domain.strip():
        return [f"#{index}: Empty or invalid domain"]

    domain = domain.strip()
    if not validate_domain(domain):
        return [f"#{index}: Invalid domain format '{domain}'"]

    # Validate unblock_delay if present
    unblock_delay = config.get("unblock_delay")
    if unblock_delay is not None and not validate_unblock_delay(unblock_delay):
        errors.append(
            f"'{domain}': invalid unblock_delay '{unblock_delay}' "
            f"(expected: 'never', '0', or duration like '30m', '2h', '1d')"
        )

    # Check schedule if present
    schedule = config.get("schedule")
    if schedule is not None:
        schedule_errors = validate_schedule(schedule, f"'{domain}'")
        errors.extend(schedule_errors)

    return errors


def validate_allowlist_config(config: dict[str, Any], index: int) -> list[str]:
    """
    Validate a single allowlist configuration entry.

    Args:
        config: Allowlist configuration dictionary
        index: Index in the allowlist array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check domain field exists and is valid
    if "domain" not in config:
        return [f"allowlist #{index}: Missing 'domain' field"]

    domain = config["domain"]
    if not domain or not isinstance(domain, str) or not domain.strip():
        return [f"allowlist #{index}: Empty or invalid domain"]

    domain = domain.strip()
    if not validate_domain(domain):
        return [f"allowlist #{index}: Invalid domain format '{domain}'"]

    # Validate schedule if present (allowlist now supports scheduled entries)
    schedule = config.get("schedule")
    if schedule is not None:
        schedule_errors = validate_schedule(schedule, f"allowlist '{domain}'")
        errors.extend(schedule_errors)

    return errors


def validate_category_config(config: dict[str, Any], index: int) -> list[str]:
    """
    Validate a single category configuration entry.

    Args:
        config: Category configuration dictionary
        index: Index in the categories array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check id field exists and is valid
    if "id" not in config:
        return [f"category #{index}: Missing 'id' field"]

    category_id = config["id"]
    if not category_id or not isinstance(category_id, str) or not category_id.strip():
        return [f"category #{index}: Empty or invalid id"]

    category_id = category_id.strip()
    if not validate_category_id(category_id):
        return [
            f"category #{index}: Invalid id format '{category_id}' "
            f"(must start with lowercase letter, contain only lowercase letters, numbers, hyphens)"
        ]

    prefix = f"category '{category_id}'"

    # Check domains field exists and is a non-empty list
    if "domains" not in config:
        errors.append(f"{prefix}: Missing 'domains' field")
    else:
        domains = config["domains"]
        if not isinstance(domains, list):
            errors.append(f"{prefix}: 'domains' must be an array")
        elif not domains:
            errors.append(f"{prefix}: 'domains' array cannot be empty")
        else:
            # Validate each domain in the category (simple strings only)
            for dom_idx, domain in enumerate(domains):
                if not isinstance(domain, str):
                    errors.append(f"{prefix}: domain #{dom_idx} must be a string")
                elif not domain or not domain.strip():
                    errors.append(f"{prefix}: domain #{dom_idx} is empty")
                elif not validate_domain(domain.strip()):
                    errors.append(f"{prefix}: invalid domain format '{domain}'")

    # Validate description if present (optional)
    description = config.get("description")
    if description is not None and not isinstance(description, str):
        errors.append(f"{prefix}: 'description' must be a string")

    # Validate unblock_delay if present (optional)
    unblock_delay = config.get("unblock_delay")
    if unblock_delay is not None and not validate_unblock_delay(unblock_delay):
        errors.append(
            f"{prefix}: invalid unblock_delay '{unblock_delay}' "
            f"(expected: 'never', '0', or duration like '30m', '2h', '1d')"
        )

    # Validate schedule if present (optional, can be null)
    schedule = config.get("schedule")
    if schedule is not None:
        schedule_errors = validate_schedule(schedule, prefix)
        errors.extend(schedule_errors)

    return errors


def validate_no_overlap(
    domains: list[dict[str, Any]], allowlist: list[dict[str, Any]]
) -> list[str]:
    """
    Validate that no domain appears in both denylist and allowlist.

    Args:
        domains: List of denylist domain configurations
        allowlist: List of allowlist domain configurations

    Returns:
        List of error messages (empty if no conflicts)
    """
    errors: list[str] = []

    denylist_domains = {
        d["domain"].strip().lower()
        for d in domains
        if "domain" in d and isinstance(d["domain"], str)
    }
    allowlist_domains = {
        a["domain"].strip().lower()
        for a in allowlist
        if "domain" in a and isinstance(a["domain"], str)
    }

    overlap = denylist_domains & allowlist_domains

    for domain in sorted(overlap):
        errors.append(
            f"Domain '{domain}' appears in both 'domains' (denylist) and 'allowlist'. "
            f"A domain cannot be blocked and allowed simultaneously."
        )

    return errors


def check_subdomain_relationships(
    domains: list[dict[str, Any]], allowlist: list[dict[str, Any]]
) -> None:
    """
    Log warnings when allowlist domains are subdomains of blocked domains.

    This is informational only - the configuration is valid, but the user
    should understand that the allowlist entry will override the block
    for that specific subdomain in NextDNS.

    Args:
        domains: List of denylist domain configurations
        allowlist: List of allowlist domain configurations
    """
    from .common import is_subdomain

    for allow_entry in allowlist:
        allow_domain = allow_entry.get("domain", "")
        if not allow_domain or not isinstance(allow_domain, str):
            continue

        for block_entry in domains:
            block_domain = block_entry.get("domain", "")
            if not block_domain or not isinstance(block_domain, str):
                continue

            if is_subdomain(allow_domain, block_domain):
                logger.warning(
                    f"Allowlist '{allow_domain}' is a subdomain of blocked '{block_domain}'. "
                    f"The allowlist entry will override the block for this subdomain in NextDNS."
                )


def check_category_subdomain_relationships(
    categories: list[dict[str, Any]], allowlist: list[dict[str, Any]]
) -> None:
    """
    Log warnings when allowlist domains are subdomains of category domains.

    This is informational only - the configuration is valid (see issue #143),
    but the user should understand that the allowlist entry will override
    the block for that specific subdomain in NextDNS.

    Args:
        categories: List of category configurations
        allowlist: List of allowlist domain configurations
    """
    from .common import is_subdomain

    for allow_entry in allowlist:
        allow_domain = allow_entry.get("domain", "")
        if not allow_domain or not isinstance(allow_domain, str):
            continue

        for category in categories:
            category_id = category.get("id", "unknown")
            category_domains = category.get("domains", [])

            for block_domain in category_domains:
                if not block_domain or not isinstance(block_domain, str):
                    continue

                if is_subdomain(allow_domain, block_domain):
                    logger.warning(
                        f"Subdomain relationship: '{allow_domain}' (allowlist) is subdomain of "
                        f"'{block_domain}' (category: {category_id})"
                    )


def validate_no_duplicate_domains(
    categories: list[dict[str, Any]], blocklist: list[dict[str, Any]]
) -> list[str]:
    """
    Validate that no domain appears in multiple categories or both category and blocklist.

    Args:
        categories: List of category configurations
        blocklist: List of blocklist domain configurations

    Returns:
        List of error messages (empty if no duplicates)
    """
    errors: list[str] = []

    # Track all domains and their sources
    domain_sources: dict[str, list[str]] = {}  # domain -> list of sources

    # Collect domains from categories
    for category in categories:
        category_id = category.get("id", "unknown")
        category_domains = category.get("domains", [])

        for domain in category_domains:
            if isinstance(domain, str) and domain.strip():
                domain_lower = domain.strip().lower()
                if domain_lower not in domain_sources:
                    domain_sources[domain_lower] = []
                domain_sources[domain_lower].append(f"category '{category_id}'")

    # Collect domains from blocklist
    for block_entry in blocklist:
        domain = block_entry.get("domain", "")
        if isinstance(domain, str) and domain.strip():
            domain_lower = domain.strip().lower()
            if domain_lower not in domain_sources:
                domain_sources[domain_lower] = []
            domain_sources[domain_lower].append("blocklist")

    # Find duplicates
    for domain, sources in sorted(domain_sources.items()):
        if len(sources) > 1:
            sources_str = " and ".join(sources)
            errors.append(
                f"Domain '{domain}' appears in multiple locations: {sources_str}. "
                f"A domain can only exist in one category or blocklist."
            )

    return errors


def validate_unique_category_ids(categories: list[dict[str, Any]]) -> list[str]:
    """
    Validate that all category IDs are unique.

    Args:
        categories: List of category configurations

    Returns:
        List of error messages (empty if all IDs are unique)
    """
    errors: list[str] = []
    seen_ids: dict[str, int] = {}  # id -> first occurrence index

    for idx, category in enumerate(categories):
        category_id = category.get("id")
        if isinstance(category_id, str) and category_id.strip():
            id_lower = category_id.strip().lower()
            if id_lower in seen_ids:
                errors.append(
                    f"category #{idx}: Duplicate id '{category_id}' "
                    f"(first defined at category #{seen_ids[id_lower]})"
                )
            else:
                seen_ids[id_lower] = idx

    return errors


# =============================================================================
# NEXTDNS PARENTAL CONTROL VALIDATION
# =============================================================================


def validate_nextdns_category(config: dict[str, Any], index: int) -> list[str]:
    """
    Validate a single NextDNS native category configuration entry.

    Args:
        config: NextDNS category configuration dictionary
        index: Index in the categories array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check id field exists
    if "id" not in config:
        return [f"nextdns.categories[{index}]: Missing 'id' field"]

    category_id = config["id"]
    if not category_id or not isinstance(category_id, str) or not category_id.strip():
        return [f"nextdns.categories[{index}]: Empty or invalid id"]

    category_id = category_id.strip().lower()

    # Validate against known NextDNS categories
    if category_id not in NEXTDNS_CATEGORIES:
        valid_ids = ", ".join(sorted(NEXTDNS_CATEGORIES))
        return [
            f"nextdns.categories[{index}]: Invalid category id '{category_id}'. "
            f"Valid IDs: {valid_ids}"
        ]

    prefix = f"nextdns.categories['{category_id}']"

    # Validate description if present (optional)
    description = config.get("description")
    if description is not None and not isinstance(description, str):
        errors.append(f"{prefix}: 'description' must be a string")

    # Validate unblock_delay if present (optional)
    unblock_delay = config.get("unblock_delay")
    if unblock_delay is not None and not validate_unblock_delay(unblock_delay):
        errors.append(
            f"{prefix}: invalid unblock_delay '{unblock_delay}' "
            f"(expected: 'never', '0', or duration like '30m', '2h', '1d')"
        )

    # Validate schedule if present (optional, can be null)
    schedule = config.get("schedule")
    if schedule is not None:
        schedule_errors = validate_schedule(schedule, prefix)
        errors.extend(schedule_errors)

    return errors


def validate_nextdns_service(config: dict[str, Any], index: int) -> list[str]:
    """
    Validate a single NextDNS native service configuration entry.

    Args:
        config: NextDNS service configuration dictionary
        index: Index in the services array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    # Check id field exists
    if "id" not in config:
        return [f"nextdns.services[{index}]: Missing 'id' field"]

    service_id = config["id"]
    if not service_id or not isinstance(service_id, str) or not service_id.strip():
        return [f"nextdns.services[{index}]: Empty or invalid id"]

    service_id = service_id.strip().lower()

    # Validate against known NextDNS services
    if service_id not in NEXTDNS_SERVICES:
        # Group services by category for better error message
        errors.append(
            f"nextdns.services[{index}]: Invalid service id '{service_id}'. "
            f"See documentation for valid service IDs (43 available)."
        )
        return errors

    prefix = f"nextdns.services['{service_id}']"

    # Validate description if present (optional)
    description = config.get("description")
    if description is not None and not isinstance(description, str):
        errors.append(f"{prefix}: 'description' must be a string")

    # Validate unblock_delay if present (optional)
    unblock_delay = config.get("unblock_delay")
    if unblock_delay is not None and not validate_unblock_delay(unblock_delay):
        errors.append(
            f"{prefix}: invalid unblock_delay '{unblock_delay}' "
            f"(expected: 'never', '0', or duration like '30m', '2h', '1d')"
        )

    # Validate schedule if present (optional, can be null)
    schedule = config.get("schedule")
    if schedule is not None:
        schedule_errors = validate_schedule(schedule, prefix)
        errors.extend(schedule_errors)

    return errors


def validate_nextdns_parental_control(config: dict[str, Any]) -> list[str]:
    """
    Validate NextDNS parental_control global settings.

    Args:
        config: Parental control configuration dictionary

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    if not isinstance(config, dict):
        return ["nextdns.parental_control: must be an object"]

    valid_keys = {"safe_search", "youtube_restricted_mode", "block_bypass"}

    for key, value in config.items():
        if key not in valid_keys:
            errors.append(
                f"nextdns.parental_control: unknown key '{key}'. "
                f"Valid keys: {', '.join(sorted(valid_keys))}"
            )
        elif not isinstance(value, bool):
            errors.append(f"nextdns.parental_control.{key}: must be a boolean")

    return errors


def validate_nextdns_config(nextdns_config: dict[str, Any]) -> list[str]:
    """
    Validate the complete nextdns configuration section.

    Args:
        nextdns_config: The 'nextdns' section from config.json

    Returns:
        List of error messages (empty if valid)
    """
    errors: list[str] = []

    if not isinstance(nextdns_config, dict):
        return ["'nextdns' must be an object"]

    # Validate parental_control if present
    parental_control = nextdns_config.get("parental_control")
    if parental_control is not None:
        errors.extend(validate_nextdns_parental_control(parental_control))

    # Validate categories if present
    categories = nextdns_config.get("categories", [])
    if not isinstance(categories, list):
        errors.append("nextdns.categories: must be an array")
    else:
        seen_category_ids: set[str] = set()
        for idx, category_config in enumerate(categories):
            if not isinstance(category_config, dict):
                errors.append(f"nextdns.categories[{idx}]: must be an object")
                continue
            errors.extend(validate_nextdns_category(category_config, idx))

            # Check for duplicate category IDs
            cat_id = category_config.get("id")
            if isinstance(cat_id, str) and cat_id.strip():
                cat_id_lower = cat_id.strip().lower()
                if cat_id_lower in seen_category_ids:
                    errors.append(f"nextdns.categories[{idx}]: duplicate category id '{cat_id}'")
                else:
                    seen_category_ids.add(cat_id_lower)

    # Validate services if present
    services = nextdns_config.get("services", [])
    if not isinstance(services, list):
        errors.append("nextdns.services: must be an array")
    else:
        seen_service_ids: set[str] = set()
        for idx, service_config in enumerate(services):
            if not isinstance(service_config, dict):
                errors.append(f"nextdns.services[{idx}]: must be an object")
                continue
            errors.extend(validate_nextdns_service(service_config, idx))

            # Check for duplicate service IDs
            svc_id = service_config.get("id")
            if isinstance(svc_id, str) and svc_id.strip():
                svc_id_lower = svc_id.strip().lower()
                if svc_id_lower in seen_service_ids:
                    errors.append(f"nextdns.services[{idx}]: duplicate service id '{svc_id}'")
                else:
                    seen_service_ids.add(svc_id_lower)

    return errors


def load_nextdns_config(script_dir: str) -> Optional[dict[str, Any]]:
    """
    Load and validate NextDNS Parental Control configuration from config.json.

    Args:
        script_dir: Directory containing config.json

    Returns:
        NextDNS config dict if present and valid, None if not present

    Raises:
        ConfigurationError: If nextdns section exists but is invalid
    """
    script_path = Path(script_dir)
    config_file = script_path / "config.json"

    if not config_file.exists():
        return None

    try:
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(config, dict):
        return None

    nextdns_config: Optional[dict[str, Any]] = config.get("nextdns")
    if nextdns_config is None:
        return None

    # Validate the nextdns configuration
    errors = validate_nextdns_config(nextdns_config)
    if errors:
        for error in errors:
            logger.error(error)
        raise ConfigurationError(f"NextDNS configuration validation failed: {len(errors)} error(s)")

    return nextdns_config


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================


def _expand_categories(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Expand categories into individual domain entries for sync.

    Each domain in a category inherits the category's schedule and unblock_delay.
    The category metadata is preserved for reference.

    Args:
        categories: List of category configurations

    Returns:
        List of expanded domain configurations
    """
    expanded: list[dict[str, Any]] = []

    for category in categories:
        category_id = category.get("id", "unknown")
        category_schedule = category.get("schedule")
        category_unblock_delay = category.get("unblock_delay")
        category_description = category.get("description")
        category_domains = category.get("domains", [])

        for domain in category_domains:
            if isinstance(domain, str) and domain.strip():
                domain_entry: dict[str, Any] = {
                    "domain": domain.strip(),
                    "_category": category_id,  # Internal metadata
                }

                # Inherit category settings
                if category_schedule is not None:
                    domain_entry["schedule"] = category_schedule
                if category_unblock_delay is not None:
                    domain_entry["unblock_delay"] = category_unblock_delay
                if category_description is not None:
                    domain_entry["_category_description"] = category_description

                expanded.append(domain_entry)

    return expanded


def load_domains(script_dir: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Load domain configurations from config.json.

    Supports both blocklist and categories. Categories are expanded into
    individual domain entries that inherit the category's settings.

    Args:
        script_dir: Directory containing config.json

    Returns:
        Tuple of (denylist domains, allowlist domains)

    Raises:
        ConfigurationError: If loading or validation fails
    """
    script_path = Path(script_dir)
    config_file = script_path / "config.json"

    if not config_file.exists():
        raise ConfigurationError(
            f"Config file not found: {config_file}\n" "Run 'nextdns-blocker init' to create one."
        )

    try:
        with open(config_file, encoding="utf-8") as f:
            config = json.load(f)
        logger.info(f"Loaded domains from {config_file.name}")
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in {config_file.name}: {e}")
    except OSError as e:
        raise ConfigurationError(f"Failed to read {config_file.name}: {e}")

    # Validate structure
    if not isinstance(config, dict):
        raise ConfigurationError("Config must be a JSON object")

    # Load blocklist (can be empty if categories exist)
    blocklist = config.get("blocklist", [])
    if not isinstance(blocklist, list):
        raise ConfigurationError("'blocklist' must be an array")

    # Load categories (optional, defaults to empty)
    categories = config.get("categories", [])
    if not isinstance(categories, list):
        raise ConfigurationError("'categories' must be an array")

    # Load allowlist (optional, defaults to empty)
    allowlist = config.get("allowlist", [])
    if not isinstance(allowlist, list):
        raise ConfigurationError("'allowlist' must be an array")

    # Must have at least blocklist or categories
    if not blocklist and not categories:
        raise ConfigurationError(
            "No domains configured. Add domains to 'blocklist' or 'categories'."
        )

    # Collect all validation errors
    all_errors: list[str] = []

    # Validate each category
    for idx, category_config in enumerate(categories):
        all_errors.extend(validate_category_config(category_config, idx))

    # Validate unique category IDs
    all_errors.extend(validate_unique_category_ids(categories))

    # Validate each domain in blocklist
    for idx, domain_config in enumerate(blocklist):
        all_errors.extend(validate_domain_config(domain_config, idx))

    # Validate each domain in allowlist
    for idx, allowlist_config in enumerate(allowlist):
        all_errors.extend(validate_allowlist_config(allowlist_config, idx))

    # Validate no duplicate domains across categories and blocklist
    all_errors.extend(validate_no_duplicate_domains(categories, blocklist))

    # Validate no overlap between denylist and allowlist
    # (includes both blocklist domains and category domains)
    category_domains_as_blocklist = _expand_categories(categories)
    combined_blocklist = blocklist + category_domains_as_blocklist
    all_errors.extend(validate_no_overlap(combined_blocklist, allowlist))

    if all_errors:
        for error in all_errors:
            logger.error(error)
        raise ConfigurationError(f"Domain validation failed: {len(all_errors)} error(s)")

    # Check for subdomain relationships (warnings only, not errors)
    # This helps users understand that allowlist entries will override blocks
    check_subdomain_relationships(blocklist, allowlist)
    check_category_subdomain_relationships(categories, allowlist)

    # Expand categories into individual domain entries
    expanded_domains = _expand_categories(categories)

    # Combine blocklist with expanded category domains
    final_domains = blocklist + expanded_domains

    return final_domains, allowlist


def _load_timezone_setting(config_dir: Path) -> str:
    """
    Load timezone setting from config.json or fall back to .env/default.

    Priority:
    1. config.json settings.timezone
    2. TIMEZONE environment variable (legacy)
    3. DEFAULT_TIMEZONE constant

    Args:
        config_dir: Directory containing config files

    Returns:
        Timezone string (e.g., 'America/New_York')
    """
    # Try config.json first
    config_file = config_dir / "config.json"
    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                config_data = json.load(f)
            # Type-safe access: ensure config_data is a dict
            if not isinstance(config_data, dict):
                logger.debug("config.json root is not a dict")
            else:
                settings = config_data.get("settings")
                # Ensure settings is a dict before accessing timezone
                if isinstance(settings, dict):
                    timezone_value = settings.get("timezone")
                    if timezone_value and isinstance(timezone_value, str):
                        return str(timezone_value)
        except json.JSONDecodeError as e:
            logger.debug(f"Could not parse timezone from config.json: {e}")
        except OSError as e:
            logger.debug(f"Could not read config.json for timezone: {e}")

    # Fall back to environment variable (legacy support)
    env_tz = os.getenv("TIMEZONE")
    if env_tz:
        return env_tz

    # Default
    return DEFAULT_TIMEZONE


def _load_env_file(env_file: Path) -> None:
    """
    Load environment variables from a .env file.

    Validates each line and sets valid key-value pairs as environment variables.
    Invalid lines are logged as warnings and skipped.

    Args:
        env_file: Path to the .env file
    """
    # Pattern for valid environment variable names (POSIX-compliant)
    env_key_pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
    max_value_length = 32768  # Reasonable limit for env var values

    with open(env_file, encoding="utf-8-sig") as f:  # utf-8-sig handles BOM
        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Validate line format
            if "=" not in line:
                logger.warning(f".env line {line_num}: missing '=' separator, skipping")
                continue

            key, value = line.split("=", 1)
            key = key.strip()

            if not key:
                logger.warning(f".env line {line_num}: empty key, skipping")
                continue

            # Validate key format (POSIX-compliant env var name)
            if not env_key_pattern.match(key):
                logger.warning(f".env line {line_num}: invalid key format '{key[:20]}', skipping")
                continue

            # Parse and validate value
            try:
                parsed_value = parse_env_value(value)
            except ValueError as e:
                logger.warning(f".env line {line_num}: {e}, skipping")
                continue

            # Check for null bytes (security issue)
            if "\x00" in parsed_value:
                logger.warning(f".env line {line_num}: value contains null byte, skipping")
                continue

            # Check for excessive length
            if len(parsed_value) > max_value_length:
                logger.warning(
                    f".env line {line_num}: value too long ({len(parsed_value)} chars), skipping"
                )
                continue

            os.environ[key] = parsed_value


def _build_config_dict(config_dir: Path) -> dict[str, Any]:
    """
    Build the configuration dictionary from environment variables.

    Args:
        config_dir: Configuration directory path

    Returns:
        Configuration dictionary with raw values
    """
    return {
        "api_key": os.getenv("NEXTDNS_API_KEY"),
        "profile_id": os.getenv("NEXTDNS_PROFILE_ID"),
        "discord_webhook_url": os.getenv("DISCORD_WEBHOOK_URL"),
        "timeout": safe_int(os.getenv("API_TIMEOUT"), DEFAULT_TIMEOUT, "API_TIMEOUT"),
        "retries": safe_int(os.getenv("API_RETRIES"), DEFAULT_RETRIES, "API_RETRIES"),
        "script_dir": str(config_dir),
    }


def _validate_required_credentials(config: dict[str, Any]) -> None:
    """
    Validate required API credentials.

    Args:
        config: Configuration dictionary

    Raises:
        ConfigurationError: If credentials are missing or invalid
    """
    if not config["api_key"]:
        raise ConfigurationError("Missing NEXTDNS_API_KEY in .env or environment")

    if not validate_api_key(config["api_key"]):
        raise ConfigurationError("Invalid NEXTDNS_API_KEY format")

    if not config["profile_id"]:
        raise ConfigurationError("Missing NEXTDNS_PROFILE_ID in .env or environment")

    if not validate_profile_id(config["profile_id"]):
        raise ConfigurationError("Invalid NEXTDNS_PROFILE_ID format")


def _validate_timezone(timezone: str) -> None:
    """
    Validate timezone string.

    Args:
        timezone: Timezone string to validate

    Raises:
        ConfigurationError: If timezone is invalid
    """
    try:
        ZoneInfo(timezone)
    except KeyError as e:
        raise ConfigurationError(
            f"Invalid TIMEZONE '{timezone}'. "
            f"See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones"
        ) from e


def _validate_optional_webhook(config: dict[str, Any]) -> None:
    """
    Validate and sanitize Discord webhook URL if provided.

    Args:
        config: Configuration dictionary (modified in place)
    """
    webhook_url = config.get("discord_webhook_url")
    if webhook_url and not validate_discord_webhook(webhook_url):
        logger.warning(
            "Invalid DISCORD_WEBHOOK_URL format - notifications disabled. "
            "Expected format: https://discord.com/api/webhooks/{id}/{token}"
        )
        config["discord_webhook_url"] = None


def load_config(config_dir: Optional[Path] = None) -> dict[str, Any]:
    """
    Load configuration from .env file and environment variables.

    Args:
        config_dir: Optional directory containing .env file.
                   If None, uses the directory of this script.

    Returns:
        Configuration dictionary with all settings

    Raises:
        ConfigurationError: If required configuration is missing
    """
    if config_dir is None:
        config_dir = get_config_dir()

    # Load .env file if it exists
    env_file = config_dir / ".env"
    if env_file.exists():
        _load_env_file(env_file)

    # Build configuration dictionary
    config = _build_config_dict(config_dir)

    # Load timezone from config.json (or legacy .env)
    config["timezone"] = _load_timezone_setting(config_dir)

    # Validate all configuration
    _validate_required_credentials(config)
    _validate_timezone(config["timezone"])
    _validate_optional_webhook(config)

    return config


def get_protected_domains(domains: list[dict[str, Any]]) -> list[str]:
    """
    Extract domains that cannot be unblocked from config.

    Includes domains with protected=true (legacy) or unblock_delay="never".

    Args:
        domains: List of domain configurations

    Returns:
        List of protected domain names
    """
    return [
        d["domain"]
        for d in domains
        if d.get("protected", False) or d.get("unblock_delay") == "never"
    ]


def get_unblock_delay(domains: list[dict[str, Any]], domain: str) -> Optional[str]:
    """
    Get the unblock_delay setting for a specific domain.

    Args:
        domains: List of domain configurations
        domain: Domain name to look up

    Returns:
        unblock_delay value ('never', '24h', '4h', '30m', '0') or None if not set.
        Returns 'never' for domains with protected=true (backward compatibility).
    """
    for d in domains:
        if d.get("domain") == domain:
            # Backward compatibility: protected=true -> unblock_delay='never'
            if d.get("protected", False):
                return "never"
            return d.get("unblock_delay")
    return None
