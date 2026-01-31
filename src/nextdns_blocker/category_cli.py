"""Category command group for NextDNS Blocker."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from .cli_formatter import CLIOutput as out
from .common import audit_log, validate_category_id, validate_domain

logger = logging.getLogger(__name__)

console = Console(highlight=False)  # Keep for tables and complex output


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _load_config_or_exit(config_dir: Optional[Path]) -> dict[str, Any]:
    """Load config from database or exit with error."""
    from . import database as db

    if not db.config_has_domains():
        out.error("No configuration in database. Run 'nextdns-blocker init' to create one.")
        sys.exit(1)
    try:
        return db.get_full_config_dict()
    except Exception as e:
        out.error(str(e))
        sys.exit(1)


def _save_config(config: dict[str, Any]) -> None:
    """Save config to database."""
    from . import database as db

    db.save_full_config_dict(config)


def _get_categories(config: dict[str, Any]) -> list[dict[str, Any]]:
    """Get categories list from config, ensuring it exists."""
    categories = config.get("categories", [])
    if not isinstance(categories, list):
        return []
    return categories


def _find_category_by_id(
    categories: list[dict[str, Any]], category_id: str
) -> Optional[dict[str, Any]]:
    """Find a category by its ID (case-insensitive)."""
    category_id_lower = category_id.lower()
    for category in categories:
        if category.get("id", "").lower() == category_id_lower:
            return category
    return None


def _find_category_index(categories: list[dict[str, Any]], category_id: str) -> Optional[int]:
    """Find the index of a category by its ID (case-insensitive)."""
    category_id_lower = category_id.lower()
    for idx, category in enumerate(categories):
        if category.get("id", "").lower() == category_id_lower:
            return idx
    return None


# =============================================================================
# CLI GROUP
# =============================================================================


@click.group()
def category_cli() -> None:
    """Manage domain categories."""
    pass


@category_cli.command("list")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_list(config_dir: Optional[Path]) -> None:
    """List all categories."""
    config = _load_config_or_exit(config_dir)
    categories = _get_categories(config)

    if not categories:
        console.print("\n  [dim]No categories configured[/dim]\n")
        return

    table = Table(title="Categories", show_header=True)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Domains", style="yellow", justify="right")
    table.add_column("Delay", style="green")
    table.add_column("Schedule", style="blue")

    for category in categories:
        category_id = category.get("id", "-")
        description = category.get("description", "-")
        domains = category.get("domains", [])
        domain_count = len(domains) if isinstance(domains, list) else 0
        delay = category.get("unblock_delay", "0")
        has_schedule = "Yes" if category.get("schedule") else "No"

        table.add_row(
            category_id,
            description[:40] + "..." if len(description) > 40 else description,
            str(domain_count),
            delay,
            has_schedule,
        )

    console.print()
    console.print(table)
    console.print()


@category_cli.command("show")
@click.argument("category_id")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_show(category_id: str, config_dir: Optional[Path]) -> None:
    """Show details of a category."""
    config = _load_config_or_exit(config_dir)
    categories = _get_categories(config)
    category = _find_category_by_id(categories, category_id)

    if not category:
        out.error(f"Category '{category_id}' not found")
        sys.exit(1)

    console.print("\n  [bold]Category Details[/bold]")
    console.print("  [bold]----------------[/bold]")
    console.print(f"  ID:          {category.get('id', '-')}")
    console.print(f"  Description: {category.get('description', '-')}")
    console.print(f"  Delay:       {category.get('unblock_delay', '0')}")

    schedule = category.get("schedule")
    if schedule:
        console.print("  Schedule:    [green]Configured[/green]")
        hours = schedule.get("available_hours", [])
        for block in hours:
            days = ", ".join(block.get("days", []))
            ranges = block.get("time_ranges", [])
            for tr in ranges:
                console.print(f"               {days}: {tr.get('start')}-{tr.get('end')}")
    else:
        console.print("  Schedule:    [dim]Always blocked[/dim]")

    domains = category.get("domains", [])
    console.print(f"\n  [bold]Domains ({len(domains)}):[/bold]")
    for domain in domains:
        console.print(f"    - {domain}")

    console.print()


@category_cli.command("add")
@click.argument("category_id")
@click.argument("domain")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_add(category_id: str, domain: str, config_dir: Optional[Path]) -> None:
    """Add a domain to a category."""
    # Validate domain format
    domain = domain.strip().lower()
    if not validate_domain(domain):
        out.error(f"Invalid domain format: {domain}")
        sys.exit(1)

    config = _load_config_or_exit(config_dir)
    categories = _get_categories(config)
    category_idx = _find_category_index(categories, category_id)

    if category_idx is None:
        out.error(f"Category '{category_id}' not found")
        sys.exit(1)

    category = categories[category_idx]

    # Check if domain already exists in this category
    existing_domains = [d.lower() for d in category.get("domains", []) if isinstance(d, str)]
    if domain in existing_domains:
        console.print(
            f"\n  [yellow]Domain '{domain}' already exists in category '{category_id}'[/yellow]\n"
        )
        return

    # Check if domain exists in blocklist
    blocklist = config.get("blocklist", [])
    blocklist_domains = [d.get("domain", "").lower() for d in blocklist if isinstance(d, dict)]
    if domain in blocklist_domains:
        console.print(
            f"\n  [red]Error: Domain '{domain}' already exists in blocklist. "
            f"Remove it first with 'nextdns-blocker config edit'.[/red]\n"
        )
        sys.exit(1)

    # Check if domain exists in another category
    for cat in categories:
        if cat.get("id") != category.get("id"):
            cat_domains = [d.lower() for d in cat.get("domains", []) if isinstance(d, str)]
            if domain in cat_domains:
                console.print(
                    f"\n  [red]Error: Domain '{domain}' already exists in category '{cat.get('id')}'[/red]\n"
                )
                sys.exit(1)

    # Add domain to category
    if "domains" not in category:
        category["domains"] = []
    category["domains"].append(domain)

    # Ensure categories list is in config
    config["categories"] = categories

    try:
        _save_config(config)
    except Exception as e:
        out.error(f"Saving config: {e}")
        sys.exit(1)

    audit_log("CATEGORY_ADD", f"Added {domain} to category {category_id}")
    out.success(f"Added '{domain}' to category '{category_id}'")


@category_cli.command("remove")
@click.argument("category_id")
@click.argument("domain")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_remove(category_id: str, domain: str, yes: bool, config_dir: Optional[Path]) -> None:
    """Remove a domain from a category."""
    domain = domain.strip().lower()
    config = _load_config_or_exit(config_dir)
    categories = _get_categories(config)
    category_idx = _find_category_index(categories, category_id)

    if category_idx is None:
        out.error(f"Category '{category_id}' not found")
        sys.exit(1)

    category = categories[category_idx]

    # Check if domain exists in this category
    existing_domains = category.get("domains", [])
    domain_idx = None
    for idx, d in enumerate(existing_domains):
        if isinstance(d, str) and d.lower() == domain:
            domain_idx = idx
            break

    if domain_idx is None:
        console.print(
            f"\n  [red]Error: Domain '{domain}' not found in category '{category_id}'[/red]\n"
        )
        sys.exit(1)

    # Confirm removal
    if not yes:
        console.print(f"\n  Remove '{domain}' from category '{category_id}'?")
        if not click.confirm("  Proceed?"):
            console.print("  Cancelled.\n")
            return

    # Remove domain
    existing_domains.pop(domain_idx)
    category["domains"] = existing_domains
    config["categories"] = categories

    try:
        _save_config(config)
    except Exception as e:
        out.error(f"Saving config: {e}")
        sys.exit(1)

    audit_log("CATEGORY_REMOVE", f"Removed {domain} from category {category_id}")
    out.success(f"Removed '{domain}' from category '{category_id}'")


@category_cli.command("create")
@click.argument("category_id")
@click.option("-d", "--description", help="Category description")
@click.option("--delay", default="0", help="Unblock delay (e.g., '30m', '4h', 'never')")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_create(
    category_id: str, description: Optional[str], delay: str, config_dir: Optional[Path]
) -> None:
    """Create a new category."""
    # Validate category ID
    if not validate_category_id(category_id):
        console.print(
            f"\n  [red]Error: Invalid category ID '{category_id}'[/red]\n"
            "  Category ID must start with a lowercase letter and contain only\n"
            "  lowercase letters, numbers, and hyphens (max 50 characters).\n"
        )
        sys.exit(1)

    config = _load_config_or_exit(config_dir)

    # Ensure categories array exists
    if "categories" not in config:
        config["categories"] = []

    categories = config["categories"]
    if not isinstance(categories, list):
        config["categories"] = []
        categories = config["categories"]

    # Check if category already exists
    if _find_category_by_id(categories, category_id):
        out.error(f"Category '{category_id}' already exists")
        sys.exit(1)

    # Validate delay format before creating
    if delay != "0":
        from .config import validate_unblock_delay

        if not validate_unblock_delay(delay):
            console.print(
                f"\n  [red]Error: Invalid delay format '{delay}'[/red]\n"
                "  Expected: 'never', '0', or duration like '30m', '2h', '1d'\n"
            )
            sys.exit(1)

    # Create new category (domains starts empty, user will add later)
    new_category: dict[str, Any] = {
        "id": category_id,
        "domains": [],
    }

    if description:
        new_category["description"] = description

    if delay != "0":
        new_category["unblock_delay"] = delay

    categories.append(new_category)
    config["categories"] = categories

    try:
        _save_config(config)
    except Exception as e:
        out.error(f"Saving config: {e}")
        sys.exit(1)

    audit_log("CATEGORY_CREATE", f"Created category {category_id}")
    out.success(f"Created category '{category_id}'")
    if description:
        out.info(f"Description: {description}")
    out.info(f"Delay: {delay}")
    out.info_block("Use 'nextdns-blocker category add' to add domains.")


@category_cli.command("delete")
@click.argument("category_id")
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_delete(category_id: str, yes: bool, config_dir: Optional[Path]) -> None:
    """Delete a category and all its domains."""
    config = _load_config_or_exit(config_dir)
    categories = _get_categories(config)
    category_idx = _find_category_index(categories, category_id)

    if category_idx is None:
        out.error(f"Category '{category_id}' not found")
        sys.exit(1)

    category = categories[category_idx]
    domain_count = len(category.get("domains", []))

    # Confirm deletion
    if not yes:
        console.print(f"\n  Delete category '{category_id}' with {domain_count} domain(s)?")
        console.print("  [yellow]This action cannot be undone.[/yellow]")
        if not click.confirm("  Proceed?"):
            console.print("  Cancelled.\n")
            return

    # Remove category
    categories.pop(category_idx)
    config["categories"] = categories

    try:
        _save_config(config)
    except Exception as e:
        out.error(f"Saving config: {e}")
        sys.exit(1)

    audit_log("CATEGORY_DELETE", f"Deleted category {category_id} ({domain_count} domains)")
    out.success(f"Deleted category '{category_id}' ({domain_count} domain(s))")


def register_category(main_group: click.Group) -> None:
    """Register category commands as subcommand of main CLI."""
    main_group.add_command(category_cli, name="category")


# Allow running standalone for testing
main = category_cli
