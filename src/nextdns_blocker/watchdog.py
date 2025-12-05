"""Cron Watchdog - Monitors and restores cron jobs if deleted."""

import logging
import shlex
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click

logger = logging.getLogger(__name__)

from .common import (
    SECURE_FILE_MODE,
    audit_log as _base_audit_log,
    get_log_dir,
    read_secure_file,
    write_secure_file,
)


# =============================================================================
# CONFIGURATION & CONSTANTS
# =============================================================================

INSTALL_DIR = Path(__file__).parent.parent.parent.absolute()
SUBPROCESS_TIMEOUT = 60


def get_disabled_file() -> Path:
    """Get the watchdog disabled state file path."""
    return get_log_dir() / ".watchdog_disabled"


def get_cron_sync() -> str:
    """Get the sync cron job definition."""
    log_dir = get_log_dir()
    install_dir = shlex.quote(str(INSTALL_DIR))
    log_file = shlex.quote(str(log_dir / "cron.log"))
    return f"*/2 * * * * cd {install_dir} && nextdns-blocker sync >> {log_file} 2>&1"


def get_cron_watchdog() -> str:
    """Get the watchdog cron job definition."""
    log_dir = get_log_dir()
    install_dir = shlex.quote(str(INSTALL_DIR))
    log_file = shlex.quote(str(log_dir / "wd.log"))
    return f"* * * * * cd {install_dir} && nextdns-blocker watchdog check >> {log_file} 2>&1"


# Keep legacy constants for backwards compatibility with tests
DISABLED_FILE = get_disabled_file()
CRON_SYNC = get_cron_sync()
CRON_WATCHDOG = get_cron_watchdog()


def audit_log(action: str, detail: str = "") -> None:
    """Wrapper for audit_log with WD prefix."""
    _base_audit_log(action, detail, prefix="WD")


# =============================================================================
# DISABLED STATE MANAGEMENT
# =============================================================================

def is_disabled() -> bool:
    """Check if watchdog is temporarily or permanently disabled."""
    content = read_secure_file(DISABLED_FILE)
    if not content:
        return False

    try:
        if content == "permanent":
            return True

        disabled_until = datetime.fromisoformat(content)
        if datetime.now() < disabled_until:
            return True

        # Expired, clean up
        _remove_disabled_file()
        return False
    except ValueError:
        return False


def get_disabled_remaining() -> str:
    """Get remaining disabled time as human-readable string."""
    content = read_secure_file(DISABLED_FILE)
    if not content:
        return ""

    try:
        if content == "permanent":
            return "permanently"

        disabled_until = datetime.fromisoformat(content)
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
        DISABLED_FILE.unlink(missing_ok=True)
    except OSError as e:
        logger.debug(f"Failed to remove disabled file: {e}")


def set_disabled(minutes: Optional[int] = None) -> None:
    """Disable watchdog temporarily or permanently."""
    if minutes:
        disabled_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
        write_secure_file(DISABLED_FILE, disabled_until.isoformat())
        audit_log("WD_DISABLED", f"{minutes} minutes until {disabled_until.isoformat()}")
    else:
        write_secure_file(DISABLED_FILE, "permanent")
        audit_log("WD_DISABLED", "permanent")


def clear_disabled() -> bool:
    """Re-enable watchdog. Returns True if was disabled."""
    if DISABLED_FILE.exists():
        _remove_disabled_file()
        audit_log("WD_ENABLED", "Manual enable")
        return True
    return False


# =============================================================================
# CRON MANAGEMENT
# =============================================================================

def get_crontab() -> str:
    """Get the current user's crontab contents."""
    try:
        result = subprocess.run(
            ['crontab', '-l'],
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT
        )
        return result.stdout if result.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return ""


def set_crontab(content: str) -> bool:
    """Set the user's crontab contents."""
    try:
        process = subprocess.Popen(
            ['crontab', '-'],
            stdin=subprocess.PIPE,
            text=True
        )
        process.communicate(input=content, timeout=SUBPROCESS_TIMEOUT)
        return process.returncode == 0
    except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
        return False


def has_sync_cron(crontab: str) -> bool:
    """Check if sync cron job is present."""
    return "nextdns-blocker sync" in crontab


def has_watchdog_cron(crontab: str) -> bool:
    """Check if watchdog cron job is present."""
    return "nextdns-blocker watchdog" in crontab


def filter_our_cron_jobs(crontab: str) -> list:
    """Remove our cron jobs from crontab, keeping other entries."""
    return [
        line for line in crontab.split('\n')
        if 'nextdns-blocker' not in line
        and line.strip()
    ]


# =============================================================================
# CLICK CLI
# =============================================================================

@click.group()
def watchdog_cli() -> None:
    """Watchdog commands for cron job management."""
    pass


@watchdog_cli.command('check')
def cmd_check() -> None:
    """Check and restore cron jobs if missing."""
    if is_disabled():
        remaining = get_disabled_remaining()
        click.echo(f"  watchdog disabled ({remaining})")
        return

    crontab = get_crontab()
    restored = False

    # Check and restore sync cron
    if not has_sync_cron(crontab):
        audit_log("CRON_DELETED", "Sync cron missing")
        new_crontab = crontab.strip()
        new_crontab = (new_crontab + "\n" if new_crontab else "") + CRON_SYNC + "\n"
        if set_crontab(new_crontab):
            click.echo("  sync cron restored")
            restored = True

    # Check and restore watchdog cron
    if not has_watchdog_cron(crontab):
        audit_log("WD_CRON_DELETED", "Watchdog cron missing")
        crontab = get_crontab()
        new_crontab = crontab.strip()
        new_crontab = (new_crontab + "\n" if new_crontab else "") + CRON_WATCHDOG + "\n"
        if set_crontab(new_crontab):
            click.echo("  watchdog cron restored")
            restored = True

    # Run sync if cron was restored
    if restored:
        try:
            subprocess.run(
                ['nextdns-blocker', 'sync'],
                timeout=SUBPROCESS_TIMEOUT
            )
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
            logger.warning(f"Failed to run sync after cron restore: {e}")


@watchdog_cli.command('install')
def cmd_install() -> None:
    """Install sync and watchdog cron jobs."""
    crontab = get_crontab()
    lines = filter_our_cron_jobs(crontab)
    lines.extend([CRON_SYNC, CRON_WATCHDOG])

    if set_crontab('\n'.join(lines) + '\n'):
        audit_log("CRON_INSTALLED", "Manual install")
        click.echo("\n  cron installed")
        click.echo("    sync       every 2 min")
        click.echo("    watchdog   every 1 min\n")
    else:
        click.echo("  error: cron install failed", err=True)
        sys.exit(1)


@watchdog_cli.command('uninstall')
def cmd_uninstall() -> None:
    """Remove cron jobs."""
    crontab = get_crontab()
    lines = filter_our_cron_jobs(crontab)
    new_content = '\n'.join(lines) + '\n' if lines else ''

    if set_crontab(new_content):
        audit_log("CRON_UNINSTALLED", "Manual uninstall")
        click.echo("\n  Cron jobs removed\n")
    else:
        click.echo("  error: failed to remove cron jobs", err=True)
        sys.exit(1)


@watchdog_cli.command('status')
def cmd_status() -> None:
    """Display current cron job status."""
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
        status = 'active' if (has_sync and has_wd) else 'compromised'
        click.echo(f"\n  status: {status}")
    click.echo()


@watchdog_cli.command('disable')
@click.argument('minutes', required=False, type=click.IntRange(min=1))
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


@watchdog_cli.command('enable')
def cmd_enable() -> None:
    """Re-enable watchdog."""
    if clear_disabled():
        click.echo("\n  Watchdog enabled\n")
    else:
        click.echo("\n  Watchdog is already enabled\n")


# Make watchdog available as subcommand of main CLI
def register_watchdog(main_group: click.Group) -> None:
    """Register watchdog commands as subcommand of main CLI."""
    main_group.add_command(watchdog_cli, name='watchdog')


# Alias for backward compatibility with tests
main = watchdog_cli
