"""Centralized CLI output formatting.

This module provides consistent formatting for all CLI output messages.
All CLI modules should use CLIOutput instead of direct console.print calls.
"""

from typing import TYPE_CHECKING, Union

from rich.console import Console

if TYPE_CHECKING:
    from rich.table import Table

console = Console(highlight=False)


class CLIOutput:
    """Centralized CLI output formatting."""

    @staticmethod
    def error(msg: str, prefix: str = "Error") -> None:
        """Print error message in red."""
        console.print(f"\n  [red]{prefix}: {msg}[/red]\n")

    @staticmethod
    def warning(msg: str, prefix: str = "Warning") -> None:
        """Print warning message in yellow."""
        console.print(f"\n  [yellow]{prefix}: {msg}[/yellow]\n")

    @staticmethod
    def success(msg: str) -> None:
        """Print success message in green."""
        console.print(f"\n  [green]{msg}[/green]\n")

    @staticmethod
    def info(msg: str) -> None:
        """Print info message."""
        console.print(f"  {msg}")

    @staticmethod
    def info_block(msg: str) -> None:
        """Print info message with newlines (for standalone messages)."""
        console.print(f"\n  {msg}\n")

    @staticmethod
    def item_added(item: str) -> None:
        """Print added item."""
        console.print(f"  [green]+[/green] {item}")

    @staticmethod
    def item_removed(item: str) -> None:
        """Print removed item."""
        console.print(f"  [red]-[/red] {item}")

    @staticmethod
    def item_skipped(item: str, reason: str = "") -> None:
        """Print skipped item."""
        suffix = f" ({reason})" if reason else ""
        console.print(f"  [yellow]~[/yellow] {item}{suffix}")

    @staticmethod
    def item_ok(item: str) -> None:
        """Print item with checkmark."""
        console.print(f"  [green]✓[/green] {item}")

    @staticmethod
    def item_fail(item: str) -> None:
        """Print item with X mark."""
        console.print(f"  [red]✗[/red] {item}")

    @staticmethod
    def header(title: str) -> None:
        """Print section header."""
        console.print(f"\n  [bold]{title}[/bold]")

    @staticmethod
    def divider() -> None:
        """Print a visual divider."""
        console.print()

    @staticmethod
    def key_value(key: str, value: str, color: str = "cyan") -> None:
        """Print key-value pair with consistent formatting."""
        console.print(f"  {key:<12} [{color}]{value}[/{color}]")

    @staticmethod
    def stat(label: str, value: Union[int, str], color: str = "white") -> None:
        """Print a statistic with label and value."""
        console.print(f"    {label}: [{color}]{value}[/{color}]")

    @staticmethod
    def table(table: "Table") -> None:
        """Print a Rich table with consistent spacing."""
        console.print()
        console.print(table)
        console.print()

    @staticmethod
    def result_summary(
        added: int = 0,
        removed: int = 0,
        skipped: int = 0,
        failed: int = 0,
    ) -> None:
        """Print a standardized operation summary."""
        parts = []
        if added > 0:
            parts.append(f"[green]{added} added[/green]")
        if removed > 0:
            parts.append(f"[red]{removed} removed[/red]")
        if skipped > 0:
            parts.append(f"[yellow]{skipped} skipped[/yellow]")
        if failed > 0:
            parts.append(f"[red]{failed} failed[/red]")
        summary = ", ".join(parts) if parts else "no changes"
        console.print(f"\n  {summary}\n")


# Convenience alias for shorter imports
out = CLIOutput
