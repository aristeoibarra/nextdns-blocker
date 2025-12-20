"""Pending command group for NextDNS Blocker."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from .completion import complete_pending_action_ids
from .pending import (
    cancel_pending_action,
    get_pending_actions,
)

logger = logging.getLogger(__name__)

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
            display_id = action.get("id", "-")[-12:] if action.get("id") else "-"

            table.add_row(
                display_id,
                action.get("domain", "-"),
                action.get("delay", "-"),
                time_str,
                action.get("status", "-"),
            )
        except (KeyError, ValueError) as e:
            # Skip malformed actions but log for debugging
            logger.debug(f"Skipping malformed pending action: {e}")
            continue

    console.print()
    console.print(table)
    console.print()


@pending_cli.command("show")
@click.argument("action_id", shell_complete=complete_pending_action_ids)
def cmd_show(action_id: str) -> None:
    """Show details of a pending action."""
    # Support partial ID matching
    actions = get_pending_actions()
    matching = [
        a for a in actions if a.get("id", "").endswith(action_id) or a.get("id", "") == action_id
    ]

    if not matching:
        console.print(f"\n  [red]Error: No action found matching '{action_id}'[/red]\n")
        return

    if len(matching) > 1:
        console.print("\n  [yellow]Multiple matches found. Please be more specific:[/yellow]")
        for a in matching:
            console.print(f"    {a.get('id', '-')}")
        console.print()
        return

    action = matching[0]

    console.print("\n  [bold]Pending Action Details[/bold]")
    console.print("  [bold]----------------------[/bold]")
    console.print(f"  ID:          {action.get('id', '-')}")
    console.print(f"  Domain:      {action.get('domain', '-')}")
    console.print(f"  Action:      {action.get('action', '-')}")
    console.print(f"  Delay:       {action.get('delay', '-')}")
    console.print(f"  Status:      {action.get('status', '-')}")
    console.print(f"  Created:     {action.get('created_at', '-')}")
    console.print(f"  Execute At:  {action.get('execute_at', '-')}")
    console.print(f"  Requested:   {action.get('requested_by', 'unknown')}")

    # Show time remaining
    if action.get("status") == "pending":
        try:
            now = datetime.now()
            execute_at_str = action.get("execute_at", "")
            if execute_at_str:
                execute_at = datetime.fromisoformat(execute_at_str)
                remaining = execute_at - now
                if remaining.total_seconds() > 0:
                    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                    minutes = remainder // 60
                    console.print(f"\n  [yellow]Time remaining: {hours}h {minutes}m[/yellow]")
                else:
                    console.print("\n  [green]Ready for execution[/green]")
        except (ValueError, KeyError) as e:
            # Invalid datetime format - log for debugging
            logger.debug(f"Could not parse execute_at datetime: {e}")

    console.print()


@pending_cli.command("cancel")
@click.argument("action_id", shell_complete=complete_pending_action_ids)
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_cancel(action_id: str, yes: bool, config_dir: Optional[Path]) -> None:
    """Cancel a pending unblock action."""
    import sys

    from .panic import is_panic_mode

    # Block cancel during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot cancel pending actions during panic mode[/red]\n")
        sys.exit(1)

    from .config import load_config
    from .notifications import send_discord_notification

    # Support partial ID matching
    actions = get_pending_actions(status="pending")
    matching = [
        a for a in actions if a.get("id", "").endswith(action_id) or a.get("id", "") == action_id
    ]

    if not matching:
        console.print(f"\n  [red]Error: No pending action found matching '{action_id}'[/red]\n")
        return

    if len(matching) > 1:
        console.print("\n  [yellow]Multiple matches found. Please be more specific:[/yellow]")
        for a in matching:
            domain = a.get("domain", "unknown")
            console.print(f"    {a.get('id', '-')} ({domain})")
        console.print()
        return

    action = matching[0]

    if not yes:
        domain = action.get("domain", "unknown")
        console.print(f"\n  Cancel unblock for [bold]{domain}[/bold]?")
        if not click.confirm("  Proceed?"):
            console.print("  Cancelled.\n")
            return

    if cancel_pending_action(action.get("id", "")):
        # Load config for webhook URL if needed
        webhook_url = None
        try:
            config = load_config(config_dir)
            webhook_url = config.get("discord_webhook_url")
        except (OSError, ValueError, KeyError) as e:
            # Ignore errors loading config; Discord notification is optional
            logger.debug(f"Could not load config for webhook: {e}")

        # Send notification
        send_discord_notification(
            domain=action.get("domain", "unknown"),
            event_type="cancel_pending",
            webhook_url=webhook_url,
        )

        console.print(
            f"\n  [green]Cancelled pending unblock for {action.get('domain', 'unknown')}[/green]\n"
        )
    else:
        console.print("\n  [red]Error: Failed to cancel action[/red]\n")


def register_pending(main_group: click.Group) -> None:
    """Register pending commands as subcommand of main CLI."""
    main_group.add_command(pending_cli, name="pending")


# Allow running standalone for testing
main = pending_cli
