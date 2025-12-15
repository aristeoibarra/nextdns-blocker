"""Pending command group for NextDNS Blocker."""

from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .pending import (
    cancel_pending_action,
    get_pending_actions,
)

console = Console(highlight=False)


@click.group()
def pending_cli() -> None:
    """Manage pending unblock actions."""
    pass


@pending_cli.command("list")
@click.option("--all", "show_all", is_flag=True, help="Show all actions including executed")
def cmd_list(show_all: bool) -> None:
    """List pending unblock actions."""
    status_filter = None if show_all else "pending"
    actions = get_pending_actions(status=status_filter)

    if not actions:
        console.print("\n  [dim]No pending actions[/dim]\n")
        return

    table = Table(title="Pending Actions", show_header=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Domain", style="white")
    table.add_column("Delay", style="yellow")
    table.add_column("Execute At", style="green")
    table.add_column("Status", style="blue")

    now = datetime.now()
    for action in actions:
        try:
            execute_at = datetime.fromisoformat(action["execute_at"])
            remaining = execute_at - now

            if remaining.total_seconds() > 0:
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                time_str = f"{execute_at.strftime('%H:%M')} ({hours}h {minutes}m)"
            else:
                time_str = "[green]READY[/green]"

            # Truncate ID for display (show last 12 chars)
            display_id = action["id"][-12:]

            table.add_row(
                display_id,
                action["domain"],
                action["delay"],
                time_str,
                action["status"],
            )
        except (KeyError, ValueError):
            # Skip malformed actions
            continue

    console.print()
    console.print(table)
    console.print()


@pending_cli.command("show")
@click.argument("action_id")
def cmd_show(action_id: str) -> None:
    """Show details of a pending action."""
    # Support partial ID matching
    actions = get_pending_actions()
    matching = [a for a in actions if a["id"].endswith(action_id) or a["id"] == action_id]

    if not matching:
        console.print(f"\n  [red]Error: No action found matching '{action_id}'[/red]\n")
        return

    if len(matching) > 1:
        console.print("\n  [yellow]Multiple matches found. Please be more specific:[/yellow]")
        for a in matching:
            console.print(f"    {a['id']}")
        console.print()
        return

    action = matching[0]

    console.print("\n  [bold]Pending Action Details[/bold]")
    console.print("  [bold]----------------------[/bold]")
    console.print(f"  ID:          {action['id']}")
    console.print(f"  Domain:      {action['domain']}")
    console.print(f"  Action:      {action['action']}")
    console.print(f"  Delay:       {action['delay']}")
    console.print(f"  Status:      {action['status']}")
    console.print(f"  Created:     {action['created_at']}")
    console.print(f"  Execute At:  {action['execute_at']}")
    console.print(f"  Requested:   {action.get('requested_by', 'unknown')}")

    # Show time remaining
    if action["status"] == "pending":
        now = datetime.now()
        execute_at = datetime.fromisoformat(action["execute_at"])
        remaining = execute_at - now
        if remaining.total_seconds() > 0:
            hours, remainder = divmod(int(remaining.total_seconds()), 3600)
            minutes = remainder // 60
            console.print(f"\n  [yellow]Time remaining: {hours}h {minutes}m[/yellow]")
        else:
            console.print("\n  [green]Ready for execution[/green]")

    console.print()


@pending_cli.command("cancel")
@click.argument("action_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_cancel(action_id: str, yes: bool, config_dir: Optional[Path]) -> None:
    """Cancel a pending unblock action."""
    from .config import load_config
    from .notifications import send_discord_notification

    # Support partial ID matching
    actions = get_pending_actions(status="pending")
    matching = [a for a in actions if a["id"].endswith(action_id) or a["id"] == action_id]

    if not matching:
        console.print(f"\n  [red]Error: No pending action found matching '{action_id}'[/red]\n")
        return

    if len(matching) > 1:
        console.print("\n  [yellow]Multiple matches found. Please be more specific:[/yellow]")
        for a in matching:
            console.print(f"    {a['id']} ({a['domain']})")
        console.print()
        return

    action = matching[0]

    if not yes:
        console.print(f"\n  Cancel unblock for [bold]{action['domain']}[/bold]?")
        if not click.confirm("  Proceed?"):
            console.print("  Cancelled.\n")
            return

    if cancel_pending_action(action["id"]):
        # Load config for webhook URL if needed
        webhook_url = None
        try:
            config = load_config(config_dir)
            webhook_url = config.get("discord_webhook_url")
        except Exception:
            pass

        # Send notification
        send_discord_notification(
            domain=action["domain"],
            event_type="cancel_pending",
            webhook_url=webhook_url,
        )

        console.print(f"\n  [green]Cancelled pending unblock for {action['domain']}[/green]\n")
    else:
        console.print("\n  [red]Error: Failed to cancel action[/red]\n")


def register_pending(main_group: click.Group) -> None:
    """Register pending commands as subcommand of main CLI."""
    main_group.add_command(pending_cli, name="pending")


# Allow running standalone for testing
main = pending_cli
