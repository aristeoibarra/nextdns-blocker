"""Command-line interface for NextDNS Blocker using Click."""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import click

from . import __version__
from .client import NextDNSClient
from .common import (
    audit_log,
    ensure_log_dir,
    get_audit_log_file,
    get_log_dir,
    read_secure_file,
    validate_domain,
    write_secure_file,
)
from .config import (
    DEFAULT_PAUSE_MINUTES,
    get_cache_status,
    get_protected_domains,
    load_config,
    load_domains,
)
from .exceptions import ConfigurationError, DomainValidationError
from .init import run_interactive_wizard, run_non_interactive
from .scheduler import ScheduleEvaluator

# =============================================================================
# LOGGING SETUP
# =============================================================================


def get_app_log_file() -> Path:
    """Get the app log file path."""
    return get_log_dir() / "app.log"


def get_pause_file() -> Path:
    """Get the pause state file path."""
    return get_log_dir() / ".paused"


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    ensure_log_dir()

    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(get_app_log_file()), logging.StreamHandler()],
    )


logger = logging.getLogger(__name__)


# =============================================================================
# PAUSE MANAGEMENT
# =============================================================================


def is_paused() -> bool:
    """Check if blocking is currently paused."""
    pause_file = get_pause_file()
    content = read_secure_file(pause_file)
    if not content:
        return False

    try:
        pause_until = datetime.fromisoformat(content)
        if datetime.now() < pause_until:
            return True
        # Expired, clean up
        pause_file.unlink(missing_ok=True)
        return False
    except ValueError:
        return False


def get_pause_remaining() -> Optional[str]:
    """Get remaining pause time as human-readable string."""
    pause_file = get_pause_file()
    content = read_secure_file(pause_file)
    if not content:
        return None

    try:
        pause_until = datetime.fromisoformat(content)
        remaining = pause_until - datetime.now()

        if remaining.total_seconds() <= 0:
            pause_file.unlink(missing_ok=True)
            return None

        mins = int(remaining.total_seconds() // 60)
        return f"{mins} min" if mins > 0 else "< 1 min"
    except ValueError:
        return None


def set_pause(minutes: int) -> datetime:
    """Set pause for specified minutes. Returns the pause end time."""
    pause_until = datetime.now().replace(microsecond=0) + timedelta(minutes=minutes)
    write_secure_file(get_pause_file(), pause_until.isoformat())
    audit_log("PAUSE", f"{minutes} minutes until {pause_until.isoformat()}")
    return pause_until


def clear_pause() -> bool:
    """Clear pause state. Returns True if was paused."""
    pause_file = get_pause_file()
    if pause_file.exists():
        pause_file.unlink(missing_ok=True)
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
@click.option(
    "--config-dir",
    type=click.Path(file_okay=False, path_type=Path),
    help="Config directory (default: XDG config dir)",
)
@click.option("--url", "domains_url", help="URL for remote domains.json")
@click.option(
    "--non-interactive", is_flag=True, help="Use environment variables instead of prompts"
)
def init(config_dir: Optional[Path], domains_url: Optional[str], non_interactive: bool) -> None:
    """Initialize NextDNS Blocker configuration.

    Runs an interactive wizard to configure API credentials and create
    the necessary configuration files.

    Use --non-interactive for CI/CD environments (requires NEXTDNS_API_KEY
    and NEXTDNS_PROFILE_ID environment variables).
    """
    if non_interactive:
        success = run_non_interactive(config_dir, domains_url)
    else:
        success = run_interactive_wizard(config_dir, domains_url)

    if not success:
        sys.exit(1)


@main.command()
@click.argument("minutes", default=DEFAULT_PAUSE_MINUTES, type=click.IntRange(min=1))
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
@click.argument("domain")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def unblock(domain: str, config_dir: Optional[Path]) -> None:
    """Manually unblock a DOMAIN."""
    try:
        config = load_config(config_dir)
        domains, _ = load_domains(config["script_dir"], config.get("domains_url"))
        protected = get_protected_domains(domains)

        if not validate_domain(domain):
            click.echo(f"\n  Error: Invalid domain format '{domain}'\n", err=True)
            sys.exit(1)

        if domain in protected:
            click.echo(f"\n  Error: '{domain}' is protected and cannot be unblocked\n", err=True)
            sys.exit(1)

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
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
@click.option("--dry-run", is_flag=True, help="Show changes without applying")
@click.option("-v", "--verbose", is_flag=True, help="Verbose output")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option(
    "--domains-url",
    "domains_url_override",
    help="URL for remote domains.json (overrides DOMAINS_URL from config)",
)
def sync(
    dry_run: bool, verbose: bool, config_dir: Optional[Path], domains_url_override: Optional[str]
) -> None:
    """Synchronize domain blocking with schedules."""
    setup_logging(verbose)

    # Check pause state
    if is_paused():
        remaining = get_pause_remaining()
        click.echo(f"  Paused ({remaining} remaining), skipping sync")
        return

    try:
        config = load_config(config_dir)
        # CLI flag overrides config file
        domains_url = domains_url_override or config.get("domains_url")
        domains, allowlist = load_domains(config["script_dir"], domains_url)
        protected = get_protected_domains(domains)

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        if dry_run:
            click.echo("\n  DRY RUN MODE - No changes will be made\n")

        # Sync denylist domains
        blocked_count = 0
        unblocked_count = 0

        for domain_config in domains:
            domain = domain_config["domain"]
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
            domain = allowlist_config["domain"]
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
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def status(config_dir: Optional[Path]) -> None:
    """Show current blocking status."""
    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"], config.get("domains_url"))
        protected = get_protected_domains(domains)

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        click.echo("\n  NextDNS Blocker Status")
        click.echo("  ----------------------")
        click.echo(f"  Profile: {config['profile_id']}")
        click.echo(f"  Timezone: {config['timezone']}")

        # Pause state
        if is_paused():
            remaining = get_pause_remaining()
            click.echo(f"  Pause: ACTIVE ({remaining})")
        else:
            click.echo("  Pause: inactive")

        click.echo(f"\n  Domains ({len(domains)}):")

        for domain_config in domains:
            domain = domain_config["domain"]
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)
            is_protected = domain in protected

            status_icon = "🔒" if is_blocked else "🔓"
            expected = "block" if should_block else "allow"
            actual = "blocked" if is_blocked else "allowed"
            match = "✓" if (should_block == is_blocked) else "✗ MISMATCH"
            protected_flag = " [protected]" if is_protected else ""

            click.echo(
                f"    {status_icon} {domain}: {actual} (should: {expected}) {match}{protected_flag}"
            )

        if allowlist:
            click.echo(f"\n  Allowlist ({len(allowlist)}):")
            for item in allowlist:
                domain = item["domain"]
                is_allowed = client.is_allowed(domain)
                status_icon = "✓" if is_allowed else "✗"
                click.echo(f"    {status_icon} {domain}")

        click.echo()

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.argument("domain")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def allow(domain: str, config_dir: Optional[Path]) -> None:
    """Add DOMAIN to allowlist."""
    try:
        if not validate_domain(domain):
            click.echo(f"\n  Error: Invalid domain format '{domain}'\n", err=True)
            sys.exit(1)

        config = load_config(config_dir)
        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )

        # Warn if domain is in denylist
        if client.is_blocked(domain):
            click.echo(f"  Warning: '{domain}' is currently blocked in denylist")

        if client.allow(domain):
            audit_log("ALLOW", domain)
            click.echo(f"\n  Added to allowlist: {domain}\n")
        else:
            click.echo("\n  Error: Failed to add to allowlist\n", err=True)
            sys.exit(1)

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)
    except DomainValidationError as e:
        click.echo(f"\n  Error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.argument("domain")
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def disallow(domain: str, config_dir: Optional[Path]) -> None:
    """Remove DOMAIN from allowlist."""
    try:
        if not validate_domain(domain):
            click.echo(f"\n  Error: Invalid domain format '{domain}'\n", err=True)
            sys.exit(1)

        config = load_config(config_dir)
        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )

        if client.disallow(domain):
            audit_log("DISALLOW", domain)
            click.echo(f"\n  Removed from allowlist: {domain}\n")
        else:
            click.echo("\n  Error: Failed to remove from allowlist\n", err=True)
            sys.exit(1)

    except ConfigurationError as e:
        click.echo(f"\n  Config error: {e}\n", err=True)
        sys.exit(1)
    except DomainValidationError as e:
        click.echo(f"\n  Error: {e}\n", err=True)
        sys.exit(1)


@main.command()
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
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
        domains, allowlist = load_domains(config["script_dir"], config.get("domains_url"))
        click.echo(f"  [✓] Domains loaded ({len(domains)} domains, {len(allowlist)} allowlist)")
        checks_passed += 1
    except ConfigurationError as e:
        click.echo(f"  [✗] Domains: {e}")
        sys.exit(1)

    # Check remote domains cache (informational only, doesn't affect pass/fail)
    if config.get("domains_url"):
        cache_status = get_cache_status()
        if cache_status.get("exists"):
            if cache_status.get("corrupted"):
                click.echo("  [!] Remote domains cache: corrupted")
            else:
                age_mins = cache_status.get("age_seconds", 0) // 60
                expired = "expired" if cache_status.get("expired") else "valid"
                click.echo(f"  [i] Remote domains cache: {expired} (age: {age_mins}m)")
        else:
            click.echo("  [i] Remote domains cache: not present")

    # Check API connectivity
    checks_total += 1
    client = NextDNSClient(
        config["api_key"], config["profile_id"], config["timeout"], config["retries"]
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
        log_dir = get_log_dir()
        if log_dir.exists() and log_dir.is_dir():
            click.echo(f"  [✓] Log directory: {log_dir}")
            checks_passed += 1
        else:
            click.echo("  [✗] Log directory not accessible")
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

    audit_file = get_audit_log_file()
    if not audit_file.exists():
        click.echo("  No audit log found\n")
        return

    try:
        with open(audit_file) as f:
            lines = f.readlines()

        actions: dict[str, int] = {}
        for line in lines:
            parts = line.strip().split(" | ")
            if len(parts) >= 2:
                action = parts[1] if len(parts) == 3 else parts[1]
                # Skip WD prefix entries or extract action
                if action == "WD":
                    action = parts[2] if len(parts) > 2 else "UNKNOWN"
                actions[action] = actions.get(action, 0) + 1

        if actions:
            for action, count in sorted(actions.items()):
                click.echo(f"    {action}: {count}")
        else:
            click.echo("  No actions recorded")

        click.echo(f"\n  Total entries: {len(lines)}\n")

    except Exception as e:
        click.echo(f"  Error reading stats: {e}\n", err=True)


if __name__ == "__main__":
    main()
