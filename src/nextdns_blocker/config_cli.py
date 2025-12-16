"""Config command group for NextDNS Blocker."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import click
from rich.console import Console

from .common import audit_log
from .config import get_config_dir
from .exceptions import ConfigurationError

console = Console(highlight=False)

# =============================================================================
# CONSTANTS
# =============================================================================

LEGACY_DOMAINS_FILE = "domains.json"
NEW_CONFIG_FILE = "config.json"
CONFIG_VERSION = "1.0"


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_config_file_path(config_dir: Optional[Path] = None) -> Path:
    """Get the path to the config file (new or legacy)."""
    if config_dir is None:
        config_dir = get_config_dir()

    new_config = config_dir / NEW_CONFIG_FILE
    legacy_config = config_dir / LEGACY_DOMAINS_FILE

    # Prefer new config if it exists
    if new_config.exists():
        return new_config
    return legacy_config


def get_editor() -> str:
    """Get the preferred editor."""
    # Check environment variable
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        return editor

    # Try common editors
    for candidate in ["vim", "nano", "vi", "notepad"]:
        if shutil.which(candidate):
            return candidate

    return "vi"  # Fallback


def load_config_file(config_path: Path) -> dict[str, Any]:
    """Load and parse a config file."""
    with open(config_path, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def save_config_file(config_path: Path, config: dict[str, Any]) -> None:
    """Save config to file with pretty formatting."""
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")


def migrate_legacy_config(legacy_config: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy domains.json format to new config.json format."""
    new_config: dict[str, Any] = {
        "version": CONFIG_VERSION,
        "settings": {
            "editor": None,
            "timezone": None,
        },
        "blocklist": [],
        "allowlist": legacy_config.get("allowlist", []),
    }

    # Migrate domains -> blocklist
    for domain_entry in legacy_config.get("domains", []):
        new_entry = dict(domain_entry)

        # Convert protected -> unblock_delay
        if new_entry.pop("protected", False):
            new_entry["unblock_delay"] = "never"
        elif "unblock_delay" not in new_entry:
            new_entry["unblock_delay"] = "0"

        new_config["blocklist"].append(new_entry)

    return new_config


# =============================================================================
# CONFIG COMMAND GROUP
# =============================================================================


@click.group()
def config_cli() -> None:
    """Configuration management commands."""
    pass


@config_cli.command("edit")
@click.option(
    "--editor",
    help="Editor to use (default: $EDITOR or vim)",
)
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_edit(editor: Optional[str], config_dir: Optional[Path]) -> None:
    """Open config file in editor."""
    # Get config file path
    config_path = get_config_file_path(config_dir)

    if not config_path.exists():
        console.print(
            f"\n  [red]Error: Config file not found[/red]"
            f"\n  [dim]Expected: {config_path}[/dim]"
            f"\n  [dim]Run 'nextdns-blocker init' to create one.[/dim]\n"
        )
        sys.exit(1)

    # Get editor
    editor_cmd = editor or get_editor()

    console.print(f"\n  Opening {config_path.name} in {editor_cmd}...\n")

    # Open editor
    try:
        subprocess.run([editor_cmd, str(config_path)], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"\n  [red]Error: Editor exited with code {e.returncode}[/red]\n")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"\n  [red]Error: Editor '{editor_cmd}' not found[/red]\n")
        sys.exit(1)

    audit_log("CONFIG_EDIT", str(config_path))

    console.print(
        "  [green]✓[/green] File saved"
        "\n  [yellow]![/yellow] Run 'nextdns-blocker config validate' to check syntax"
        "\n  [yellow]![/yellow] Run 'nextdns-blocker config sync' to apply changes\n"
    )


@config_cli.command("show")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def cmd_show(config_dir: Optional[Path], output_json: bool) -> None:
    """Display current configuration."""
    try:
        config_path = get_config_file_path(config_dir)

        if not config_path.exists():
            console.print(f"\n  [red]Error: Config file not found: {config_path}[/red]\n")
            sys.exit(1)

        config_data = load_config_file(config_path)

        if output_json:
            print(json.dumps(config_data, indent=2))
        else:
            console.print(f"\n  [bold]Config File:[/bold] {config_path}")

            # Show version if present
            if "version" in config_data:
                console.print(f"  [bold]Version:[/bold] {config_data['version']}")

            # Show settings if present
            if "settings" in config_data:
                console.print("\n  [bold]Settings:[/bold]")
                for key, value in config_data["settings"].items():
                    display_value = value if value is not None else "[dim]not set[/dim]"
                    console.print(f"    {key}: {display_value}")

            # Count blocklist/domains
            blocklist = config_data.get("blocklist", config_data.get("domains", []))
            allowlist = config_data.get("allowlist", [])

            console.print(f"\n  [bold]Blocklist:[/bold] {len(blocklist)} domains")
            console.print(f"  [bold]Allowlist:[/bold] {len(allowlist)} domains\n")

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n")
        sys.exit(1)
    except json.JSONDecodeError as e:
        console.print(f"\n  [red]JSON error: {e}[/red]\n")
        sys.exit(1)


@config_cli.command("set")
@click.argument("key")
@click.argument("value")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_set(key: str, value: str, config_dir: Optional[Path]) -> None:
    """Set a configuration value.

    Examples:
        nextdns-blocker config set editor vim
        nextdns-blocker config set timezone America/New_York
    """
    config_path = get_config_file_path(config_dir)

    if not config_path.exists():
        console.print(f"\n  [red]Error: Config file not found: {config_path}[/red]\n")
        sys.exit(1)

    try:
        config_data = load_config_file(config_path)

        # Ensure settings section exists
        if "settings" not in config_data:
            config_data["settings"] = {}

        # Validate key
        valid_keys = ["editor", "timezone"]
        if key not in valid_keys:
            console.print(
                f"\n  [red]Error: Unknown setting '{key}'[/red]"
                f"\n  [dim]Valid settings: {', '.join(valid_keys)}[/dim]\n"
            )
            sys.exit(1)

        # Handle special value "null" to unset
        if value.lower() == "null":
            config_data["settings"][key] = None
            console.print(f"\n  [green]✓[/green] Unset: {key}\n")
        else:
            config_data["settings"][key] = value
            console.print(f"\n  [green]✓[/green] Set {key} = '{value}'\n")

        # Ensure version exists
        if "version" not in config_data:
            config_data["version"] = CONFIG_VERSION

        save_config_file(config_path, config_data)
        audit_log("CONFIG_SET", f"{key}={value}")

    except json.JSONDecodeError as e:
        console.print(f"\n  [red]JSON error: {e}[/red]\n")
        sys.exit(1)


@config_cli.command("migrate")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be migrated without making changes")
@click.option("--force", is_flag=True, help="Overwrite existing config.json")
def cmd_migrate(config_dir: Optional[Path], dry_run: bool, force: bool) -> None:
    """Migrate from legacy domains.json to config.json format."""
    if config_dir is None:
        config_dir = get_config_dir()

    legacy_path = config_dir / LEGACY_DOMAINS_FILE
    new_path = config_dir / NEW_CONFIG_FILE

    # Check if legacy file exists
    if not legacy_path.exists():
        console.print(f"\n  [yellow]No legacy {LEGACY_DOMAINS_FILE} found.[/yellow]")

        if new_path.exists():
            console.print(f"  [green]Already using {NEW_CONFIG_FILE}[/green]\n")
        else:
            console.print("  [dim]Run 'nextdns-blocker init' to create a config.[/dim]\n")
        return

    # Check if new config already exists
    if new_path.exists() and not force:
        console.print(
            f"\n  [yellow]{NEW_CONFIG_FILE} already exists.[/yellow]"
            f"\n  [dim]Use --force to overwrite.[/dim]\n"
        )
        return

    try:
        # Load legacy config
        legacy_config = load_config_file(legacy_path)

        # Migrate to new format
        new_config = migrate_legacy_config(legacy_config)

        # Count entries
        blocklist_count = len(new_config.get("blocklist", []))
        allowlist_count = len(new_config.get("allowlist", []))

        if dry_run:
            console.print("\n  [bold]Migration Preview (dry-run)[/bold]")
            console.print("\n  Would migrate:")
            console.print(f"    Blocklist: {blocklist_count} entries (renamed from 'domains')")
            console.print(f"    Allowlist: {allowlist_count} entries")
            console.print("    Settings: defaults applied")
            console.print(f"    Version: {CONFIG_VERSION}")
            console.print("\n  [dim]Run without --dry-run to apply changes.[/dim]\n")
            return

        # Create backup
        backup_path = config_dir / f"{LEGACY_DOMAINS_FILE}.bak"
        shutil.copy2(legacy_path, backup_path)

        # Save new config
        save_config_file(new_path, new_config)

        console.print("\n  [bold]Migration Complete[/bold]")
        console.print(f"\n  [green]✓[/green] Blocklist: {blocklist_count} entries migrated")
        console.print(f"  [green]✓[/green] Allowlist: {allowlist_count} entries migrated")
        console.print("  [green]✓[/green] Settings: defaults applied")
        console.print(f"  [green]✓[/green] Backup created: {backup_path.name}")
        console.print("\n  [dim]Run 'nextdns-blocker config validate' to verify.[/dim]\n")

        audit_log("CONFIG_MIGRATE", f"{LEGACY_DOMAINS_FILE} -> {NEW_CONFIG_FILE}")

    except json.JSONDecodeError as e:
        console.print(f"\n  [red]JSON error in {LEGACY_DOMAINS_FILE}: {e}[/red]\n")
        sys.exit(1)


@config_cli.command("validate")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.pass_context
def cmd_validate(ctx: click.Context, output_json: bool, config_dir: Optional[Path]) -> None:
    """Validate configuration files before deployment.

    Checks config.json/domains.json for:
    - Valid JSON syntax
    - Valid domain formats
    - Valid schedule time formats (HH:MM)
    - No blocklist/allowlist conflicts
    """
    # Import here to avoid circular imports
    from .cli import validate as root_validate

    # Call the root validate function (without deprecation warning)
    ctx.invoke(
        root_validate, output_json=output_json, config_dir=config_dir, _from_config_group=True
    )


@config_cli.command("sync")
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option(
    "--config-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.pass_context
def cmd_sync(
    ctx: click.Context,
    dry_run: bool,
    verbose: bool,
    config_dir: Optional[Path],
) -> None:
    """Synchronize domain blocking with schedules."""
    # Import here to avoid circular imports
    from .cli import sync as root_sync

    # Call the root sync function (without deprecation warning)
    ctx.invoke(
        root_sync,
        dry_run=dry_run,
        verbose=verbose,
        config_dir=config_dir,
        _from_config_group=True,
    )


# =============================================================================
# REGISTRATION
# =============================================================================


def register_config(main_group: click.Group) -> None:
    """Register config commands as subcommand of main CLI."""
    main_group.add_command(config_cli, name="config")


# Allow running standalone for testing
main = config_cli
