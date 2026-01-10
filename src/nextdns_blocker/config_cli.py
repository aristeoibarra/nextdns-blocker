"""Config command group for NextDNS Blocker."""

import contextlib
import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

# Type checking imports
from typing import TYPE_CHECKING, Any, Optional

import click
from rich.console import Console

from .common import audit_log
from .config import get_config_dir
from .exceptions import ConfigurationError

if TYPE_CHECKING:
    from .client import NextDNSClient

logger = logging.getLogger(__name__)

console = Console(highlight=False)

# =============================================================================
# CONSTANTS
# =============================================================================

NEW_CONFIG_FILE = "config.json"
CONFIG_VERSION = "1.0"

# Safe editors whitelist for security (prevents arbitrary command execution)
SAFE_EDITORS = frozenset(
    {
        "vim",
        "vi",
        "nvim",
        "nano",
        "emacs",
        "pico",
        "micro",
        "joe",
        "ne",
        "code",
        "subl",
        "atom",
        "gedit",
        "kate",
        "notepad",
        "notepad++",
        "sublime_text",
        "TextEdit",
        "open",
    }
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_config_file_path(config_dir: Optional[Path] = None) -> Path:
    """Get the path to config.json."""
    if config_dir is None:
        config_dir = get_config_dir()

    return config_dir / NEW_CONFIG_FILE


def get_editor() -> str:
    """
    Get the preferred editor command.

    Returns:
        Editor command string (may include arguments if set via EDITOR env var)
    """
    # Check environment variable
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL")
    if editor:
        return editor

    # Try common editors
    for candidate in ["vim", "nano", "vi", "notepad"]:
        if shutil.which(candidate):
            return candidate

    return "vi"  # Fallback


def _parse_editor_command(editor: str) -> list[str]:
    """
    Parse editor command string into list of arguments.

    Safely handles editor commands that may include arguments
    (e.g., "code --wait" or "vim -u NONE").

    Args:
        editor: Editor command string

    Returns:
        List of command arguments safe for subprocess

    Raises:
        ValueError: If editor command is empty, malformed, or not in safe list
    """
    if not editor or not editor.strip():
        raise ValueError("Editor command cannot be empty")

    try:
        parts = shlex.split(editor)
        if not parts:
            raise ValueError("Editor command cannot be empty")

        # Validate that the base editor is in the safe list
        base_editor = Path(parts[0]).name  # Get just the executable name
        if base_editor not in SAFE_EDITORS:
            raise ValueError(
                f"Editor '{base_editor}' is not in the safe editors list. "
                f"Allowed editors: {', '.join(sorted(SAFE_EDITORS))}"
            )

        return parts
    except ValueError as e:
        # Re-raise ValueError (includes our validation errors)
        if "not in the safe editors list" in str(e) or "Editor command" in str(e):
            raise
        # shlex.split can raise ValueError on malformed input (unclosed quotes)
        raise ValueError(f"Invalid editor command format: {e}")


def load_config_file(config_path: Path) -> dict[str, Any]:
    """
    Load and parse a config file.

    Args:
        config_path: Path to the config file

    Returns:
        Parsed config dictionary

    Raises:
        ConfigurationError: If file cannot be read, parsed, or has invalid structure
    """
    try:
        with open(config_path, encoding="utf-8") as f:
            result = json.load(f)
            # Validate that the result is a dictionary
            if not isinstance(result, dict):
                raise ConfigurationError(
                    f"Invalid config format in {config_path.name}: expected object, got {type(result).__name__}"
                )
            return result
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in {config_path.name}: {e}")
    except OSError as e:
        raise ConfigurationError(f"Failed to read {config_path.name}: {e}")


def save_config_file(config_path: Path, config: dict[str, Any]) -> None:
    """
    Save config to file with atomic write for safety.

    Uses temporary file + rename pattern to prevent corruption
    if write is interrupted.

    Args:
        config_path: Path to save config to
        config: Config dictionary to save

    Raises:
        OSError: If file operations fail
    """
    import tempfile

    # Write to temporary file first
    temp_fd, temp_path = tempfile.mkstemp(
        dir=config_path.parent, prefix=f".{config_path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename (on POSIX; on Windows this may not be atomic)
        Path(temp_path).replace(config_path)
    except (OSError, TypeError, ValueError) as e:
        # Clean up temp file on error
        logger.debug(f"Failed to save config file: {e}")
        with contextlib.suppress(OSError):
            Path(temp_path).unlink()
        raise


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
    from .cli import require_pin_verification
    from .panic import is_panic_mode

    # Block config edit during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot edit config during panic mode[/red]\n")
        sys.exit(1)

    # Require PIN verification
    require_pin_verification("config edit")

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
    editor_str = editor or get_editor()

    console.print(f"\n  Opening {config_path.name} in {editor_str}...\n")

    # Parse editor command safely (handles editors with arguments like "code --wait")
    try:
        editor_args = _parse_editor_command(editor_str)
    except ValueError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)

    # Open editor with config file path appended
    try:
        subprocess.run(editor_args + [str(config_path)], check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"\n  [red]Error: Editor exited with code {e.returncode}[/red]\n")
        sys.exit(1)
    except FileNotFoundError:
        console.print(f"\n  [red]Error: Editor '{editor_args[0]}' not found[/red]\n")
        sys.exit(1)

    audit_log("CONFIG_EDIT", str(config_path))

    console.print(
        "  [green]✓[/green] File saved"
        "\n  [yellow]![/yellow] Run 'nextdns-blocker config validate' to check syntax"
        "\n  [yellow]![/yellow] Run 'nextdns-blocker config sync' to apply changes\n"
    )


def _format_schedule_summary(schedule: Optional[dict[str, Any]]) -> str:
    """Format a schedule into a human-readable summary."""
    if not schedule:
        return "always blocked"

    # Check for available_hours
    if "available_hours" in schedule:
        blocks = schedule["available_hours"]
        if blocks:
            # Get first time range as representative
            first_block = blocks[0]
            time_ranges = first_block.get("time_ranges", [])
            if time_ranges:
                first_range = time_ranges[0]
                return f"{first_range['start']}-{first_range['end']}"
        return "scheduled"

    # Check for blocked_hours
    if "blocked_hours" in schedule:
        blocks = schedule["blocked_hours"]
        if blocks:
            first_block = blocks[0]
            time_ranges = first_block.get("time_ranges", [])
            if time_ranges:
                first_range = time_ranges[0]
                return f"blocked {first_range['start']}-{first_range['end']}"
        return "scheduled"

    return "always blocked"


def _get_unblock_display(domain_config: dict[str, Any]) -> str:
    """Get unblock delay display string."""
    delay = domain_config.get("unblock_delay")
    if delay == "never":
        return "never"
    if delay:
        return str(delay)
    return "0"


# =============================================================================
# DIFF/PULL HELPER FUNCTIONS
# =============================================================================


def _get_client(config_dir: Optional[Path] = None) -> "NextDNSClient":
    """Create a NextDNS client from config."""
    from .client import NextDNSClient
    from .config import load_config

    config = load_config(config_dir)
    return NextDNSClient(
        config["api_key"],
        config["profile_id"],
        config["timeout"],
        config["retries"],
    )


def _get_local_domains(config_path: Path) -> tuple[set[str], set[str]]:
    """
    Extract domain sets from local config.json.

    Expands categories into individual domains.

    Returns:
        Tuple of (blocklist_domains, allowlist_domains)
    """
    config = load_config_file(config_path)

    # Extract blocklist domains
    blocklist_domains: set[str] = set()
    for entry in config.get("blocklist", []):
        domain = entry.get("domain", "")
        if domain:
            blocklist_domains.add(domain)

    # Expand categories into blocklist
    for category in config.get("categories", []):
        for domain in category.get("domains", []):
            if domain:
                blocklist_domains.add(domain)

    # Extract allowlist domains
    allowlist_domains: set[str] = set()
    for entry in config.get("allowlist", []):
        domain = entry.get("domain", "")
        if domain:
            allowlist_domains.add(domain)

    return blocklist_domains, allowlist_domains


def _get_remote_domains(client: "NextDNSClient") -> tuple[set[str], set[str]]:
    """
    Fetch domain sets from NextDNS API.

    Returns:
        Tuple of (denylist_domains, allowlist_domains)

    Raises:
        RuntimeError: If API request fails
    """
    # Fetch denylist (bypass cache for fresh data)
    denylist = client.get_denylist(use_cache=False)
    if denylist is None:
        raise RuntimeError("Failed to fetch denylist from NextDNS API")

    denylist_domains = {
        entry["id"] for entry in denylist if entry.get("active", True) and entry.get("id")
    }

    # Fetch allowlist
    allowlist = client.get_allowlist(use_cache=False)
    if allowlist is None:
        raise RuntimeError("Failed to fetch allowlist from NextDNS API")

    allowlist_domains = {
        entry["id"] for entry in allowlist if entry.get("active", True) and entry.get("id")
    }

    return denylist_domains, allowlist_domains


def _compute_diff(local: set[str], remote: set[str]) -> tuple[set[str], set[str], set[str]]:
    """
    Compute diff between local and remote domain sets.

    Returns:
        Tuple of (local_only, remote_only, in_sync)
    """
    local_only = local - remote
    remote_only = remote - local
    in_sync = local & remote
    return local_only, remote_only, in_sync


def _create_config_backup(config_path: Path) -> Optional[Path]:
    """
    Create a timestamped backup of config.json.

    Keeps up to 3 most recent backups.

    Returns:
        Path to backup file, or None if backup failed
    """
    from datetime import datetime

    if not config_path.exists():
        return None

    # Create backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config_path.parent / f".config.json.backup.{timestamp}"

    try:
        shutil.copy2(config_path, backup_path)

        # Clean up old backups (keep only 3 most recent)
        backup_pattern = ".config.json.backup.*"
        backups = sorted(config_path.parent.glob(backup_pattern), reverse=True)
        for old_backup in backups[3:]:
            old_backup.unlink()

        return backup_path
    except OSError as e:
        logger.warning(f"Failed to create backup: {e}")
        return None


def _check_protected_removal(
    config: dict[str, Any],
    new_domains: set[str],
    list_type: str,
) -> list[str]:
    """
    Check if operation would remove protected domains.

    Protected means: locked=True or unblock_delay="never"

    Args:
        config: Current config dictionary
        new_domains: Set of domains that will remain
        list_type: "blocklist" or "allowlist"

    Returns:
        List of protected domains that would be removed
    """
    from .protection import is_locked

    current_list = config.get(list_type, [])
    protected_removals = []

    for entry in current_list:
        domain = entry.get("domain", "")
        if is_locked(entry) and domain not in new_domains:
            protected_removals.append(domain)

    return protected_removals


@config_cli.command("show")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def cmd_show(config_dir: Optional[Path], output_json: bool) -> None:
    """Display formatted configuration summary."""
    from rich.table import Table

    from .config import load_config, load_domains, load_nextdns_config
    from .scheduler import ScheduleEvaluator

    try:
        config_path = get_config_file_path(config_dir)

        if not config_path.exists():
            console.print(f"\n  [red]Error: Config file not found: {config_path}[/red]\n")
            sys.exit(1)

        config_data = load_config_file(config_path)

        if output_json:
            print(json.dumps(config_data, indent=2))
            return

        # Load full config for profile/timezone
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])
        nextdns_config = load_nextdns_config(config["script_dir"])

        # Create evaluator for schedule status
        evaluator = ScheduleEvaluator(config["timezone"])

        # === HEADER ===
        console.print()
        console.print("  [bold]NextDNS Blocker Configuration[/bold]")
        console.print("  [dim]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/dim]")
        console.print()

        # === PROFILE INFO ===
        console.print(f"  Profile:  [cyan]{config['profile_id']}[/cyan]")
        console.print(f"  Timezone: [cyan]{config['timezone']}[/cyan]")

        # === CATEGORIES ===
        categories = config_data.get("categories", [])
        if categories:
            console.print()
            console.print(f"  [bold]Categories ({len(categories)}):[/bold]")

            table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            table.add_column("ID", style="cyan")
            table.add_column("Domains", justify="right")
            table.add_column("Schedule")
            table.add_column("Unblock")

            for cat in categories:
                cat_id = cat.get("id", "unknown")
                cat_domains = cat.get("domains", [])
                schedule = cat.get("schedule")
                schedule_str = _format_schedule_summary(schedule)

                # Get unblock delay (use category default)
                unblock = cat.get("unblock_delay", "0")

                table.add_row(cat_id, str(len(cat_domains)), schedule_str, unblock)

            console.print(table)

        # === BLOCKLIST (individual domains) ===
        blocklist = config_data.get("blocklist", [])
        if blocklist:
            console.print()
            console.print(f"  [bold]Blocklist ({len(blocklist)} domains):[/bold]")

            # Show first few domains as summary
            for domain_config in blocklist[:5]:
                domain = domain_config.get("domain", "unknown")
                schedule = domain_config.get("schedule")
                schedule_str = _format_schedule_summary(schedule)
                unblock = _get_unblock_display(domain_config)

                if unblock == "never":
                    console.print(
                        f"    [blue]{domain}[/blue] - {schedule_str} [blue][never][/blue]"
                    )
                else:
                    console.print(f"    {domain} - {schedule_str}")

            if len(blocklist) > 5:
                console.print(f"    [dim]... and {len(blocklist) - 5} more[/dim]")

        # === NEXTDNS PARENTAL CONTROL ===
        if nextdns_config:
            console.print()
            console.print("  [bold]NextDNS Parental Control:[/bold]")

            # Categories from config
            pc_categories = nextdns_config.get("categories", [])
            if pc_categories:
                cat_ids = [c.get("id", "") for c in pc_categories]
                console.print(f"    Categories: [cyan]{', '.join(cat_ids)}[/cyan]")

            # Services from config
            pc_services = nextdns_config.get("services", [])
            if pc_services:
                svc_parts = []
                for svc in pc_services:
                    svc_id = svc.get("id", "")
                    schedule = svc.get("schedule")
                    if schedule:
                        sched_str = _format_schedule_summary(schedule)
                        svc_parts.append(f"{svc_id} ({sched_str})")
                    else:
                        svc_parts.append(svc_id)
                console.print(f"    Services: [cyan]{', '.join(svc_parts)}[/cyan]")

            # Settings from config
            pc_settings = nextdns_config.get("parental_control", {})
            if pc_settings:
                settings_parts = []
                safe_search = pc_settings.get("safe_search", False)
                youtube = pc_settings.get("youtube_restricted_mode", False)
                bypass = pc_settings.get("block_bypass", False)

                settings_parts.append(
                    "[green]safe_search ✓[/green]" if safe_search else "[dim]safe_search ✗[/dim]"
                )
                settings_parts.append(
                    "[green]youtube_restricted ✓[/green]"
                    if youtube
                    else "[dim]youtube_restricted ✗[/dim]"
                )
                settings_parts.append(
                    "[green]block_bypass ✓[/green]" if bypass else "[dim]block_bypass ✗[/dim]"
                )
                console.print(f"    Settings: {', '.join(settings_parts)}")

        # === ALLOWLIST ===
        if allowlist:
            console.print()
            # Count always-active vs scheduled
            always_active = [a for a in allowlist if not a.get("schedule")]
            scheduled = [a for a in allowlist if a.get("schedule")]

            console.print(f"  [bold]Allowlist ({len(allowlist)} entries):[/bold]")
            if always_active:
                console.print(f"    - {len(always_active)} always active")
            if scheduled:
                # Count active vs inactive
                active_now = sum(1 for s in scheduled if evaluator.should_allow_domain(s))
                inactive_now = len(scheduled) - active_now

                # Get domain names for display
                scheduled_names = [s.get("domain", "") for s in scheduled[:3]]
                names_str = ", ".join(scheduled_names)
                if len(scheduled) > 3:
                    names_str += f" +{len(scheduled) - 3} more"

                console.print(
                    f"    - {len(scheduled)} scheduled "
                    f"([green]{active_now} active[/green], "
                    f"[dim]{inactive_now} inactive[/dim])"
                )
                console.print(f"      [dim]{names_str}[/dim]")

        # === CONFIG PATH ===
        console.print()
        console.print(f"  [dim]Config: {config_path}[/dim]")
        console.print()

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n")
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


@config_cli.command("validate")
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_validate(output_json: bool, config_dir: Optional[Path]) -> None:
    """Validate configuration files before deployment.

    Checks config.json for:
    - Valid JSON syntax
    - Valid domain formats
    - Valid schedule time formats (HH:MM)
    - No blocklist/allowlist conflicts
    """
    # Import here to avoid circular imports
    from .cli import validate_impl

    validate_impl(output_json=output_json, config_dir=config_dir)


@config_cli.command("sync")
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option(
    "--config-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def cmd_sync(
    dry_run: bool,
    verbose: bool,
    config_dir: Optional[Path],
) -> None:
    """Synchronize domain blocking with schedules."""
    # Import here to avoid circular imports
    from .cli import sync_impl

    sync_impl(dry_run=dry_run, verbose=verbose, config_dir=config_dir)


@config_cli.command("diff")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("--json", "output_json", is_flag=True, help="Output in JSON format")
def cmd_diff(config_dir: Optional[Path], output_json: bool) -> None:
    """Show differences between local config and remote NextDNS.

    Compares domains in local config.json with the current state
    of your NextDNS denylist and allowlist.

    Legend:
      + domain  (remote only - exists in NextDNS but not in local config)
      - domain  (local only - exists in local config but not in NextDNS)
      = domain  (in sync - exists in both)
    """
    config_path = get_config_file_path(config_dir)

    if not config_path.exists():
        console.print(f"\n  [red]Error: Config file not found: {config_path}[/red]\n")
        sys.exit(1)

    try:
        # Get local domains
        local_blocklist, local_allowlist = _get_local_domains(config_path)

        # Get remote domains
        client = _get_client(config_dir)
        remote_blocklist, remote_allowlist = _get_remote_domains(client)

        # Compute diffs
        bl_local_only, bl_remote_only, bl_in_sync = _compute_diff(local_blocklist, remote_blocklist)
        al_local_only, al_remote_only, al_in_sync = _compute_diff(local_allowlist, remote_allowlist)

        # JSON output
        if output_json:
            result = {
                "blocklist": {
                    "local_only": sorted(bl_local_only),
                    "remote_only": sorted(bl_remote_only),
                    "in_sync": sorted(bl_in_sync),
                },
                "allowlist": {
                    "local_only": sorted(al_local_only),
                    "remote_only": sorted(al_remote_only),
                    "in_sync": sorted(al_in_sync),
                },
                "summary": {
                    "blocklist": {
                        "local": len(bl_local_only),
                        "remote": len(bl_remote_only),
                        "sync": len(bl_in_sync),
                    },
                    "allowlist": {
                        "local": len(al_local_only),
                        "remote": len(al_remote_only),
                        "sync": len(al_in_sync),
                    },
                },
            }
            print(json.dumps(result, indent=2))
            return

        # Rich output
        console.print()
        console.print("  [bold]NextDNS Config Diff[/bold]")
        console.print("  [dim]━━━━━━━━━━━━━━━━━━[/dim]")

        # Blocklist diff
        console.print()
        console.print("  [bold]Denylist:[/bold]")
        if not bl_local_only and not bl_remote_only and not bl_in_sync:
            console.print("    [dim]Empty on both sides[/dim]")
        else:
            for domain in sorted(bl_remote_only):
                console.print(f"    [green]+[/green] {domain}  [dim](remote only)[/dim]")
            for domain in sorted(bl_local_only):
                console.print(f"    [red]-[/red] {domain}  [dim](local only)[/dim]")
            for domain in sorted(bl_in_sync)[:5]:
                console.print(f"    [blue]=[/blue] {domain}  [dim](in sync)[/dim]")
            if len(bl_in_sync) > 5:
                console.print(f"    [dim]... and {len(bl_in_sync) - 5} more in sync[/dim]")

        # Allowlist diff
        console.print()
        console.print("  [bold]Allowlist:[/bold]")
        if not al_local_only and not al_remote_only and not al_in_sync:
            console.print("    [dim]Empty on both sides[/dim]")
        else:
            for domain in sorted(al_remote_only):
                console.print(f"    [green]+[/green] {domain}  [dim](remote only)[/dim]")
            for domain in sorted(al_local_only):
                console.print(f"    [red]-[/red] {domain}  [dim](local only)[/dim]")
            for domain in sorted(al_in_sync)[:5]:
                console.print(f"    [blue]=[/blue] {domain}  [dim](in sync)[/dim]")
            if len(al_in_sync) > 5:
                console.print(f"    [dim]... and {len(al_in_sync) - 5} more in sync[/dim]")

        # Summary
        console.print()
        console.print("  [bold]Summary:[/bold]")
        console.print(
            f"    Denylist:  [red]{len(bl_local_only)} local[/red], "
            f"[green]{len(bl_remote_only)} remote[/green], "
            f"[blue]{len(bl_in_sync)} sync[/blue]"
        )
        console.print(
            f"    Allowlist: [red]{len(al_local_only)} local[/red], "
            f"[green]{len(al_remote_only)} remote[/green], "
            f"[blue]{len(al_in_sync)} sync[/blue]"
        )
        console.print()

    except RuntimeError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)
    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n")
        sys.exit(1)


@config_cli.command("pull")
@click.option("--dry-run", is_flag=True, help="Preview changes without applying")
@click.option("--merge", is_flag=True, help="Merge with existing, preserving metadata")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def cmd_pull(
    dry_run: bool,
    merge: bool,
    config_dir: Optional[Path],
    yes: bool,
) -> None:
    """Fetch domains from NextDNS and update local config.

    By default, overwrites blocklist/allowlist with remote state.
    Use --merge to add new domains without removing existing ones.

    Examples:
        ndb config pull --dry-run      # Preview changes
        ndb config pull --merge        # Add new domains, keep existing
        ndb config pull -y             # Skip confirmation
    """
    from .cli import require_pin_verification
    from .panic import is_panic_mode

    config_path = get_config_file_path(config_dir)

    if not config_path.exists():
        console.print(f"\n  [red]Error: Config file not found: {config_path}[/red]\n")
        sys.exit(1)

    # Block during panic mode
    if is_panic_mode():
        console.print("\n  [red]Error: Cannot modify config during panic mode[/red]\n")
        sys.exit(1)

    # Require PIN for non-dry-run operations
    if not dry_run:
        require_pin_verification("config pull")

    try:
        # Load current config
        config = load_config_file(config_path)

        # Get remote domains
        client = _get_client(config_dir)
        remote_blocklist, remote_allowlist = _get_remote_domains(client)

        # Check for protected domain removal (only in overwrite mode)
        if not merge and not dry_run:
            protected_blocklist = _check_protected_removal(config, remote_blocklist, "blocklist")

            if protected_blocklist:
                console.print("\n  [red]Error: Pull would remove protected domains[/red]")
                console.print("\n  Protected blocklist domains:")
                for domain in protected_blocklist:
                    console.print(f"    [blue]{domain}[/blue] (locked)")
                console.print(
                    "\n  [yellow]Tip:[/yellow] Use --merge to add remote domains "
                    "without removing local ones.\n"
                )
                sys.exit(1)

        if merge:
            # Merge mode: add new domains, preserve existing metadata
            changes = _pull_merge(config_path, config, remote_blocklist, remote_allowlist, dry_run)
        else:
            # Overwrite mode: replace blocklist/allowlist
            changes = _pull_overwrite(
                config_path, config, remote_blocklist, remote_allowlist, dry_run, yes
            )

        # Show results
        if dry_run:
            console.print("\n  [yellow]Dry run - no changes applied[/yellow]")

        console.print()
        console.print("  [bold]Pull Summary:[/bold]")

        if merge:
            console.print(f"    Blocklist: [green]+{changes['blocklist_added']} added[/green]")
            console.print(f"    Allowlist: [green]+{changes['allowlist_added']} added[/green]")
            if changes.get("blocklist_local_only"):
                console.print(
                    f"\n  [yellow]Warning:[/yellow] {len(changes['blocklist_local_only'])} "
                    "blocklist domains exist locally but not in remote"
                )
        else:
            console.print(
                f"    Blocklist: {changes['blocklist_count']} domains "
                f"(was {changes['blocklist_previous']})"
            )
            console.print(
                f"    Allowlist: {changes['allowlist_count']} domains "
                f"(was {changes['allowlist_previous']})"
            )

        if not dry_run and changes.get("backup_path"):
            console.print(f"\n  [dim]Backup: {changes['backup_path']}[/dim]")

        console.print()

        if not dry_run:
            console.print(
                "  [green]✓[/green] Config updated\n"
                "  [yellow]![/yellow] Run 'ndb config sync' to apply changes to NextDNS\n"
            )

    except RuntimeError as e:
        console.print(f"\n  [red]Error: {e}[/red]\n")
        sys.exit(1)
    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n")
        sys.exit(1)


def _pull_overwrite(
    config_path: Path,
    config: dict[str, Any],
    remote_blocklist: set[str],
    remote_allowlist: set[str],
    dry_run: bool,
    skip_confirm: bool,
) -> dict[str, Any]:
    """
    Replace local blocklist/allowlist with remote domains.

    Preserves all other config sections (settings, categories, nextdns, etc.)
    """
    blocklist_previous = len(config.get("blocklist", []))
    allowlist_previous = len(config.get("allowlist", []))

    # Convert remote domains to local format
    new_blocklist = [{"domain": d} for d in sorted(remote_blocklist)]
    new_allowlist = [{"domain": d} for d in sorted(remote_allowlist)]

    changes: dict[str, Any] = {
        "blocklist_count": len(new_blocklist),
        "blocklist_previous": blocklist_previous,
        "allowlist_count": len(new_allowlist),
        "allowlist_previous": allowlist_previous,
        "backup_path": None,
    }

    if dry_run:
        return changes

    # Confirm before overwriting
    if not skip_confirm:
        console.print(
            f"\n  This will replace {blocklist_previous} blocklist and "
            f"{allowlist_previous} allowlist entries."
        )
        console.print("  [yellow]Warning:[/yellow] Metadata (schedules, delays) will be lost.")
        if not click.confirm("  Continue?", default=False):
            console.print("\n  [dim]Aborted[/dim]\n")
            sys.exit(0)

    # Create backup
    backup_path = _create_config_backup(config_path)
    changes["backup_path"] = str(backup_path) if backup_path else None

    # Update config
    config["blocklist"] = new_blocklist
    config["allowlist"] = new_allowlist

    # Ensure version exists
    if "version" not in config:
        config["version"] = CONFIG_VERSION

    save_config_file(config_path, config)
    audit_log(
        "CONFIG_PULL", f"overwrite: blocklist={len(new_blocklist)}, allowlist={len(new_allowlist)}"
    )

    return changes


def _pull_merge(
    config_path: Path,
    config: dict[str, Any],
    remote_blocklist: set[str],
    remote_allowlist: set[str],
    dry_run: bool,
) -> dict[str, Any]:
    """
    Merge remote domains into local config, preserving metadata.

    - Adds new domains from remote
    - Preserves existing metadata (schedule, unblock_delay, locked)
    - Does not remove any local domains
    """
    # Build lookup of existing domains
    existing_blocklist = {
        entry["domain"]: entry for entry in config.get("blocklist", []) if entry.get("domain")
    }
    existing_allowlist = {
        entry["domain"]: entry for entry in config.get("allowlist", []) if entry.get("domain")
    }

    # Find new domains to add
    new_blocklist_domains = remote_blocklist - set(existing_blocklist.keys())
    new_allowlist_domains = remote_allowlist - set(existing_allowlist.keys())

    # Find domains in local but not in remote (for warning)
    local_only_blocklist = set(existing_blocklist.keys()) - remote_blocklist
    local_only_allowlist = set(existing_allowlist.keys()) - remote_allowlist

    changes: dict[str, Any] = {
        "blocklist_added": len(new_blocklist_domains),
        "allowlist_added": len(new_allowlist_domains),
        "blocklist_local_only": sorted(local_only_blocklist),
        "allowlist_local_only": sorted(local_only_allowlist),
        "backup_path": None,
    }

    if dry_run:
        return changes

    # Create backup
    backup_path = _create_config_backup(config_path)
    changes["backup_path"] = str(backup_path) if backup_path else None

    # Add new domains
    updated_blocklist = list(existing_blocklist.values())
    for domain in sorted(new_blocklist_domains):
        updated_blocklist.append({"domain": domain})

    updated_allowlist = list(existing_allowlist.values())
    for domain in sorted(new_allowlist_domains):
        updated_allowlist.append({"domain": domain})

    # Update config
    config["blocklist"] = updated_blocklist
    config["allowlist"] = updated_allowlist

    # Ensure version exists
    if "version" not in config:
        config["version"] = CONFIG_VERSION

    save_config_file(config_path, config)
    audit_log(
        "CONFIG_PULL",
        f"merge: +{len(new_blocklist_domains)} blocklist, +{len(new_allowlist_domains)} allowlist",
    )

    return changes


# =============================================================================
# REGISTRATION
# =============================================================================


def register_config(main_group: click.Group) -> None:
    """Register config commands as subcommand of main CLI."""
    main_group.add_command(config_cli, name="config")


# Allow running standalone for testing
main = config_cli
