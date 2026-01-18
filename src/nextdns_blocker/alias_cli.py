"""Alias command group for NextDNS Blocker.

Provides commands to configure shell aliases for the nextdns-blocker command.
"""

import os
import re
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from .platform_utils import is_macos, is_windows

console = Console(highlight=False)

# =============================================================================
# CONSTANTS
# =============================================================================

# Alias name validation pattern (alphanumeric, dash, underscore, 2-20 chars)
ALIAS_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{1,19}$")

# Marker comments for identifying our aliases in config files
ALIAS_MARKER_START = "# nextdns-blocker alias - DO NOT EDIT"
ALIAS_MARKER_END = "# end nextdns-blocker alias"

# Shell config file locations
SHELL_CONFIG_FILES = {
    "bash": [".bashrc", ".bash_profile"],
    "zsh": [".zshrc"],
    "fish": [".config/fish/config.fish"],
}

# PowerShell profile paths (Windows)
POWERSHELL_PROFILE_PATHS = [
    Path.home() / "Documents" / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1",
    Path.home() / "Documents" / "PowerShell" / "Microsoft.PowerShell_profile.ps1",
]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _validate_alias_name(name: str) -> bool:
    """Validate alias name format."""
    return bool(ALIAS_NAME_PATTERN.match(name))


def _detect_shell() -> Optional[str]:
    """Detect the current user's shell."""
    if is_windows():
        return "powershell"

    shell_env = os.environ.get("SHELL", "")
    if "zsh" in shell_env:
        return "zsh"
    elif "bash" in shell_env:
        return "bash"
    elif "fish" in shell_env:
        return "fish"

    # Fallback: check common locations
    if is_macos():
        # macOS default is zsh since Catalina
        return "zsh"
    return "bash"


def _get_shell_config_path(shell: str) -> Optional[Path]:
    """Get the path to the shell config file."""
    if shell == "powershell":
        # Check which PowerShell profile exists or use first one
        for profile_path in POWERSHELL_PROFILE_PATHS:
            if profile_path.exists():
                return profile_path
        # Default to first path (will be created)
        return POWERSHELL_PROFILE_PATHS[0]

    # Unix shells
    config_files = SHELL_CONFIG_FILES.get(shell, [])
    home = Path.home()

    for config_file in config_files:
        config_path = home / config_file
        if config_path.exists():
            return config_path

    # Return first option if none exist (will be created)
    if config_files:
        return home / config_files[0]

    return None


def _generate_alias_line(name: str, shell: str) -> str:
    """Generate the alias command for the given shell."""
    if shell == "powershell":
        return f"Set-Alias -Name {name} -Value nextdns-blocker"
    elif shell == "fish":
        return f"alias {name} 'nextdns-blocker'"
    else:
        # bash, zsh
        return f"alias {name}='nextdns-blocker'"


def _generate_alias_block(name: str, shell: str) -> str:
    """Generate the full alias block with markers."""
    alias_line = _generate_alias_line(name, shell)
    return f"{ALIAS_MARKER_START}\n{alias_line}\n{ALIAS_MARKER_END}"


def _find_existing_alias(config_path: Path) -> Optional[str]:
    """Find an existing nextdns-blocker alias in config file.

    Returns:
        The alias name if found, None otherwise.
    """
    if not config_path.exists():
        return None

    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError:
        return None

    # Look for our marker
    if ALIAS_MARKER_START not in content:
        return None

    # Extract the alias name from the line
    # Patterns: alias name='nextdns-blocker' or Set-Alias -Name name -Value nextdns-blocker
    patterns = [
        r"alias\s+(\w+)=['\"]?nextdns-blocker['\"]?",  # bash/zsh/fish
        r"Set-Alias\s+-Name\s+(\w+)\s+-Value\s+nextdns-blocker",  # PowerShell
    ]

    for pattern in patterns:
        match = re.search(pattern, content)
        if match:
            return match.group(1)

    return None


def _remove_alias_block(content: str) -> str:
    """Remove the alias block from config content."""
    # Remove the entire block including markers
    pattern = rf"{re.escape(ALIAS_MARKER_START)}.*?{re.escape(ALIAS_MARKER_END)}\n?"
    return re.sub(pattern, "", content, flags=re.DOTALL)


def _install_alias(name: str, shell: str, config_path: Path) -> tuple[bool, str]:
    """Install alias in shell config file.

    Returns:
        Tuple of (success, message)
    """
    # Check if file exists
    if config_path.exists():
        try:
            content = config_path.read_text(encoding="utf-8")
        except OSError as e:
            return False, f"Failed to read {config_path}: {e}"

        # Check for existing alias
        existing = _find_existing_alias(config_path)
        if existing:
            if existing == name:
                return True, f"Alias '{name}' already installed"
            else:
                # Remove old alias, install new one
                content = _remove_alias_block(content)
    else:
        content = ""
        # Ensure parent directory exists (for fish)
        config_path.parent.mkdir(parents=True, exist_ok=True)

    # Add new alias block
    alias_block = _generate_alias_block(name, shell)

    # Ensure there's a newline before our block
    if content and not content.endswith("\n"):
        content += "\n"
    if content:
        content += "\n"
    content += alias_block + "\n"

    try:
        config_path.write_text(content, encoding="utf-8")
    except OSError as e:
        return False, f"Failed to write {config_path}: {e}"

    return True, f"Alias '{name}' installed in {config_path}"


def _uninstall_alias(config_path: Path) -> tuple[bool, str]:
    """Remove alias from shell config file.

    Returns:
        Tuple of (success, message)
    """
    if not config_path.exists():
        return False, f"Config file not found: {config_path}"

    try:
        content = config_path.read_text(encoding="utf-8")
    except OSError as e:
        return False, f"Failed to read {config_path}: {e}"

    if ALIAS_MARKER_START not in content:
        return False, "No nextdns-blocker alias found"

    # Remove alias block
    new_content = _remove_alias_block(content)

    try:
        config_path.write_text(new_content, encoding="utf-8")
    except OSError as e:
        return False, f"Failed to write {config_path}: {e}"

    return True, f"Alias removed from {config_path}"


def _get_reload_command(shell: str, config_path: Path) -> str:
    """Get the command to reload shell config."""
    if shell == "powershell":
        return f". {config_path}"
    elif shell == "fish":
        return f"source {config_path}"
    else:
        return f"source {config_path}"


# =============================================================================
# CLI COMMANDS
# =============================================================================


@click.group()
def alias_cli() -> None:
    """Manage shell alias for nextdns-blocker."""
    pass


@alias_cli.command("install")
@click.argument("name")
def cmd_install(name: str) -> None:
    """Install a shell alias for nextdns-blocker.

    NAME is the alias you want to use (e.g., 'ndb', 'ndns', 'block').

    Examples:
        nextdns-blocker alias install ndb
        nextdns-blocker alias install ndns
    """
    # Validate alias name
    if not _validate_alias_name(name):
        console.print(
            f"\n  [red]Error: Invalid alias name '{name}'[/red]"
            "\n  [dim]Must be 2-20 characters, start with a letter,[/dim]"
            "\n  [dim]and contain only letters, numbers, dashes, and underscores.[/dim]\n"
        )
        sys.exit(1)

    # Detect shell
    shell = _detect_shell()
    if not shell:
        console.print("\n  [red]Error: Could not detect shell[/red]\n")
        sys.exit(1)

    # Get config file path
    config_path = _get_shell_config_path(shell)
    if not config_path:
        console.print(f"\n  [red]Error: Could not find config file for {shell}[/red]\n")
        sys.exit(1)

    console.print("\n  [bold]Installing alias...[/bold]\n")
    console.print(f"  Shell:  {shell}")
    console.print(f"  File:   {config_path}")
    console.print(f"  Alias:  {name} \u2192 nextdns-blocker")
    console.print()

    # Install alias
    success, message = _install_alias(name, shell, config_path)

    if success:
        console.print(f"  [green]\u2713 {message}[/green]")
        console.print()
        console.print("  [yellow]Reload your shell or run:[/yellow]")
        reload_cmd = _get_reload_command(shell, config_path)
        console.print(f"    [cyan]{reload_cmd}[/cyan]")
        console.print()
    else:
        console.print(f"  [red]\u2717 {message}[/red]\n")
        sys.exit(1)


@alias_cli.command("uninstall")
def cmd_uninstall() -> None:
    """Remove the nextdns-blocker shell alias."""
    # Detect shell
    shell = _detect_shell()
    if not shell:
        console.print("\n  [red]Error: Could not detect shell[/red]\n")
        sys.exit(1)

    # Get config file path
    config_path = _get_shell_config_path(shell)
    if not config_path:
        console.print(f"\n  [red]Error: Could not find config file for {shell}[/red]\n")
        sys.exit(1)

    console.print("\n  [bold]Uninstalling alias...[/bold]\n")

    # Uninstall alias
    success, message = _uninstall_alias(config_path)

    if success:
        console.print(f"  [green]\u2713 {message}[/green]")
        console.print()
        console.print("  [yellow]Reload your shell or run:[/yellow]")
        reload_cmd = _get_reload_command(shell, config_path)
        console.print(f"    [cyan]{reload_cmd}[/cyan]")
        console.print()
    else:
        console.print(f"  [yellow]{message}[/yellow]\n")


@alias_cli.command("status")
def cmd_status() -> None:
    """Show current alias status."""
    # Detect shell
    shell = _detect_shell()
    if not shell:
        console.print("\n  [red]Error: Could not detect shell[/red]\n")
        sys.exit(1)

    # Get config file path
    config_path = _get_shell_config_path(shell)
    if not config_path:
        console.print(f"\n  [red]Error: Could not find config file for {shell}[/red]\n")
        sys.exit(1)

    console.print("\n  [bold]Alias Status[/bold]")
    console.print(
        "  [dim]\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500[/dim]\n"
    )
    console.print(f"  Shell:       {shell}")
    console.print(f"  Config file: {config_path}")

    # Check for existing alias
    existing = _find_existing_alias(config_path)
    if existing:
        console.print(f"  Alias:       [green]{existing}[/green] \u2192 nextdns-blocker")
        console.print("\n  [green]Alias is installed[/green]\n")
    else:
        console.print("  Alias:       [dim]not installed[/dim]")
        console.print("\n  [yellow]No alias configured[/yellow]")
        console.print("  Run: [cyan]nextdns-blocker alias install <name>[/cyan]\n")


# =============================================================================
# REGISTRATION
# =============================================================================


def register_alias(main_group: click.Group) -> None:
    """Register alias commands as subcommand of main CLI."""
    main_group.add_command(alias_cli, name="alias")


# Allow running standalone for testing
main = alias_cli
