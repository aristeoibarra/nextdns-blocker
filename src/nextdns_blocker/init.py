"""Interactive initialization wizard for NextDNS Blocker."""

import os
import subprocess
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import click
import requests

from .common import SECURE_FILE_MODE, get_log_dir, validate_url
from .config import get_config_dir
from .platform_utils import (
    get_executable_args,
    get_executable_path,
    is_macos,
    is_windows,
)

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
            timeout=10,
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
            pass

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
                        ZoneInfo(tz_name)
                        return tz_name
        except (OSError, KeyError):
            pass

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
        except (subprocess.SubprocessError, OSError):
            pass

    return "UTC"


def create_env_file(
    config_dir: Path,
    api_key: str,
    profile_id: str,
    timezone: str,
    domains_url: Optional[str] = None,
) -> Path:
    """
    Create .env file with configuration.

    Args:
        config_dir: Directory to create .env in
        api_key: NextDNS API key
        profile_id: NextDNS profile ID
        timezone: Timezone string
        domains_url: Optional URL for remote domains.json

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

# Timezone for schedule evaluation
TIMEZONE={timezone}
"""

    if domains_url:
        content += f"""
# Remote domains.json URL (optional)
DOMAINS_URL={domains_url}
"""

    # Write with secure permissions
    fd = os.open(env_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, SECURE_FILE_MODE)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(content)
    except OSError:
        os.close(fd)
        raise

    return env_file


def create_sample_domains(config_dir: Path) -> Path:
    """
    Create a sample domains.json file.

    Args:
        config_dir: Directory to create domains.json in

    Returns:
        Path to created domains.json file
    """
    config_dir.mkdir(parents=True, exist_ok=True)

    domains_file = config_dir / "domains.json"

    content = """{
  "domains": [
    {
      "domain": "example.com",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "18:00", "end": "21:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "22:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": []
}
"""

    domains_file.write_text(content)
    return domains_file


# =============================================================================
# EXISTING CONFIGURATION DETECTION
# =============================================================================


def detect_existing_config(config_dir: Path) -> dict[str, Any]:
    """
    Detect existing domains configuration.

    Returns:
        Dict with keys:
            - has_local: bool - True if domains.json exists locally
            - has_url: bool - True if DOMAINS_URL is set in .env
            - url: str|None - The DOMAINS_URL value if set
            - local_path: Path - Path to local domains.json
    """
    env_file = config_dir / ".env"
    domains_file = config_dir / "domains.json"

    result: dict[str, Any] = {
        "has_local": domains_file.exists(),
        "has_url": False,
        "url": None,
        "local_path": domains_file,
    }

    # Check .env for DOMAINS_URL
    if env_file.exists():
        try:
            content = env_file.read_text()
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("DOMAINS_URL=") and not line.startswith("#"):
                    url_value = line.split("=", 1)[1].strip()
                    # Remove quotes if present
                    if (url_value.startswith('"') and url_value.endswith('"')) or (
                        url_value.startswith("'") and url_value.endswith("'")
                    ):
                        url_value = url_value[1:-1]
                    if url_value:
                        result["has_url"] = True
                        result["url"] = url_value
                    break
        except OSError:
            pass

    return result


def prompt_domains_migration(existing: dict[str, Any]) -> tuple[str, Optional[str]]:
    """
    Prompt user for domains configuration when existing config is detected.

    Args:
        existing: Dict from detect_existing_config()

    Returns:
        Tuple of (choice, url):
            - choice: "local", "url", or "keep"
            - url: The URL if choice is "url", None otherwise
    """
    click.echo()
    click.echo(click.style("  Existing domains configuration detected:", fg="yellow"))

    if existing["has_local"] and existing["has_url"]:
        click.echo(f"    - Local file: {existing['local_path']}")
        click.echo(f"    - Remote URL: {existing['url']}")
        click.echo()
        click.echo("  Options:")
        click.echo("    [1] Keep remote URL (recommended)")
        click.echo("    [2] Switch to local file (will remove URL from config)")
        click.echo("    [3] Change to different URL")
        click.echo("    [4] Keep both (URL takes priority)")

        choice = click.prompt("  Choice", type=click.Choice(["1", "2", "3", "4"]), default="1")

        if choice == "1":
            return "keep_url", existing["url"]
        elif choice == "2":
            return "local", None
        elif choice == "3":
            new_url = click.prompt("  New URL")
            if validate_url(new_url):
                return "url", new_url
            else:
                click.echo(click.style("  Invalid URL, keeping current", fg="red"))
                return "keep_url", existing["url"]
        else:
            return "both", existing["url"]

    elif existing["has_local"]:
        click.echo(f"    - Local file: {existing['local_path']}")
        click.echo()
        click.echo("  Options:")
        click.echo("    [1] Keep local file")
        click.echo("    [2] Switch to remote URL (will delete local file)")

        choice = click.prompt("  Choice", type=click.Choice(["1", "2"]), default="1")

        if choice == "1":
            return "local", None
        else:
            new_url = click.prompt("  Enter URL")
            if validate_url(new_url):
                return "url", new_url
            else:
                click.echo(click.style("  Invalid URL, keeping local file", fg="red"))
                return "local", None

    elif existing["has_url"]:
        click.echo(f"    - Remote URL: {existing['url']}")
        click.echo()
        click.echo("  Options:")
        click.echo("    [1] Keep remote URL")
        click.echo("    [2] Switch to local file (will remove URL from config)")
        click.echo("    [3] Change to different URL")

        choice = click.prompt("  Choice", type=click.Choice(["1", "2", "3"]), default="1")

        if choice == "1":
            return "keep_url", existing["url"]
        elif choice == "2":
            return "local", None
        else:
            new_url = click.prompt("  New URL")
            if validate_url(new_url):
                return "url", new_url
            else:
                click.echo(click.style("  Invalid URL, keeping current", fg="red"))
                return "keep_url", existing["url"]

    # No existing config
    return "none", None


def handle_domains_migration(
    config_dir: Path, choice: str, url: Optional[str]
) -> tuple[Optional[str], bool]:
    """
    Handle the domains migration based on user choice.

    Args:
        config_dir: Configuration directory
        choice: User's choice ("local", "url", "keep_url", "both", "none")
        url: URL if applicable

    Returns:
        Tuple of (domains_url, should_create_local):
            - domains_url: URL to save in .env, or None
            - should_create_local: True if should create/keep local domains.json
    """
    domains_file = config_dir / "domains.json"

    if choice == "url":
        # Switch to URL, delete local file if exists
        if domains_file.exists():
            try:
                domains_file.unlink()
                click.echo(f"  Deleted local file: {domains_file}")
            except OSError as e:
                click.echo(
                    click.style(f"  Warning: Could not delete {domains_file}: {e}", fg="yellow")
                )
        return url, False

    elif choice == "local":
        # Switch to local, URL will not be saved
        return None, not domains_file.exists()

    elif choice == "keep_url":
        # Keep existing URL
        return url, False

    elif choice == "both":
        # Keep both (URL takes priority in sync)
        return url, False

    else:  # "none" - no existing config
        return None, False


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
            timeout=30,
        )
        subprocess.run(
            ["launchctl", "unload", str(watchdog_plist_path)],
            capture_output=True,
            timeout=30,
        )

        # Load jobs
        result_sync = subprocess.run(
            ["launchctl", "load", str(sync_plist_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result_wd = subprocess.run(
            ["launchctl", "load", str(watchdog_plist_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result_sync.returncode == 0 and result_wd.returncode == 0:
            return True, "launchd"
        else:
            return False, "Failed to load launchd jobs"

    except Exception as e:
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
            timeout=30,
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
            timeout=30,
        )

        if result.returncode == 0:
            return True, "cron"
        else:
            return False, "Failed to set crontab"

    except Exception as e:
        return False, f"cron error: {e}"


def _escape_windows_path(path: str) -> str:
    """
    Escape a path for use in Windows Task Scheduler commands.

    Within double quotes in cmd.exe:
    - Percent signs must be doubled (%% instead of %)
    - Double quotes must be escaped as ""
    """
    safe_path = path.replace("%", "%%")
    safe_path = safe_path.replace('"', '""')
    return safe_path


def _build_task_command(exe: str, args: str, log_file: str) -> str:
    """
    Build a properly escaped command string for Windows Task Scheduler.

    Handles paths with spaces, special characters, and ensures proper
    quoting for cmd.exe execution context.
    """
    safe_exe = _escape_windows_path(exe)
    safe_log = _escape_windows_path(log_file)
    # Use nested quotes: outer for schtasks, inner for cmd /c
    return f'cmd /c ""{safe_exe}" {args} >> "{safe_log}" 2>&1"'


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
            timeout=30,
        )
        subprocess.run(
            ["schtasks", "/delete", "/tn", watchdog_task_name, "/f"],
            capture_output=True,
            timeout=30,
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
            timeout=30,
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
            timeout=30,
        )

        if result_sync.returncode == 0 and result_wd.returncode == 0:
            return True, "Task Scheduler"
        else:
            error_msg = result_sync.stderr or result_wd.stderr or "Unknown error"
            return False, f"Failed to create scheduled tasks: {error_msg}"

    except Exception as e:
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
    except Exception:
        return False


def run_interactive_wizard(
    config_dir_override: Optional[Path] = None, domains_url: Optional[str] = None
) -> bool:
    """
    Run the interactive setup wizard.

    Args:
        config_dir_override: Optional config directory override
        domains_url: Optional URL for remote domains.json

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

    # Prompt for timezone (auto-detect from system)
    default_tz = detect_system_timezone()
    timezone = click.prompt("  Timezone", default=default_tz)
    timezone = timezone.strip()

    # Validate timezone
    tz_valid, tz_msg = validate_timezone(timezone)
    if not tz_valid:
        click.echo(click.style(f"\n  Error: {tz_msg}", fg="red"))
        click.echo("  See: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones\n")
        return False

    # Validate credentials first
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

    # Check for existing domains configuration
    existing = detect_existing_config(config_dir)
    should_create_local = False

    if domains_url:
        # URL provided via --url flag, use it directly
        # If local file exists, ask if they want to delete it
        if existing["has_local"]:
            click.echo()
            delete_local = click.confirm("  Local domains.json exists. Delete it?", default=True)
            if delete_local:
                try:
                    existing["local_path"].unlink()
                    click.echo(f"  Deleted: {existing['local_path']}")
                except OSError as e:
                    click.echo(click.style(f"  Warning: Could not delete: {e}", fg="yellow"))
    elif existing["has_local"] or existing["has_url"]:
        # Existing configuration detected, show migration options
        choice, url = prompt_domains_migration(existing)
        domains_url, should_create_local = handle_domains_migration(config_dir, choice, url)
    else:
        # No existing config, prompt for new configuration
        click.echo()
        click.echo("  Domains URL (optional, press Enter to skip)")
        url_input = click.prompt("  URL", default="", show_default=False)
        url_input = url_input.strip()

        if url_input:
            if validate_url(url_input):
                domains_url = url_input
            else:
                click.echo(
                    click.style("\n  Error: Invalid URL format (must be http/https)", fg="red")
                )
                return False
        else:
            # No URL, will offer to create sample domains.json
            should_create_local = True

    # Create .env file
    click.echo()
    env_file = create_env_file(config_dir, api_key, profile_id, timezone, domains_url)
    click.echo(f"  Configuration saved to: {env_file}")

    # Create sample domains.json if needed
    if should_create_local and not (config_dir / "domains.json").exists():
        click.echo()
        create_sample = click.confirm("  Create sample domains.json?", default=True)

        if create_sample:
            domains_file = create_sample_domains(config_dir)
            click.echo(f"  Created: {domains_file}")

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

    # Success message
    click.echo()
    click.echo(click.style("  Setup complete!", fg="green", bold=True))
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


def run_non_interactive(
    config_dir_override: Optional[Path] = None, domains_url: Optional[str] = None
) -> bool:
    """
    Run non-interactive setup using environment variables.

    Expects:
        NEXTDNS_API_KEY: API key
        NEXTDNS_PROFILE_ID: Profile ID
        TIMEZONE: Timezone (optional, defaults to UTC)

    Args:
        config_dir_override: Optional config directory override
        domains_url: Optional URL for remote domains.json

    Returns:
        True if setup completed successfully
    """
    api_key = os.environ.get("NEXTDNS_API_KEY")
    profile_id = os.environ.get("NEXTDNS_PROFILE_ID")
    timezone = os.environ.get("TIMEZONE", "UTC")

    if not api_key:
        click.echo("Error: NEXTDNS_API_KEY environment variable not set", err=True)
        return False

    if not profile_id:
        click.echo("Error: NEXTDNS_PROFILE_ID environment variable not set", err=True)
        return False

    # Validate timezone
    tz_valid, tz_msg = validate_timezone(timezone)
    if not tz_valid:
        click.echo(f"Error: {tz_msg}", err=True)
        return False

    # Validate credentials
    valid, msg = validate_api_credentials(api_key, profile_id)
    if not valid:
        click.echo(f"Error: {msg}", err=True)
        return False

    # Determine config directory
    config_dir = get_config_dir(config_dir_override)

    # Create .env file
    env_file = create_env_file(config_dir, api_key, profile_id, timezone, domains_url)
    click.echo(f"Configuration saved to: {env_file}")

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
