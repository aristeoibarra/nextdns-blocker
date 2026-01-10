"""Command-line interface for NextDNS Blocker using Click."""

import logging
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console

from . import __version__
from .analytics_cli import register_stats
from .client import NextDNSClient
from .common import (
    audit_log,
    ensure_log_dir,
    ensure_naive_datetime,
    get_log_dir,
    read_secure_file,
    validate_domain,
    write_secure_file,
)
from .completion import (
    complete_allowlist_domains,
    complete_blocklist_domains,
    detect_shell,
    get_completion_script,
    install_completion,
    is_completion_installed,
)
from .config import (
    DEFAULT_PAUSE_MINUTES,
    _expand_categories,
    get_config_dir,
    load_config,
    load_domains,
    load_nextdns_config,
    validate_allowlist_config,
    validate_domain_config,
    validate_no_overlap,
)
from .config_cli import register_config
from .exceptions import ConfigurationError, DomainValidationError
from .init import run_interactive_wizard, run_non_interactive
from .nextdns_cli import register_nextdns
from .notifications import (
    EventType,
    NotificationManager,
    get_notification_manager,
    send_notification,
)
from .platform_utils import get_executable_path, is_macos, is_windows
from .protection_cli import register_protection
from .scheduler import ScheduleEvaluator
from .watchdog import (
    LAUNCHD_SYNC_LABEL,
    LAUNCHD_WATCHDOG_LABEL,
    WINDOWS_TASK_SYNC_NAME,
    WINDOWS_TASK_WATCHDOG_NAME,
    get_crontab,
    has_windows_task,
    is_launchd_job_loaded,
)

# =============================================================================
# LOGGING SETUP
# =============================================================================


def get_app_log_file() -> Path:
    """Get the app log file path."""
    return get_log_dir() / "app.log"


def get_pause_file() -> Path:
    """Get the pause state file path."""
    return get_log_dir() / ".paused"


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration.

    This function configures logging with both file and console handlers.
    It avoids adding duplicate handlers if called multiple times.

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
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    # File handler
    file_handler = logging.FileHandler(get_app_log_file())
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


logger = logging.getLogger(__name__)
console = Console(highlight=False)


# =============================================================================
# PIN VERIFICATION HELPER
# =============================================================================


def require_pin_verification(command_name: str) -> bool:
    """
    Check if PIN verification is required and prompt if needed.

    This function should be called at the start of dangerous commands.
    It will prompt for PIN if enabled and no valid session exists.

    Args:
        command_name: Name of the command being executed

    Returns:
        True if command can proceed, False if blocked

    Raises:
        SystemExit: If PIN verification fails
    """
    from .protection import (
        PIN_MAX_ATTEMPTS,
        get_failed_attempts_count,
        get_lockout_remaining,
        is_pin_enabled,
        is_pin_locked_out,
        is_pin_session_valid,
        verify_pin,
    )

    # No PIN protection = proceed
    if not is_pin_enabled():
        return True

    # Valid session = proceed
    if is_pin_session_valid():
        return True

    # Check lockout
    if is_pin_locked_out():
        remaining = get_lockout_remaining()
        console.print(
            f"\n  [red]PIN locked out due to failed attempts. Try again in {remaining}[/red]\n"
        )
        sys.exit(1)

    # Prompt for PIN
    console.print(f"\n  [yellow]PIN required for '{command_name}'[/yellow]")

    import click

    pin = click.prompt("  Enter PIN", hide_input=True, default="", show_default=False)

    if not pin:
        console.print("\n  [red]PIN verification cancelled[/red]\n")
        sys.exit(1)

    if verify_pin(pin):
        return True
    else:
        if is_pin_locked_out():
            remaining = get_lockout_remaining()
            console.print(f"\n  [red]Too many failed attempts. Locked out for {remaining}[/red]\n")
        else:
            attempts_left = PIN_MAX_ATTEMPTS - get_failed_attempts_count()
            console.print(f"\n  [red]Incorrect PIN. {attempts_left} attempts remaining.[/red]\n")
        sys.exit(1)


# =============================================================================
# CONSTANTS
# =============================================================================

# Port validation constants
MIN_PORT = 1
MAX_PORT = 65535

# PyPI API URL for update checking
PYPI_PACKAGE_URL = "https://pypi.org/pypi/nextdns-blocker/json"


# =============================================================================
# PAUSE MANAGEMENT
# =============================================================================


def _get_pause_info() -> tuple[bool, Optional[datetime]]:
    """
    Get pause state information.

    Returns:
        Tuple of (is_paused, pause_until_datetime).
        If not paused or error, returns (False, None).

    Note:
        Uses missing_ok=True for unlink to handle race conditions where
        another process may have already cleaned up the file.
    """
    pause_file = get_pause_file()
    content = read_secure_file(pause_file)
    if not content:
        return False, None

    try:
        pause_until = ensure_naive_datetime(datetime.fromisoformat(content))
        if datetime.now() < pause_until:
            return True, pause_until
        # Expired, clean up
        pause_file.unlink(missing_ok=True)
        return False, None
    except ValueError:
        # Invalid content, clean up
        logger.warning(f"Invalid pause file content, removing: {content[:50]}")
        pause_file.unlink(missing_ok=True)
        return False, None


def is_paused() -> bool:
    """Check if blocking is currently paused."""
    paused, _ = _get_pause_info()
    return paused


def get_pause_remaining() -> Optional[str]:
    """
    Get remaining pause time as human-readable string.

    Returns:
        Human-readable remaining time, or None if not paused.
    """
    paused, pause_until = _get_pause_info()
    if not paused or pause_until is None:
        return None

    remaining = pause_until - datetime.now()
    mins = int(remaining.total_seconds() // 60)
    return f"{mins} min" if mins > 0 else "< 1 min"


def set_pause(minutes: int) -> datetime:
    """Set pause for specified minutes. Returns the pause end time."""
    pause_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
    write_secure_file(get_pause_file(), pause_until.isoformat())
    audit_log("PAUSE", f"{minutes} minutes until {pause_until.isoformat()}")
    return pause_until


def clear_pause() -> bool:
    """Clear pause state. Returns True if was paused."""
    pause_file = get_pause_file()
    if pause_file.exists():
        pause_file.unlink(missing_ok=True)
        audit_log("RESUME", "Manual resume")
        return True
    return False


# =============================================================================
# CLICK CLI
# =============================================================================


class PanicAwareGroup(click.Group):
    """Click Group that hides dangerous commands during panic mode."""

    def get_command(self, ctx: click.Context, cmd_name: str) -> Optional[click.Command]:
        """Get a command, returning None if hidden during panic mode."""
        from .panic import DANGEROUS_COMMANDS, is_panic_mode

        cmd = super().get_command(ctx, cmd_name)
        if cmd is None:
            return None

        # Check if this top-level command should be hidden
        if is_panic_mode() and cmd_name in DANGEROUS_COMMANDS:
            return None  # Returns "No such command" error

        return cmd

    def list_commands(self, ctx: click.Context) -> list[str]:
        """List commands, excluding hidden ones during panic mode."""
        from .panic import DANGEROUS_COMMANDS, is_panic_mode

        commands = list(super().list_commands(ctx))
        if is_panic_mode():
            commands = [c for c in commands if c not in DANGEROUS_COMMANDS]
        return commands


@click.group(cls=PanicAwareGroup, invoke_without_command=True)
@click.version_option(version=__version__, prog_name="nextdns-blocker")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.pass_context
def main(ctx: click.Context, no_color: bool) -> None:
    """NextDNS Blocker - Domain blocking with per-domain scheduling."""
    from .panic import get_panic_remaining, is_panic_mode

    if no_color:
        console.no_color = True

    # Show panic mode banner if active
    if is_panic_mode():
        remaining = get_panic_remaining()
        console.print(f"\n  [red bold]PANIC MODE ACTIVE ({remaining} remaining)[/red bold]\n")

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
@click.argument("minutes", default=DEFAULT_PAUSE_MINUTES, type=click.IntRange(min=1))
def pause(minutes: int) -> None:
    """Pause blocking for MINUTES (default: 30)."""
    require_pin_verification("pause")

    set_pause(minutes)
    pause_until = datetime.now() + timedelta(minutes=minutes)
    console.print(f"\n  [yellow]Blocking paused for {minutes} minutes[/yellow]")
    console.print(f"  Resumes at: [bold]{pause_until.strftime('%H:%M')}[/bold]\n")


@main.command()
def resume() -> None:
    """Resume blocking immediately."""
    if clear_pause():
        console.print("\n  [green]Blocking resumed[/green]\n")
    else:
        console.print("\n  [yellow]Not currently paused[/yellow]\n")


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
            console.print(
                f"\n  [red]Error: Invalid domain format '{domain}'[/red]\n", highlight=False
            )
            sys.exit(1)

        # Get unblock_delay setting for this domain
        unblock_delay = get_unblock_delay(domains, domain)

        # Handle 'never' - cannot unblock
        if unblock_delay == "never":
            console.print(
                f"\n  [blue]Error: '{domain}' cannot be unblocked (unblock_delay: never)[/blue]\n",
                highlight=False,
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

        if client.unblock(domain):
            audit_log("UNBLOCK", domain)
            send_notification(EventType.UNBLOCK, domain, config)
            console.print(f"\n  [green]Unblocked: {domain}[/green]\n")
        else:
            console.print(f"\n  [red]Error: Failed to unblock '{domain}'[/red]\n", highlight=False)
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except DomainValidationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n", highlight=False)
        sys.exit(1)


# =============================================================================
# SYNC HELPER FUNCTIONS
# =============================================================================


def _sync_denylist(
    domains: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    panic_active: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize denylist domains based on schedules.

    Args:
        domains: List of domain configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        panic_active: If True, skip unblocks
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (blocked_count, unblocked_count)
    """
    blocked_count = 0
    unblocked_count = 0

    for domain_config in domains:
        domain = domain_config["domain"]
        should_block = evaluator.should_block_domain(domain_config)
        is_blocked = client.is_blocked(domain)

        if should_block and not is_blocked:
            # Domain should be blocked but isn't
            if dry_run:
                console.print(f"  [yellow]Would BLOCK: {domain}[/yellow]")
            else:
                if client.block(domain):
                    audit_log("BLOCK", domain)
                    nm.queue(EventType.BLOCK, domain)
                    blocked_count += 1

        elif not should_block and is_blocked:
            # Domain should be unblocked
            unblocked = _handle_unblock(
                domain, domain_config, domains, client, config, dry_run, verbose, panic_active, nm
            )
            if unblocked:
                unblocked_count += 1

    return blocked_count, unblocked_count


def _handle_unblock(
    domain: str,
    domain_config: dict[str, Any],
    domains: list[dict[str, Any]],
    client: "NextDNSClient",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    panic_active: bool,
    nm: "NotificationManager",
) -> bool:
    """
    Handle unblocking a domain with delay logic.

    Args:
        domain: Domain name to unblock
        domain_config: Domain configuration dict
        domains: All domain configurations (for delay lookup)
        client: NextDNS API client
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        panic_active: If True, skip unblocks
        nm: NotificationManager for queuing notifications

    Returns:
        True if domain was unblocked immediately, False otherwise
    """
    from .config import get_unblock_delay, parse_unblock_delay_seconds
    from .pending import create_pending_action, get_pending_for_domain

    # Skip unblocks during panic mode
    if panic_active:
        if verbose:
            console.print(f"  [red]Skipping unblock (panic mode): {domain}[/red]")
        return False

    # Check unblock_delay for this domain
    domain_delay = get_unblock_delay(domains, domain)

    # Handle 'never' - cannot unblock
    if domain_delay == "never":
        if verbose:
            console.print(f"  [blue]Cannot unblock (never): {domain}[/blue]")
        return False

    delay_seconds = parse_unblock_delay_seconds(domain_delay or "0")

    # Handle delayed unblock
    if delay_seconds and delay_seconds > 0 and domain_delay is not None:
        existing = get_pending_for_domain(domain)
        if existing:
            if verbose:
                console.print(f"  [yellow]Already pending: {domain}[/yellow]")
            return False

        if dry_run:
            console.print(
                f"  [yellow]Would schedule UNBLOCK: {domain} (delay: {domain_delay})[/yellow]"
            )
        else:
            action = create_pending_action(domain, domain_delay, requested_by="sync")
            if action and verbose:
                console.print(f"  [yellow]Scheduled unblock: {domain} ({domain_delay})[/yellow]")
        return False

    # Immediate unblock (no delay)
    if dry_run:
        console.print(f"  [green]Would UNBLOCK: {domain}[/green]")
        return False
    else:
        if client.unblock(domain):
            audit_log("UNBLOCK", domain)
            nm.queue(EventType.UNBLOCK, domain)
            return True
    return False


def _sync_allowlist(
    allowlist: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    panic_active: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize allowlist domains based on schedules.

    During panic mode, ALL allowlist operations are skipped to prevent
    scheduled allowlist entries from creating security holes. The allowlist
    has highest priority in NextDNS and would bypass all blocks.

    Args:
        allowlist: List of allowlist configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration (for webhook URL)
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        panic_active: If True, skip all allowlist operations
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (allowed_count, disallowed_count)
    """
    # During panic mode, skip ALL allowlist operations
    # This prevents scheduled allowlist entries from creating security holes
    # (allowlist has highest priority in NextDNS and would bypass all blocks)
    if panic_active:
        if verbose:
            console.print("  [red]Skipping allowlist sync (panic mode active)[/red]")
        return 0, 0

    allowed_count = 0
    disallowed_count = 0

    for allowlist_config in allowlist:
        domain = allowlist_config["domain"]
        should_allow = evaluator.should_allow_domain(allowlist_config)
        is_allowed = client.is_allowed(domain)

        if should_allow and not is_allowed:
            # Should be in allowlist but isn't - add it
            if dry_run:
                console.print(f"  [green]Would ADD to allowlist: {domain}[/green]")
            else:
                if client.allow(domain):
                    audit_log("ALLOW", domain)
                    nm.queue(EventType.ALLOW, domain)
                    allowed_count += 1

        elif not should_allow and is_allowed:
            # Should NOT be in allowlist but is - remove it
            if dry_run:
                console.print(f"  [yellow]Would REMOVE from allowlist: {domain}[/yellow]")
            else:
                if client.disallow(domain):
                    audit_log("DISALLOW", domain)
                    nm.queue(EventType.DISALLOW, domain)
                    disallowed_count += 1

    return allowed_count, disallowed_count


def _sync_nextdns_categories(
    categories: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    panic_active: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize NextDNS Parental Control categories based on schedules.

    When schedule says "available" (should_block=False) → deactivate category
    When schedule says "blocked" (should_block=True) → activate category

    Args:
        categories: List of NextDNS category configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        panic_active: If True, skip deactivations (maintain blocks)
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (activated_count, deactivated_count)
    """
    activated_count = 0
    deactivated_count = 0

    for category_config in categories:
        category_id = category_config["id"]
        should_block = evaluator.should_block(category_config.get("schedule"))
        is_active = client.is_category_active(category_id)

        # Handle API errors
        if is_active is None:
            if verbose:
                console.print(f"  [red]Failed to check category status: {category_id}[/red]")
            continue

        if should_block and not is_active:
            # Should be blocking but isn't - activate
            if dry_run:
                console.print(f"  [red]Would ACTIVATE category: {category_id}[/red]")
            else:
                if client.activate_category(category_id):
                    audit_log("PC_ACTIVATE", f"category:{category_id}")
                    nm.queue(EventType.PC_ACTIVATE, f"category:{category_id}")
                    activated_count += 1

        elif not should_block and is_active:
            # Should be available but is blocking - deactivate
            if panic_active:
                if verbose:
                    console.print(f"  [red]Skipping deactivation (panic mode): {category_id}[/red]")
                continue

            if dry_run:
                console.print(f"  [green]Would DEACTIVATE category: {category_id}[/green]")
            else:
                if client.deactivate_category(category_id):
                    audit_log("PC_DEACTIVATE", f"category:{category_id}")
                    nm.queue(EventType.PC_DEACTIVATE, f"category:{category_id}")
                    deactivated_count += 1

    return activated_count, deactivated_count


def _sync_nextdns_services(
    services: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    panic_active: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize NextDNS Parental Control services based on schedules.

    When schedule says "available" (should_block=False) → deactivate service
    When schedule says "blocked" (should_block=True) → activate service

    Args:
        services: List of NextDNS service configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        panic_active: If True, skip deactivations (maintain blocks)
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (activated_count, deactivated_count)
    """
    activated_count = 0
    deactivated_count = 0

    for service_config in services:
        service_id = service_config["id"]
        should_block = evaluator.should_block(service_config.get("schedule"))
        is_active = client.is_service_active(service_id)

        # Handle API errors
        if is_active is None:
            if verbose:
                console.print(f"  [red]Failed to check service status: {service_id}[/red]")
            continue

        if should_block and not is_active:
            # Should be blocking but isn't - activate
            if dry_run:
                console.print(f"  [red]Would ACTIVATE service: {service_id}[/red]")
            else:
                if client.activate_service(service_id):
                    audit_log("PC_ACTIVATE", f"service:{service_id}")
                    nm.queue(EventType.PC_ACTIVATE, f"service:{service_id}")
                    activated_count += 1

        elif not should_block and is_active:
            # Should be available but is blocking - deactivate
            if panic_active:
                if verbose:
                    console.print(f"  [red]Skipping deactivation (panic mode): {service_id}[/red]")
                continue

            if dry_run:
                console.print(f"  [green]Would DEACTIVATE service: {service_id}[/green]")
            else:
                if client.deactivate_service(service_id):
                    audit_log("PC_DEACTIVATE", f"service:{service_id}")
                    nm.queue(EventType.PC_DEACTIVATE, f"service:{service_id}")
                    deactivated_count += 1

    return activated_count, deactivated_count


def _sync_nextdns_parental_control(
    nextdns_config: dict[str, Any],
    client: "NextDNSClient",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
) -> bool:
    """
    Sync NextDNS Parental Control global settings.

    Args:
        nextdns_config: The 'nextdns' section from config.json
        client: NextDNS API client
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output

    Returns:
        True if sync was successful
    """
    parental_control = nextdns_config.get("parental_control")
    if not parental_control:
        return True

    safe_search = parental_control.get("safe_search")
    youtube_restricted = parental_control.get("youtube_restricted_mode")
    block_bypass = parental_control.get("block_bypass")

    # Get current state from NextDNS to compare
    current = client.get_parental_control()
    if current is None:
        logger.warning("Could not fetch current parental control state")
        return False

    # Build list of settings that need to change
    changes: list[str] = []
    if safe_search is not None and current.get("safeSearch") != safe_search:
        changes.append(f"safe_search={safe_search}")
    if (
        youtube_restricted is not None
        and current.get("youtubeRestrictedMode") != youtube_restricted
    ):
        changes.append(f"youtube_restricted_mode={youtube_restricted}")
    if block_bypass is not None and current.get("blockBypass") != block_bypass:
        changes.append(f"block_bypass={block_bypass}")

    if not changes:
        logger.debug("Parental control settings already in sync")
        return True

    if dry_run:
        console.print(f"  [yellow]Would UPDATE parental control: {', '.join(changes)}[/yellow]")
        return True

    if client.update_parental_control(
        safe_search=safe_search,
        youtube_restricted_mode=youtube_restricted,
        block_bypass=block_bypass,
    ):
        if verbose:
            console.print("  [green]Updated parental control settings[/green]")
        return True

    console.print("  [red]Failed to update parental control settings[/red]")
    return False


def _print_sync_summary(
    blocked_count: int,
    unblocked_count: int,
    allowed_count: int,
    disallowed_count: int,
    verbose: bool,
    pc_activated: int = 0,
    pc_deactivated: int = 0,
) -> None:
    """Print sync operation summary."""
    has_changes = (
        blocked_count
        or unblocked_count
        or allowed_count
        or disallowed_count
        or pc_activated
        or pc_deactivated
    )
    if has_changes:
        parts = []
        if blocked_count or unblocked_count:
            parts.append(
                f"[red]{blocked_count} blocked[/red], [green]{unblocked_count} unblocked[/green]"
            )
        if allowed_count or disallowed_count:
            parts.append(
                f"[green]{allowed_count} allowed[/green], [yellow]{disallowed_count} disallowed[/yellow]"
            )
        if pc_activated or pc_deactivated:
            parts.append(
                f"[magenta]{pc_activated} PC activated[/magenta], [cyan]{pc_deactivated} PC deactivated[/cyan]"
            )
        console.print(f"  Sync: {', '.join(parts)}")
    elif verbose:
        console.print("  Sync: [green]No changes needed[/green]")


def sync_impl(
    dry_run: bool,
    verbose: bool,
    config_dir: Optional[Path],
) -> None:
    """
    Synchronize domain blocking with schedules.

    This is the implementation function called by config_cli.py.
    """
    setup_logging(verbose)

    # Check pause state
    if is_paused():
        remaining = get_pause_remaining()
        click.echo(f"  Paused ({remaining} remaining), skipping sync")
        return

    # Check panic mode - blocks continue, unblocks and allowlist changes skipped
    from .panic import is_panic_mode

    panic_active = is_panic_mode()

    # Check auto-panic schedule
    import json as json_mod

    from .protection import is_auto_panic_time

    try:
        config_for_autopanic = load_config(config_dir)
        config_path = Path(config_for_autopanic["script_dir"]) / "config.json"
        with open(config_path, encoding="utf-8") as f:
            full_config = json_mod.load(f)

        if is_auto_panic_time(full_config) and not panic_active:
            # Auto-panic is active but panic mode isn't - treat as panic
            panic_active = True
            if verbose:
                console.print("  [red]Auto-panic active (scheduled)[/red]")
    except (OSError, json_mod.JSONDecodeError, ConfigurationError):
        pass  # If we can't read config, continue without auto-panic

    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])

        # Load NextDNS Parental Control config (optional)
        nextdns_config = load_nextdns_config(config["script_dir"])

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        if dry_run:
            console.print("\n  [yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        # =========================================================================
        # SYNC ORDER: Denylist first, then Allowlist, then Parental Control
        #
        # This order matters because NextDNS processes allowlist with higher
        # priority. By syncing denylist first, we ensure blocks are applied
        # before exceptions. The allowlist sync then adds/removes exceptions.
        #
        # Priority in NextDNS (highest to lowest):
        # 1. Allowlist (always wins - bypasses everything)
        # 2. Denylist (your custom blocks)
        # 3. Third-party blocklists (OISD, HaGeZi, etc.)
        # 4. Security features (Threat Intelligence, NRDs, etc.)
        # 5. Parental Control (categories and services)
        #
        # During panic mode:
        # - Denylist: blocks continue, unblocks skipped
        # - Allowlist: completely skipped (prevents security holes)
        # - Parental Control: activations continue, deactivations skipped
        # =========================================================================

        # Use NotificationManager context for batched notifications
        nm = get_notification_manager()
        with nm.sync_context(config["profile_id"], config):
            # Sync denylist domains
            blocked_count, unblocked_count = _sync_denylist(
                domains, client, evaluator, config, dry_run, verbose, panic_active, nm
            )

            # Sync allowlist (schedule-aware, panic-aware)
            allowed_count, disallowed_count = _sync_allowlist(
                allowlist, client, evaluator, config, dry_run, verbose, panic_active, nm
            )

            # Sync NextDNS Parental Control (if configured)
            pc_activated = 0
            pc_deactivated = 0
            if nextdns_config:
                # Sync global parental control settings
                _sync_nextdns_parental_control(nextdns_config, client, config, dry_run, verbose)

                # Sync categories
                nextdns_categories = nextdns_config.get("categories", [])
                if nextdns_categories:
                    cat_activated, cat_deactivated = _sync_nextdns_categories(
                        nextdns_categories,
                        client,
                        evaluator,
                        config,
                        dry_run,
                        verbose,
                        panic_active,
                        nm,
                    )
                    pc_activated += cat_activated
                    pc_deactivated += cat_deactivated

                # Sync services
                nextdns_services = nextdns_config.get("services", [])
                if nextdns_services:
                    svc_activated, svc_deactivated = _sync_nextdns_services(
                        nextdns_services,
                        client,
                        evaluator,
                        config,
                        dry_run,
                        verbose,
                        panic_active,
                        nm,
                    )
                    pc_activated += svc_activated
                    pc_deactivated += svc_deactivated

            # Print summary
            if not dry_run:
                _print_sync_summary(
                    blocked_count,
                    unblocked_count,
                    allowed_count,
                    disallowed_count,
                    verbose,
                    pc_activated,
                    pc_deactivated,
                )

    except ConfigurationError as e:
        console.print(f"  [red]Config error: {e}[/red]", highlight=False)
        sys.exit(1)


@main.command()
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option(
    "--no-update-check",
    is_flag=True,
    help="Skip checking for updates",
)
@click.option(
    "--list",
    "show_list",
    is_flag=True,
    help="Show detailed list of all domains",
)
def status(config_dir: Optional[Path], no_update_check: bool, show_list: bool) -> None:
    """Show current blocking status."""
    from .update_check import check_for_update

    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        # Collect domain statistics
        blocked_count = 0
        allowed_count = 0
        mismatches: list[dict[str, Any]] = []
        protected_domains: list[str] = []

        for domain_config in domains:
            domain = domain_config["domain"]
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)

            if is_blocked:
                blocked_count += 1
            else:
                allowed_count += 1

            # Check for protected domains (unblock_delay="never")
            domain_delay = domain_config.get("unblock_delay")
            if domain_delay == "never":
                protected_domains.append(domain)

            # Check for mismatches
            if should_block != is_blocked:
                expected = "blocked" if should_block else "allowed"
                current = "blocked" if is_blocked else "allowed"
                mismatches.append(
                    {
                        "domain": domain,
                        "expected": expected,
                        "current": current,
                        "type": "denylist",
                    }
                )

        # Collect allowlist statistics
        allowlist_always_active = 0  # No schedule, always in allowlist
        allowlist_scheduled_active = 0  # Has schedule, currently active
        allowlist_scheduled_inactive = 0  # Has schedule, currently inactive
        for item in allowlist:
            domain = item["domain"]
            is_allowed = client.is_allowed(domain)
            has_schedule = item.get("schedule") is not None
            should_allow = evaluator.should_allow_domain(item)

            if has_schedule:
                if should_allow:
                    allowlist_scheduled_active += 1
                else:
                    allowlist_scheduled_inactive += 1
            else:
                allowlist_always_active += 1

            # Check for mismatches in scheduled allowlist
            if has_schedule and should_allow != is_allowed:
                expected = "allowed" if should_allow else "not allowed"
                current = "allowed" if is_allowed else "not allowed"
                mismatches.append(
                    {
                        "domain": domain,
                        "expected": expected,
                        "current": current,
                        "type": "allowlist",
                    }
                )

        # Check scheduler status
        scheduler_ok = False
        if is_macos():
            sync_ok = is_launchd_job_loaded(LAUNCHD_SYNC_LABEL)
            wd_ok = is_launchd_job_loaded(LAUNCHD_WATCHDOG_LABEL)
            scheduler_ok = sync_ok and wd_ok
        elif is_windows():
            sync_ok = has_windows_task(WINDOWS_TASK_SYNC_NAME)
            wd_ok = has_windows_task(WINDOWS_TASK_WATCHDOG_NAME)
            scheduler_ok = sync_ok and wd_ok
        else:
            crontab = get_crontab()
            has_sync = "nextdns-blocker" in crontab and "sync" in crontab
            has_wd = "nextdns-blocker" in crontab and "watchdog" in crontab
            scheduler_ok = has_sync and has_wd

        # === RENDER OUTPUT ===
        console.print()
        console.print("  [bold]NextDNS Blocker Status[/bold]")
        console.print("  [dim]━━━━━━━━━━━━━━━━━━━━━━[/dim]")
        console.print()

        # Key info row
        console.print(f"  Profile    [cyan]{config['profile_id']}[/cyan]")
        console.print(f"  Timezone   [cyan]{config['timezone']}[/cyan]")

        # Scheduler status (compact)
        if scheduler_ok:
            console.print("  Scheduler  [green]running[/green]")
        else:
            console.print("  Scheduler  [red]NOT RUNNING[/red]")

        # Pause state (only show if active)
        if is_paused():
            remaining = get_pause_remaining()
            console.print(f"  Pause      [yellow]ACTIVE ({remaining})[/yellow]")

        # Check for updates (unless disabled)
        if not no_update_check:
            update_info = check_for_update(__version__)
            if update_info:
                console.print()
                console.print(
                    f"  [yellow]Update available: "
                    f"{update_info.current_version} → {update_info.latest_version}[/yellow]"
                )
                console.print("  Run: [cyan]nextdns-blocker update[/cyan]")

        console.print()

        # Summary line
        mismatch_count = len(mismatches)
        summary = f"{blocked_count} blocked  ·  {allowed_count} allowed"
        if mismatch_count == 0:
            summary += "  ·  ✓"
        else:
            summary += f"  ·  ⚠ {mismatch_count}"

        console.print(f"  [bold]{summary}[/bold]")

        # Show mismatches (always - this is the important stuff)
        if mismatches:
            console.print()
            console.print("  [bold red]Mismatches:[/bold red]")
            for m in mismatches:
                console.print(
                    f"    [red]✗[/red] {m['domain']:<25} "
                    f"should be {m['expected']} (currently: {m['current']})"
                )

        # Protected domains (compact)
        if protected_domains:
            console.print()
            protected_str = ", ".join(protected_domains)
            console.print(f"  [blue]Protected:[/blue] {protected_str}")

        # Allowlist summary
        if allowlist:
            total_scheduled = allowlist_scheduled_active + allowlist_scheduled_inactive
            if total_scheduled > 0:
                # Show breakdown when there are scheduled entries
                parts = []
                if allowlist_always_active > 0:
                    parts.append(f"{allowlist_always_active} always active")
                if total_scheduled > 0:
                    sched_detail = (
                        f"{total_scheduled} scheduled "
                        f"([green]{allowlist_scheduled_active} active[/green], "
                        f"[dim]{allowlist_scheduled_inactive} inactive[/dim])"
                    )
                    parts.append(sched_detail)
                console.print(f"  [dim]Allowlist:[/dim] {', '.join(parts)}")
            else:
                # Simple display when all entries are always-active
                console.print(f"  [dim]Allowlist:[/dim] {allowlist_always_active} active")

        # NextDNS Parental Control section
        parental_control = client.get_parental_control()
        if parental_control is not None:
            # Get active categories
            categories = parental_control.get("categories", [])
            active_categories = [c["id"] for c in categories if c.get("active", False)]

            # Get active services
            services = parental_control.get("services", [])
            active_services = [s["id"] for s in services if s.get("active", False)]

            # Get settings
            safe_search = parental_control.get("safeSearch", False)
            youtube_restricted = parental_control.get("youtubeRestrictedMode", False)
            block_bypass = parental_control.get("blockBypass", False)

            # Only show section if there's something configured
            has_parental_config = (
                active_categories
                or active_services
                or any([safe_search, youtube_restricted, block_bypass])
            )

            if has_parental_config:
                console.print()
                console.print("  [bold]NextDNS Parental Control:[/bold]")

                if active_categories:
                    cat_list = ", ".join(active_categories)
                    console.print(
                        f"    Categories: [cyan]{cat_list}[/cyan] ({len(active_categories)} active)"
                    )

                if active_services:
                    svc_list = ", ".join(active_services)
                    console.print(
                        f"    Services: [cyan]{svc_list}[/cyan] ({len(active_services)} active)"
                    )

                # Show settings
                settings_parts = []
                if safe_search:
                    settings_parts.append("[green]safe_search ✓[/green]")
                else:
                    settings_parts.append("[dim]safe_search ✗[/dim]")

                if youtube_restricted:
                    settings_parts.append("[green]youtube_restricted ✓[/green]")
                else:
                    settings_parts.append("[dim]youtube_restricted ✗[/dim]")

                if block_bypass:
                    settings_parts.append("[green]block_bypass ✓[/green]")
                else:
                    settings_parts.append("[dim]block_bypass ✗[/dim]")

                console.print(f"    Settings: {', '.join(settings_parts)}")

        # Scheduler not running warning
        if not scheduler_ok:
            console.print()
            console.print("  [yellow]Run: nextdns-blocker watchdog install[/yellow]")

        # Detailed list (only with --list flag)
        if show_list:
            console.print()
            console.print("  [bold]Domains:[/bold]")
            for domain_config in domains:
                domain = domain_config["domain"]
                is_blocked = client.is_blocked(domain)
                status_icon = "🔴" if is_blocked else "🟢"

                domain_delay = domain_config.get("unblock_delay")
                if domain_delay == "never":
                    delay_flag = " [blue]\\[never][/blue]"
                elif domain_delay and domain_delay != "0":
                    delay_flag = f" [cyan]\\[{domain_delay}][/cyan]"
                else:
                    delay_flag = ""

                console.print(f"    {status_icon} {domain}{delay_flag}")

            if allowlist:
                console.print()
                console.print("  [bold]Allowlist:[/bold]")
                for item in allowlist:
                    domain = item["domain"]
                    is_allowed = client.is_allowed(domain)
                    has_schedule = item.get("schedule") is not None
                    status_icon = "[green]✓[/green]" if is_allowed else "[dim]○[/dim]"
                    schedule_flag = " [cyan]\\[scheduled][/cyan]" if has_schedule else ""
                    console.print(f"    {status_icon} {domain}{schedule_flag}")

        console.print()

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)


@main.command()
@click.argument("domain")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allow(domain: str, config_dir: Optional[Path]) -> None:
    """Add DOMAIN to allowlist."""
    require_pin_verification("allow")

    try:
        if not validate_domain(domain):
            console.print(
                f"\n  [red]Error: Invalid domain format '{domain}'[/red]\n", highlight=False
            )
            sys.exit(1)

        config = load_config(config_dir)
        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )

        # Warn if domain is in denylist
        if client.is_blocked(domain):
            console.print(
                f"  [yellow]Warning: '{domain}' is currently blocked in denylist[/yellow]"
            )

        if client.allow(domain):
            audit_log("ALLOW", domain)
            send_notification(EventType.ALLOW, domain, config)
            console.print(f"\n  [green]Added to allowlist: {domain}[/green]\n")
        else:
            console.print("\n  [red]Error: Failed to add to allowlist[/red]\n", highlight=False)
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except DomainValidationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n", highlight=False)
        sys.exit(1)


@main.command()
@click.argument("domain", shell_complete=complete_allowlist_domains)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def disallow(domain: str, config_dir: Optional[Path]) -> None:
    """Remove DOMAIN from allowlist."""
    require_pin_verification("disallow")

    try:
        if not validate_domain(domain):
            console.print(
                f"\n  [red]Error: Invalid domain format '{domain}'[/red]\n", highlight=False
            )
            sys.exit(1)

        config = load_config(config_dir)
        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )

        if client.disallow(domain):
            audit_log("DISALLOW", domain)
            send_notification(EventType.DISALLOW, domain, config)
            console.print(f"\n  [green]Removed from allowlist: {domain}[/green]\n")
        else:
            console.print(
                "\n  [red]Error: Failed to remove from allowlist[/red]\n", highlight=False
            )
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except DomainValidationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n", highlight=False)
        sys.exit(1)


@main.command()
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def health(config_dir: Optional[Path]) -> None:
    """Perform health checks."""
    checks_passed = 0
    checks_total = 0

    console.print("\n  [bold]Health Check[/bold]")
    console.print("  [bold]------------[/bold]")

    # Check config
    checks_total += 1
    try:
        config = load_config(config_dir)
        console.print("  [green][✓][/green] Configuration loaded")
        checks_passed += 1
    except ConfigurationError as e:
        console.print(f"  [red][✗][/red] Configuration: {e}")
        sys.exit(1)

    # Check config.json
    checks_total += 1
    try:
        domains, allowlist = load_domains(config["script_dir"])
        console.print(
            f"  [green][✓][/green] Domains loaded ({len(domains)} domains, {len(allowlist)} allowlist)"
        )
        checks_passed += 1
    except ConfigurationError as e:
        console.print(f"  [red][✗][/red] Domains: {e}")
        sys.exit(1)

    # Check API connectivity
    checks_total += 1
    client = NextDNSClient(
        config["api_key"], config["profile_id"], config["timeout"], config["retries"]
    )
    denylist = client.get_denylist()
    if denylist is not None:
        console.print(f"  [green][✓][/green] API connectivity ({len(denylist)} items in denylist)")
        checks_passed += 1
    else:
        console.print("  [red][✗][/red] API connectivity failed")

    # Check log directory
    checks_total += 1
    try:
        ensure_log_dir()
        log_dir = get_log_dir()
        if log_dir.exists() and log_dir.is_dir():
            console.print(f"  [green][✓][/green] Log directory: {log_dir}")
            checks_passed += 1
        else:
            console.print("  [red][✗][/red] Log directory not accessible")
    except (OSError, PermissionError) as e:
        console.print(f"  [red][✗][/red] Log directory: {e}")

    # Summary
    console.print(f"\n  Result: {checks_passed}/{checks_total} checks passed")
    if checks_passed == checks_total:
        console.print("  Status: [green]HEALTHY[/green]\n")
    else:
        console.print("  Status: [red]DEGRADED[/red]\n")
        sys.exit(1)


@main.command()
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def test_notifications(config_dir: Optional[Path]) -> None:
    """Send a test notification to verify notification configuration."""
    try:
        config = load_config(config_dir)
        notifications = config.get("notifications", {})

        if not notifications:
            console.print(
                "\n  [red]Error: No 'notifications' section in config.json[/red]",
                highlight=False,
            )
            console.print("      Please add notification configuration.\n", highlight=False)
            sys.exit(1)

        if not notifications.get("enabled", True):
            console.print(
                "\n  [yellow]Warning: Notifications are disabled in config[/yellow]",
                highlight=False,
            )
            sys.exit(1)

        channels = notifications.get("channels", {})
        enabled_channels = [name for name, cfg in channels.items() if cfg.get("enabled")]

        if not enabled_channels:
            console.print(
                "\n  [red]Error: No notification channels enabled[/red]",
                highlight=False,
            )
            console.print("      Enable at least one channel in config.json\n", highlight=False)
            sys.exit(1)

        console.print(f"\n  Sending test notification to: {', '.join(enabled_channels)}...")

        send_notification(EventType.TEST, "Test Connection", config)

        console.print("  [green]Notification sent! Check your configured channels.[/green]\n")

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)


@main.command()
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def uninstall(yes: bool) -> None:
    """Completely remove NextDNS Blocker and all its data.

    This command will:
    - Remove all scheduled jobs (launchd/cron/Task Scheduler)
    - Delete configuration files (.env, config.json)
    - Delete all logs, cache, and data files

    After running this command, you will need to reinstall the package
    using your package manager (pip, pipx, or brew).
    """
    import shutil

    from .config import get_config_dir, get_data_dir
    from .watchdog import (
        _uninstall_cron_jobs,
        _uninstall_launchd_jobs,
        _uninstall_windows_tasks,
    )

    config_dir = get_config_dir()
    data_dir = get_data_dir()

    # Collect unique directories to remove
    dirs_to_remove: list[tuple[str, Path]] = []
    dirs_to_remove.append(("Config", config_dir))
    if data_dir != config_dir:
        dirs_to_remove.append(("Data", data_dir))

    console.print("\n  [bold red]NextDNS Blocker Uninstall[/bold red]")
    console.print("  [bold red]-------------------------[/bold red]")
    console.print("\n  This will permanently delete:")
    console.print("    • Scheduled jobs (watchdog)")
    for name, path in dirs_to_remove:
        console.print(f"    • {name}: [yellow]{path}[/yellow]")
    console.print()

    if not yes:
        if not click.confirm("  Are you sure you want to continue?", default=False):
            console.print("\n  [green]Uninstall cancelled.[/green]\n")
            return

    console.print("\n  [bold]Removing...[/bold]")

    total_steps = 1 + len(dirs_to_remove)
    step = 1

    # Step 1: Remove scheduled jobs
    console.print(f"    [{step}/{total_steps}] Removing scheduled jobs...")
    try:
        if is_macos():
            _uninstall_launchd_jobs()
        elif is_windows():
            _uninstall_windows_tasks()
        else:
            _uninstall_cron_jobs()
        console.print("          [green]Done[/green]")
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        console.print(f"          [yellow]Warning: {e}[/yellow]")

    # Remove directories
    for name, path in dirs_to_remove:
        step += 1
        console.print(f"    [{step}/{total_steps}] Removing {name.lower()} directory...")
        try:
            if path.exists():
                shutil.rmtree(path)
                console.print("          [green]Done[/green]")
            else:
                console.print("          [yellow]Already removed[/yellow]")
        except (OSError, PermissionError) as e:
            console.print(f"          [red]Error: {e}[/red]")

    console.print("\n  [green]Uninstall complete![/green]")
    console.print("  To remove the package itself, run:")
    console.print("    [yellow]brew uninstall nextdns-blocker[/yellow]  (Homebrew)")
    console.print("    [yellow]pipx uninstall nextdns-blocker[/yellow]  (pipx)")
    console.print("    [yellow]pip uninstall nextdns-blocker[/yellow]   (pip)")
    console.print()


@main.command()
def fix() -> None:
    """Fix common issues by reinstalling scheduler and running sync."""
    import subprocess

    click.echo("\n  NextDNS Blocker Fix")
    click.echo("  -------------------\n")

    # Step 1: Verify config
    console.print("  [bold][1/5] Checking configuration...[/bold]")
    try:
        load_config()  # Validates config exists and is valid
        console.print("        Config: [green]OK[/green]")
    except ConfigurationError as e:
        console.print(f"        Config: [red]FAILED - {e}[/red]")
        console.print("\n  Run 'nextdns-blocker init' to set up configuration.\n")
        sys.exit(1)

    # Step 2: Find executable
    console.print("  [bold][2/5] Detecting installation...[/bold]")
    detected_path = get_executable_path()
    exe_cmd: Optional[str] = detected_path
    # Detect installation type
    if "-m nextdns_blocker" in detected_path:
        console.print("        Type: module")
        exe_cmd = None  # Use module invocation
    elif ".local" in detected_path or "pipx" in detected_path.lower():
        console.print("        Type: pipx")
    else:
        console.print("        Type: system")

    # Step 3: Reinstall scheduler
    console.print("  [bold][3/5] Reinstalling scheduler...[/bold]")
    try:
        if is_macos():
            # Uninstall launchd jobs with timeout protection
            subprocess.run(
                [
                    "launchctl",
                    "unload",
                    str(Path.home() / "Library/LaunchAgents/com.nextdns-blocker.sync.plist"),
                ],
                capture_output=True,
                timeout=30,
                check=False,  # Don't raise on non-zero exit
            )
            subprocess.run(
                [
                    "launchctl",
                    "unload",
                    str(Path.home() / "Library/LaunchAgents/com.nextdns-blocker.watchdog.plist"),
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
        elif is_windows():
            # Uninstall Windows Task Scheduler tasks with timeout protection
            subprocess.run(
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_SYNC_NAME, "/f"],
                capture_output=True,
                timeout=30,
                check=False,
            )
            subprocess.run(
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_WATCHDOG_NAME, "/f"],
                capture_output=True,
                timeout=30,
                check=False,
            )

        # Use the watchdog install command
        if exe_cmd:
            result = subprocess.run(
                [exe_cmd, "watchdog", "install"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "nextdns_blocker", "watchdog", "install"],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode == 0:
            console.print("        Scheduler: [green]OK[/green]")
        else:
            console.print(f"        Scheduler: [red]FAILED - {result.stderr}[/red]")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("        Scheduler: [red]FAILED - timeout[/red]")
        sys.exit(1)
    except OSError as e:
        console.print(f"        Scheduler: [red]FAILED - {e}[/red]")
        sys.exit(1)

    # Step 4: Run sync
    console.print("  [bold][4/5] Running sync...[/bold]")
    try:
        if exe_cmd:
            result = subprocess.run(
                [exe_cmd, "sync"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "nextdns_blocker", "sync"],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode == 0:
            console.print("        Sync: [green]OK[/green]")
        else:
            console.print(f"        Sync: [red]FAILED - {result.stderr}[/red]")
    except subprocess.TimeoutExpired:
        console.print("        Sync: [red]TIMEOUT[/red]")
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"        Sync: [red]FAILED - {e}[/red]")

    # Step 5: Shell completion
    console.print("  [bold][5/5] Checking shell completion...[/bold]")
    shell = detect_shell()
    if shell and not is_windows():
        if is_completion_installed(shell):
            console.print("        Completion: [green]OK[/green]")
        else:
            success, msg = install_completion(shell)
            if success:
                console.print("        Completion: [green]INSTALLED[/green]")
                console.print(f"        {msg}")
            else:
                console.print("        Completion: [yellow]SKIPPED[/yellow]")
                console.print(f"        {msg}")
    else:
        console.print("        Completion: [dim]N/A (Windows or unsupported shell)[/dim]")

    console.print("\n  [green]Fix complete![/green]\n")


@main.command()
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def update(yes: bool) -> None:
    """Check for updates and upgrade to the latest version.

    Automatically detects installation method (Homebrew, pipx, or pip)
    and uses the appropriate upgrade command.
    """
    import json
    import ssl
    import subprocess
    import urllib.error
    import urllib.request

    console.print("\n  Checking for updates...")

    current_version = __version__

    # Fetch latest version from PyPI
    try:
        with urllib.request.urlopen(PYPI_PACKAGE_URL, timeout=10) as response:  # nosec B310
            data = json.loads(response.read().decode())
            # Safely access nested keys
            info = data.get("info")
            if not isinstance(info, dict):
                console.print("  [red]Error: Invalid PyPI response format[/red]\n", highlight=False)
                sys.exit(1)
            latest_version = info.get("version")
            if not isinstance(latest_version, str):
                console.print(
                    "  [red]Error: Missing version in PyPI response[/red]\n", highlight=False
                )
                sys.exit(1)
    except ssl.SSLError as e:
        # SSLError is the base class and includes SSLCertVerificationError
        console.print(f"  [red]SSL error: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except urllib.error.URLError as e:
        console.print(f"  [red]Network error: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except (json.JSONDecodeError, ValueError) as e:
        console.print(f"  [red]Error parsing PyPI response: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except OSError as e:
        console.print(f"  [red]Error checking PyPI: {e}[/red]\n", highlight=False)
        sys.exit(1)

    console.print(f"  Current version: {current_version}")
    console.print(f"  Latest version:  {latest_version}")

    # Compare versions
    if current_version == latest_version:
        console.print("\n  [green]You are already on the latest version.[/green]\n")
        return

    # Parse versions for comparison (handles semver with suffixes like "1.0.0rc1")
    def parse_version(v: str) -> tuple[int, ...]:
        # Extract only the numeric parts (e.g., "1.0.0rc1" -> "1.0.0")
        # This regex captures digits separated by dots, ignoring suffixes
        numeric_match = re.match(r"^(\d+(?:\.\d+)*)", v)
        if not numeric_match:
            raise ValueError(f"Cannot parse version: {v}")
        numeric_part = numeric_match.group(1)
        return tuple(int(x) for x in numeric_part.split("."))

    try:
        current_tuple = parse_version(current_version)
        latest_tuple = parse_version(latest_version)
    except ValueError:
        # If parsing fails, assume update is available to be safe
        current_tuple = (0,)
        latest_tuple = (1,)

    if current_tuple >= latest_tuple:
        console.print("\n  [green]You are already on the latest version.[/green]\n")
        return

    console.print(f"\n  [yellow]A new version is available: {latest_version}[/yellow]")

    # Ask for confirmation unless --yes flag is provided
    if not yes:
        if not click.confirm("  Do you want to update?"):
            console.print("  Update cancelled.\n")
            return

    # Detect installation method (cross-platform)
    exe_path = get_executable_path()

    # Check for Homebrew installation (macOS/Linux)
    is_homebrew_install = "/homebrew/" in exe_path.lower() or "/cellar/" in exe_path.lower()

    # Check multiple indicators for pipx installation
    pipx_venv_unix = Path.home() / ".local" / "pipx" / "venvs" / "nextdns-blocker"
    pipx_venv_win = Path.home() / "pipx" / "venvs" / "nextdns-blocker"
    is_pipx_install = (
        pipx_venv_unix.exists() or pipx_venv_win.exists() or "pipx" in exe_path.lower()
    )

    # Perform the update
    console.print("\n  Updating...")
    try:
        if is_homebrew_install:
            console.print("  (detected Homebrew installation)")
            result = subprocess.run(
                ["brew", "upgrade", "nextdns-blocker"],
                capture_output=True,
                text=True,
            )
        elif is_pipx_install:
            console.print("  (detected pipx installation)")
            result = subprocess.run(
                ["pipx", "upgrade", "nextdns-blocker"],
                capture_output=True,
                text=True,
            )
        else:
            console.print("  (detected pip installation)")
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", "nextdns-blocker"],
                capture_output=True,
                text=True,
            )
        if result.returncode == 0:
            console.print(f"  [green]Successfully updated to version {latest_version}[/green]")

            # Check/install shell completion after update
            shell = detect_shell()
            if shell and not is_windows():
                if not is_completion_installed(shell):
                    success, msg = install_completion(shell)
                    if success:
                        console.print(f"  Shell completion installed: {msg}")

            console.print("  Please restart the application to use the new version.\n")
        else:
            console.print(f"  [red]Update failed: {result.stderr}[/red]\n", highlight=False)
            sys.exit(1)
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        console.print(f"  [red]Update failed: {e}[/red]\n", highlight=False)
        sys.exit(1)


def validate_impl(output_json: bool, config_dir: Optional[Path]) -> None:
    """
    Validate configuration files before deployment.

    This is the implementation function called by config_cli.py.

    Checks config.json for:
    - Valid JSON syntax
    - Valid domain formats
    - Valid schedule time formats (HH:MM)
    - No denylist/allowlist conflicts
    """
    import json as json_module

    # Determine config directory
    if config_dir is None:
        config_dir = get_config_dir()

    results: dict[str, Any] = {
        "valid": True,
        "checks": [],
        "errors": [],
        "warnings": [],
        "summary": {},
    }

    def add_check(name: str, passed: bool, detail: str = "") -> None:
        results["checks"].append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            results["valid"] = False

    def add_error(message: str) -> None:
        results["errors"].append(message)
        results["valid"] = False

    def add_warning(message: str) -> None:
        results["warnings"].append(message)

    # Check 1: config.json exists and has valid JSON syntax
    config_file = config_dir / "config.json"
    domains_data = None

    if config_file.exists():
        try:
            with open(config_file, encoding="utf-8") as f:
                domains_data = json_module.load(f)
            add_check("config.json", True, "valid JSON syntax")
        except json_module.JSONDecodeError as e:
            add_check("config.json", False, f"invalid JSON: {e}")
            add_error(f"JSON syntax error: {e}")
    else:
        add_check("config.json", False, "file not found")
        add_error(
            f"Config file not found: {config_file}\nRun 'nextdns-blocker init' to create one."
        )

    if domains_data is None:
        # Cannot proceed without valid domains data
        if output_json:
            console.print(json_module.dumps(results, indent=2))
        else:
            console.print("\n  [red]❌ Configuration validation failed[/red]")
            for error in results["errors"]:
                console.print(f"  [red]✗[/red] {error}")
            console.print()
        sys.exit(1)

    # Check 2: Validate structure
    if not isinstance(domains_data, dict):
        add_error("Configuration must be a JSON object")
    elif "blocklist" not in domains_data:
        add_error("Missing 'blocklist' array in configuration")

    domains_list: list[dict[str, Any]] = []
    allowlist_list: list[dict[str, Any]] = []
    categories_list: list[dict[str, Any]] = []
    schedules_dict: dict[str, Any] = {}
    if isinstance(domains_data, dict):
        domains_list = domains_data.get("blocklist", [])
        allowlist_list = domains_data.get("allowlist", [])
        categories_list = domains_data.get("categories", [])
        schedules_dict = domains_data.get("schedules", {})

    # Get valid schedule template names for reference validation
    valid_schedule_names: set[str] = (
        set(schedules_dict.keys()) if isinstance(schedules_dict, dict) else set()
    )

    # Expand categories to get individual domain entries
    expanded_category_domains = _expand_categories(categories_list)
    total_domains = len(domains_list) + len(expanded_category_domains)
    categories_count = len(categories_list)

    # Update summary
    results["summary"]["domains_count"] = total_domains
    results["summary"]["allowlist_count"] = len(allowlist_list)

    # Check 3: Count and validate domains
    if total_domains > 0:
        if categories_count > 0:
            add_check(
                "domains configured",
                True,
                f"{total_domains} domains ({len(domains_list)} blocklist + {len(expanded_category_domains)} from {categories_count} categories)",
            )
        else:
            add_check("domains configured", True, f"{total_domains} domains")
    else:
        add_check("domains configured", False, "no domains found")

    # Check 4: Count allowlist entries
    if allowlist_list:
        add_check("allowlist entries", True, f"{len(allowlist_list)} entries")

    # Combine blocklist and expanded category domains for validation
    all_blocked_domains = domains_list + expanded_category_domains

    # Check 5: Count protected domains (unblock_delay="never")
    protected_domains = [d for d in all_blocked_domains if d.get("unblock_delay") == "never"]
    results["summary"]["protected_count"] = len(protected_domains)
    if protected_domains:
        add_check("protected domains", True, f"{len(protected_domains)} protected")

    # Check 6: Validate each domain configuration
    domain_errors: list[str] = []
    schedule_count = 0

    for idx, domain_config in enumerate(all_blocked_domains):
        errors = validate_domain_config(domain_config, idx, valid_schedule_names)
        domain_errors.extend(errors)
        if domain_config.get("schedule"):
            schedule_count += 1

    results["summary"]["schedules_count"] = schedule_count

    # Check 7: Validate allowlist entries
    for idx, allowlist_config in enumerate(allowlist_list):
        errors = validate_allowlist_config(allowlist_config, idx, valid_schedule_names)
        domain_errors.extend(errors)

    if domain_errors:
        add_check("domain formats", False, f"{len(domain_errors)} error(s)")
        for error in domain_errors:
            add_error(error)
    else:
        add_check("domain formats", True, "all valid")

    # Check 8: Validate schedules
    if schedule_count > 0:
        # Schedule validation is done as part of validate_domain_config
        # If we got here without errors, schedules are valid
        if not domain_errors:
            add_check("schedules", True, f"{schedule_count} schedule(s) valid")

    # Check 9: Check for denylist/allowlist conflicts
    overlap_errors = validate_no_overlap(domains_list, allowlist_list)
    if overlap_errors:
        add_check("no conflicts", False, f"{len(overlap_errors)} conflict(s)")
        for error in overlap_errors:
            add_error(error)
    else:
        add_check("no conflicts", True, "no denylist/allowlist conflicts")

    # Output results
    if output_json:
        console.print(json_module.dumps(results, indent=2))
    else:
        console.print()
        for check in results["checks"]:
            if check["passed"]:
                console.print(f"  [green]✓[/green] {check['name']}: {check['detail']}")
            else:
                console.print(f"  [red]✗[/red] {check['name']}: {check['detail']}")

        if results["errors"]:
            console.print(f"\n  [red]❌ Configuration has {len(results['errors'])} error(s)[/red]")
            for error in results["errors"]:
                console.print(f"    • {error}")
        else:
            console.print("\n  [green]✅ Configuration OK[/green]")

        console.print()

    sys.exit(0 if results["valid"] else 1)


# =============================================================================
# SHELL COMPLETION
# =============================================================================


@main.command()
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str) -> None:
    """Generate shell completion script.

    Output the completion script for your shell. To enable completions,
    add the appropriate line to your shell configuration file.

    Examples:

    \b
    # Bash - add to ~/.bashrc
    eval "$(nextdns-blocker completion bash)"

    \b
    # Zsh - add to ~/.zshrc
    eval "$(nextdns-blocker completion zsh)"

    \b
    # Fish - save to completions directory
    nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
    """
    script = get_completion_script(shell)
    click.echo(script)


# =============================================================================
# REGISTER COMMAND GROUPS
# =============================================================================

# Register config command group
register_config(main)

# Register nextdns command group
register_nextdns(main)

# Register protection command group
register_protection(main)

# Register stats command group
register_stats(main)


if __name__ == "__main__":
    main()
