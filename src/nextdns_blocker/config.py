"""Configuration loading and validation for NextDNS Blocker."""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

# Timezone support: use zoneinfo (Python 3.9+)
from zoneinfo import ZoneInfo

from .common import (
    LOG_DIR,
    VALID_DAYS,
    parse_env_value,
    safe_int,
    validate_domain,
    validate_time_format,
    validate_url,
)
from .exceptions import ConfigurationError


# =============================================================================
# CONSTANTS
# =============================================================================

DEFAULT_TIMEOUT = 10
DEFAULT_RETRIES = 3
DEFAULT_TIMEZONE = "UTC"
DEFAULT_PAUSE_MINUTES = 30

logger = logging.getLogger(__name__)


# =============================================================================
# DOMAIN CONFIG VALIDATION
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


def validate_allowlist_config(config: Dict[str, Any], index: int) -> List[str]:
    """
    Validate a single allowlist configuration entry.

    Args:
        config: Allowlist configuration dictionary
        index: Index in the allowlist array (for error messages)

    Returns:
        List of error messages (empty if valid)
    """
    errors: List[str] = []

    # Check domain field exists and is valid
    if 'domain' not in config:
        return [f"allowlist #{index}: Missing 'domain' field"]

    domain = config['domain']
    if not domain or not isinstance(domain, str) or not domain.strip():
        return [f"allowlist #{index}: Empty or invalid domain"]

    domain = domain.strip()
    if not validate_domain(domain):
        return [f"allowlist #{index}: Invalid domain format '{domain}'"]

    # Allowlist should NOT have schedule (it's always 24/7)
    if 'schedule' in config and config['schedule'] is not None:
        errors.append(
            f"allowlist '{domain}': 'schedule' field not allowed "
            f"(allowlist is always 24/7)"
        )

    return errors


def validate_no_overlap(
    domains: List[Dict[str, Any]],
    allowlist: List[Dict[str, Any]]
) -> List[str]:
    """
    Validate that no domain appears in both denylist and allowlist.

    Args:
        domains: List of denylist domain configurations
        allowlist: List of allowlist domain configurations

    Returns:
        List of error messages (empty if no conflicts)
    """
    errors: List[str] = []

    denylist_domains = {
        d['domain'].strip().lower()
        for d in domains
        if 'domain' in d and isinstance(d['domain'], str)
    }
    allowlist_domains = {
        a['domain'].strip().lower()
        for a in allowlist
        if 'domain' in a and isinstance(a['domain'], str)
    }

    overlap = denylist_domains & allowlist_domains

    for domain in sorted(overlap):
        errors.append(
            f"Domain '{domain}' appears in both 'domains' (denylist) and 'allowlist'. "
            f"A domain cannot be blocked and allowed simultaneously."
        )

    return errors


# =============================================================================
# CONFIGURATION LOADING
# =============================================================================

def load_domains(
    script_dir: str,
    domains_url: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Load domain configurations from URL or local file.

    Args:
        script_dir: Directory containing the script (for local domains.json)
        domains_url: Optional URL to fetch domains from

    Returns:
        Tuple of (denylist domains, allowlist domains)

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

    # Load allowlist (optional, defaults to empty)
    allowlist = config.get('allowlist', [])

    # Validate each domain in denylist
    all_errors: List[str] = []
    for idx, domain_config in enumerate(domains):
        all_errors.extend(validate_domain_config(domain_config, idx))

    # Validate each domain in allowlist
    for idx, allowlist_config in enumerate(allowlist):
        all_errors.extend(validate_allowlist_config(allowlist_config, idx))

    # Validate no overlap between denylist and allowlist
    all_errors.extend(validate_no_overlap(domains, allowlist))

    if all_errors:
        for error in all_errors:
            logger.error(error)
        raise ConfigurationError(f"Domain validation failed: {len(all_errors)} error(s)")

    return domains, allowlist


def load_config(config_dir: Optional[Path] = None) -> Dict[str, Any]:
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
        # Default to looking in current working directory first,
        # then fall back to package directory
        cwd = Path.cwd()
        if (cwd / '.env').exists():
            config_dir = cwd
        else:
            config_dir = Path(__file__).parent.parent.parent.absolute()

    env_file = config_dir / '.env'

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
        'script_dir': str(config_dir)
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


def get_protected_domains(domains: List[Dict[str, Any]]) -> List[str]:
    """
    Extract domains marked as protected from config.

    Args:
        domains: List of domain configurations

    Returns:
        List of protected domain names
    """
    return [d['domain'] for d in domains if d.get('protected', False)]
