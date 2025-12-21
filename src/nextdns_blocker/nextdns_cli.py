"""NextDNS Parental Control command group for NextDNS Blocker."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console
from rich.table import Table

from .client import NextDNSClient
from .common import NEXTDNS_CATEGORIES, NEXTDNS_SERVICES, audit_log
from .config import get_config_dir, load_config, load_nextdns_config
from .exceptions import ConfigurationError

logger = logging.getLogger(__name__)

console = Console(highlight=False)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _get_client(config_dir: Optional[Path] = None) -> tuple[NextDNSClient, dict[str, Any]]:
    """Load config and create API client."""
    config = load_config(config_dir)
    client = NextDNSClient(
        config["api_key"],
        config["profile_id"],
        config["timeout"],
        config["retries"],
    )
    return client, config


# =============================================================================
# CLI GROUP
# =============================================================================


@click.group()
def nextdns_cli() -> None:
    """Manage NextDNS Parental Control categories and services."""
    pass


@nextdns_cli.command("list")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--remote", is_flag=True, help="Show status from NextDNS API (not just config)")
def cmd_list(config_dir: Optional[Path], remote: bool) -> None:
    """List configured and active NextDNS categories/services."""
    try:
        if remote:
            # Fetch from API
            client, config = _get_client(config_dir)
            parental_control = client.get_parental_control()

            if parental_control is None:
                console.print("\n  [red]Error: Failed to fetch Parental Control settings[/red]\n")
                sys.exit(1)

            # Show global settings
            console.print("\n  [bold]NextDNS Parental Control (from API)[/bold]")
            console.print("  [bold]-----------------------------------[/bold]")
            console.print(f"  Safe Search:        {parental_control.get('safeSearch', False)}")
            console.print(
                f"  YouTube Restricted: {parental_control.get('youtubeRestrictedMode', False)}"
            )
            console.print(f"  Block Bypass:       {parental_control.get('blockBypass', False)}")

            # Categories table
            categories = parental_control.get("categories", [])
            if categories:
                console.print("\n  [bold]Active Categories:[/bold]")
                cat_table = Table(show_header=True)
                cat_table.add_column("ID", style="cyan")
                cat_table.add_column("Active", style="green")

                for cat in categories:
                    cat_table.add_row(
                        cat.get("id", "-"),
                        "Yes" if cat.get("active", False) else "No",
                    )
                console.print(cat_table)
            else:
                console.print("\n  [dim]No categories active[/dim]")

            # Services table
            services = parental_control.get("services", [])
            if services:
                console.print("\n  [bold]Active Services:[/bold]")
                svc_table = Table(show_header=True)
                svc_table.add_column("ID", style="cyan")
                svc_table.add_column("Active", style="green")

                for svc in services:
                    svc_table.add_row(
                        svc.get("id", "-"),
                        "Yes" if svc.get("active", False) else "No",
                    )
                console.print(svc_table)
            else:
                console.print("\n  [dim]No services active[/dim]")

            console.print()

        else:
            # Show from config file
            if config_dir is None:
                config_dir = get_config_dir()

            nextdns_config = load_nextdns_config(str(config_dir))

            if not nextdns_config:
                console.print("\n  [dim]No NextDNS section configured in config.json[/dim]")
                console.print("  Add a 'nextdns' section to configure Parental Control.\n")
                return

            console.print("\n  [bold]NextDNS Parental Control (from config)[/bold]")
            console.print("  [bold]-------------------------------------[/bold]")

            # Show parental control settings
            parental_control = nextdns_config.get("parental_control", {})
            if parental_control:
                console.print(f"  Safe Search:        {parental_control.get('safe_search', False)}")
                console.print(
                    f"  YouTube Restricted: {parental_control.get('youtube_restricted_mode', False)}"
                )
                console.print(
                    f"  Block Bypass:       {parental_control.get('block_bypass', False)}"
                )

            # Categories
            categories = nextdns_config.get("categories", [])
            if categories:
                console.print("\n  [bold]Categories:[/bold]")
                cat_table = Table(show_header=True)
                cat_table.add_column("ID", style="cyan")
                cat_table.add_column("Description", style="white")
                cat_table.add_column("Delay", style="green")
                cat_table.add_column("Schedule", style="blue")

                for cat in categories:
                    desc = cat.get("description", "-")
                    cat_table.add_row(
                        cat.get("id", "-"),
                        desc[:40] + "..." if len(desc) > 40 else desc,
                        cat.get("unblock_delay", "0"),
                        "Yes" if cat.get("schedule") else "No",
                    )
                console.print(cat_table)

            # Services
            services = nextdns_config.get("services", [])
            if services:
                console.print("\n  [bold]Services:[/bold]")
                svc_table = Table(show_header=True)
                svc_table.add_column("ID", style="cyan")
                svc_table.add_column("Description", style="white")
                svc_table.add_column("Delay", style="green")
                svc_table.add_column("Schedule", style="blue")

                for svc in services:
                    desc = svc.get("description", "-")
                    svc_table.add_row(
                        svc.get("id", "-"),
                        desc[:40] + "..." if len(desc) > 40 else desc,
                        svc.get("unblock_delay", "0"),
                        "Yes" if svc.get("schedule") else "No",
                    )
                console.print(svc_table)

            if not categories and not services:
                console.print("\n  [dim]No categories or services configured[/dim]")

            console.print()

    except ConfigurationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@nextdns_cli.command("add-category")
@click.argument("category_id")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_add_category(category_id: str, config_dir: Optional[Path]) -> None:
    """Add a NextDNS Parental Control category (activate blocking).

    Valid category IDs: porn, gambling, dating, piracy, social-networks
    """
    from .panic import is_panic_mode

    # Block during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot modify Parental Control during panic mode[/red]\n")
        sys.exit(1)

    # Validate category ID
    category_id = category_id.strip().lower()
    if category_id not in NEXTDNS_CATEGORIES:
        valid_ids = ", ".join(sorted(NEXTDNS_CATEGORIES))
        console.print(f"\n  [red]Error: Invalid category ID '{category_id}'[/red]")
        console.print(f"  Valid IDs: {valid_ids}\n")
        sys.exit(1)

    try:
        client, config = _get_client(config_dir)

        if client.activate_category(category_id):
            audit_log("PC_ADD_CATEGORY", category_id)
            console.print(f"\n  [green]Activated category: {category_id}[/green]\n")
        else:
            console.print(f"\n  [red]Error: Failed to activate category: {category_id}[/red]\n")
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@nextdns_cli.command("remove-category")
@click.argument("category_id")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_remove_category(category_id: str, config_dir: Optional[Path]) -> None:
    """Remove a NextDNS Parental Control category (stop blocking).

    Valid category IDs: porn, gambling, dating, piracy, social-networks
    """
    from .panic import is_panic_mode

    # Block during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot modify Parental Control during panic mode[/red]\n")
        sys.exit(1)

    # Validate category ID
    category_id = category_id.strip().lower()
    if category_id not in NEXTDNS_CATEGORIES:
        valid_ids = ", ".join(sorted(NEXTDNS_CATEGORIES))
        console.print(f"\n  [red]Error: Invalid category ID '{category_id}'[/red]")
        console.print(f"  Valid IDs: {valid_ids}\n")
        sys.exit(1)

    try:
        client, config = _get_client(config_dir)

        if client.deactivate_category(category_id):
            audit_log("PC_REMOVE_CATEGORY", category_id)
            console.print(f"\n  [green]Deactivated category: {category_id}[/green]\n")
        else:
            console.print(f"\n  [red]Error: Failed to deactivate category: {category_id}[/red]\n")
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@nextdns_cli.command("add-service")
@click.argument("service_id")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_add_service(service_id: str, config_dir: Optional[Path]) -> None:
    """Add a NextDNS Parental Control service (activate blocking).

    Examples: tiktok, netflix, youtube, instagram, discord, fortnite, etc.
    Use 'nextdns-blocker nextdns services' to see all valid IDs.
    """
    from .panic import is_panic_mode

    # Block during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot modify Parental Control during panic mode[/red]\n")
        sys.exit(1)

    # Validate service ID
    service_id = service_id.strip().lower()
    if service_id not in NEXTDNS_SERVICES:
        console.print(f"\n  [red]Error: Invalid service ID '{service_id}'[/red]")
        console.print("  Use 'nextdns-blocker nextdns services' to see valid IDs.\n")
        sys.exit(1)

    try:
        client, config = _get_client(config_dir)

        if client.activate_service(service_id):
            audit_log("PC_ADD_SERVICE", service_id)
            console.print(f"\n  [green]Activated service: {service_id}[/green]\n")
        else:
            console.print(f"\n  [red]Error: Failed to activate service: {service_id}[/red]\n")
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@nextdns_cli.command("remove-service")
@click.argument("service_id")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_remove_service(service_id: str, config_dir: Optional[Path]) -> None:
    """Remove a NextDNS Parental Control service (stop blocking).

    Use 'nextdns-blocker nextdns services' to see all valid IDs.
    """
    from .panic import is_panic_mode

    # Block during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot modify Parental Control during panic mode[/red]\n")
        sys.exit(1)

    # Validate service ID
    service_id = service_id.strip().lower()
    if service_id not in NEXTDNS_SERVICES:
        console.print(f"\n  [red]Error: Invalid service ID '{service_id}'[/red]")
        console.print("  Use 'nextdns-blocker nextdns services' to see valid IDs.\n")
        sys.exit(1)

    try:
        client, config = _get_client(config_dir)

        if client.deactivate_service(service_id):
            audit_log("PC_REMOVE_SERVICE", service_id)
            console.print(f"\n  [green]Deactivated service: {service_id}[/green]\n")
        else:
            console.print(f"\n  [red]Error: Failed to deactivate service: {service_id}[/red]\n")
            sys.exit(1)

    except ConfigurationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


@nextdns_cli.command("categories")
def cmd_categories() -> None:
    """Show all valid NextDNS category IDs."""
    console.print("\n  [bold]Valid NextDNS Category IDs[/bold]")
    console.print("  [bold]-------------------------[/bold]")
    for cat_id in sorted(NEXTDNS_CATEGORIES):
        console.print(f"    - {cat_id}")
    console.print()


@nextdns_cli.command("services")
def cmd_services() -> None:
    """Show all valid NextDNS service IDs."""
    console.print("\n  [bold]Valid NextDNS Service IDs (43 total)[/bold]")
    console.print("  [bold]------------------------------------[/bold]")

    # Group services by category for readability
    groups = {
        "Social & Messaging": [
            "facebook",
            "instagram",
            "twitter",
            "tiktok",
            "snapchat",
            "whatsapp",
            "telegram",
            "messenger",
            "discord",
            "signal",
            "skype",
            "mastodon",
            "bereal",
            "vk",
            "tumblr",
            "pinterest",
            "reddit",
            "9gag",
            "imgur",
            "google-chat",
        ],
        "Streaming": [
            "youtube",
            "netflix",
            "disneyplus",
            "hbomax",
            "primevideo",
            "hulu",
            "twitch",
            "vimeo",
            "dailymotion",
        ],
        "Gaming": [
            "fortnite",
            "minecraft",
            "roblox",
            "leagueoflegends",
            "steam",
            "blizzard",
            "xboxlive",
            "playstation-network",
        ],
        "Dating": ["tinder"],
        "Other": ["spotify", "amazon", "ebay", "zoom", "chatgpt"],
    }

    for group_name, services in groups.items():
        console.print(f"\n  [cyan]{group_name}:[/cyan]")
        for svc in services:
            console.print(f"    - {svc}")

    console.print()


@nextdns_cli.command("status")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_status(config_dir: Optional[Path]) -> None:
    """Show current Parental Control status from NextDNS API."""
    try:
        client, config = _get_client(config_dir)
        parental_control = client.get_parental_control()

        if parental_control is None:
            console.print("\n  [red]Error: Failed to fetch Parental Control settings[/red]\n")
            sys.exit(1)

        console.print("\n  [bold]NextDNS Parental Control Status[/bold]")
        console.print("  [bold]-------------------------------[/bold]")

        # Global settings
        safe_search = parental_control.get("safeSearch", False)
        youtube = parental_control.get("youtubeRestrictedMode", False)
        block_bypass = parental_control.get("blockBypass", False)

        ss_status = "[green]enabled[/green]" if safe_search else "[dim]disabled[/dim]"
        yt_status = "[green]enabled[/green]" if youtube else "[dim]disabled[/dim]"
        bb_status = "[green]enabled[/green]" if block_bypass else "[dim]disabled[/dim]"

        console.print(f"  Safe Search:        {ss_status}")
        console.print(f"  YouTube Restricted: {yt_status}")
        console.print(f"  Block Bypass:       {bb_status}")

        # Active categories
        categories = parental_control.get("categories", [])
        active_cats = [c["id"] for c in categories if c.get("active", False)]

        console.print(f"\n  [bold]Active Categories ({len(active_cats)}):[/bold]")
        if active_cats:
            for cat_id in sorted(active_cats):
                console.print(f"    [red]🔴[/red] {cat_id}")
        else:
            console.print("    [dim]None[/dim]")

        # Active services
        services = parental_control.get("services", [])
        active_svcs = [s["id"] for s in services if s.get("active", False)]

        console.print(f"\n  [bold]Active Services ({len(active_svcs)}):[/bold]")
        if active_svcs:
            for svc_id in sorted(active_svcs):
                console.print(f"    [red]🔴[/red] {svc_id}")
        else:
            console.print("    [dim]None[/dim]")

        console.print()

    except ConfigurationError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)


def register_nextdns(main_group: click.Group) -> None:
    """Register nextdns commands as subcommand of main CLI."""
    main_group.add_command(nextdns_cli, name="nextdns")


# Allow running standalone for testing
main = nextdns_cli
