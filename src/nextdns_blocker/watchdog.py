"""Watchdog - Monitors and restores scheduled jobs (cron/launchd/Task Scheduler) if deleted."""

import contextlib
import logging
import os
import plistlib
import shlex
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import click

from .common import audit_log as _base_audit_log
from .common import (
    ensure_naive_datetime,
    get_log_dir,
    read_secure_file,
    safe_int,
    write_secure_file,
)
from .exceptions import APIError, ConfigurationError, DomainValidationError
from .platform_utils import (
    get_executable_args,
    get_executable_path,
    is_macos,
    is_windows,
)

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

# Subprocess timeout in seconds (configurable via environment variable)
# Enforce minimum of 10 seconds and maximum of 300 seconds to prevent misconfiguration
_raw_subprocess_timeout = safe_int(
    os.environ.get("NEXTDNS_SUBPROCESS_TIMEOUT"), 60, "NEXTDNS_SUBPROCESS_TIMEOUT"
)
SUBPROCESS_TIMEOUT = min(300, max(10, _raw_subprocess_timeout))

# Cleanup interval in hours (run cleanup once per day)
CLEANUP_INTERVAL_HOURS = 24

# launchd constants for macOS
LAUNCHD_SYNC_LABEL = "com.nextdns-blocker.sync"
LAUNCHD_WATCHDOG_LABEL = "com.nextdns-blocker.watchdog"

# Windows Task Scheduler constants
WINDOWS_TASK_SYNC_NAME = "NextDNS-Blocker-Sync"
WINDOWS_TASK_WATCHDOG_NAME = "NextDNS-Blocker-Watchdog"


def get_launch_agents_dir() -> Path:
    """Get the LaunchAgents directory for the current user."""
    return Path.home() / "Library" / "LaunchAgents"


def get_sync_plist_path() -> Path:
    """Get the path to the sync plist file."""
    return get_launch_agents_dir() / f"{LAUNCHD_SYNC_LABEL}.plist"


def get_watchdog_plist_path() -> Path:
    """Get the path to the watchdog plist file."""
    return get_launch_agents_dir() / f"{LAUNCHD_WATCHDOG_LABEL}.plist"


def get_disabled_file() -> Path:
    """Get the watchdog disabled state file path."""
    return get_log_dir() / ".watchdog_disabled"


def _escape_shell_path(path: str) -> str:
    """
    Escape a path for safe use in shell commands.

    Args:
        path: File system path to escape

    Returns:
        Shell-escaped path safe for use in cron/shell commands
    """
    return shlex.quote(path)


def get_cron_sync() -> str:
    """Get the sync cron job definition."""
    log_dir = get_log_dir()
    exe = get_executable_path()
    log_file = str(log_dir / "cron.log")
    safe_exe = _escape_shell_path(exe)
    safe_log = _escape_shell_path(log_file)
    return f"*/2 * * * * {safe_exe} sync >> {safe_log} 2>&1"


def get_cron_watchdog() -> str:
    """Get the watchdog cron job definition."""
    log_dir = get_log_dir()
    exe = get_executable_path()
    log_file = str(log_dir / "wd.log")
    safe_exe = _escape_shell_path(exe)
    safe_log = _escape_shell_path(log_file)
    return f"* * * * * {safe_exe} watchdog check >> {safe_log} 2>&1"


def audit_log(action: str, detail: str = "") -> None:
    """Wrapper for audit_log with WD prefix."""
    _base_audit_log(action, detail, prefix="WD")


def _get_last_cleanup_file() -> Path:
    """Get the path to the last cleanup timestamp file."""
    return get_log_dir() / ".last_cleanup"


def _should_run_cleanup() -> bool:
    """
    Check if cleanup should run based on time since last cleanup.

    Uses a deterministic time-based approach instead of random chance.
    Cleanup runs once per CLEANUP_INTERVAL_HOURS.

    Returns:
        True if cleanup should run, False otherwise.
    """
    cleanup_file = _get_last_cleanup_file()

    try:
        if cleanup_file.exists():
            content = read_secure_file(cleanup_file)
            if content:
                last_cleanup = ensure_naive_datetime(datetime.fromisoformat(content))
                hours_since = (datetime.now() - last_cleanup).total_seconds() / 3600
                if hours_since < CLEANUP_INTERVAL_HOURS:
                    return False
    except ValueError as e:
        # Invalid date format in cleanup file - will run cleanup to reset
        logger.debug(f"Invalid cleanup timestamp format, will run cleanup: {e}")
    except OSError as e:
        # File access error - will run cleanup
        logger.debug(f"Cannot read cleanup file, will run cleanup: {e}")

    return True


def _mark_cleanup_done() -> None:
    """Record that cleanup was just performed."""
    cleanup_file = _get_last_cleanup_file()
    with contextlib.suppress(OSError):
        write_secure_file(cleanup_file, datetime.now().isoformat())


# =============================================================================
# DISABLED STATE MANAGEMENT
# =============================================================================


def is_disabled() -> bool:
    """
    Check if watchdog is temporarily or permanently disabled.

    Note:
        Cleanup of expired files is handled safely to avoid race conditions.
    """
    disabled_file = get_disabled_file()
    content = read_secure_file(disabled_file)
    if not content:
        return False

    try:
        if content == "permanent":
            return True

        disabled_until = ensure_naive_datetime(datetime.fromisoformat(content))
        if datetime.now() < disabled_until:
            return True

        # Expired, clean up (safe cleanup handles race conditions)
        _remove_disabled_file()
        return False
    except ValueError:
        # Invalid content, attempt cleanup
        _remove_disabled_file()
        return False


def get_disabled_remaining() -> str:
    """Get remaining disabled time as human-readable string."""
    disabled_file = get_disabled_file()
    content = read_secure_file(disabled_file)
    if not content:
        return ""

    try:
        if content == "permanent":
            return "permanently"

        disabled_until = ensure_naive_datetime(datetime.fromisoformat(content))
        remaining = disabled_until - datetime.now()

        if remaining.total_seconds() <= 0:
            _remove_disabled_file()
            return ""

        mins = int(remaining.total_seconds() // 60)
        return f"{mins} min" if mins > 0 else "< 1 min"
    except ValueError:
        return ""


def _remove_disabled_file() -> None:
    """Remove the disabled file safely."""
    try:
        get_disabled_file().unlink(missing_ok=True)
    except OSError as e:
        logger.debug(f"Failed to remove disabled file: {e}")


def set_disabled(minutes: Optional[int] = None) -> None:
    """Disable watchdog temporarily or permanently."""
    disabled_file = get_disabled_file()
    if minutes:
        disabled_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
        write_secure_file(disabled_file, disabled_until.isoformat())
        audit_log("WD_DISABLED", f"{minutes} minutes until {disabled_until.isoformat()}")
    else:
        write_secure_file(disabled_file, "permanent")
        audit_log("WD_DISABLED", "permanent")


def clear_disabled() -> bool:
    """Re-enable watchdog. Returns True if was disabled."""
    disabled_file = get_disabled_file()
    if disabled_file.exists():
        _remove_disabled_file()
        audit_log("WD_ENABLED", "Manual enable")
        return True
    return False


# =============================================================================
# CRON MANAGEMENT
# =============================================================================


def get_crontab() -> str:
    """
    Get the current user's crontab contents.

    Returns:
        Crontab contents as string.
        Empty string if no crontab exists or on error.

    Note:
        This function logs errors to distinguish between "no crontab" (normal)
        and actual failures (permission denied, timeout, etc.).
    """
    try:
        result = subprocess.run(
            ["crontab", "-l"], capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT
        )
        if result.returncode == 0:
            return result.stdout
        # crontab -l returns non-zero when no crontab exists (common case)
        # stderr typically contains "no crontab for <user>"
        if "no crontab" in result.stderr.lower():
            logger.debug("No crontab exists for current user")
        else:
            # Unexpected error - log it
            logger.warning(f"crontab -l failed: {result.stderr.strip()}")
        return ""
    except subprocess.TimeoutExpired:
        logger.error(f"crontab -l timed out after {SUBPROCESS_TIMEOUT}s")
        return ""
    except OSError as e:
        logger.error(f"Failed to run crontab command: {e}")
        return ""
    except subprocess.SubprocessError as e:
        logger.error(f"Subprocess error running crontab: {e}")
        return ""


def set_crontab(content: str) -> bool:
    """Set the user's crontab contents."""
    try:
        result = subprocess.run(
            ["crontab", "-"],
            input=content,
            text=True,
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Failed to set crontab: {e}")
        return False


def has_sync_cron(crontab: str) -> bool:
    """Check if sync cron job is present."""
    return "nextdns-blocker sync" in crontab


def has_watchdog_cron(crontab: str) -> bool:
    """Check if watchdog cron job is present."""
    return "nextdns-blocker watchdog" in crontab


def filter_our_cron_jobs(crontab: str) -> list[str]:
    """Remove our cron jobs from crontab, keeping other entries."""
    return [line for line in crontab.split("\n") if "nextdns-blocker" not in line and line.strip()]


# =============================================================================
# LAUNCHD MANAGEMENT (macOS)
# =============================================================================


def generate_plist(
    label: str,
    program_args: list[str],
    start_interval: int,
    log_file: Path,
) -> bytes:
    """Generate plist content for a launchd job."""
    plist_dict: dict[str, Any] = {
        "Label": label,
        "ProgramArguments": program_args,
        "StartInterval": start_interval,
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},  # Restart if process crashes
        "StandardOutPath": str(log_file),
        "StandardErrorPath": str(log_file),
        "EnvironmentVariables": {
            "PATH": f"{Path.home()}/.local/bin:/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
        },
    }
    return plistlib.dumps(plist_dict)


def load_launchd_job(plist_path: Path) -> bool:
    """Load a launchd job from a plist file."""
    try:
        # First unload if exists (ignore errors)
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        # Then load
        result = subprocess.run(
            ["launchctl", "load", str(plist_path)],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Failed to load launchd job: {e}")
        return False


def unload_launchd_job(plist_path: Path, label: str) -> bool:
    """Unload a launchd job and remove the plist file."""
    try:
        # Unload the job
        subprocess.run(
            ["launchctl", "unload", str(plist_path)],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        # Remove plist file
        if plist_path.exists():
            plist_path.unlink()
        return True
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        logger.warning(f"Failed to unload launchd job {label}: {e}")
        return False


def is_launchd_job_loaded(label: str) -> bool:
    """Check if a launchd job is currently loaded."""
    try:
        result = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False


# =============================================================================
# PLATFORM-SPECIFIC HELPERS
# =============================================================================


def _install_cron_jobs() -> None:
    """Install cron jobs (Linux)."""
    crontab = get_crontab()
    lines = filter_our_cron_jobs(crontab)
    lines.extend([get_cron_sync(), get_cron_watchdog()])

    if set_crontab("\n".join(lines) + "\n"):
        audit_log("CRON_INSTALLED", "Manual install")
        click.echo("\n  cron installed")
        click.echo("    sync       every 2 min")
        click.echo("    watchdog   every 1 min\n")
    else:
        click.echo("  error: cron install failed", err=True)
        sys.exit(1)


def _uninstall_cron_jobs() -> None:
    """Uninstall cron jobs (Linux)."""
    crontab = get_crontab()
    lines = filter_our_cron_jobs(crontab)
    new_content = "\n".join(lines) + "\n" if lines else ""

    if set_crontab(new_content):
        audit_log("CRON_UNINSTALLED", "Manual uninstall")
        click.echo("\n  Cron jobs removed\n")
    else:
        click.echo("  error: failed to remove cron jobs", err=True)
        sys.exit(1)


def _status_cron_jobs() -> None:
    """Display cron job status (Linux)."""
    crontab = get_crontab()
    has_sync = has_sync_cron(crontab)
    has_wd = has_watchdog_cron(crontab)
    disabled_remaining = get_disabled_remaining()

    click.echo("\n  cron")
    click.echo("  ----")
    click.echo(f"    sync       {'ok' if has_sync else 'missing'}")
    click.echo(f"    watchdog   {'ok' if has_wd else 'missing'}")

    if disabled_remaining:
        click.echo(f"\n  watchdog: DISABLED ({disabled_remaining})")
    else:
        status = "active" if (has_sync and has_wd) else "compromised"
        click.echo(f"\n  status: {status}")
    click.echo()


def _check_cron_jobs() -> None:
    """Check and restore cron jobs if missing (Linux)."""
    crontab = get_crontab()
    restored = False

    # Check and restore sync cron
    if not has_sync_cron(crontab):
        audit_log("CRON_DELETED", "Sync cron missing")
        new_crontab = crontab.strip()
        new_crontab = (new_crontab + "\n" if new_crontab else "") + get_cron_sync() + "\n"
        if set_crontab(new_crontab):
            click.echo("  sync cron restored")
            restored = True
        else:
            click.echo("  warning: failed to restore sync cron", err=True)

    # Check and restore watchdog cron
    if not has_watchdog_cron(crontab):
        audit_log("WD_CRON_DELETED", "Watchdog cron missing")
        crontab = get_crontab()
        new_crontab = crontab.strip()
        new_crontab = (new_crontab + "\n" if new_crontab else "") + get_cron_watchdog() + "\n"
        if set_crontab(new_crontab):
            click.echo("  watchdog cron restored")
            restored = True
        else:
            click.echo("  warning: failed to restore watchdog cron", err=True)

    # Run sync if cron was restored
    if restored:
        _run_sync_after_restore()


def _write_plist_file(plist_path: Path, content: bytes) -> bool:
    """Write plist file with correct permissions (0o644)."""
    try:
        plist_path.write_bytes(content)
        plist_path.chmod(0o644)
        return True
    except OSError as e:
        logger.warning(f"Failed to write plist file {plist_path}: {e}")
        return False


def _safe_unlink(path: Path) -> None:
    """Safely remove a file, ignoring errors."""
    try:
        if path.exists():
            path.unlink()
    except OSError as e:
        logger.debug(f"Failed to remove file {path}: {e}")


def _install_launchd_jobs() -> None:
    """Install launchd jobs (macOS)."""
    launch_agents_dir = get_launch_agents_dir()
    launch_agents_dir.mkdir(parents=True, exist_ok=True)

    exe_args = get_executable_args()
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    # Generate and write sync plist
    sync_plist = get_sync_plist_path()
    sync_content = generate_plist(
        label=LAUNCHD_SYNC_LABEL,
        program_args=exe_args + ["sync"],
        start_interval=120,  # 2 minutes
        log_file=log_dir / "launchd_sync.log",
    )
    if not _write_plist_file(sync_plist, sync_content):
        click.echo("  error: failed to write sync plist", err=True)
        sys.exit(1)

    # Generate and write watchdog plist
    watchdog_plist = get_watchdog_plist_path()
    watchdog_content = generate_plist(
        label=LAUNCHD_WATCHDOG_LABEL,
        program_args=exe_args + ["watchdog", "check"],
        start_interval=60,  # 1 minute
        log_file=log_dir / "launchd_wd.log",
    )
    if not _write_plist_file(watchdog_plist, watchdog_content):
        # Clean up sync plist that was already written
        _safe_unlink(sync_plist)
        click.echo("  error: failed to write watchdog plist", err=True)
        sys.exit(1)

    # Load the jobs
    success_sync = load_launchd_job(sync_plist)
    if not success_sync:
        # Sync failed, clean up and exit early
        _safe_unlink(sync_plist)
        _safe_unlink(watchdog_plist)
        click.echo("  error: failed to load sync launchd job", err=True)
        sys.exit(1)

    success_wd = load_launchd_job(watchdog_plist)
    if not success_wd:
        # Watchdog failed, unload sync and clean up
        with contextlib.suppress(OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            subprocess.run(
                ["launchctl", "unload", str(sync_plist)],
                capture_output=True,
                timeout=SUBPROCESS_TIMEOUT,
            )
        _safe_unlink(sync_plist)
        _safe_unlink(watchdog_plist)
        click.echo("  error: failed to load watchdog launchd job", err=True)
        sys.exit(1)

    audit_log("LAUNCHD_INSTALLED", "Manual install")
    click.echo("\n  launchd jobs installed")
    click.echo("    sync       every 2 min")
    click.echo("    watchdog   every 1 min\n")


def _uninstall_launchd_jobs() -> None:
    """Uninstall launchd jobs (macOS)."""
    sync_plist = get_sync_plist_path()
    watchdog_plist = get_watchdog_plist_path()

    success_sync = unload_launchd_job(sync_plist, LAUNCHD_SYNC_LABEL)
    success_wd = unload_launchd_job(watchdog_plist, LAUNCHD_WATCHDOG_LABEL)

    audit_log("LAUNCHD_UNINSTALLED", "Manual uninstall")

    if success_sync and success_wd:
        click.echo("\n  launchd jobs removed\n")
    elif not success_sync and not success_wd:
        click.echo("\n  warning: failed to unload both launchd jobs\n", err=True)
    elif not success_sync:
        click.echo("\n  watchdog removed, warning: failed to unload sync job\n", err=True)
    else:
        click.echo("\n  sync removed, warning: failed to unload watchdog job\n", err=True)


def _status_launchd_jobs() -> None:
    """Display launchd job status (macOS)."""
    has_sync = is_launchd_job_loaded(LAUNCHD_SYNC_LABEL)
    has_wd = is_launchd_job_loaded(LAUNCHD_WATCHDOG_LABEL)
    disabled_remaining = get_disabled_remaining()

    click.echo("\n  launchd")
    click.echo("  -------")
    click.echo(f"    sync       {'ok' if has_sync else 'missing'}")
    click.echo(f"    watchdog   {'ok' if has_wd else 'missing'}")

    if disabled_remaining:
        click.echo(f"\n  watchdog: DISABLED ({disabled_remaining})")
    else:
        status = "active" if (has_sync and has_wd) else "compromised"
        click.echo(f"\n  status: {status}")
    click.echo()


def _check_launchd_jobs() -> None:
    """Check and restore launchd jobs if missing (macOS)."""
    restored = False

    # Check sync job
    if not is_launchd_job_loaded(LAUNCHD_SYNC_LABEL):
        audit_log("LAUNCHD_DELETED", "Sync job missing")
        sync_plist = get_sync_plist_path()
        if sync_plist.exists():
            if load_launchd_job(sync_plist):
                click.echo("  sync launchd job restored")
                restored = True
            else:
                click.echo("  warning: failed to restore sync launchd job", err=True)
        else:
            # Recreate plist
            if _create_sync_plist():
                if load_launchd_job(sync_plist):
                    click.echo("  sync launchd job recreated")
                    restored = True
                else:
                    # Clean up orphaned plist
                    _safe_unlink(sync_plist)
                    click.echo("  warning: failed to load sync launchd job", err=True)
            else:
                click.echo("  warning: failed to create sync plist", err=True)

    # Check watchdog job
    if not is_launchd_job_loaded(LAUNCHD_WATCHDOG_LABEL):
        audit_log("LAUNCHD_WD_DELETED", "Watchdog job missing")
        watchdog_plist = get_watchdog_plist_path()
        if watchdog_plist.exists():
            if load_launchd_job(watchdog_plist):
                click.echo("  watchdog launchd job restored")
                restored = True
            else:
                click.echo("  warning: failed to restore watchdog launchd job", err=True)
        else:
            # Recreate plist
            if _create_watchdog_plist():
                if load_launchd_job(watchdog_plist):
                    click.echo("  watchdog launchd job recreated")
                    restored = True
                else:
                    # Clean up orphaned plist
                    _safe_unlink(watchdog_plist)
                    click.echo("  warning: failed to load watchdog launchd job", err=True)
            else:
                click.echo("  warning: failed to create watchdog plist", err=True)

    # Run sync if jobs were restored
    if restored:
        _run_sync_after_restore()


def _create_sync_plist() -> bool:
    """Create sync plist file. Returns True on success."""
    exe_args = get_executable_args()
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    sync_plist = get_sync_plist_path()
    sync_plist.parent.mkdir(parents=True, exist_ok=True)
    sync_content = generate_plist(
        label=LAUNCHD_SYNC_LABEL,
        program_args=exe_args + ["sync"],
        start_interval=120,
        log_file=log_dir / "launchd_sync.log",
    )
    return _write_plist_file(sync_plist, sync_content)


def _create_watchdog_plist() -> bool:
    """Create watchdog plist file. Returns True on success."""
    exe_args = get_executable_args()
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    watchdog_plist = get_watchdog_plist_path()
    watchdog_plist.parent.mkdir(parents=True, exist_ok=True)
    watchdog_content = generate_plist(
        label=LAUNCHD_WATCHDOG_LABEL,
        program_args=exe_args + ["watchdog", "check"],
        start_interval=60,
        log_file=log_dir / "launchd_wd.log",
    )
    return _write_plist_file(watchdog_plist, watchdog_content)


def _run_sync_after_restore() -> None:
    """Run sync command after restoring scheduled jobs."""
    try:
        exe_args = get_executable_args()
        result = subprocess.run(
            exe_args + ["sync"],
            timeout=SUBPROCESS_TIMEOUT,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            logger.info("Sync completed successfully after restore")
        else:
            logger.warning(
                f"Sync after restore exited with code {result.returncode}: "
                f"{result.stderr.strip() if result.stderr else 'no error output'}"
            )
    except subprocess.TimeoutExpired:
        logger.warning(f"Sync after restore timed out after {SUBPROCESS_TIMEOUT}s")
    except OSError as e:
        logger.warning(f"Failed to run sync after restore: {e}")
    except subprocess.SubprocessError as e:
        logger.warning(f"Subprocess error running sync after restore: {e}")


# =============================================================================
# WINDOWS TASK SCHEDULER MANAGEMENT
# =============================================================================


def _escape_windows_path(path: str) -> str:
    """
    Escape a path for use in Windows Task Scheduler commands.

    Handles paths with spaces, special characters, and non-ASCII characters
    by properly quoting them for cmd.exe execution context.

    Within double quotes in cmd.exe:
    - Double quotes must be escaped as ""
    - Percent signs must be doubled (%% instead of %)
    - Other special characters (&, |, <, >, ^) are treated literally

    Args:
        path: The path string to escape

    Returns:
        Properly escaped path string safe for schtasks /tr argument
    """
    # Escape percent signs first (must be doubled in cmd.exe)
    safe_path = path.replace("%", "%%")
    # Escape double quotes (standard Windows escaping within quotes)
    safe_path = safe_path.replace('"', '""')
    return safe_path


def _build_task_command(exe: str, args: str, log_file: str) -> str:
    """
    Build a properly escaped command string for Windows Task Scheduler.

    This handles paths with spaces, special characters, and ensures proper
    quoting for cmd.exe execution context.

    Args:
        exe: Path to the executable
        args: Command arguments (e.g., "sync" or "watchdog check")
        log_file: Path to the log file for output redirection

    Returns:
        Properly formatted command string for schtasks /tr argument
    """
    safe_exe = _escape_windows_path(exe)
    safe_log = _escape_windows_path(log_file)
    # Use nested quotes: outer for schtasks, inner for cmd /c
    # Format: cmd /c ""exe" args >> "logfile" 2>&1"
    return f'cmd /c ""{safe_exe}" {args} >> "{safe_log}" 2>&1"'


def _run_schtasks(
    args: list[str], timeout: int = SUBPROCESS_TIMEOUT
) -> subprocess.CompletedProcess[str]:
    """
    Run schtasks command with standard options.

    Args:
        args: List of arguments to pass to schtasks
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess with stdout/stderr captured
    """
    return subprocess.run(
        ["schtasks"] + args,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def has_windows_task(task_name: str) -> bool:
    """Check if a Windows scheduled task exists."""
    try:
        result = _run_schtasks(["/query", "/tn", task_name])
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False


def _install_windows_tasks() -> None:
    """Install Windows Task Scheduler tasks."""
    log_dir = get_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    exe = get_executable_path()
    sync_log = str(log_dir / "sync.log")
    wd_log = str(log_dir / "wd.log")

    # Delete existing tasks (ignore errors)
    _run_schtasks(["/delete", "/tn", WINDOWS_TASK_SYNC_NAME, "/f"])
    _run_schtasks(["/delete", "/tn", WINDOWS_TASK_WATCHDOG_NAME, "/f"])

    # Create sync task (every 2 minutes)
    sync_cmd = _build_task_command(exe, "sync", sync_log)
    result_sync = _run_schtasks(
        [
            "/create",
            "/tn",
            WINDOWS_TASK_SYNC_NAME,
            "/tr",
            sync_cmd,
            "/sc",
            "minute",
            "/mo",
            "2",
            "/f",
        ]
    )

    if result_sync.returncode != 0:
        click.echo(f"  error: failed to create sync task: {result_sync.stderr}", err=True)
        sys.exit(1)

    # Create watchdog task (every 1 minute)
    wd_cmd = _build_task_command(exe, "watchdog check", wd_log)
    result_wd = _run_schtasks(
        [
            "/create",
            "/tn",
            WINDOWS_TASK_WATCHDOG_NAME,
            "/tr",
            wd_cmd,
            "/sc",
            "minute",
            "/mo",
            "1",
            "/f",
        ]
    )

    if result_wd.returncode != 0:
        # Rollback: delete sync task
        _run_schtasks(["/delete", "/tn", WINDOWS_TASK_SYNC_NAME, "/f"])
        click.echo(f"  error: failed to create watchdog task: {result_wd.stderr}", err=True)
        sys.exit(1)

    audit_log("SCHTASKS_INSTALLED", "Manual install")
    click.echo("\n  Task Scheduler jobs installed")
    click.echo("    sync       every 2 min")
    click.echo("    watchdog   every 1 min\n")


def _uninstall_windows_tasks() -> None:
    """Uninstall Windows Task Scheduler tasks."""
    result_sync = _run_schtasks(["/delete", "/tn", WINDOWS_TASK_SYNC_NAME, "/f"])
    result_wd = _run_schtasks(["/delete", "/tn", WINDOWS_TASK_WATCHDOG_NAME, "/f"])

    audit_log("SCHTASKS_UNINSTALLED", "Manual uninstall")

    if result_sync.returncode == 0 and result_wd.returncode == 0:
        click.echo("\n  Task Scheduler jobs removed\n")
    elif result_sync.returncode != 0 and result_wd.returncode != 0:
        click.echo("\n  warning: failed to remove both tasks\n", err=True)
    elif result_sync.returncode != 0:
        click.echo("\n  watchdog removed, warning: failed to remove sync task\n", err=True)
    else:
        click.echo("\n  sync removed, warning: failed to remove watchdog task\n", err=True)


def _status_windows_tasks() -> None:
    """Display Windows Task Scheduler status."""
    has_sync = has_windows_task(WINDOWS_TASK_SYNC_NAME)
    has_wd = has_windows_task(WINDOWS_TASK_WATCHDOG_NAME)
    disabled_remaining = get_disabled_remaining()

    click.echo("\n  Task Scheduler")
    click.echo("  --------------")
    click.echo(f"    sync       {'ok' if has_sync else 'missing'}")
    click.echo(f"    watchdog   {'ok' if has_wd else 'missing'}")

    if disabled_remaining:
        click.echo(f"\n  watchdog: DISABLED ({disabled_remaining})")
    else:
        status = "active" if (has_sync and has_wd) else "compromised"
        click.echo(f"\n  status: {status}")
    click.echo()


def _check_windows_tasks() -> None:
    """Check and restore Windows Task Scheduler tasks if missing."""
    restored = False

    # Check sync task
    if not has_windows_task(WINDOWS_TASK_SYNC_NAME):
        audit_log("SCHTASK_DELETED", "Sync task missing")
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        exe = get_executable_path()
        sync_log = str(log_dir / "sync.log")
        sync_cmd = _build_task_command(exe, "sync", sync_log)

        result = _run_schtasks(
            [
                "/create",
                "/tn",
                WINDOWS_TASK_SYNC_NAME,
                "/tr",
                sync_cmd,
                "/sc",
                "minute",
                "/mo",
                "2",
                "/f",
            ]
        )

        if result.returncode == 0:
            click.echo("  sync task restored")
            restored = True
        else:
            click.echo("  warning: failed to restore sync task", err=True)

    # Check watchdog task
    if not has_windows_task(WINDOWS_TASK_WATCHDOG_NAME):
        audit_log("SCHTASK_WD_DELETED", "Watchdog task missing")
        log_dir = get_log_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        exe = get_executable_path()
        wd_log = str(log_dir / "wd.log")
        wd_cmd = _build_task_command(exe, "watchdog check", wd_log)

        result = _run_schtasks(
            [
                "/create",
                "/tn",
                WINDOWS_TASK_WATCHDOG_NAME,
                "/tr",
                wd_cmd,
                "/sc",
                "minute",
                "/mo",
                "1",
                "/f",
            ]
        )

        if result.returncode == 0:
            click.echo("  watchdog task restored")
            restored = True
        else:
            click.echo("  warning: failed to restore watchdog task", err=True)

    # Run sync if tasks were restored
    if restored:
        _run_sync_after_restore()


# =============================================================================
# CLICK CLI
# =============================================================================


@click.group()
def watchdog_cli() -> None:
    """Watchdog commands for scheduled job management (cron/launchd/Task Scheduler)."""
    pass


def _process_pending_actions() -> None:
    """Execute pending actions that are ready."""
    from .panic import is_panic_mode

    # Skip pending actions during panic mode
    if is_panic_mode():
        logger.debug("Panic mode active, skipping pending actions")
        return

    from .client import NextDNSClient
    from .config import load_config
    from .notifications import send_discord_notification
    from .pending import cleanup_old_actions, get_ready_actions, mark_action_executed

    ready_actions = get_ready_actions()
    if not ready_actions:
        return

    try:
        config = load_config()
        client = NextDNSClient(
            config["api_key"],
            config["profile_id"],
            config["timeout"],
            config["retries"],
        )
    except ConfigurationError as e:
        logger.error(f"Configuration error for pending actions: {e}")
        return
    except KeyError as e:
        logger.error(f"Missing configuration key for pending actions: {e}")
        return
    except OSError as e:
        logger.error(f"I/O error loading config for pending actions: {e}")
        return

    for action in ready_actions:
        domain = action.get("domain")
        action_id = action.get("id")
        action_type = action.get("action")

        # Validate required fields with proper type checking
        if not isinstance(domain, str) or not domain:
            logger.warning(f"Skipping action with invalid domain: {action}")
            continue
        if not isinstance(action_id, str) or not action_id:
            logger.warning(f"Skipping action with invalid id: {action}")
            continue
        if action_type is None:
            logger.warning(f"Skipping action with missing type: {action}")
            continue

        if action_type == "unblock":
            try:
                if client.unblock(domain):
                    mark_action_executed(action_id)
                    audit_log("UNBLOCK", f"{domain} (pending: {action_id})")
                    send_discord_notification(
                        domain,
                        "unblock",
                        webhook_url=config.get("discord_webhook_url"),
                    )
                    click.echo(f"  Executed pending unblock: {domain}")
                else:
                    logger.error(f"Failed to unblock {domain} (pending: {action_id})")
            except DomainValidationError as e:
                # Domain validation failed - log and skip this action
                logger.error(f"Invalid domain in pending action {action_id}: {e}")
            except APIError as e:
                # API error - may be temporary, will retry on next check
                logger.error(f"API error processing pending action {action_id}: {e}")
            except OSError as e:
                # File system or network error
                logger.error(f"I/O error processing pending action {action_id}: {e}")

    # Periodic cleanup of old actions (time-based, once per day)
    if _should_run_cleanup():
        cleanup_old_actions(max_age_days=7)
        _mark_cleanup_done()


@watchdog_cli.command("check")
def cmd_check() -> None:
    """Check and restore scheduled jobs if missing."""
    if is_disabled():
        remaining = get_disabled_remaining()
        click.echo(f"  watchdog disabled ({remaining})")
        return

    # Process pending actions first
    _process_pending_actions()

    if is_macos():
        _check_launchd_jobs()
    elif is_windows():
        _check_windows_tasks()
    else:
        _check_cron_jobs()


@watchdog_cli.command("install")
def cmd_install() -> None:
    """Install sync and watchdog scheduled jobs."""
    if is_macos():
        _install_launchd_jobs()
    elif is_windows():
        _install_windows_tasks()
    else:
        _install_cron_jobs()


@watchdog_cli.command("uninstall")
def cmd_uninstall() -> None:
    """Remove scheduled jobs."""
    if is_macos():
        _uninstall_launchd_jobs()
    elif is_windows():
        _uninstall_windows_tasks()
    else:
        _uninstall_cron_jobs()


@watchdog_cli.command("status")
def cmd_status() -> None:
    """Display current scheduled job status."""
    if is_macos():
        _status_launchd_jobs()
    elif is_windows():
        _status_windows_tasks()
    else:
        _status_cron_jobs()


@watchdog_cli.command("disable")
@click.argument("minutes", required=False, type=click.IntRange(min=1))
def cmd_disable(minutes: Optional[int]) -> None:
    """Disable watchdog temporarily or permanently."""
    set_disabled(minutes)

    if minutes:
        disabled_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
        click.echo(f"\n  Watchdog disabled for {minutes} minutes")
        click.echo(f"  Re-enables at: {disabled_until.strftime('%H:%M')}")
    else:
        click.echo("\n  Watchdog disabled permanently")
        click.echo("  Use 'enable' to re-enable")
    click.echo()


@watchdog_cli.command("enable")
def cmd_enable() -> None:
    """Re-enable watchdog."""
    if clear_disabled():
        click.echo("\n  Watchdog enabled\n")
    else:
        click.echo("\n  Watchdog is already enabled\n")


# Make watchdog available as subcommand of main CLI
def register_watchdog(main_group: click.Group) -> None:
    """Register watchdog commands as subcommand of main CLI."""
    main_group.add_command(watchdog_cli, name="watchdog")


# Alias for backward compatibility with tests
main = watchdog_cli
