"""Shared CLI helpers to reduce code duplication across CLI modules."""

import json
import logging
import sys
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, NoReturn, Optional

import requests
from rich.console import Console

from .cli_formatter import CLIOutput as out
from .client import NextDNSClient
from .config import load_config
from .exceptions import EXIT_API_ERROR, EXIT_CONFIG_ERROR, EXIT_VALIDATION_ERROR, ConfigurationError

logger = logging.getLogger(__name__)

console = Console(highlight=False)


def handle_error(e: Exception, context: str = "") -> NoReturn:
    """Handle errors with specific messages based on exception type.

    Args:
        e: The exception to handle
        context: Optional context string (e.g., "fetching denylist")
    """
    prefix = f"{context}: " if context else ""

    exit_code = 1
    if isinstance(e, requests.exceptions.Timeout):
        out.error(f"{prefix}API timeout - please try again")
        exit_code = EXIT_API_ERROR
    elif isinstance(e, requests.exceptions.ConnectionError):
        out.error(f"{prefix}Connection failed - check your network")
        exit_code = EXIT_API_ERROR
    elif isinstance(e, requests.exceptions.HTTPError):
        out.error(f"{prefix}API error - {e}")
        exit_code = EXIT_API_ERROR
    elif isinstance(e, ConfigurationError):
        out.error(f"{prefix}Config error - {e}")
        exit_code = EXIT_CONFIG_ERROR
    elif isinstance(e, PermissionError):
        out.error(f"{prefix}Permission denied - {getattr(e, 'filename', 'unknown')}")
    elif isinstance(e, FileNotFoundError):
        out.error(f"{prefix}File not found - {getattr(e, 'filename', 'unknown')}")
    elif isinstance(e, json.JSONDecodeError):
        out.error(f"{prefix}Invalid JSON format - {e.msg}")
        exit_code = EXIT_CONFIG_ERROR
    elif isinstance(e, ValueError):
        out.error(f"{prefix}Invalid value - {e}")
        exit_code = EXIT_VALIDATION_ERROR
    else:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        out.error(f"{prefix}{e}")

    sys.exit(exit_code)


def get_client(config_dir: Optional[Path] = None) -> NextDNSClient:
    """Create a NextDNS client from config.

    Args:
        config_dir: Optional config directory path

    Returns:
        Configured NextDNSClient instance

    Raises:
        ConfigurationError: If config cannot be loaded
    """
    config = load_config(config_dir)
    return NextDNSClient(config["api_key"], config["profile_id"])


def get_client_and_config(
    config_dir: Optional[Path] = None,
) -> tuple[NextDNSClient, dict[str, Any]]:
    """Create a NextDNS client and return the config.

    Useful when you need both the client and config (e.g., for notifications).

    Args:
        config_dir: Optional config directory path

    Returns:
        Tuple of (NextDNSClient, config dict)

    Raises:
        ConfigurationError: If config cannot be loaded
    """
    config = load_config(config_dir)
    client = NextDNSClient(config["api_key"], config["profile_id"])
    return client, config


@contextmanager
def command_context(
    config_dir: Optional[Path] = None,
    error_context: str = "",
) -> Generator[tuple[NextDNSClient, dict[str, Any]], None, None]:
    """Context manager for CLI commands that need a client.

    Handles common error patterns for API commands:
    - Config loading errors
    - API request errors
    - File errors
    - Unexpected errors

    Args:
        config_dir: Optional config directory path
        error_context: Optional context string for error messages

    Yields:
        Tuple of (NextDNSClient, config dict)

    Example:
        with command_context(config_dir) as (client, config):
            domains = client.get_denylist()
            # ... process domains
    """
    try:
        client, config = get_client_and_config(config_dir)
        yield client, config
    except (
        requests.exceptions.RequestException,
        ConfigurationError,
        PermissionError,
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ) as e:
        handle_error(e, error_context)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        prefix = f"{error_context}: " if error_context else ""
        console.print(f"\n  [red]{prefix}Unexpected error: {e}[/red]\n")
        sys.exit(1)


@contextmanager
def config_context(
    config_dir: Optional[Path] = None,
    error_context: str = "",
) -> Generator[dict[str, Any], None, None]:
    """Context manager for CLI commands that only need config.

    Lighter weight than command_context when you don't need an API client.

    Args:
        config_dir: Optional config directory path
        error_context: Optional context string for error messages

    Yields:
        Config dict

    Example:
        with config_context(config_dir) as config:
            # ... use config
    """
    try:
        config = load_config(config_dir)
        yield config
    except (
        ConfigurationError,
        PermissionError,
        FileNotFoundError,
        json.JSONDecodeError,
        ValueError,
    ) as e:
        handle_error(e, error_context)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        prefix = f"{error_context}: " if error_context else ""
        console.print(f"\n  [red]{prefix}Unexpected error: {e}[/red]\n")
        sys.exit(1)
