"""Command-line interface for NextDNS Blocker using Click."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import click

from . import __version__
from .client import NextDNSClient
from .common import (
    AUDIT_LOG_FILE,
    LOG_DIR,
    audit_log,
    ensure_log_dir,
    read_secure_file,
    validate_domain,
    write_secure_file,
)
from .config import (
    DEFAULT_PAUSE_MINUTES,
    get_protected_domains,
    load_config,
    load_domains,
)
from .exceptions import ConfigurationError, DomainValidationError
from .scheduler import ScheduleEvaluator


# =============================================================================
# LOGGING SETUP
# =============================================================================

APP_LOG_FILE = LOG_DIR / "app.log"
PAUSE_FILE = LOG_DIR / ".paused"


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    ensure_log_dir()

    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(APP_LOG_FILE),
            logging.StreamHandler()
        ]
    )


logger = logging.getLogger(__name__)


# =============================================================================
# PAUSE MANAGEMENT
# =============================================================================

def is_paused() -> bool:
    """Check if blocking is currently paused."""
    content = read_secure_file(PAUSE_FILE)
    if not content:
        return False

    try:
        pause_until = datetime.fromisoformat(content)
        if datetime.now() < pause_until:
            return True
        # Expired, clean up
        PAUSE_FILE.unlink(missing_ok=True)
        return False
    except ValueError:
        return False


def get_pause_remaining() -> Optional[str]:
    """Get remaining pause time as human-readable string."""
    content = read_secure_file(PAUSE_FILE)
    if not content:
        return None

    try:
        pause_until = datetime.fromisoformat(content)
        remaining = pause_until - datetime.now()

        if remaining.total_seconds() <= 0:
            PAUSE_FILE.unlink(missing_ok=True)
            return None

        mins = int(remaining.total_seconds() // 60)
        return f"{mins} min" if mins > 0 else "< 1 min"
    except ValueError:
        return None


def set_pause(minutes: int) -> datetime:
    """Set pause for specified minutes. Returns the pause end time."""
    pause_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
    write_secure_file(PAUSE_FILE, pause_until.isoformat())
    audit_log("PAUSE", f"{minutes} minutes until {pause_until.isoformat()}")
    return pause_until


def clear_pause() -> bool:
    """Clear pause state. Returns True if was paused."""
    if PAUSE_FILE.exists():
        PAUSE_FILE.unlink(missing_ok=True)
        audit_log("RESUME", "Manual resume")
        return True
    return False


# =============================================================================
# CLICK CLI
# =============================================================================

@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="nextdns-blocker")
@click.pass_context
def main(ctx: click.Context) -> None:
    """NextDNS Blocker - Domain blocking with per-domain scheduling."""
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@main.command()
@click.argument('minutes', default=DEFAULT_PAUSE_MINUTES, type=click.IntRange(min=1))
def pause(minutes: int) -> None:
    """Pause blocking for MINUTES (default: 30)."""
    set_pause(minutes)
    pause_until = datetime.now() + timedelta(minutes=minutes)
    click.echo(f"\n  Blocking paused for {minutes} minutes")
    click.echo(f"  Resumes at: {pause_until.strftime('%H:%M')}\n")


@main.command()
def resume() -> None:
    """Resume blocking immediately."""
    if clear_pause():
        click.echo("\n  Blocking resumed\n")
    else:
        click.echo("\n  Not currently paused\n")


@main.command()
@click.argument('domain')
@click.option('--config-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Config directory (default: auto-detect)')
def unblock(domain: str, config_dir: Optional[Path]) -> None:
    """Manually unblock a DOMAIN."""
    try:
        config = load_config(config_dir)
        domains, _ = load_domains(config['script_dir'], config.get('domains_url'))
        protected = get_protected_domains(domains)

        if not validate_domain(domain):
            click.echo(f"\n  Error: Invalid domain format '{domain}'\n", err=True)
            sys.exit(1)

        if domain in protected:
            click.echo(f"\n  Error: '{domain}' is protected and cannot be unblocked\n", err=True)
            sys.exit(1)

        client = NextDNSClient(
            config['api_key'],
            config['profile_id'],
            config['timeout'],
            config['retries']
        )

        if client.unblock(domain):
            audit_log("UNBLOCK", domain)
            click.echo(f"\n  Unblocked: {domain}\n")
        else:
            click.echo(f"\n  Error: Failed to unblock '{domain}'\n", err=True)
            sys.exit(1)

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)
    except DomainValidationError as e:
        click.echo(f"\n  Error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.option('--dry-run', is_flag=True, help='Show changes without applying')
@click.option('-v', '--verbose', is_flag=True, help='Verbose output')
@click.option('--config-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Config directory (default: auto-detect)')
def sync(dry_run: bool, verbose: bool, config_dir: Optional[Path]) -> None:
    """Synchronize domain blocking with schedules."""
    setup_logging(verbose)

    # Check pause state
    if is_paused():
        remaining = get_pause_remaining()
        click.echo(f"  Paused ({remaining} remaining), skipping sync")
        return

    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config['script_dir'], config.get('domains_url'))
        protected = get_protected_domains(domains)

        client = NextDNSClient(
            config['api_key'],
            config['profile_id'],
            config['timeout'],
            config['retries']
        )
        evaluator = ScheduleEvaluator(config['timezone'])

        if dry_run:
            click.echo("\n  DRY RUN MODE - No changes will be made\n")

        # Sync denylist domains
        blocked_count = 0
        unblocked_count = 0

        for domain_config in domains:
            domain = domain_config['domain']
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)

            if should_block and not is_blocked:
                if dry_run:
                    click.echo(f"  Would BLOCK: {domain}")
                else:
                    if client.block(domain):
                        audit_log("BLOCK", domain)
                        blocked_count += 1
            elif not should_block and is_blocked:
                # Don't unblock protected domains
                if domain in protected:
                    if verbose:
                        click.echo(f"  Protected (skip unblock): {domain}")
                    continue

                if dry_run:
                    click.echo(f"  Would UNBLOCK: {domain}")
                else:
                    if client.unblock(domain):
                        audit_log("UNBLOCK", domain)
                        unblocked_count += 1

        # Sync allowlist
        for allowlist_config in allowlist:
            domain = allowlist_config['domain']
            if not client.is_allowed(domain):
                if dry_run:
                    click.echo(f"  Would ADD to allowlist: {domain}")
                else:
                    if client.allow(domain):
                        audit_log("ALLOW", domain)

        if not dry_run:
            if blocked_count or unblocked_count:
                click.echo(f"  Sync: {blocked_count} blocked, {unblocked_count} unblocked")
            elif verbose:
                click.echo("  Sync: No changes needed")

    except ConfigurationError as e:
        click.echo(f"  Config error: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option('--config-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Config directory (default: auto-detect)')
def status(config_dir: Optional[Path]) -> None:
    """Show current blocking status."""
    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config['script_dir'], config.get('domains_url'))
        protected = get_protected_domains(domains)

        client = NextDNSClient(
            config['api_key'],
            config['profile_id'],
            config['timeout'],
            config['retries']
        )
        evaluator = ScheduleEvaluator(config['timezone'])

        click.echo(f"\n  NextDNS Blocker Status")
        click.echo(f"  ----------------------")
        click.echo(f"  Profile: {config['profile_id']}")
        click.echo(f"  Timezone: {config['timezone']}")

        # Pause state
        if is_paused():
            remaining = get_pause_remaining()
            click.echo(f"  Pause: ACTIVE ({remaining})")
        else:
            click.echo(f"  Pause: inactive")

        click.echo(f"\n  Domains ({len(domains)}):")

        for domain_config in domains:
            domain = domain_config['domain']
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)
            is_protected = domain in protected

            status_icon = "🔒" if is_blocked else "🔓"
            expected = "block" if should_block else "allow"
            actual = "blocked" if is_blocked else "allowed"
            match = "✓" if (should_block == is_blocked) else "✗ MISMATCH"
            protected_flag = " [protected]" if is_protected else ""

            click.echo(f"    {status_icon} {domain}: {actual} (should: {expected}) {match}{protected_flag}")

        if allowlist:
            click.echo(f"\n  Allowlist ({len(allowlist)}):")
            for item in allowlist:
                domain = item['domain']
                is_allowed = client.is_allowed(domain)
                status_icon = "✓" if is_allowed else "✗"
                click.echo(f"    {status_icon} {domain}")

        click.echo()

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.argument('domain')
@click.option('--config-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Config directory (default: auto-detect)')
def allow(domain: str, config_dir: Optional[Path]) -> None:
    """Add DOMAIN to allowlist."""
    try:
        if not validate_domain(domain):
            click.echo(f"\n  Error: Invalid domain format '{domain}'\n", err=True)
            sys.exit(1)

        config = load_config(config_dir)
        client = NextDNSClient(
            config['api_key'],
            config['profile_id'],
            config['timeout'],
            config['retries']
        )

        # Warn if domain is in denylist
        if client.is_blocked(domain):
            click.echo(f"  Warning: '{domain}' is currently blocked in denylist")

        if client.allow(domain):
            audit_log("ALLOW", domain)
            click.echo(f"\n  Added to allowlist: {domain}\n")
        else:
            click.echo(f"\n  Error: Failed to add to allowlist\n", err=True)
            sys.exit(1)

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)
    except DomainValidationError as e:
        click.echo(f"\n  Error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.argument('domain')
@click.option('--config-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Config directory (default: auto-detect)')
def disallow(domain: str, config_dir: Optional[Path]) -> None:
    """Remove DOMAIN from allowlist."""
    try:
        if not validate_domain(domain):
            click.echo(f"\n  Error: Invalid domain format '{domain}'\n", err=True)
            sys.exit(1)

        config = load_config(config_dir)
        client = NextDNSClient(
            config['api_key'],
            config['profile_id'],
            config['timeout'],
            config['retries']
        )

        if client.disallow(domain):
            audit_log("DISALLOW", domain)
            click.echo(f"\n  Removed from allowlist: {domain}\n")
        else:
            click.echo(f"\n  Error: Failed to remove from allowlist\n", err=True)
            sys.exit(1)

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)
    except DomainValidationError as e:
        click.echo(f"\n  Error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.option('--config-dir', type=click.Path(exists=True, file_okay=False, path_type=Path),
              help='Config directory (default: auto-detect)')
def health(config_dir: Optional[Path]) -> None:
    """Perform health checks."""
    checks_passed = 0
    checks_total = 0

    click.echo("\n  Health Check")
    click.echo("  ------------")

    # Check config
    checks_total += 1
    try:
        config = load_config(config_dir)
        click.echo("  [✓] Configuration loaded")
        checks_passed += 1
    except ConfigurationError as e:
        click.echo(f"  [✗] Configuration: {e}")
        sys.exit(1)

    # Check domains.json
    checks_total += 1
    try:
        domains, allowlist = load_domains(config['script_dir'], config.get('domains_url'))
        click.echo(f"  [✓] Domains loaded ({len(domains)} domains, {len(allowlist)} allowlist)")
        checks_passed += 1
    except ConfigurationError as e:
        click.echo(f"  [✗] Domains: {e}")
        sys.exit(1)

    # Check API connectivity
    checks_total += 1
    client = NextDNSClient(
        config['api_key'],
        config['profile_id'],
        config['timeout'],
        config['retries']
    )
    denylist = client.get_denylist()
    if denylist is not None:
        click.echo(f"  [✓] API connectivity ({len(denylist)} items in denylist)")
        checks_passed += 1
    else:
        click.echo("  [✗] API connectivity failed")

    # Check log directory
    checks_total += 1
    try:
        ensure_log_dir()
        if LOG_DIR.exists() and LOG_DIR.is_dir():
            click.echo(f"  [✓] Log directory: {LOG_DIR}")
            checks_passed += 1
        else:
            click.echo(f"  [✗] Log directory not accessible")
    except Exception as e:
        click.echo(f"  [✗] Log directory: {e}")

    # Summary
    click.echo(f"\n  Result: {checks_passed}/{checks_total} checks passed")
    if checks_passed == checks_total:
        click.echo("  Status: HEALTHY\n")
    else:
        click.echo("  Status: DEGRADED\n")
        sys.exit(1)


@main.command()
def stats() -> None:
    """Show usage statistics from audit log."""
    click.echo("\n  Statistics")
    click.echo("  ----------")

    audit_file = LOG_DIR / "audit.log"
    if not audit_file.exists():
        click.echo("  No audit log found\n")
        return

    try:
        with open(audit_file, 'r') as f:
            lines = f.readlines()

        actions: Dict[str, int] = {}
        for line in lines:
            parts = line.strip().split(' | ')
            if len(parts) >= 2:
                action = parts[1] if len(parts) == 3 else parts[1]
                # Skip WD prefix entries or extract action
                if action == 'WD':
                    action = parts[2] if len(parts) > 2 else 'UNKNOWN'
                actions[action] = actions.get(action, 0) + 1

        if actions:
            for action, count in sorted(actions.items()):
                click.echo(f"    {action}: {count}")
        else:
            click.echo("  No actions recorded")

        click.echo(f"\n  Total entries: {len(lines)}\n")

    except Exception as e:
        click.echo(f"  Error reading stats: {e}\n", err=True)


# =============================================================================
# LEGACY FUNCTIONS FOR BACKWARD COMPATIBILITY WITH TESTS
# =============================================================================

def cmd_allow(target: str, client: NextDNSClient, denylist_domains: List[str]) -> int:
    """
    Legacy function for allowing a domain.

    Args:
        target: Domain to allow
        client: NextDNS client instance
        denylist_domains: List of domains in denylist (for warning)

    Returns:
        0 on success, 1 on error
    """
    if not validate_domain(target):
        print(f"\n  Error: Invalid domain format '{target}'\n")
        return 1

    # Warn if domain is in denylist
    if target in denylist_domains:
        print(f"  Warning: '{target}' is currently blocked in denylist")

    if client.allow(target):
        audit_log("ALLOW", target)
        print(f"\n  Added to allowlist: {target}\n")
        return 0
    else:
        print(f"\n  Error: Failed to add to allowlist\n")
        return 1


def cmd_disallow(target: str, client: NextDNSClient) -> int:
    """
    Legacy function for removing a domain from allowlist.

    Args:
        target: Domain to disallow
        client: NextDNS client instance

    Returns:
        0 on success, 1 on error
    """
    if not validate_domain(target):
        print(f"\n  Error: Invalid domain format '{target}'\n")
        return 1

    if client.disallow(target):
        audit_log("DISALLOW", target)
        print(f"\n  Removed from allowlist: {target}\n")
        return 0
    else:
        print(f"\n  Error: Failed to remove from allowlist\n")
        return 1


def cmd_sync(
    client: NextDNSClient,
    domains: List[Dict[str, Any]],
    allowlist: List[Dict[str, Any]],
    protected_domains: List[str],
    timezone: str,
    dry_run: bool = False,
    verbose: bool = False
) -> int:
    """
    Legacy function for syncing domains.

    Args:
        client: NextDNS client instance
        domains: List of domain configurations
        allowlist: List of allowlist configurations
        protected_domains: List of protected domain names
        timezone: Timezone string
        dry_run: If True, don't make changes
        verbose: If True, show detailed output

    Returns:
        0 on success, 1 on error
    """
    # Check if paused
    if is_paused():
        remaining = get_pause_remaining()
        if verbose:
            print(f"  Sync skipped: paused ({remaining} remaining)")
        return 0

    try:
        evaluator = ScheduleEvaluator(timezone)
    except Exception:
        print(f"\n  Invalid timezone: {timezone}\n")
        return 1

    if dry_run:
        print("\n  DRY RUN MODE - No changes will be made\n")

    blocked_count = 0
    unblocked_count = 0

    for domain_config in domains:
        domain = domain_config['domain']
        should_block = evaluator.should_block_domain(domain_config)
        is_blocked = client.is_blocked(domain)

        if should_block and not is_blocked:
            if dry_run:
                print(f"  Would BLOCK: {domain}")
            else:
                if client.block(domain):
                    audit_log("BLOCK", domain)
                    blocked_count += 1
        elif not should_block and is_blocked:
            if domain in protected_domains:
                if verbose:
                    print(f"  Protected (skip unblock): {domain}")
                continue

            if dry_run:
                print(f"  Would UNBLOCK: {domain}")
            else:
                if client.unblock(domain):
                    audit_log("UNBLOCK", domain)
                    unblocked_count += 1

    # Sync allowlist
    for allowlist_config in allowlist:
        domain = allowlist_config['domain']
        if not client.is_allowed(domain):
            if dry_run:
                print(f"  Would ADD to allowlist: {domain}")
            else:
                if client.allow(domain):
                    audit_log("ALLOW", domain)

    if not dry_run:
        if blocked_count or unblocked_count:
            print(f"  Sync: {blocked_count} blocked, {unblocked_count} unblocked")
        elif verbose:
            print("  Sync: No changes needed")

    return 0


def cmd_status(
    client: NextDNSClient,
    domains: List[Dict[str, Any]],
    allowlist: List[Dict[str, Any]],
    protected_domains: List[str],
    timezone: str = "UTC"
) -> int:
    """
    Legacy function for showing status.

    Args:
        client: NextDNS client instance
        domains: List of domain configurations
        allowlist: List of allowlist configurations
        protected_domains: List of protected domain names
        timezone: Timezone string

    Returns:
        0 on success
    """
    evaluator = ScheduleEvaluator(timezone)

    # Check pause state
    if is_paused():
        remaining = get_pause_remaining()
        print(f"\n  Status: PAUSED ({remaining} remaining)")

    print(f"\n  Domains ({len(domains)}):")

    for domain_config in domains:
        domain = domain_config['domain']
        should_block = evaluator.should_block_domain(domain_config)
        is_blocked = client.is_blocked(domain)
        is_protected = domain in protected_domains

        status_icon = "🔒" if is_blocked else "🔓"
        expected = "block" if should_block else "allow"
        actual = "blocked" if is_blocked else "allowed"
        match = "✓" if (should_block == is_blocked) else "✗ MISMATCH"
        protected_flag = " [protected]" if is_protected else ""

        print(f"    {status_icon} {domain}: {actual} (should: {expected}) {match}{protected_flag}")

    if allowlist:
        print(f"\n  Allowlist ({len(allowlist)}):")
        for item in allowlist:
            domain = item['domain']
            is_allowed = client.is_allowed(domain)
            status_icon = "✓" if is_allowed else "✗"
            print(f"    {status_icon} {domain}")

    print()
    return 0


def cmd_pause(minutes: int = DEFAULT_PAUSE_MINUTES) -> int:
    """
    Legacy function for pausing blocking.

    Args:
        minutes: Duration to pause in minutes

    Returns:
        0 on success
    """
    set_pause(minutes)
    pause_until = datetime.now() + timedelta(minutes=minutes)
    print(f"\n  Blocking paused for {minutes} minutes")
    print(f"  Resumes at: {pause_until.strftime('%H:%M')}\n")
    return 0


def cmd_resume() -> int:
    """
    Legacy function for resuming blocking.

    Returns:
        0 on success
    """
    if clear_pause():
        print("\n  Blocking resumed\n")
    else:
        print("\n  Not currently paused\n")
    return 0


def cmd_unblock(domain: str, client: NextDNSClient, protected_domains: List[str]) -> int:
    """
    Legacy function for unblocking a domain.

    Args:
        domain: Domain to unblock
        client: NextDNS client instance
        protected_domains: List of protected domain names

    Returns:
        0 on success, 1 on error
    """
    if not validate_domain(domain):
        print(f"\n  Invalid domain: {domain}\n")
        return 1

    if domain in protected_domains:
        print(f"\n  Cannot unblock protected domain: {domain}\n")
        return 1

    if client.unblock(domain):
        audit_log("UNBLOCK", domain)
        print(f"\n  Unblocked: {domain}\n")
        return 0
    else:
        print(f"\n  Failed to unblock: {domain}\n")
        return 1


def cmd_health(client: NextDNSClient, config: Dict[str, Any]) -> int:
    """
    Legacy function for health check.

    Args:
        client: NextDNS client instance
        config: Configuration dictionary

    Returns:
        0 if healthy, 1 if unhealthy
    """
    from zoneinfo import ZoneInfo

    print("\n  === Health Check ===\n")
    healthy = True

    # Check timezone
    tz = config.get('timezone', 'UTC')
    try:
        ZoneInfo(tz)
        print(f"  [OK] Timezone: {tz}")
    except Exception:
        print(f"  [FAIL] Invalid timezone: {tz}")
        healthy = False

    # Check API connectivity
    result = client.get_denylist(use_cache=False)
    if result is not None:
        print("  [OK] API connectivity")
    else:
        print("  [FAIL] API connectivity: Failed to fetch denylist")
        healthy = False

    # Check pause state
    if is_paused():
        remaining = get_pause_remaining()
        print(f"  [INFO] PAUSED ({remaining} remaining)")

    # Summary
    if healthy:
        print("\n  Status: HEALTHY\n")
        return 0
    else:
        print("\n  Status: UNHEALTHY\n")
        return 1


def cmd_stats() -> int:
    """
    Legacy function for showing statistics.

    Returns:
        0 on success
    """
    print("\n  === Statistics ===\n")

    stats = get_stats()
    print(f"  Total blocks: {stats['total_blocks']}")
    print(f"  Total unblocks: {stats['total_unblocks']}")
    print(f"  Total pauses: {stats['total_pauses']}")

    if stats.get('last_action'):
        print(f"  Last action: {stats['last_action']}")

    print()
    return 0


def get_stats() -> Dict[str, Any]:
    """
    Get statistics from audit log.

    Returns:
        Dictionary with stats
    """
    stats = {
        'total_blocks': 0,
        'total_unblocks': 0,
        'total_pauses': 0,
        'last_action': None
    }

    if not AUDIT_LOG_FILE.exists():
        return stats

    try:
        lines = AUDIT_LOG_FILE.read_text().strip().split('\n')
        for line in lines:
            if '| BLOCK |' in line:
                stats['total_blocks'] += 1
            elif '| UNBLOCK |' in line:
                stats['total_unblocks'] += 1
            elif '| PAUSE |' in line:
                stats['total_pauses'] += 1

        if lines and lines[-1]:
            # Extract timestamp from last line
            parts = lines[-1].split(' | ')
            if parts:
                stats['last_action'] = parts[0].strip()
    except Exception:
        pass

    return stats


def print_usage() -> None:
    """Legacy function to print usage information."""
    print("""
  Usage: nextdns-blocker <command> [options]

  Commands:
    sync          Sync domain blocking based on schedules
    status        Show current blocking status
    unblock       Manually unblock a domain
    pause         Pause blocking temporarily
    resume        Resume blocking
    allow         Add domain to allowlist
    disallow      Remove domain from allowlist
    health        Check system health
    stats         Show statistics

  Options:
    --dry-run     Preview changes without making them
    --verbose,-v  Show detailed output
    --help        Show help for a command

  Examples:
    nextdns-blocker sync
    nextdns-blocker sync --dry-run
    nextdns-blocker pause 60
    nextdns-blocker unblock example.com
""")


if __name__ == '__main__':
    main()
