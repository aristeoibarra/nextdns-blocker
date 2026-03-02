"""Command-line interface for NextDNS Blocker using Click."""

import json as _json
import logging
import os
import re
import signal
import sys
from pathlib import Path
from typing import Any, Optional

import rich_click as click

from . import __version__
from . import database as db
from .cli_formatter import console
from .client import NextDNSClient
from .common import (
    audit_log,
    ensure_log_dir,
    get_log_dir,
    validate_domain,
)
from .completion import complete_blocklist_domains
from .config import (
    get_config_dir,
    load_config,
    load_domains,
)
from .exceptions import (
    EXIT_CONFIG_ERROR,
    EXIT_VALIDATION_ERROR,
    ConfigurationError,
    DomainValidationError,
)
from .init import run_interactive_wizard, run_non_interactive
from .notifications import (
    EventType,
    send_notification,
)
from .pin_helpers import require_pin_verification

# Configure rich-click styling
click.rich_click.TEXT_MARKUP = "rich"
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True

# =============================================================================
# LOGGING SETUP
# =============================================================================


def get_app_log_file() -> Path:
    """Get the app log file path."""
    return get_log_dir() / "app.log"


class SecretsRedactionFilter(logging.Filter):
    """Filter that redacts sensitive information from log messages."""

    # Patterns for secrets that should be redacted
    SECRET_PATTERNS = [
        (re.compile(r"X-Api-Key:\s*[a-zA-Z0-9_-]{8,}"), "X-Api-Key: [REDACTED]"),
        (
            re.compile(r"api[_-]?key['\"]?\s*[:=]\s*['\"]?[a-zA-Z0-9_-]{8,}['\"]?", re.IGNORECASE),
            "api_key: [REDACTED]",
        ),
        (
            re.compile(r"https://discord\.com/api/webhooks/\d+/[a-zA-Z0-9_.-]+"),
            "https://discord.com/api/webhooks/[REDACTED]",
        ),
        (re.compile(r"\d+:[a-zA-Z0-9_-]{35,}"), "[TELEGRAM_TOKEN_REDACTED]"),  # Telegram bot token
        (
            re.compile(r"https://hooks\.slack\.com/services/[A-Z0-9]+/[A-Z0-9]+/[a-zA-Z0-9]+"),
            "https://hooks.slack.com/services/[REDACTED]",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Redact secrets from log record message."""
        if record.msg:
            msg = str(record.msg)
            for pattern, replacement in self.SECRET_PATTERNS:
                msg = pattern.sub(replacement, msg)
            record.msg = msg
        if record.args:
            args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in self.SECRET_PATTERNS:
                        arg = pattern.sub(replacement, arg)
                args.append(arg)
            record.args = tuple(args)
        return True


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration.

    This function configures logging with both file and console handlers.
    It avoids adding duplicate handlers if called multiple times.
    Includes a secrets redaction filter to prevent leaking sensitive data.

    Args:
        verbose: If True, sets log level to DEBUG; otherwise INFO.
    """
    ensure_log_dir()

    level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger()

    # Avoid adding duplicate handlers
    if root_logger.handlers:
        root_logger.setLevel(level)
        return

    root_logger.setLevel(level)

    if os.environ.get("LOG_FORMAT", "").lower() == "json":

        class _JsonFormatter(logging.Formatter):
            def format(self, record: logging.LogRecord) -> str:
                return _json.dumps(
                    {
                        "timestamp": self.formatTime(record),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                    }
                )

        formatter: logging.Formatter = _JsonFormatter()
    else:
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # Create secrets redaction filter
    secrets_filter = SecretsRedactionFilter()

    # File handler with secrets redaction
    file_handler = logging.FileHandler(get_app_log_file())
    file_handler.setFormatter(formatter)
    file_handler.addFilter(secrets_filter)
    root_logger.addHandler(file_handler)

    # Console handler with secrets redaction
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(secrets_filter)
    root_logger.addHandler(console_handler)


logger = logging.getLogger(__name__)


# =============================================================================
# CLICK CLI
# =============================================================================


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="nextdns-blocker")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.pass_context
def main(ctx: click.Context, no_color: bool) -> None:
    """NextDNS Blocker - Domain blocking with per-domain scheduling."""

    def _shutdown_handler(signum: int, frame: Any) -> None:
        logger.info("Received signal %s, shutting down gracefully", signum)
        db.close_connection()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown_handler)
    signal.signal(signal.SIGINT, _shutdown_handler)

    if no_color:
        console.no_color = True

    try:
        db.init_database()
        config_dir = get_config_dir()
        json_config_path = config_dir / "config.json"
        if json_config_path.exists() and not db.config_has_domains():
            try:
                db.import_config_from_json(json_config_path)
                logging.getLogger(__name__).info("Imported config from JSON file into database")
            except Exception as e:
                logging.getLogger(__name__).warning("Import from JSON config file failed: %s", e)
    except Exception as e:
        logging.getLogger(__name__).warning("Database initialization failed: %s", e)

    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())


@main.command()
@click.option(
    "--config-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Config directory (default: XDG config dir)",
)
@click.option(
    "--non-interactive", is_flag=True, help="Use environment variables instead of prompts"
)
def init(config_dir: Optional[Path], non_interactive: bool) -> None:
    """Initialize NextDNS Blocker configuration.

    Runs an interactive wizard to configure API credentials and create
    the necessary configuration files.

    Use --non-interactive for CI/CD environments (requires NEXTDNS_API_KEY
    and NEXTDNS_PROFILE_ID environment variables).
    """
    if non_interactive:
        success = run_non_interactive(config_dir)
    else:
        success = run_interactive_wizard(config_dir)

    if not success:
        sys.exit(1)


@main.command()
@click.argument("domain", shell_complete=complete_blocklist_domains)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--force", is_flag=True, help="Skip delay and unblock immediately")
def unblock(domain: str, config_dir: Optional[Path], force: bool) -> None:
    """Manually unblock a DOMAIN."""
    require_pin_verification("unblock")

    from .config import get_unblock_delay, parse_unblock_delay_seconds
    from .pending import create_pending_action, get_pending_for_domain

    try:
        config = load_config(config_dir)
        domains, _ = load_domains(config["script_dir"])

        if not validate_domain(domain):
            console.print(f"\n  [red]Error: Invalid domain format '{domain}'[/red]\n")
            sys.exit(1)

        # Get unblock_delay setting for this domain
        unblock_delay = get_unblock_delay(domains, domain)

        # Handle 'never' - cannot unblock
        if unblock_delay == "never":
            console.print(
                f"\n  [blue]Error: '{domain}' cannot be unblocked (unblock_delay: never)[/blue]\n"
            )
            sys.exit(1)

        # Check for existing pending action
        existing = get_pending_for_domain(domain)
        if existing and not force:
            execute_at = existing["execute_at"]
            console.print(
                f"\n  [yellow]Pending unblock already scheduled for '{domain}'[/yellow]"
                f"\n  Execute at: {execute_at}"
                f"\n  ID: {existing['id']}"
                f"\n  Use 'pending cancel {existing['id'][-12:]}' to cancel\n"
            )
            return

        # Handle delay (if set and not forcing)
        delay_seconds = parse_unblock_delay_seconds(unblock_delay or "0")

        if delay_seconds and delay_seconds > 0 and not force and unblock_delay:
            # Create pending action
            action = create_pending_action(domain, unblock_delay, requested_by="cli")
            if action:
                send_notification(EventType.PENDING, f"{domain} (scheduled)", config)
                execute_at = action["execute_at"]
                console.print(f"\n  [yellow]Unblock scheduled for '{domain}'[/yellow]")
                console.print(f"  Delay: {unblock_delay}")
                console.print(f"  Execute at: {execute_at}")
                console.print(f"  ID: {action['id']}")
                console.print("\n  Use 'pending list' to view or 'pending cancel' to abort\n")
            else:
                console.print("\n  [red]Error: Failed to schedule unblock[/red]\n")
                sys.exit(1)
            return

        # Immediate unblock (no delay, delay=0, or --force)
        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )

        success, was_removed = client.unblock(domain)
        if success:
            if was_removed:
                audit_log("UNBLOCK", domain)
                send_notification(EventType.UNBLOCK, domain, config)
                console.print(f"\n  [green]Unblocked: {domain}[/green]\n")
            else:
                console.print(f"\n  [yellow]Domain not in denylist: {domain}[/yellow]\n")
        else:
            console.print(f"\n  [red]Error: Failed to unblock '{domain}'[/red]\n")
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n")
        sys.exit(EXIT_CONFIG_ERROR)
    except DomainValidationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(EXIT_VALIDATION_ERROR)


if __name__ == "__main__":
    main()
