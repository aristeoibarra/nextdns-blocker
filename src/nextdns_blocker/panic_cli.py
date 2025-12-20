"""Panic mode CLI commands for NextDNS Blocker.

Panic mode provides an emergency lockdown that blocks all domains and
hides dangerous commands for a specified duration.
"""

import sys

import click
from rich.console import Console

from .panic import (
    MIN_PANIC_DURATION_MINUTES,
    extend_panic,
    get_panic_remaining,
    get_panic_until,
    is_panic_mode,
    parse_duration,
    try_activate_or_extend,
)

console = Console(highlight=False)


def _block_all_domains() -> int:
    """
    Block all currently unblocked domains from config.

    Returns:
        Number of domains blocked
    """
    from .client import NextDNSClient
    from .common import audit_log
    from .config import load_config, load_domains
    from .notifications import send_discord_notification

    blocked_domains: list[str] = []

    try:
        config = load_config()
        domains, _ = load_domains(config["script_dir"])

        client = NextDNSClient(
            config["api_key"],
            config["profile_id"],
            config["timeout"],
            config["retries"],
        )

        for domain_config in domains:
            domain = domain_config["domain"]
            if not client.is_blocked(domain):
                if client.block(domain):
                    audit_log("BLOCK", f"{domain} (panic mode)")
                    blocked_domains.append(domain)
                    console.print(f"    - {domain} [green]blocked[/green]")

        # Send single notification for panic activation
        if blocked_domains:
            send_discord_notification(
                domain=f"PANIC MODE ({len(blocked_domains)} domains blocked)",
                event_type="panic",
                webhook_url=config.get("discord_webhook_url"),
            )

        return len(blocked_domains)

    except (OSError, KeyError, TypeError, ValueError) as e:
        # Handle specific exceptions that might occur during blocking:
        # - OSError: Network/file system errors
        # - KeyError: Missing config keys
        # - TypeError/ValueError: Data format issues
        console.print(f"  [yellow]Warning: Could not block all domains: {e}[/yellow]")
        return len(blocked_domains)


@click.group(invoke_without_command=True)
@click.pass_context
def panic_cli(ctx: click.Context) -> None:
    """Emergency lockdown mode - blocks all domains immediately.

    Activates panic mode for the specified duration. During panic mode,
    all configured domains are blocked and cannot be unblocked.
    Dangerous commands (unblock, pause, config edit, etc.) are hidden.

    \b
    Usage:
        nextdns-blocker panic 2h          Activate for 2 hours
        nextdns-blocker panic status      Check status
        nextdns-blocker panic extend 30m  Extend by 30 minutes

    \b
    Duration formats:
        Nm - minutes (e.g., 30m)
        Nh - hours (e.g., 2h)
        Nd - days (e.g., 1d)

    Minimum duration: 15 minutes
    """
    # If a subcommand was invoked, let it handle things
    if ctx.invoked_subcommand is not None:
        return

    # Show help when no arguments provided
    console.print(ctx.get_help())


@panic_cli.command("activate")
@click.argument("duration")
def cmd_activate(duration: str) -> None:
    """Activate panic mode for specified duration.

    DURATION: Time duration (e.g., 30m, 2h, 1d)
    """
    _do_activate(duration)


def _do_activate(duration: str) -> None:
    """Internal function to activate panic mode."""
    try:
        minutes = parse_duration(duration)

        if minutes < MIN_PANIC_DURATION_MINUTES:
            console.print(
                f"\n  [red]Error: Minimum duration is {MIN_PANIC_DURATION_MINUTES} minutes ({MIN_PANIC_DURATION_MINUTES}m)[/red]\n"
            )
            sys.exit(1)

        panic_until, was_extended = try_activate_or_extend(minutes)

        if was_extended:
            console.print("\n  [yellow]PANIC MODE EXTENDED[/yellow]")
            console.print(f"  New duration: {duration}")
            console.print(f"  Expires: {panic_until.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"  Remaining: {get_panic_remaining()}\n")
        else:
            console.print("\n  [red bold]PANIC MODE ACTIVATED[/red bold]")
            console.print(f"  Duration: {duration}")
            console.print(f"  Expires: {panic_until.strftime('%Y-%m-%d %H:%M')}")
            console.print()

            # Block all unblocked domains
            console.print("  Blocking active domains...")
            blocked_count = _block_all_domains()

            if blocked_count > 0:
                console.print(f"\n  [green]{blocked_count} domain(s) blocked[/green]")
            else:
                console.print("  [dim]No active domains to block[/dim]")

            console.print("\n  Dangerous commands are now hidden.\n")

    except ValueError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


# Create aliases for common duration patterns so users can type "panic 2h"
# by registering duration patterns as command names
class DurationCommand(click.Command):
    """Custom command that acts as an alias for panic activate."""

    def invoke(self, ctx: click.Context) -> None:
        # Get the command name which is the duration
        duration = ctx.info_name
        if duration is None:
            # Should never happen for registered commands, but handle gracefully
            raise click.ClickException("Duration command invoked without info_name")
        _do_activate(duration)


# Register common duration patterns as commands
for pattern in ["15m", "30m", "1h", "2h", "4h", "8h", "12h", "24h", "1d", "2d", "7d"]:
    panic_cli.add_command(DurationCommand(name=pattern, help=f"Activate panic mode for {pattern}"))


@panic_cli.command("status")
def cmd_status() -> None:
    """Show panic mode status."""
    if not is_panic_mode():
        console.print("\n  [green]Panic mode is not active[/green]\n")
        return

    remaining = get_panic_remaining()
    panic_until = get_panic_until()

    console.print("\n  [red bold]PANIC MODE ACTIVE[/red bold]")
    console.print(f"  Remaining: {remaining}")
    if panic_until:
        console.print(f"  Expires: {panic_until.strftime('%Y-%m-%d %H:%M')}")
    console.print()


@panic_cli.command("extend")
@click.argument("duration")
def cmd_extend(duration: str) -> None:
    """Extend panic mode duration.

    DURATION: Time to add (e.g., 30m, 1h, 1d)
    """
    if not is_panic_mode():
        console.print("\n  [red]Error: Panic mode is not active[/red]")
        console.print("  Use 'nextdns-blocker panic <duration>' to activate.\n")
        sys.exit(1)

    try:
        minutes = parse_duration(duration)
        new_until = extend_panic(minutes)

        if new_until:
            console.print("\n  [yellow]Panic mode extended[/yellow]")
            console.print(f"  Added: +{duration}")
            console.print(f"  New expiry: {new_until.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"  Remaining: {get_panic_remaining()}\n")
        else:
            console.print("\n  [red]Error: Failed to extend panic mode[/red]\n")
            sys.exit(1)

    except ValueError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


def register_panic(main_group: click.Group) -> None:
    """Register panic commands as subcommand of main CLI."""
    main_group.add_command(panic_cli, name="panic")


# Allow running standalone for testing
main = panic_cli
