"""Database command group for NextDNS Blocker.

Provides CLI commands for managing the SQLite database:
- db migrate: Migrate from JSON files to SQLite
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
from .migrate_to_sqlite import (
    check_migration_needed,
    get_audit_log_path,
    get_config_json_path,
    get_pending_json_path,
    get_retry_queue_json_path,
    get_unlock_requests_json_path,
    run_migration,
)

logger = logging.getLogger(__name__)

console = Console(highlight=False)


# =============================================================================
# DATABASE COMMAND GROUP
# =============================================================================


@click.group()
def db_cli() -> None:
    """Database management commands."""
    pass


@db_cli.command("migrate")
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without making changes")
@click.option("--skip-audit", is_flag=True, help="Skip migrating audit.log (can be large)")
@click.option("--no-backup", is_flag=True, help="Don't create backups of JSON files")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def cmd_migrate(
    dry_run: bool,
    skip_audit: bool,
    no_backup: bool,
    verbose: bool,
    yes: bool,
) -> None:
    """Migrate data from JSON files to SQLite database.

    This command migrates existing data from JSON files to the new SQLite
    database. It should be run once during the upgrade process.

    Files migrated:
    - config.json -> config, blocklist, allowlist, categories tables
    - pending.json -> pending_actions table
    - unlock_requests.json -> unlock_requests table
    - retry_queue.json -> retry_queue table
    - audit.log -> audit_log table

    Examples:
        nextdns-blocker db migrate             # Run migration
        nextdns-blocker db migrate --dry-run   # Preview changes
        nextdns-blocker db migrate --skip-audit  # Skip large audit.log
    """
    # Configure logging for verbose mode
    if verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    # Show current status
    console.print()
    console.print("  [bold]SQLite Migration[/bold]")
    console.print("  [dim]━━━━━━━━━━━━━━━━━[/dim]")
    console.print()

    # Show file locations
    console.print("  [bold]Source files:[/bold]")
    json_files = [
        ("config.json", get_config_json_path()),
        ("pending.json", get_pending_json_path()),
        ("unlock_requests.json", get_unlock_requests_json_path()),
        ("retry_queue.json", get_retry_queue_json_path()),
        ("audit.log", get_audit_log_path()),
    ]

    files_found = 0
    for name, path in json_files:
        exists = path.exists()
        if exists:
            files_found += 1
            size = path.stat().st_size
            console.print(f"    [green]✓[/green] {name} ({size:,} bytes)")
        else:
            console.print(f"    [dim]✗ {name} (not found)[/dim]")

    console.print()
    console.print(f"  [bold]Target:[/bold] {db.get_db_path()}")
    console.print()

    if files_found == 0:
        console.print("  [yellow]No JSON files found to migrate.[/yellow]")
        console.print("  [dim]Migration is only needed for existing installations.[/dim]")
        console.print()
        return

    # Check if database already has data
    if db.database_exists():
        db.init_database()
        existing_config = db.get_all_config()
        if existing_config and not dry_run:
            console.print("  [yellow]Warning: Database already contains data.[/yellow]")
            console.print("  [dim]Running migration again may create duplicates.[/dim]")
            console.print()
            if not yes and not click.confirm("  Continue anyway?", default=False):
                console.print("\n  [dim]Aborted[/dim]\n")
                return

    # Confirmation
    if not dry_run and not yes:
        if not click.confirm("  Proceed with migration?", default=True):
            console.print("\n  [dim]Aborted[/dim]\n")
            return

    console.print()

    # Run migration
    if dry_run:
        console.print("  [yellow]DRY RUN - No changes will be made[/yellow]")
        console.print()

    results = run_migration(
        dry_run=dry_run,
        skip_audit=skip_audit,
        backup=not no_backup,
    )

    # Show results
    console.print("  [bold]Migration Summary:[/bold]")
    console.print()

    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Category")
    table.add_column("Items", justify="right")

    table.add_row("Config items", str(results["config"]))
    table.add_row("Pending actions", str(results["pending_actions"]))
    table.add_row("Unlock requests", str(results["unlock_requests"]))
    table.add_row("Retry queue", str(results["retry_queue"]))
    table.add_row("Audit log entries", str(results["audit_log"]))

    console.print(table)
    console.print()

    total = sum(results.values())
    if dry_run:
        console.print(f"  Would migrate [cyan]{total}[/cyan] total items")
    else:
        console.print(f"  [green]✓[/green] Successfully migrated [cyan]{total}[/cyan] items")
        console.print()
        console.print(f"  Database size: {db.get_database_size():,} bytes")

    console.print()


@db_cli.command("dump")
@click.option("--table", "table_name", help="Dump specific table only")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option("--limit", default=50, help="Limit rows per table (default: 50)")
def cmd_dump(table_name: Optional[str], output_json: bool, limit: int) -> None:
    """Dump database contents for debugging.

    Shows the contents of all tables (or a specific table) in the SQLite
    database. Useful for debugging and verifying migration.

    Examples:
        nextdns-blocker db dump                     # Show all tables
        nextdns-blocker db dump --table config      # Show only config
        nextdns-blocker db dump --json              # Output as JSON
        nextdns-blocker db dump --limit 10          # Limit to 10 rows
    """
    if not db.database_exists():
        console.print("\n  [red]Database not found.[/red]")
        console.print(f"  [dim]Expected at: {db.get_db_path()}[/dim]")
        console.print("  [dim]Run 'nextdns-blocker db migrate' first.[/dim]\n")
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
        console.print(f"  [dim]Expected at: {db.get_db_path()}[/dim]")
        console.print("  [dim]Run 'nextdns-blocker db migrate' first.[/dim]\n")
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


@db_cli.command("check")
def cmd_check() -> None:
    """Check if migration is needed.

    Checks whether JSON files exist that need to be migrated to SQLite.
    Useful for scripts and automated checks.

    Exit codes:
        0: Migration needed or database is up to date
        1: Error checking status
    """
    needs_migration = check_migration_needed()

    console.print()
    if needs_migration:
        console.print("  [yellow]Migration needed[/yellow]")
        console.print("  [dim]Run 'nextdns-blocker db migrate' to migrate data.[/dim]")
    else:
        if db.database_exists():
            console.print("  [green]✓[/green] Database is up to date")
        else:
            console.print("  [dim]No existing data to migrate.[/dim]")
            console.print("  [dim]Database will be created on first use.[/dim]")
    console.print()


# =============================================================================
# REGISTRATION
# =============================================================================


def register_db(main_group: click.Group) -> None:
    """Register db commands as subcommand of main CLI."""
    main_group.add_command(db_cli, name="db")


# Allow running standalone for testing
main = db_cli
