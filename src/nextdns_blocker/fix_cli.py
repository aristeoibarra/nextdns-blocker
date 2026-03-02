"""Fix and uninstall commands for NextDNS Blocker."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import rich_click as click

from .cli_formatter import console
from .config import load_config
from .exceptions import ConfigurationError
from .platform_utils import get_executable_path, is_macos, is_windows
from .watchdog import WINDOWS_TASK_SYNC_NAME, WINDOWS_TASK_WATCHDOG_NAME


@click.command()
@click.option("-y", "--yes", is_flag=True, help="Skip confirmation prompt")
def uninstall(yes: bool) -> None:
    """Completely remove NextDNS Blocker and all its data.

    This command will:
    - Remove all scheduled jobs (launchd/cron/Task Scheduler)
    - Delete configuration (.env and database)
    - Delete all logs, cache, and data files

    After running this command, you will need to reinstall the package
    using your package manager (pip, pipx, or brew).
    """
    import shutil

    from .config import get_config_dir, get_data_dir
    from .watchdog import (
        _uninstall_cron_jobs,
        _uninstall_launchd_jobs,
        _uninstall_windows_tasks,
    )

    config_dir = get_config_dir()
    data_dir = get_data_dir()

    # Collect unique directories to remove
    dirs_to_remove: list[tuple[str, Path]] = []
    dirs_to_remove.append(("Config", config_dir))
    if data_dir != config_dir:
        dirs_to_remove.append(("Data", data_dir))

    console.print("\n  [bold red]NextDNS Blocker Uninstall[/bold red]")
    console.print("  [bold red]-------------------------[/bold red]")
    console.print("\n  This will permanently delete:")
    console.print("    \u2022 Scheduled jobs (watchdog)")
    for name, path in dirs_to_remove:
        console.print(f"    \u2022 {name}: [yellow]{path}[/yellow]")
    console.print()

    if not yes:
        if not click.confirm("  Are you sure you want to continue?", default=False):
            console.print("\n  [green]Uninstall cancelled.[/green]\n")
            return

    console.print("\n  [bold]Removing...[/bold]")

    total_steps = 1 + len(dirs_to_remove)
    step = 1

    # Step 1: Remove scheduled jobs
    console.print(f"    [{step}/{total_steps}] Removing scheduled jobs...")
    try:
        if is_macos():
            _uninstall_launchd_jobs()
        elif is_windows():
            _uninstall_windows_tasks()
        else:
            _uninstall_cron_jobs()
        console.print("          [green]Done[/green]")
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        console.print(f"          [yellow]Warning: {e}[/yellow]")

    # Remove directories
    for name, path in dirs_to_remove:
        step += 1
        console.print(f"    [{step}/{total_steps}] Removing {name.lower()} directory...")
        try:
            if path.exists():
                shutil.rmtree(path)
                console.print("          [green]Done[/green]")
            else:
                console.print("          [yellow]Already removed[/yellow]")
        except (OSError, PermissionError) as e:
            console.print(f"          [red]Error: {e}[/red]")

    console.print("\n  [green]Uninstall complete![/green]")
    console.print("  To remove the package itself, run:")
    console.print("    [yellow]brew uninstall nextdns-blocker[/yellow]  (Homebrew)")
    console.print("    [yellow]pipx uninstall nextdns-blocker[/yellow]  (pipx)")
    console.print("    [yellow]pip uninstall nextdns-blocker[/yellow]   (pip)")
    console.print()


@click.command()
def fix() -> None:
    """Fix common issues by reinstalling scheduler and running sync."""
    console.print("\n  NextDNS Blocker Fix")
    console.print("  -------------------\n")

    # Step 1: Verify config
    console.print("  [bold][1/5] Checking configuration...[/bold]")
    try:
        load_config()  # Validates config exists and is valid
        console.print("        Config: [green]OK[/green]")
    except ConfigurationError as e:
        console.print(f"        Config: [red]FAILED - {e}[/red]")
        console.print("\n  Run 'nextdns-blocker init' to set up configuration.\n")
        sys.exit(1)

    # Step 2: Find executable
    console.print("  [bold][2/5] Detecting installation...[/bold]")
    detected_path = get_executable_path()
    exe_cmd: Optional[str] = detected_path
    # Detect installation type
    if "-m nextdns_blocker" in detected_path:
        console.print("        Type: module")
        exe_cmd = None  # Use module invocation
    elif ".local" in detected_path or "pipx" in detected_path.lower():
        console.print("        Type: pipx")
    else:
        console.print("        Type: system")

    # Step 3: Reinstall scheduler
    console.print("  [bold][3/5] Reinstalling scheduler...[/bold]")
    try:
        if is_macos():
            # Uninstall launchd jobs with timeout protection
            subprocess.run(
                [
                    "launchctl",
                    "unload",
                    str(Path.home() / "Library/LaunchAgents/com.nextdns-blocker.sync.plist"),
                ],
                capture_output=True,
                timeout=30,
                check=False,  # Don't raise on non-zero exit
            )
            subprocess.run(
                [
                    "launchctl",
                    "unload",
                    str(Path.home() / "Library/LaunchAgents/com.nextdns-blocker.watchdog.plist"),
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
        elif is_windows():
            # Uninstall Windows Task Scheduler tasks with timeout protection
            subprocess.run(
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_SYNC_NAME, "/f"],
                capture_output=True,
                timeout=30,
                check=False,
            )
            subprocess.run(
                ["schtasks", "/delete", "/tn", WINDOWS_TASK_WATCHDOG_NAME, "/f"],
                capture_output=True,
                timeout=30,
                check=False,
            )

        # Use the watchdog install command
        if exe_cmd:
            result = subprocess.run(
                [exe_cmd, "watchdog", "install"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "nextdns_blocker", "watchdog", "install"],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode == 0:
            console.print("        Scheduler: [green]OK[/green]")
        else:
            console.print(f"        Scheduler: [red]FAILED - {result.stderr}[/red]")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print("        Scheduler: [red]FAILED - timeout[/red]")
        sys.exit(1)
    except OSError as e:
        console.print(f"        Scheduler: [red]FAILED - {e}[/red]")
        sys.exit(1)

    # Step 4: Run sync
    console.print("  [bold][4/5] Running sync...[/bold]")
    try:
        if exe_cmd:
            result = subprocess.run(
                [exe_cmd, "sync"],
                capture_output=True,
                text=True,
                timeout=60,
            )
        else:
            result = subprocess.run(
                [sys.executable, "-m", "nextdns_blocker", "sync"],
                capture_output=True,
                text=True,
                timeout=60,
            )

        if result.returncode == 0:
            console.print("        Sync: [green]OK[/green]")
        else:
            console.print(f"        Sync: [red]FAILED - {result.stderr}[/red]")
    except subprocess.TimeoutExpired:
        console.print("        Sync: [red]TIMEOUT[/red]")
    except (OSError, subprocess.SubprocessError) as e:
        console.print(f"        Sync: [red]FAILED - {e}[/red]")

    # Step 5: Shell completion
    console.print("\n  [green]Fix complete![/green]\n")


def register_fix(main_group: click.Group) -> None:
    """Register fix and uninstall commands with the main CLI group."""
    main_group.add_command(fix)
    main_group.add_command(uninstall)
