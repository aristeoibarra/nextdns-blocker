"""Database command group for NextDNS Blocker.

Provides CLI commands for managing the SQLite database:
- db dump: Inspect database contents
- db stats: Show database statistics
"""

import json
import logging
import sys
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from . import database as db

logger = logging.getLogger(__name__)

console = Console(highlight=False)


# =============================================================================
# DATABASE COMMAND GROUP
# =============================================================================


@click.group()
def db_cli() -> None:
    """Database management commands."""
    pass


@db_cli.command("dump")
@click.option("--table", "table_name", help="Dump specific table only")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option("--limit", default=50, help="Limit rows per table (default: 50)")
def cmd_dump(table_name: Optional[str], output_json: bool, limit: int) -> None:
    """Dump database contents for debugging.

    Shows the contents of all tables (or a specific table) in the SQLite
    database. Useful for debugging and verification.

    Examples:
        nextdns-blocker db dump                     # Show all tables
        nextdns-blocker db dump --table config      # Show only config
        nextdns-blocker db dump --json              # Output as JSON
        nextdns-blocker db dump --limit 10          # Limit to 10 rows
    """
    if not db.database_exists():
        console.print("\n  [red]Database not found.[/red]")
        console.print(f"  [dim]Expected at: {db.get_db_path()}[/dim]\n")
        sys.exit(1)

    db.init_database()

    # Get list of tables
    conn = db.get_connection()
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    if table_name:
        if table_name not in tables:
            console.print(f"\n  [red]Table '{table_name}' not found.[/red]")
            console.print(f"  [dim]Available tables: {', '.join(tables)}[/dim]\n")
            sys.exit(1)
        tables = [table_name]

    result = {}

    for tbl in tables:
        # Get column names
        cursor = conn.execute(f"PRAGMA table_info({tbl})")  # noqa: S608  # nosec B608
        columns = [row[1] for row in cursor.fetchall()]

        # Get row count
        cursor = conn.execute(f"SELECT COUNT(*) FROM {tbl}")  # noqa: S608  # nosec B608
        total_count = cursor.fetchone()[0]

        # Get rows (with limit)
        cursor = conn.execute(f"SELECT * FROM {tbl} LIMIT ?", (limit,))  # noqa: S608  # nosec B608
        rows = cursor.fetchall()

        result[tbl] = {
            "columns": columns,
            "total_count": total_count,
            "rows": [dict(zip(columns, row)) for row in rows],
        }

    if output_json:
        print(json.dumps(result, indent=2, default=str))
        return

    # Rich output
    console.print()
    console.print("  [bold]Database Dump[/bold]")
    console.print("  [dim]━━━━━━━━━━━━━━[/dim]")
    console.print()
    console.print(f"  [dim]Path: {db.get_db_path()}[/dim]")
    console.print()

    for tbl, data in result.items():
        total = data["total_count"]
        shown = len(data["rows"])

        console.print(f"  [bold]{tbl}[/bold] ({total} rows)")

        if not data["rows"]:
            console.print("    [dim](empty)[/dim]")
            console.print()
            continue

        # Create table
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))

        for col in data["columns"]:
            table.add_column(col, overflow="fold", max_width=40)

        for row in data["rows"]:
            # Truncate long values
            values = []
            for col in data["columns"]:
                val = row[col]
                if val is None:
                    values.append("[dim]null[/dim]")
                elif isinstance(val, str) and len(val) > 40:
                    values.append(val[:37] + "...")
                else:
                    values.append(str(val))
            table.add_row(*values)

        console.print(table)

        if shown < total:
            console.print(f"    [dim]... and {total - shown} more rows[/dim]")

        console.print()


@db_cli.command("stats")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def cmd_stats(output_json: bool) -> None:
    """Show database statistics.

    Displays statistics about the SQLite database including:
    - Database file size
    - Row counts per table
    - Recent activity summary

    Examples:
        nextdns-blocker db stats           # Show stats
        nextdns-blocker db stats --json    # Output as JSON
    """
    if not db.database_exists():
        console.print("\n  [red]Database not found.[/red]")
        console.print(f"  [dim]Expected at: {db.get_db_path()}[/dim]\n")
        sys.exit(1)

    db.init_database()

    # Gather statistics
    stats: dict[str, Any] = {
        "database_path": str(db.get_db_path()),
        "database_size_bytes": db.get_database_size(),
        "tables": {},
    }

    conn = db.get_connection()

    # Get table statistics
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]

    for tbl in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {tbl}")  # noqa: S608  # nosec B608
        count = cursor.fetchone()[0]
        stats["tables"][tbl] = {"row_count": count}

    # Get recent audit log activity
    try:
        cursor = conn.execute(
            "SELECT event_type, COUNT(*) FROM audit_log "
            "WHERE created_at > datetime('now', '-7 days') "
            "GROUP BY event_type ORDER BY COUNT(*) DESC LIMIT 5"
        )
        recent_activity = {row[0]: row[1] for row in cursor.fetchall()}
        stats["recent_activity_7d"] = recent_activity
    except Exception:
        stats["recent_activity_7d"] = {}

    # Get pending action counts
    try:
        cursor = conn.execute("SELECT status, COUNT(*) FROM pending_actions GROUP BY status")
        pending_stats = {row[0]: row[1] for row in cursor.fetchall()}
        stats["pending_actions_by_status"] = pending_stats
    except Exception:
        stats["pending_actions_by_status"] = {}

    if output_json:
        print(json.dumps(stats, indent=2))
        return

    # Rich output
    console.print()
    console.print("  [bold]Database Statistics[/bold]")
    console.print("  [dim]━━━━━━━━━━━━━━━━━━━[/dim]")
    console.print()

    console.print(f"  [bold]Location:[/bold] {stats['database_path']}")
    console.print(f"  [bold]Size:[/bold] {stats['database_size_bytes']:,} bytes")
    console.print()

    # Table counts
    console.print("  [bold]Tables:[/bold]")

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Table")
    table.add_column("Rows", justify="right")

    for tbl, data in sorted(stats["tables"].items()):
        table.add_row(tbl, str(data["row_count"]))

    console.print(table)
    console.print()

    # Recent activity
    if stats["recent_activity_7d"]:
        console.print("  [bold]Recent Activity (7 days):[/bold]")
        for event, count in stats["recent_activity_7d"].items():
            console.print(f"    {event}: {count}")
        console.print()

    # Pending actions
    if stats["pending_actions_by_status"]:
        console.print("  [bold]Pending Actions:[/bold]")
        for status, count in stats["pending_actions_by_status"].items():
            console.print(f"    {status}: {count}")
        console.print()


# =============================================================================
# REGISTRATION
# =============================================================================


def register_db(main_group: click.Group) -> None:
    """Register db commands as subcommand of main CLI."""
    main_group.add_command(db_cli, name="db")


# Allow running standalone for testing
main = db_cli
