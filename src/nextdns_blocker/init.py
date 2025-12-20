"""Interactive initialization wizard for NextDNS Blocker."""

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import click
import requests

from .common import get_log_dir, write_secure_file
from .completion import detect_shell, install_completion
from .config import DEFAULT_TIMEOUT, get_config_dir
from .platform_utils import (
    get_executable_args,
    get_executable_path,
    is_macos,
    is_windows,
)
from .watchdog import _build_task_command

logger = logging.getLogger(__name__)

# Timeout for subprocess commands during init (seconds)
INIT_SUBPROCESS_TIMEOUT = 30

# NextDNS API base URL for validation
NEXTDNS_API_URL = "https://api.nextdns.io"


def validate_api_credentials(api_key: str, profile_id: str) -> tuple[bool, str]:
    """
    Validate API credentials against NextDNS API.

    Args:
        api_key: NextDNS API key
        profile_id: NextDNS profile ID

    Returns:
        Tuple of (success, message)
    """
    try:
        response = requests.get(
            f"{NEXTDNS_API_URL}/profiles/{profile_id}/denylist",
            headers={"X-Api-Key": api_key},
            timeout=DEFAULT_TIMEOUT,
        )

        if response.status_code == 200:
            return True, "Credentials valid"
        elif response.status_code == 401:
            return False, "Invalid API key"
        elif response.status_code == 404:
            return False, "Profile ID not found"
        else:
            return False, f"API error: {response.status_code}"

    except requests.exceptions.Timeout:
        return False, "Connection timeout"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed"
    except requests.exceptions.RequestException as e:
        return False, f"Request error: {e}"


def validate_timezone(tz_str: str) -> tuple[bool, str]:
    """
    Validate a timezone string.

    Args:
        tz_str: Timezone string (e.g., 'America/Mexico_City')

    Returns:
        Tuple of (success, message)
    """
    try:
        ZoneInfo(tz_str)
        return True, "Valid timezone"
    except KeyError:
        return False, f"Invalid timezone: {tz_str}"


def detect_system_timezone() -> str:
    """
    Auto-detect the system timezone.

    Attempts detection in order:
    1. TZ environment variable
    2. /etc/localtime symlink (macOS/Linux)
    3. Windows tzutil command
    4. Falls back to UTC

    Returns:
        IANA timezone string (e.g., 'America/Mexico_City')
    """
    # Try TZ environment variable first
    tz_env = os.environ.get("TZ")
    if tz_env:
        try:
            ZoneInfo(tz_env)
            return tz_env
        except KeyError:
            logger.debug(f"TZ environment variable '{tz_env}' is not a valid timezone")

    # Try reading /etc/localtime symlink (macOS/Linux)
    if not is_windows():
        try:
            localtime = Path("/etc/localtime")
            if localtime.is_symlink():
                target = str(localtime.resolve())
                # Handle both "zoneinfo/" and "zoneinfo.default/" (macOS)
                for marker in ("zoneinfo/", "zoneinfo.default/"):
                    if marker in target:
                        tz_name = target.split(marker)[-1]
                        try:
                            ZoneInfo(tz_name)
                            return tz_name
                        except KeyError:
                            logger.debug(f"Timezone '{tz_name}' from /etc/localtime is not valid")
                            # Continue to try next marker or fallback
        except OSError as e:
            logger.debug(f"Could not read /etc/localtime symlink: {e}")

    # Try Windows tzutil command
    if is_windows():
        try:
            result = subprocess.run(
                ["tzutil", "/g"],
                capture_output=True,
                text=True,
                check=True,
            )
            windows_tz = result.stdout.strip()
            # Map common Windows timezone names to IANA
            windows_to_iana = {
                "Pacific Standard Time": "America/Los_Angeles",
                "Mountain Standard Time": "America/Denver",
                "Central Standard Time": "America/Chicago",
                "Eastern Standard Time": "America/New_York",
                "Central Standard Time (Mexico)": "America/Mexico_City",
                "US Eastern Standard Time": "America/Indianapolis",
                "Atlantic Standard Time": "America/Halifax",
                "UTC": "UTC",
                "GMT Standard Time": "Europe/London",
                "W. Europe Standard Time": "Europe/Berlin",
                "Romance Standard Time": "Europe/Paris",
                "Central European Standard Time": "Europe/Warsaw",
                "E. Europe Standard Time": "Europe/Bucharest",
                "Russian Standard Time": "Europe/Moscow",
                "China Standard Time": "Asia/Shanghai",
                "Tokyo Standard Time": "Asia/Tokyo",
                "Korea Standard Time": "Asia/Seoul",
                "India Standard Time": "Asia/Kolkata",
                "AUS Eastern Standard Time": "Australia/Sydney",
                "E. Australia Standard Time": "Australia/Brisbane",
                "New Zealand Standard Time": "Pacific/Auckland",
            }
            if windows_tz in windows_to_iana:
                return windows_to_iana[windows_tz]
            else:
                logger.debug(f"Windows timezone '{windows_tz}' has no IANA mapping")
        except (subprocess.SubprocessError, OSError) as e:
            logger.debug(f"Could not detect Windows timezone: {e}")

    return "UTC"


def create_env_file(
    config_dir: Path,
    api_key: str,
    profile_id: str,
) -> Path:
    """
    Create .env file with API credentials.

    Args:
        config_dir: Directory to create .env in
        api_key: NextDNS API key
        profile_id: NextDNS profile ID

    Returns:
        Path to created .env file
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    env_file = config_dir / ".env"

    content = f"""# NextDNS Blocker Configuration
# Generated by 'nextdns-blocker init'

# NextDNS API credentials (required)
NEXTDNS_API_KEY={api_key}
NEXTDNS_PROFILE_ID={profile_id}
"""

    # Write with secure permissions (0o600)
    write_secure_file(env_file, content)

    return env_file


def create_config_file(config_dir: Path, timezone: str) -> Path:
    """
    Create config.json with initial structure.

    Args:
        config_dir: Directory to create config.json in
        timezone: Auto-detected timezone string

    Returns:
        Path to created config.json file
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / "config.json"

    config = {
        "_comment": "NextDNS Blocker configuration. See docs for schedule format.",
        "version": "1.0",
        "settings": {
            "timezone": timezone,
            "editor": None,
        },
        "blocklist": [],
        "allowlist": [],
    }

    # Use write_secure_file for consistent secure permissions (0o600)
    write_secure_file(config_file, json.dumps(config, indent=2) + "\n")
    return config_file


# =============================================================================
# SCHEDULING INSTALLATION
# =============================================================================


def install_scheduling() -> tuple[bool, str]:
    """
    Install scheduling jobs (launchd on macOS, cron on Linux, Task Scheduler on Windows).

    Returns:
        Tuple of (success, message)
    """
    if is_macos():
        return _install_launchd()
    elif is_windows():
        return _install_windows_task()
    else:
        return _install_cron()


def _install_launchd() -> tuple[bool, str]:
    """Install launchd jobs for macOS."""
    import plistlib

    try:
        # Get paths
        launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
        launch_agents_dir.mkdir(parents=True, exist_ok=True)

        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use centralized executable detection
        exe_args = get_executable_args()

        # Sync plist
        sync_plist_path = launch_agents_dir / "com.nextdns-blocker.sync.plist"
        sync_plist: dict[str, Any] = {
            "Label": "com.nextdns-blocker.sync",
            "ProgramArguments": exe_args + ["sync"],
            "StartInterval": 120,  # 2 minutes
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "StandardOutPath": str(log_dir / "sync.log"),
            "StandardErrorPath": str(log_dir / "sync.log"),
            "EnvironmentVariables": {
                "PATH": f"{Path.home()}/.local/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
            },
        }

        # Watchdog plist
        watchdog_plist_path = launch_agents_dir / "com.nextdns-blocker.watchdog.plist"
        watchdog_plist: dict[str, Any] = {
            "Label": "com.nextdns-blocker.watchdog",
            "ProgramArguments": exe_args + ["watchdog", "check"],
            "StartInterval": 60,  # 1 minute
            "RunAtLoad": True,
            "KeepAlive": {"SuccessfulExit": False},
            "StandardOutPath": str(log_dir / "watchdog.log"),
            "StandardErrorPath": str(log_dir / "watchdog.log"),
            "EnvironmentVariables": {
                "PATH": f"{Path.home()}/.local/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
            },
        }
        # Write plist files
        sync_plist_path.write_bytes(plistlib.dumps(sync_plist))
        sync_plist_path.chmod(0o644)

        watchdog_plist_path.write_bytes(plistlib.dumps(watchdog_plist))
        watchdog_plist_path.chmod(0o644)

        # Unload existing jobs (ignore errors)
        subprocess.run(
            ["launchctl", "unload", str(sync_plist_path)],
            capture_output=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )
        subprocess.run(
            ["launchctl", "unload", str(watchdog_plist_path)],
            capture_output=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )

        # Load jobs
        result_sync = subprocess.run(
            ["launchctl", "load", str(sync_plist_path)],
            capture_output=True,
            text=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )
        result_wd = subprocess.run(
            ["launchctl", "load", str(watchdog_plist_path)],
            capture_output=True,
            text=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )

        if result_sync.returncode == 0 and result_wd.returncode == 0:
            return True, "launchd"
        else:
            return False, "Failed to load launchd jobs"

    except subprocess.TimeoutExpired:
        return False, "launchd command timed out"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"launchd error: {e}"


def _install_cron() -> tuple[bool, str]:
    """Install cron jobs for Linux."""
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use centralized executable detection
        exe = get_executable_path()

        # Cron job definitions
        sync_log = str(log_dir / "sync.log")
        wd_log = str(log_dir / "watchdog.log")
        cron_sync = f'*/2 * * * * {exe} sync >> "{sync_log}" 2>&1'
        cron_wd = f'* * * * * {exe} watchdog check >> "{wd_log}" 2>&1'
        # Get current crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )
        current_crontab = result.stdout if result.returncode == 0 else ""

        # Remove existing nextdns-blocker entries
        lines = [
            line
            for line in current_crontab.split("\n")
            if "nextdns-blocker" not in line and line.strip()
        ]

        # Add new entries
        lines.extend([cron_sync, cron_wd])
        new_crontab = "\n".join(lines) + "\n"

        # Set new crontab
        result = subprocess.run(
            ["crontab", "-"],
            input=new_crontab,
            text=True,
            capture_output=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )

        if result.returncode == 0:
            return True, "cron"
        else:
            return False, "Failed to set crontab"

    except subprocess.TimeoutExpired:
        return False, "cron command timed out"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"cron error: {e}"


def _install_windows_task() -> tuple[bool, str]:
    """Install Windows Task Scheduler tasks."""
    try:
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)

        # Use centralized executable detection
        exe = get_executable_path()

        # Task names
        sync_task_name = "NextDNS-Blocker-Sync"
        watchdog_task_name = "NextDNS-Blocker-Watchdog"

        # Delete existing tasks (ignore errors)
        subprocess.run(
            ["schtasks", "/delete", "/tn", sync_task_name, "/f"],
            capture_output=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )
        subprocess.run(
            ["schtasks", "/delete", "/tn", watchdog_task_name, "/f"],
            capture_output=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )

        # Create sync task (every 2 minutes)
        sync_log = str(log_dir / "sync.log")
        sync_cmd = _build_task_command(exe, "sync", sync_log)
        result_sync = subprocess.run(
            [
                "schtasks",
                "/create",
                "/tn",
                sync_task_name,
                "/tr",
                sync_cmd,
                "/sc",
                "minute",
                "/mo",
                "2",
                "/f",
            ],
            capture_output=True,
            text=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )

        # Create watchdog task (every 1 minute)
        wd_log = str(log_dir / "watchdog.log")
        wd_cmd = _build_task_command(exe, "watchdog check", wd_log)
        result_wd = subprocess.run(
            [
                "schtasks",
                "/create",
                "/tn",
                watchdog_task_name,
                "/tr",
                wd_cmd,
                "/sc",
                "minute",
                "/mo",
                "1",
                "/f",
            ],
            capture_output=True,
            text=True,
            timeout=INIT_SUBPROCESS_TIMEOUT,
        )

        if result_sync.returncode == 0 and result_wd.returncode == 0:
            return True, "Task Scheduler"
        else:
            error_msg = result_sync.stderr or result_wd.stderr or "Unknown error"
            return False, f"Failed to create scheduled tasks: {error_msg}"

    except subprocess.TimeoutExpired:
        return False, "Task Scheduler command timed out"
    except (OSError, subprocess.SubprocessError) as e:
        return False, f"Task Scheduler error: {e}"


def run_initial_sync() -> bool:
    """Run initial sync command."""
    try:
        # Use centralized executable detection
        exe_args = get_executable_args()
        result = subprocess.run(
            exe_args + ["sync"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        logger.warning("Initial sync timed out after 60 seconds")
        return False
    except OSError as e:
        logger.warning(f"Initial sync failed: {e}")
        return False


def run_interactive_wizard(config_dir_override: Optional[Path] = None) -> bool:
    """
    Run the interactive setup wizard.

    Args:
        config_dir_override: Optional config directory override

    Returns:
        True if setup completed successfully
    """
    click.echo()
    click.echo(click.style("  NextDNS Blocker Setup", fg="cyan", bold=True))
    click.echo(click.style("  " + "=" * 21, fg="cyan"))
    click.echo()

    # Prompt for API key
    api_key = click.prompt("  API Key (from https://my.nextdns.io/account)", hide_input=True)

    if not api_key or not api_key.strip():
        click.echo(click.style("\n  Error: API key is required\n", fg="red"))
        return False

    api_key = api_key.strip()

    # Prompt for Profile ID
    profile_id = click.prompt("  Profile ID (from URL my.nextdns.io/<profile_id>)")

    if not profile_id or not profile_id.strip():
        click.echo(click.style("\n  Error: Profile ID is required\n", fg="red"))
        return False

    profile_id = profile_id.strip()

    # Validate credentials
    click.echo()
    click.echo("  Validating credentials... ", nl=False)

    valid, msg = validate_api_credentials(api_key, profile_id)

    if valid:
        click.echo(click.style("OK", fg="green"))
    else:
        click.echo(click.style("FAILED", fg="red"))
        click.echo(click.style(f"\n  Error: {msg}\n", fg="red"))
        return False

    # Determine config directory
    config_dir = get_config_dir(config_dir_override)

    # Auto-detect timezone
    timezone = detect_system_timezone()
    click.echo(f"  Timezone detected: {timezone}")

    # Create .env file (credentials only)
    click.echo()
    env_file = create_env_file(config_dir, api_key, profile_id)
    click.echo(f"  Created: {env_file}")

    # Create config.json if it doesn't exist
    config_file = config_dir / "config.json"
    if not config_file.exists():
        config_file = create_config_file(config_dir, timezone)
        click.echo(f"  Created: {config_file}")
    else:
        click.echo(f"  Existing config.json found: {config_file}")

    # Install scheduling (launchd/cron)
    click.echo()
    click.echo("  Installing scheduling...")
    sched_success, sched_type = install_scheduling()

    if sched_success:
        click.echo(click.style(f"  {sched_type} jobs installed", fg="green"))
        click.echo("    sync:      every 2 min")
        click.echo("    watchdog:  every 1 min")
    else:
        click.echo(click.style(f"  Warning: {sched_type}", fg="yellow"))
        click.echo("  You can install manually with: nextdns-blocker watchdog install")

    # Run initial sync
    click.echo()
    click.echo("  Running initial sync... ", nl=False)
    if run_initial_sync():
        click.echo(click.style("OK", fg="green"))
    else:
        click.echo(click.style("FAILED", fg="yellow"))
        click.echo("  You can run manually: nextdns-blocker sync")

    # Install shell completion
    shell = detect_shell()
    if shell and not is_windows():
        click.echo()
        click.echo("  Installing shell completion... ", nl=False)
        success, msg = install_completion(shell)
        if success:
            if "Already" in msg:
                click.echo(click.style("OK", fg="green") + " (already installed)")
            else:
                click.echo(click.style("OK", fg="green"))
                click.echo(f"    {msg}")
                click.echo(
                    f"    Restart your shell or run: source ~/{'.zshrc' if shell == 'zsh' else '.bashrc'}"
                )
        else:
            click.echo(click.style("SKIPPED", fg="yellow"))
            click.echo(f"    {msg}")
            click.echo("    You can install manually: nextdns-blocker completion --help")

    # Success message
    click.echo()
    click.echo(click.style("  Setup complete!", fg="green", bold=True))
    click.echo()
    click.echo("  Next steps:")
    click.echo("    nextdns-blocker config edit  - Add domains to block")
    click.echo()
    click.echo("  Commands:")
    click.echo("    nextdns-blocker status    - Show blocking status")
    click.echo("    nextdns-blocker sync      - Manual sync")
    click.echo("    nextdns-blocker pause 30  - Pause for 30 min")
    click.echo("    nextdns-blocker health    - Health check")
    click.echo()
    click.echo("  Logs:")
    click.echo(f"    {get_log_dir()}")
    click.echo()
    if is_macos():
        click.echo("  launchd:")
        click.echo("    launchctl list | grep nextdns")
        click.echo()
    elif is_windows():
        click.echo("  Task Scheduler:")
        click.echo("    schtasks /query /tn NextDNS-Blocker-Sync")
        click.echo("    schtasks /query /tn NextDNS-Blocker-Watchdog")
        click.echo()
    else:
        click.echo("  cron:")
        click.echo("    crontab -l | grep nextdns")
        click.echo()

    return True


def run_non_interactive(config_dir_override: Optional[Path] = None) -> bool:
    """
    Run non-interactive setup using environment variables.

    Expects:
        NEXTDNS_API_KEY: API key
        NEXTDNS_PROFILE_ID: Profile ID

    Args:
        config_dir_override: Optional config directory override

    Returns:
        True if setup completed successfully
    """
    api_key = os.environ.get("NEXTDNS_API_KEY")
    profile_id = os.environ.get("NEXTDNS_PROFILE_ID")

    if not api_key:
        click.echo("Error: NEXTDNS_API_KEY environment variable not set", err=True)
        return False

    if not profile_id:
        click.echo("Error: NEXTDNS_PROFILE_ID environment variable not set", err=True)
        return False

    # Validate credentials
    valid, msg = validate_api_credentials(api_key, profile_id)
    if not valid:
        click.echo(f"Error: {msg}", err=True)
        return False

    # Determine config directory
    config_dir = get_config_dir(config_dir_override)

    # Auto-detect timezone
    timezone = detect_system_timezone()

    # Create .env file (credentials only)
    env_file = create_env_file(config_dir, api_key, profile_id)
    click.echo(f"Configuration saved to: {env_file}")

    # Create config.json if it doesn't exist
    config_file = config_dir / "config.json"
    if not config_file.exists():
        create_config_file(config_dir, timezone)
        click.echo(f"Created: {config_file}")

    # Install scheduling
    sched_success, sched_type = install_scheduling()
    if sched_success:
        click.echo(f"Scheduling installed ({sched_type})")
    else:
        click.echo(f"Warning: {sched_type}", err=True)

    # Run initial sync
    if run_initial_sync():
        click.echo("Initial sync completed")
    else:
        click.echo("Warning: Initial sync failed", err=True)

    return True
