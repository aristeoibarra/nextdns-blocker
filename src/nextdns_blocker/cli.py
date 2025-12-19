"""Command-line interface for NextDNS Blocker using Click."""

import contextlib
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console

from . import __version__
from .client import NextDNSClient
from .common import (
    audit_log,
    ensure_log_dir,
    get_audit_log_file,
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
    get_config_dir,
    load_config,
    load_domains,
    validate_allowlist_config,
    validate_domain_config,
    validate_no_overlap,
)
from .config_cli import register_config
from .exceptions import ConfigurationError, DomainValidationError
from .init import run_interactive_wizard, run_non_interactive
from .notifications import send_discord_notification
from .platform_utils import get_executable_path, is_macos, is_windows
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
        pause_until = datetime.fromisoformat(content)
        if datetime.now() < pause_until:
            return True, pause_until
        # Expired, clean up (missing_ok handles race conditions)
        with contextlib.suppress(OSError):
            pause_file.unlink(missing_ok=True)
        return False, None
    except ValueError:
        # Invalid content, clean up
        logger.warning(f"Invalid pause file content, removing: {content[:50]}")
        with contextlib.suppress(OSError):
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
                f"\n  [blue]Error: '{domain}' cannot be unblocked "
                f"(unblock_delay: never)[/blue]\n",
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

        if delay_seconds and delay_seconds > 0 and not force:
            # Create pending action
            # At this point, unblock_delay is guaranteed to be a valid non-None string
            # because delay_seconds is > 0
            if unblock_delay is None:  # Should never happen, but satisfy type checker
                unblock_delay = "0"
            action = create_pending_action(domain, unblock_delay, requested_by="cli")
            if action:
                send_discord_notification(
                    domain=f"{domain} (scheduled)",
                    event_type="pending",
                    webhook_url=config.get("discord_webhook_url"),
                )
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
            send_discord_notification(
                domain, "unblock", webhook_url=config.get("discord_webhook_url")
            )
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


@main.command()
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--_from_config_group", is_flag=True, hidden=True)
def sync(
    dry_run: bool,
    verbose: bool,
    config_dir: Optional[Path],
    _from_config_group: bool = False,
) -> None:
    """Synchronize domain blocking with schedules."""
    # Show deprecation warning if called directly
    if not _from_config_group:
        console.print(
            "\n  [yellow]⚠ Deprecated:[/yellow] Use 'nextdns-blocker config sync' instead.\n",
            highlight=False,
        )

    setup_logging(verbose)

    # Check pause state
    if is_paused():
        remaining = get_pause_remaining()
        click.echo(f"  Paused ({remaining} remaining), skipping sync")
        return

    # Check panic mode - blocks allowed, unblocks skipped
    from .panic import is_panic_mode

    panic_active = is_panic_mode()

    try:
        from .config import get_unblock_delay, parse_unblock_delay_seconds
        from .pending import create_pending_action, get_pending_for_domain

        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        if dry_run:
            console.print("\n  [yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        # Sync denylist domains
        blocked_count = 0
        unblocked_count = 0

        for domain_config in domains:
            domain = domain_config["domain"]
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)

            if should_block and not is_blocked:
                if dry_run:
                    console.print(f"  [yellow]Would BLOCK: {domain}[/yellow]")
                else:
                    if client.block(domain):
                        audit_log("BLOCK", domain)
                        send_discord_notification(
                            domain, "block", webhook_url=config.get("discord_webhook_url")
                        )
                        blocked_count += 1
            elif not should_block and is_blocked:
                # Skip unblocks during panic mode
                if panic_active:
                    if verbose:
                        console.print(f"  [red]Skipping unblock (panic mode): {domain}[/red]")
                    continue

                # Check unblock_delay for this domain
                domain_delay = get_unblock_delay(domains, domain)

                # Handle 'never' - cannot unblock
                if domain_delay == "never":
                    if verbose:
                        console.print(f"  [blue]Cannot unblock (never): {domain}[/blue]")
                    continue

                delay_seconds = parse_unblock_delay_seconds(domain_delay or "0")

                if delay_seconds and delay_seconds > 0:
                    # Check if already pending
                    existing = get_pending_for_domain(domain)
                    if existing:
                        if verbose:
                            console.print(f"  [yellow]Already pending: {domain}[/yellow]")
                        continue

                    if dry_run:
                        console.print(
                            f"  [yellow]Would schedule UNBLOCK: {domain} "
                            f"(delay: {domain_delay})[/yellow]"
                        )
                    else:
                        # At this point, domain_delay is guaranteed to be a valid non-None string
                        # because delay_seconds is > 0
                        if domain_delay is None:  # Should never happen, but satisfy type checker
                            domain_delay = "0"
                        action = create_pending_action(domain, domain_delay, requested_by="sync")
                        if action and verbose:
                            console.print(
                                f"  [yellow]Scheduled unblock: {domain} ({domain_delay})[/yellow]"
                            )
                    continue

                # Immediate unblock (no delay)
                if dry_run:
                    console.print(f"  [green]Would UNBLOCK: {domain}[/green]")
                else:
                    if client.unblock(domain):
                        audit_log("UNBLOCK", domain)
                        send_discord_notification(
                            domain, "unblock", webhook_url=config.get("discord_webhook_url")
                        )
                        unblocked_count += 1

        # Sync allowlist (schedule-aware)
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
                        allowed_count += 1

            elif not should_allow and is_allowed:
                # Should NOT be in allowlist but is - remove it
                if dry_run:
                    console.print(f"  [yellow]Would REMOVE from allowlist: {domain}[/yellow]")
                else:
                    if client.disallow(domain):
                        audit_log("DISALLOW", domain)
                        disallowed_count += 1

        if not dry_run:
            has_changes = blocked_count or unblocked_count or allowed_count or disallowed_count
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
                console.print(f"  Sync: {', '.join(parts)}")
            elif verbose:
                console.print("  Sync: [green]No changes needed[/green]")

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
def status(config_dir: Optional[Path], no_update_check: bool) -> None:
    """Show current blocking status."""
    from .update_check import check_for_update

    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        console.print("\n  [bold]NextDNS Blocker Status[/bold]")
        console.print("  [bold]----------------------[/bold]")
        console.print(f"  Profile: {config['profile_id']}")
        console.print(f"  Timezone: {config['timezone']}")

        # Pause state
        if is_paused():
            remaining = get_pause_remaining()
            console.print(f"  Pause: [yellow]ACTIVE ({remaining})[/yellow]")
        else:
            console.print("  Pause: [green]inactive[/green]")

        # Check for updates (unless disabled)
        if not no_update_check:
            update_info = check_for_update(__version__)
            if update_info:
                console.print()
                console.print(
                    f"  [yellow]⚠️  Update available: "
                    f"{update_info.current_version} → {update_info.latest_version}[/yellow]"
                )
                console.print("      Run: [cyan]nextdns-blocker update[/cyan]")

        console.print(f"\n  [bold]Domains ({len(domains)}):[/bold]")

        for domain_config in domains:
            domain = domain_config["domain"]
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)

            if is_blocked:
                status_icon = "🔴"
                status_text = "[red]blocked[/red]"
            else:
                status_icon = "🟢"
                status_text = "[green]active[/green]"

            expected = "block" if should_block else "allow"
            match = "[green]✓[/green]" if (should_block == is_blocked) else "[red]✗ MISMATCH[/red]"

            # Show unblock_delay setting
            domain_delay = domain_config.get("unblock_delay")
            # Backward compatibility: protected=true -> never
            if domain_config.get("protected", False):
                domain_delay = "never"
            if domain_delay == "never":
                delay_flag = " [blue]\\[never][/blue]"
            elif domain_delay and domain_delay != "0":
                delay_flag = f" [cyan]\\[{domain_delay}][/cyan]"
            else:
                delay_flag = ""

            # Pad domain for alignment
            console.print(
                f"    {status_icon} {domain:<20} {status_text} (should: {expected}) {match}{delay_flag}"
            )

        if allowlist:
            console.print(f"\n  [bold]Allowlist ({len(allowlist)}):[/bold]")
            for item in allowlist:
                domain = item["domain"]
                is_allowed = client.is_allowed(domain)
                has_schedule = item.get("schedule") is not None
                should_allow = evaluator.should_allow_domain(item)

                if has_schedule:
                    # Scheduled allowlist entry
                    expected = "allow" if should_allow else "disallow"
                    match = (
                        "[green]✓[/green]"
                        if (should_allow == is_allowed)
                        else "[red]✗ MISMATCH[/red]"
                    )
                    status_text = (
                        "[green]allowed[/green]" if is_allowed else "[yellow]not allowed[/yellow]"
                    )
                    console.print(
                        f"    {domain:<20} {status_text} (should: {expected}) {match} [cyan]\\[scheduled][/cyan]"
                    )
                else:
                    # Always-allowed entry (no schedule)
                    status_icon = "[green]✓[/green]" if is_allowed else "[red]✗[/red]"
                    console.print(f"    {status_icon} {domain}")

        # Scheduler status
        console.print("\n  [bold]Scheduler:[/bold]")
        if is_macos():
            sync_ok = is_launchd_job_loaded(LAUNCHD_SYNC_LABEL)
            wd_ok = is_launchd_job_loaded(LAUNCHD_WATCHDOG_LABEL)
            sync_status = "[green]ok[/green]" if sync_ok else "[red]NOT RUNNING[/red]"
            wd_status = "[green]ok[/green]" if wd_ok else "[red]NOT RUNNING[/red]"
            console.print(f"    sync:     {sync_status}")
            console.print(f"    watchdog: {wd_status}")
            if not sync_ok or not wd_ok:
                console.print("    Run: [yellow]nextdns-blocker watchdog install[/yellow]")
        elif is_windows():
            sync_ok = has_windows_task(WINDOWS_TASK_SYNC_NAME)
            wd_ok = has_windows_task(WINDOWS_TASK_WATCHDOG_NAME)
            sync_status = "[green]ok[/green]" if sync_ok else "[red]NOT RUNNING[/red]"
            wd_status = "[green]ok[/green]" if wd_ok else "[red]NOT RUNNING[/red]"
            console.print(f"    sync:     {sync_status}")
            console.print(f"    watchdog: {wd_status}")
            if not sync_ok or not wd_ok:
                console.print("    Run: [yellow]nextdns-blocker watchdog install[/yellow]")
        else:
            crontab = get_crontab()
            has_sync = "nextdns-blocker" in crontab and "sync" in crontab
            has_wd = "nextdns-blocker" in crontab and "watchdog" in crontab
            sync_status = "[green]ok[/green]" if has_sync else "[red]NOT FOUND[/red]"
            wd_status = "[green]ok[/green]" if has_wd else "[red]NOT FOUND[/red]"
            console.print(f"    sync:     {sync_status}")
            console.print(f"    watchdog: {wd_status}")
            if not has_sync or not has_wd:
                console.print("    Run: [yellow]nextdns-blocker watchdog install[/yellow]")

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
    """Send a test notification to verify Discord integration."""
    try:
        config = load_config(config_dir)
        webhook_url = config.get("discord_webhook_url")

        if not webhook_url:
            console.print(
                "\n  [red]Error: DISCORD_WEBHOOK_URL is not set in configuration.[/red]",
                highlight=False,
            )
            console.print("      Please add it to your .env file.\n", highlight=False)
            sys.exit(1)

        console.print("\n  Sending test notification...")

        # We pass the loaded webhook_url explicitly
        send_discord_notification(
            event_type="test", domain="Test Connection", webhook_url=webhook_url
        )

        console.print(" [green]Notification sent! Check your Discord channel.[/green]\n")

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
    except Exception as e:
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
        except Exception as e:
            console.print(f"          [red]Error: {e}[/red]")

    console.print("\n  [green]Uninstall complete![/green]")
    console.print("  To remove the package itself, run:")
    console.print("    [yellow]brew uninstall nextdns-blocker[/yellow]  (Homebrew)")
    console.print("    [yellow]pipx uninstall nextdns-blocker[/yellow]  (pipx)")
    console.print("    [yellow]pip uninstall nextdns-blocker[/yellow]   (pip)")
    console.print()


@main.command()
def stats() -> None:
    """Show usage statistics from audit log."""
    console.print("\n  [bold]Statistics[/bold]")
    console.print("  [bold]----------[/bold]")

    audit_file = get_audit_log_file()
    if not audit_file.exists():
        console.print("  No audit log found\n")
        return

    try:
        with open(audit_file, encoding="utf-8") as f:
            lines = f.readlines()

        actions: dict[str, int] = {}
        for line in lines:
            parts = line.strip().split(" | ")
            if len(parts) >= 2:
                action = parts[1]
                # Handle WD prefix entries: [timestamp, WD, action, detail]
                if action == "WD" and len(parts) > 2:
                    action = parts[2]
                actions[action] = actions.get(action, 0) + 1

        if actions:
            for action, count in sorted(actions.items()):
                console.print(f"    {action}: [bold]{count}[/bold]")
        else:
            console.print("  No actions recorded")

        console.print(f"\n  Total entries: {len(lines)}\n")

    except (OSError, ValueError) as e:
        console.print(f"  [red]Error reading stats: {e}[/red]\n", highlight=False)


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
            # Uninstall launchd jobs
            subprocess.run(
                [
                    "launchctl",
                    "unload",
                    str(Path.home() / "Library/LaunchAgents/com.nextdns-blocker.sync.plist"),
                ],
                capture_output=True,
            )
            subprocess.run(
                [
                    "launchctl",
                    "unload",
                    str(Path.home() / "Library/LaunchAgents/com.nextdns-blocker.watchdog.plist"),
                ],
                capture_output=True,
            )
        elif is_windows():
            # Uninstall Windows Task Scheduler tasks
            subprocess.run(
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_SYNC_NAME, "/f"],
                capture_output=True,
            )
            subprocess.run(
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_WATCHDOG_NAME, "/f"],
                capture_output=True,
            )

        # Use the watchdog install command
        if exe_cmd:
            result = subprocess.run(
                [exe_cmd, "watchdog", "install"],
                capture_output=True,
                text=True,
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "nextdns_blocker", "watchdog", "install"],
                capture_output=True,
                text=True,
            )

        if result.returncode == 0:
            console.print("        Scheduler: [green]OK[/green]")
        else:
            console.print(f"        Scheduler: [red]FAILED - {result.stderr}[/red]")
            sys.exit(1)
    except Exception as e:
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
    except Exception as e:
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
        pypi_url = "https://pypi.org/pypi/nextdns-blocker/json"
        with urllib.request.urlopen(pypi_url, timeout=10) as response:  # nosec B310
            data = json.loads(response.read().decode())
            # Safely access nested keys
            info = data.get("info")
            if not isinstance(info, dict):
                console.print("  [red]Error: Invalid PyPI response format[/red]\n", highlight=False)
                sys.exit(1)
            latest_version = info.get("version")
            if not isinstance(latest_version, str):
                console.print("  [red]Error: Missing version in PyPI response[/red]\n", highlight=False)
                sys.exit(1)
    except ssl.SSLError as e:
        console.print(f"  [red]SSL error: {e}[/red]\n", highlight=False)
        sys.exit(1)
    except ssl.CertificateError as e:
        console.print(f"  [red]Certificate error: {e}[/red]\n", highlight=False)
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

    # Parse versions for comparison
    def parse_version(v: str) -> tuple[int, ...]:
        return tuple(int(x) for x in v.split("."))

    try:
        current_tuple = parse_version(current_version)
        latest_tuple = parse_version(latest_version)
    except ValueError:
        # If parsing fails, just do string comparison
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
    except Exception as e:
        console.print(f"  [red]Update failed: {e}[/red]\n", highlight=False)
        sys.exit(1)


@main.command()
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--_from_config_group", is_flag=True, hidden=True)
def validate(
    output_json: bool, config_dir: Optional[Path], _from_config_group: bool = False
) -> None:
    """Validate configuration files before deployment.

    Checks config.json for:
    - Valid JSON syntax
    - Valid domain formats
    - Valid schedule time formats (HH:MM)
    - No denylist/allowlist conflicts
    """
    # Show deprecation warning if called directly (but not for JSON output)
    if not _from_config_group and not output_json:
        console.print(
            "\n  [yellow]⚠ Deprecated:[/yellow] Use 'nextdns-blocker config validate' instead.\n",
            highlight=False,
        )

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
            f"Config file not found: {config_file}\n" "Run 'nextdns-blocker init' to create one."
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
    if isinstance(domains_data, dict):
        domains_list = domains_data.get("blocklist", [])
        allowlist_list = domains_data.get("allowlist", [])

    # Update summary
    results["summary"]["domains_count"] = len(domains_list)
    results["summary"]["allowlist_count"] = len(allowlist_list)

    # Check 3: Count and validate domains
    if domains_list:
        add_check("domains configured", True, f"{len(domains_list)} domains")
    else:
        add_check("domains configured", False, "no domains found")

    # Check 4: Count allowlist entries
    if allowlist_list:
        add_check("allowlist entries", True, f"{len(allowlist_list)} entries")

    # Check 5: Count protected domains
    protected_domains = [d for d in domains_list if d.get("protected", False)]
    results["summary"]["protected_count"] = len(protected_domains)
    if protected_domains:
        add_check("protected domains", True, f"{len(protected_domains)} protected")

    # Check 6: Validate each domain configuration
    domain_errors: list[str] = []
    schedule_count = 0

    for idx, domain_config in enumerate(domains_list):
        errors = validate_domain_config(domain_config, idx)
        domain_errors.extend(errors)
        if domain_config.get("schedule"):
            schedule_count += 1

    results["summary"]["schedules_count"] = schedule_count

    # Check 7: Validate allowlist entries
    for idx, allowlist_config in enumerate(allowlist_list):
        errors = validate_allowlist_config(allowlist_config, idx)
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


if __name__ == "__main__":
    main()
