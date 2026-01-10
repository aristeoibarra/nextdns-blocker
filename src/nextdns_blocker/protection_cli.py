"""CLI commands for protection features."""

import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .config import load_config
from .exceptions import ConfigurationError
from .protection import (
    DEFAULT_UNLOCK_DELAY_HOURS,
    MIN_UNLOCK_DELAY_HOURS,
    PIN_MAX_ATTEMPTS,
    PIN_REMOVAL_DELAY_HOURS,
    PIN_SESSION_DURATION_MINUTES,
    cancel_unlock_request,
    create_unlock_request,
    get_failed_attempts_count,
    get_lockout_remaining,
    get_pending_unlock_requests,
    get_pin_removal_request,
    get_pin_session_remaining,
    is_auto_panic_time,
    is_pin_enabled,
    is_pin_locked_out,
    is_pin_session_valid,
    remove_pin,
    set_pin,
    verify_pin,
)

console = Console(highlight=False)


def register_protection(main_group: click.Group) -> None:
    """Register protection commands with the main CLI group."""
    main_group.add_command(protection)


@click.group()
def protection() -> None:
    """Manage addiction protection features.

    Protection features help maintain barriers against impulsive behavior
    by requiring delays before locked items can be removed.
    """
    pass


@protection.command(name="status")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def protection_status(config_dir: Optional[Path]) -> None:
    """Show protection status and locked items."""
    try:
        config = load_config(config_dir)
        config_path = Path(config["script_dir"]) / "config.json"

        import json

        with open(config_path, encoding="utf-8") as f:
            full_config = json.load(f)

        protection_config = full_config.get("protection", {})
        auto_panic = protection_config.get("auto_panic", {})

        console.print("\n  [bold]Protection Status[/bold]")
        console.print("  [dim]━━━━━━━━━━━━━━━━━━━[/dim]\n")

        # PIN status
        if is_pin_enabled():
            if is_pin_session_valid():
                session_remaining = get_pin_session_remaining()
                console.print(f"  PIN: [green]enabled[/green] (session: {session_remaining})")
            elif is_pin_locked_out():
                lockout_remaining = get_lockout_remaining()
                console.print(f"  PIN: [red]LOCKED OUT[/red] ({lockout_remaining})")
            else:
                console.print("  PIN: [green]enabled[/green] [dim](no active session)[/dim]")
        else:
            console.print("  PIN: [dim]not enabled[/dim]")

        # Unlock delay
        delay = protection_config.get("unlock_delay_hours", DEFAULT_UNLOCK_DELAY_HOURS)
        console.print(f"  Unlock delay: [cyan]{delay}h[/cyan]")

        # Auto-panic status
        if auto_panic.get("enabled"):
            schedule = auto_panic.get("schedule", {})
            start = schedule.get("start", "23:00")
            end = schedule.get("end", "06:00")
            cannot_disable = auto_panic.get("cannot_disable", False)

            status = (
                "[green]ACTIVE NOW[/green]"
                if is_auto_panic_time(full_config)
                else "[dim]scheduled[/dim]"
            )
            lock_status = (
                "[red]cannot disable[/red]" if cannot_disable else "[dim]can disable[/dim]"
            )

            console.print(f"  Auto-panic: {status} ({start} - {end})")
            console.print(f"              {lock_status}")
        else:
            console.print("  Auto-panic: [dim]disabled[/dim]")

        # Locked categories
        console.print("\n  [bold]Locked Items[/bold]")

        nextdns = full_config.get("nextdns", {})
        locked_cats = [
            c
            for c in nextdns.get("categories", [])
            if c.get("locked") or c.get("unblock_delay") == "never"
        ]
        locked_svcs = [
            s
            for s in nextdns.get("services", [])
            if s.get("locked") or s.get("unblock_delay") == "never"
        ]

        if locked_cats:
            cat_ids = ", ".join(c["id"] for c in locked_cats)
            console.print(f"  Categories: [red]{cat_ids}[/red]")
        else:
            console.print("  Categories: [dim]none[/dim]")

        if locked_svcs:
            svc_ids = ", ".join(s["id"] for s in locked_svcs)
            console.print(f"  Services: [red]{svc_ids}[/red]")
        else:
            console.print("  Services: [dim]none[/dim]")

        # Pending unlock requests
        pending = get_pending_unlock_requests()
        if pending:
            console.print("\n  [bold]Pending Unlock Requests[/bold]")
            for req in pending:
                execute_at = datetime.fromisoformat(req["execute_at"])
                remaining = execute_at - datetime.now()
                hours = int(remaining.total_seconds() // 3600)
                mins = int((remaining.total_seconds() % 3600) // 60)

                console.print(
                    f"  [yellow]•[/yellow] {req['item_type']}:{req['item_id']} "
                    f"- [cyan]{hours}h {mins}m remaining[/cyan] "
                    f"(ID: {req['id']})"
                )

        console.print()

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)


@protection.command(name="unlock-request")
@click.argument("item_id")
@click.option(
    "--type",
    "item_type",
    type=click.Choice(["category", "service", "domain"]),
    default="category",
    help="Type of item to unlock",
)
@click.option(
    "--reason",
    type=str,
    help="Reason for unlock request (for audit log)",
)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def unlock_request(
    item_id: str, item_type: str, reason: Optional[str], config_dir: Optional[Path]
) -> None:
    """Request to unlock a protected item.

    Creates a pending request that will be executable after the configured
    delay period (default: 48 hours). You can cancel the request at any
    time before it's executed.
    """
    try:
        config = load_config(config_dir)
        config_path = Path(config["script_dir"]) / "config.json"

        import json

        with open(config_path, encoding="utf-8") as f:
            full_config = json.load(f)

        protection_config = full_config.get("protection", {})
        delay_hours = protection_config.get("unlock_delay_hours", DEFAULT_UNLOCK_DELAY_HOURS)

        # Enforce minimum
        delay_hours = max(delay_hours, MIN_UNLOCK_DELAY_HOURS)

        # Check if item exists and is locked
        found = False
        is_locked = False

        if item_type == "category":
            for cat in full_config.get("nextdns", {}).get("categories", []):
                if cat.get("id") == item_id:
                    found = True
                    is_locked = cat.get("locked") or cat.get("unblock_delay") == "never"
                    break
        elif item_type == "service":
            for svc in full_config.get("nextdns", {}).get("services", []):
                if svc.get("id") == item_id:
                    found = True
                    is_locked = svc.get("locked") or svc.get("unblock_delay") == "never"
                    break

        if not found:
            console.print(f"\n  [red]Error: {item_type} '{item_id}' not found[/red]\n")
            sys.exit(1)

        if not is_locked:
            console.print(
                f"\n  [yellow]'{item_id}' is not locked. You can remove it directly.[/yellow]\n"
            )
            return

        # Check for existing pending request
        pending = get_pending_unlock_requests()
        for req in pending:
            if req["item_type"] == item_type and req["item_id"] == item_id:
                execute_at = datetime.fromisoformat(req["execute_at"])
                remaining = execute_at - datetime.now()
                hours = int(remaining.total_seconds() // 3600)

                console.print(
                    f"\n  [yellow]Unlock request already pending for '{item_id}'[/yellow]"
                )
                console.print(f"  Remaining: {hours}h")
                console.print(f"  ID: {req['id']}")
                console.print(f"\n  Use 'ndb protection cancel {req['id']}' to cancel\n")
                return

        # Create the request
        request = create_unlock_request(item_type, item_id, delay_hours, reason)

        execute_at = datetime.fromisoformat(request["execute_at"])

        console.print("\n  [yellow]Unlock request created[/yellow]")
        console.print(f"  Item: {item_type}:{item_id}")
        console.print(f"  Delay: {delay_hours} hours")
        console.print(f"  Execute at: {execute_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"  Request ID: {request['id']}")
        console.print("\n  [dim]You can cancel this request anytime with:[/dim]")
        console.print(f"  [cyan]ndb protection cancel {request['id']}[/cyan]\n")

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n", highlight=False)
        sys.exit(1)


@protection.command(name="cancel")
@click.argument("request_id")
def cancel_request(request_id: str) -> None:
    """Cancel a pending unlock request.

    You can provide a partial request ID (first few characters).
    """
    if cancel_unlock_request(request_id):
        console.print(f"\n  [green]Unlock request '{request_id}' cancelled[/green]\n")
    else:
        console.print(f"\n  [red]Request '{request_id}' not found or already processed[/red]\n")
        sys.exit(1)


@protection.command(name="list")
def list_requests() -> None:
    """List all pending unlock requests."""
    pending = get_pending_unlock_requests()

    if not pending:
        console.print("\n  [dim]No pending unlock requests[/dim]\n")
        return

    console.print("\n  [bold]Pending Unlock Requests[/bold]\n")

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Item")
    table.add_column("Remaining")
    table.add_column("Execute At")

    for req in pending:
        execute_at = datetime.fromisoformat(req["execute_at"])
        remaining = execute_at - datetime.now()
        hours = int(remaining.total_seconds() // 3600)
        mins = int((remaining.total_seconds() % 3600) // 60)

        table.add_row(
            req["id"],
            req["item_type"],
            req["item_id"],
            f"{hours}h {mins}m",
            execute_at.strftime("%Y-%m-%d %H:%M"),
        )

    console.print(table)
    console.print()


# =============================================================================
# PIN COMMANDS
# =============================================================================


@protection.group(name="pin")
def pin_group() -> None:
    """Manage PIN protection for sensitive commands.

    PIN protection adds an authentication layer to dangerous commands
    like unblock, pause, and config edit. Once enabled, these commands
    will require PIN verification before execution.
    """
    pass


@pin_group.command(name="set")
def pin_set() -> None:
    """Set or change the protection PIN.

    You will be prompted to enter and confirm your PIN.
    The PIN must be at least 4 characters.

    If PIN is already set, you must verify the current PIN first.
    """
    # Check if PIN already exists
    if is_pin_enabled():
        console.print("\n  [yellow]PIN protection is already enabled.[/yellow]")
        console.print("  You must verify your current PIN to change it.\n")

        current = click.prompt("  Current PIN", hide_input=True)
        if not verify_pin(current):
            if is_pin_locked_out():
                remaining = get_lockout_remaining()
                console.print(
                    f"\n  [red]Too many failed attempts. Locked out for {remaining}[/red]\n"
                )
            else:
                attempts_left = PIN_MAX_ATTEMPTS - get_failed_attempts_count()
                console.print(
                    f"\n  [red]Incorrect PIN. {attempts_left} attempts remaining.[/red]\n"
                )
            sys.exit(1)

    # Get new PIN
    console.print()
    new_pin = click.prompt(
        "  New PIN",
        hide_input=True,
        confirmation_prompt="  Confirm PIN",
    )

    try:
        set_pin(new_pin)
        console.print("\n  [green]PIN protection enabled[/green]")
        console.print(f"  Session duration: {PIN_SESSION_DURATION_MINUTES} minutes")
        console.print(f"  Max attempts before lockout: {PIN_MAX_ATTEMPTS}")
        console.print("\n  [dim]Protected commands now require PIN verification.[/dim]\n")
    except ValueError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@pin_group.command(name="remove")
def pin_remove() -> None:
    """Remove PIN protection.

    For safety, PIN removal has a 24-hour delay. This prevents
    impulsive disabling during moments of weakness.

    You can cancel the removal request during this period.
    """
    if not is_pin_enabled():
        console.print("\n  [dim]PIN protection is not enabled.[/dim]\n")
        return

    # Check for existing removal request
    existing = get_pin_removal_request()
    if existing:
        execute_at = datetime.fromisoformat(existing["execute_at"])
        time_remaining = execute_at - datetime.now()
        hours = int(time_remaining.total_seconds() // 3600)
        mins = int((time_remaining.total_seconds() % 3600) // 60)

        console.print("\n  [yellow]PIN removal already pending[/yellow]")
        console.print(f"  Remaining: {hours}h {mins}m")
        console.print(f"  Request ID: {existing['id']}")
        console.print(f"\n  Use 'ndb protection cancel {existing['id']}' to cancel\n")
        return

    console.print("\n  [yellow]PIN Removal Request[/yellow]")
    console.print(f"  This will disable PIN protection after {PIN_REMOVAL_DELAY_HOURS}h delay.")
    console.print("  You can cancel this request anytime during the delay period.\n")

    current = click.prompt("  Enter current PIN to confirm", hide_input=True)

    if is_pin_locked_out():
        lockout_remaining = get_lockout_remaining()
        console.print(
            f"\n  [red]Too many failed attempts. Locked out for {lockout_remaining}[/red]\n"
        )
        sys.exit(1)

    if remove_pin(current):
        request = get_pin_removal_request()
        if request:
            execute_at = datetime.fromisoformat(request["execute_at"])
            console.print("\n  [yellow]PIN removal scheduled[/yellow]")
            console.print(f"  Execute at: {execute_at.strftime('%Y-%m-%d %H:%M')}")
            console.print(f"  Request ID: {request['id']}")
            console.print("\n  [dim]Cancel with:[/dim]")
            console.print(f"  [cyan]ndb protection cancel {request['id']}[/cyan]\n")
    else:
        attempts_left = PIN_MAX_ATTEMPTS - get_failed_attempts_count()
        console.print(f"\n  [red]Incorrect PIN. {attempts_left} attempts remaining.[/red]\n")
        sys.exit(1)


@pin_group.command(name="status")
def pin_status() -> None:
    """Show PIN protection status."""
    console.print("\n  [bold]PIN Protection Status[/bold]")
    console.print("  [dim]━━━━━━━━━━━━━━━━━━━━━[/dim]\n")

    if not is_pin_enabled():
        console.print("  Status: [dim]not enabled[/dim]")
        console.print("\n  [dim]Enable with: ndb protection pin set[/dim]\n")
        return

    console.print("  Status: [green]enabled[/green]")

    # Session status
    if is_pin_session_valid():
        remaining = get_pin_session_remaining()
        console.print(f"  Session: [green]active[/green] ({remaining} remaining)")
    else:
        console.print("  Session: [dim]expired[/dim]")

    # Lockout status
    if is_pin_locked_out():
        remaining = get_lockout_remaining()
        console.print(f"  Lockout: [red]LOCKED[/red] ({remaining} remaining)")
    else:
        attempts = get_failed_attempts_count()
        if attempts > 0:
            console.print(f"  Failed attempts: [yellow]{attempts}/{PIN_MAX_ATTEMPTS}[/yellow]")

    # Pending removal
    removal = get_pin_removal_request()
    if removal:
        execute_at = datetime.fromisoformat(removal["execute_at"])
        time_remaining = execute_at - datetime.now()
        hours = int(time_remaining.total_seconds() // 3600)
        mins = int((time_remaining.total_seconds() % 3600) // 60)
        console.print(f"\n  [yellow]Removal pending: {hours}h {mins}m[/yellow]")
        console.print(f"  Cancel with: ndb protection cancel {removal['id']}")

    console.print()


@pin_group.command(name="verify")
def pin_verify() -> None:
    """Verify PIN and create a new session.

    Use this to pre-authenticate before running multiple
    protected commands.
    """
    if not is_pin_enabled():
        console.print("\n  [dim]PIN protection is not enabled.[/dim]\n")
        return

    if is_pin_locked_out():
        remaining = get_lockout_remaining()
        console.print(f"\n  [red]Too many failed attempts. Locked out for {remaining}[/red]\n")
        sys.exit(1)

    if is_pin_session_valid():
        remaining = get_pin_session_remaining()
        console.print(f"\n  [green]Session already active ({remaining} remaining)[/green]\n")
        return

    pin = click.prompt("\n  Enter PIN", hide_input=True)

    if verify_pin(pin):
        remaining = get_pin_session_remaining()
        console.print(f"\n  [green]PIN verified. Session active for {remaining}[/green]\n")
    else:
        if is_pin_locked_out():
            remaining = get_lockout_remaining()
            console.print(f"\n  [red]Too many failed attempts. Locked out for {remaining}[/red]\n")
        else:
            attempts_left = PIN_MAX_ATTEMPTS - get_failed_attempts_count()
            console.print(f"\n  [red]Incorrect PIN. {attempts_left} attempts remaining.[/red]\n")
        sys.exit(1)
