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
    cancel_unlock_request,
    create_unlock_request,
    get_pending_unlock_requests,
    is_auto_panic_time,
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
