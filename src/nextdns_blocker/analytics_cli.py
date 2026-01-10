"""Analytics CLI commands for NextDNS Blocker.

Provides commands for viewing usage statistics, patterns,
and exporting data to CSV.
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .analytics import AnalyticsManager, HourlyPattern

logger = logging.getLogger(__name__)

console = Console(highlight=False)


# =============================================================================
# VISUALIZATION HELPERS
# =============================================================================


def _create_bar(count: int, max_count: int, width: int = 20) -> str:
    """Create an ASCII bar chart segment."""
    if max_count == 0:
        return ""
    filled = int((count / max_count) * width)
    return "\u2588" * filled + "\u2591" * (width - filled)


def _get_effectiveness_color(score: float) -> str:
    """Get color for effectiveness score."""
    if score >= 80:
        return "green"
    elif score >= 50:
        return "yellow"
    else:
        return "red"


def _get_activity_level(count: int, max_count: int) -> tuple[str, str]:
    """Get activity level label and color."""
    if max_count == 0:
        return "none", "dim"

    ratio = count / max_count
    if ratio >= 0.75:
        return "peak", "red"
    elif ratio >= 0.5:
        return "high", "yellow"
    elif ratio >= 0.25:
        return "medium", "blue"
    else:
        return "low", "dim"


# =============================================================================
# STATS COMMAND GROUP
# =============================================================================


@click.group(invoke_without_command=True)
@click.option("--days", default=7, help="Number of days to analyze (default: 7)")
@click.option("--domain", help="Filter statistics by domain")
@click.pass_context
def stats(ctx: click.Context, days: int, domain: Optional[str]) -> None:
    """Show usage statistics and patterns.

    Without subcommand, shows a summary of blocking statistics.

    Examples:
        ndb stats              # Show 7-day summary
        ndb stats --days 30    # Show 30-day summary
        ndb stats --domain youtube  # Filter by domain
        ndb stats export -o data.csv  # Export to CSV
    """
    # Store options in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["days"] = days
    ctx.obj["domain"] = domain

    # If no subcommand, show summary
    if ctx.invoked_subcommand is None:
        _show_summary(days, domain)


def _show_summary(days: int, domain: Optional[str]) -> None:
    """Display the main statistics summary."""
    manager = AnalyticsManager()

    if domain:
        _show_domain_summary(manager, domain, days)
    else:
        _show_overall_summary(manager, days)


def _show_overall_summary(manager: AnalyticsManager, days: int) -> None:
    """Display overall statistics summary."""
    overall = manager.get_overall_statistics(days=days)

    if overall.total_entries == 0:
        console.print("\n  [dim]No activity recorded in the last {days} days[/dim]\n")
        return

    # Header
    console.print()
    title = f"NextDNS Blocker Statistics (last {days} days)"
    console.print(Panel(f"[bold]{title}[/bold]", expand=False))

    # Overall stats
    console.print("\n  [bold]Summary[/bold]")
    console.print(f"    Total entries: [cyan]{overall.total_entries}[/cyan]")
    console.print(f"    Unique domains: [cyan]{overall.unique_domains}[/cyan]")

    if overall.date_range_start and overall.date_range_end:
        start = overall.date_range_start.strftime("%Y-%m-%d")
        end = overall.date_range_end.strftime("%Y-%m-%d")
        console.print(f"    Date range: [dim]{start} to {end}[/dim]")

    # Action breakdown
    console.print("\n  [bold]Actions[/bold]")
    console.print(f"    Blocks: [red]{overall.total_blocks}[/red]")
    console.print(f"    Unblocks: [green]{overall.total_unblocks}[/green]")
    console.print(f"    Allows: [blue]{overall.total_allows}[/blue]")
    console.print(f"    Disallows: [yellow]{overall.total_disallows}[/yellow]")

    if overall.total_pauses > 0 or overall.total_resumes > 0:
        console.print(f"    Pauses: [magenta]{overall.total_pauses}[/magenta]")
        console.print(f"    Resumes: [magenta]{overall.total_resumes}[/magenta]")

    if overall.total_panic_activations > 0:
        console.print(
            f"    Panic activations: [red bold]{overall.total_panic_activations}[/red bold]"
        )

    # Effectiveness score
    score = overall.effectiveness_score
    color = _get_effectiveness_color(score)
    console.print(f"\n  [bold]Effectiveness Score: [{color}]{score:.0f}%[/{color}][/bold]")
    console.print("    [dim](blocks maintained / total blocks)[/dim]")

    # Top blocked domains
    top_domains = manager.get_top_blocked_domains(limit=5, days=days)
    if top_domains:
        console.print("\n  [bold]Top Blocked Domains[/bold]")
        max_blocks = max(d.block_count for d in top_domains)

        for i, domain_stat in enumerate(top_domains, 1):
            bar = _create_bar(domain_stat.block_count, max_blocks, width=12)
            console.print(f"    {i}. {domain_stat.domain:20} {bar} {domain_stat.block_count}")

    # Hourly patterns
    patterns = manager.get_hourly_patterns(days=days)
    if any(p.total_activity > 0 for p in patterns):
        _show_hourly_patterns(patterns)

    console.print()


def _show_domain_summary(manager: AnalyticsManager, domain: str, days: int) -> None:
    """Display statistics for a specific domain."""
    stats = manager.get_domain_stats(domain, days=days)

    if stats is None:
        console.print(f"\n  [dim]No activity for '{domain}' in the last {days} days[/dim]\n")
        return

    console.print()
    title = f"Statistics for {stats.domain} (last {days} days)"
    console.print(Panel(f"[bold]{title}[/bold]", expand=False))

    console.print("\n  [bold]Activity[/bold]")
    console.print(f"    Blocks: [red]{stats.block_count}[/red]")
    console.print(f"    Unblocks: [green]{stats.unblock_count}[/green]")
    console.print(f"    Allows: [blue]{stats.allow_count}[/blue]")
    console.print(f"    Disallows: [yellow]{stats.disallow_count}[/yellow]")

    if stats.pending_created > 0:
        console.print("\n  [bold]Pending Actions[/bold]")
        console.print(f"    Created: {stats.pending_created}")
        console.print(f"    Cancelled: {stats.pending_cancelled}")
        console.print(f"    Executed: {stats.pending_executed}")

    if stats.last_blocked:
        console.print(
            f"\n  Last blocked: [dim]{stats.last_blocked.strftime('%Y-%m-%d %H:%M')}[/dim]"
        )
    if stats.last_unblocked:
        console.print(
            f"  Last unblocked: [dim]{stats.last_unblocked.strftime('%Y-%m-%d %H:%M')}[/dim]"
        )

    score = stats.effectiveness_score
    color = _get_effectiveness_color(score)
    console.print(f"\n  [bold]Effectiveness Score: [{color}]{score:.0f}%[/{color}][/bold]")

    console.print()


def _show_hourly_patterns(patterns: list[HourlyPattern]) -> None:
    """Display hourly activity patterns."""
    console.print("\n  [bold]Activity by Hour[/bold]")

    max_activity = max(p.total_activity for p in patterns)

    # Group hours into 6-hour blocks for compact display
    hour_ranges = [
        (0, 6, "00-06"),
        (6, 12, "06-12"),
        (12, 18, "12-18"),
        (18, 24, "18-24"),
    ]

    for start, end, label in hour_ranges:
        total = sum(patterns[h].total_activity for h in range(start, end))
        bar = _create_bar(total, max_activity * 6, width=8)
        level, color = _get_activity_level(total, max_activity * 6)
        console.print(f"    {label}: {bar} [{color}]({level})[/{color}]")


# =============================================================================
# SUBCOMMANDS
# =============================================================================


@stats.command("export")
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False, path_type=Path),
    required=True,
    help="Output CSV file path",
)
@click.pass_context
def stats_export(ctx: click.Context, output: Path) -> None:
    """Export statistics to CSV file.

    Example:
        ndb stats export -o ~/stats.csv
        ndb stats export -o data.csv --days 30
    """
    days = ctx.obj.get("days", 7)
    manager = AnalyticsManager()

    if manager.export_csv(output, days=days):
        console.print(f"\n  [green]Exported to {output}[/green]\n")
    else:
        console.print(f"\n  [red]Failed to export to {output}[/red]\n")


@stats.command("domains")
@click.option("--limit", default=10, help="Number of domains to show (default: 10)")
@click.pass_context
def stats_domains(ctx: click.Context, limit: int) -> None:
    """Show top blocked domains with details.

    Example:
        ndb stats domains
        ndb stats domains --limit 20
    """
    days = ctx.obj.get("days", 7)
    manager = AnalyticsManager()
    top_domains = manager.get_top_blocked_domains(limit=limit, days=days)

    if not top_domains:
        console.print(f"\n  [dim]No blocked domains in the last {days} days[/dim]\n")
        return

    console.print()
    table = Table(title=f"Top {len(top_domains)} Blocked Domains (last {days} days)")
    table.add_column("#", style="dim", width=3)
    table.add_column("Domain", style="white")
    table.add_column("Blocks", style="red", justify="right")
    table.add_column("Unblocks", style="green", justify="right")
    table.add_column("Effectiveness", justify="right")

    for i, domain_stat in enumerate(top_domains, 1):
        score = domain_stat.effectiveness_score
        color = _get_effectiveness_color(score)
        effectiveness = f"[{color}]{score:.0f}%[/{color}]"

        table.add_row(
            str(i),
            domain_stat.domain,
            str(domain_stat.block_count),
            str(domain_stat.unblock_count),
            effectiveness,
        )

    console.print(table)
    console.print()


@stats.command("hours")
@click.pass_context
def stats_hours(ctx: click.Context) -> None:
    """Show detailed hourly activity patterns.

    Example:
        ndb stats hours
        ndb stats hours --days 30
    """
    days = ctx.obj.get("days", 7)
    manager = AnalyticsManager()
    patterns = manager.get_hourly_patterns(days=days)

    max_activity = max(p.total_activity for p in patterns)

    if max_activity == 0:
        console.print(f"\n  [dim]No activity in the last {days} days[/dim]\n")
        return

    console.print()
    console.print(Panel(f"[bold]Hourly Activity (last {days} days)[/bold]", expand=False))
    console.print()

    for pattern in patterns:
        hour_label = f"{pattern.hour:02d}:00"
        bar = _create_bar(pattern.total_activity, max_activity, width=30)
        blocks = f"[red]{pattern.block_count}[/red]" if pattern.block_count else "[dim]0[/dim]"
        unblocks = (
            f"[green]{pattern.unblock_count}[/green]" if pattern.unblock_count else "[dim]0[/dim]"
        )

        console.print(f"  {hour_label} {bar} B:{blocks} U:{unblocks}")

    console.print()


@stats.command("actions")
@click.pass_context
def stats_actions(ctx: click.Context) -> None:
    """Show breakdown of all action types.

    Example:
        ndb stats actions
        ndb stats actions --days 30
    """
    days = ctx.obj.get("days", 7)
    manager = AnalyticsManager()
    overall = manager.get_overall_statistics(days=days)

    if not overall.action_counts:
        console.print(f"\n  [dim]No actions in the last {days} days[/dim]\n")
        return

    console.print()
    table = Table(title=f"Action Breakdown (last {days} days)")
    table.add_column("Action", style="white")
    table.add_column("Count", justify="right", style="cyan")
    table.add_column("", width=25)

    max_count = max(overall.action_counts.values())

    for action, count in sorted(overall.action_counts.items(), key=lambda x: -x[1]):
        bar = _create_bar(count, max_count, width=20)
        table.add_row(action, str(count), bar)

    console.print(table)
    console.print(f"\n  Total entries: [bold]{overall.total_entries}[/bold]\n")


# =============================================================================
# REGISTRATION
# =============================================================================


def register_stats(main_group: click.Group) -> None:
    """Register stats command group with the main CLI."""
    main_group.add_command(stats, name="stats")
