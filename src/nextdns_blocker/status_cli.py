"""Status and health commands for NextDNS Blocker."""

import sys
from pathlib import Path
from typing import Any, Optional

import rich_click as click

from . import __version__
from . import database as db
from .cli_formatter import console
from .client import NextDNSClient
from .common import ensure_log_dir, get_log_dir
from .config import load_config, load_domains
from .exceptions import ConfigurationError
from .platform_utils import is_macos, is_windows
from .scheduler import ScheduleEvaluator
from .watchdog import (
    LAUNCHD_SYNC_LABEL,
    LAUNCHD_WATCHDOG_LABEL,
    WINDOWS_TASK_SYNC_NAME,
    WINDOWS_TASK_WATCHDOG_NAME,
    get_crontab,
    has_windows_task,
    is_launchd_job_loaded,
)


@click.command()
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
@click.option(
    "--no-update-check",
    is_flag=True,
    help="Skip checking for updates",
)
@click.option(
    "--list",
    "show_list",
    is_flag=True,
    help="Show detailed list of all domains",
)
def status(config_dir: Optional[Path], no_update_check: bool, show_list: bool) -> None:
    """Show current blocking status."""
    from .update_check import check_for_update

    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        # Collect domain statistics
        blocked_count = 0
        allowed_count = 0
        mismatches: list[dict[str, Any]] = []
        protected_domains: list[str] = []

        for domain_config in domains:
            domain = domain_config["domain"]
            should_block = evaluator.should_block_domain(domain_config)
            is_blocked = client.is_blocked(domain)

            if is_blocked:
                blocked_count += 1
            else:
                allowed_count += 1

            # Check for protected domains (unblock_delay="never")
            domain_delay = domain_config.get("unblock_delay")
            if domain_delay == "never":
                protected_domains.append(domain)

            # Check for mismatches
            if should_block != is_blocked:
                expected = "blocked" if should_block else "allowed"
                current = "blocked" if is_blocked else "allowed"
                mismatches.append(
                    {
                        "domain": domain,
                        "expected": expected,
                        "current": current,
                        "type": "denylist",
                    }
                )

        # Collect allowlist statistics
        allowlist_always_active = 0  # No schedule, always in allowlist
        allowlist_scheduled_active = 0  # Has schedule, currently active
        allowlist_scheduled_inactive = 0  # Has schedule, currently inactive
        for item in allowlist:
            domain = item["domain"]
            is_allowed = client.is_allowed(domain)
            has_schedule = item.get("schedule") is not None
            should_allow = evaluator.should_allow_domain(item)

            if has_schedule:
                if should_allow:
                    allowlist_scheduled_active += 1
                else:
                    allowlist_scheduled_inactive += 1
            else:
                allowlist_always_active += 1

            # Check for mismatches in scheduled allowlist
            if has_schedule and should_allow != is_allowed:
                expected = "allowed" if should_allow else "not allowed"
                current_str = "allowed" if is_allowed else "not allowed"
                mismatches.append(
                    {
                        "domain": domain,
                        "expected": expected,
                        "current": current_str,
                        "type": "allowlist",
                    }
                )

        # Check scheduler status
        scheduler_ok = False
        if is_macos():
            sync_ok = is_launchd_job_loaded(LAUNCHD_SYNC_LABEL)
            wd_ok = is_launchd_job_loaded(LAUNCHD_WATCHDOG_LABEL)
            scheduler_ok = sync_ok and wd_ok
        elif is_windows():
            sync_ok = has_windows_task(WINDOWS_TASK_SYNC_NAME)
            wd_ok = has_windows_task(WINDOWS_TASK_WATCHDOG_NAME)
            scheduler_ok = sync_ok and wd_ok
        else:
            crontab = get_crontab()
            has_sync = "nextdns-blocker" in crontab and "sync" in crontab
            has_wd = "nextdns-blocker" in crontab and "watchdog" in crontab
            scheduler_ok = has_sync and has_wd

        # === RENDER OUTPUT ===
        console.print()
        console.print("  [bold]NextDNS Blocker Status[/bold]")
        console.print(
            "  [dim]\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501[/dim]"
        )
        console.print()

        # Key info row
        console.print(f"  Profile    [cyan]{config['profile_id']}[/cyan]")
        console.print(f"  Timezone   [cyan]{config['timezone']}[/cyan]")

        # Scheduler status (compact)
        if scheduler_ok:
            console.print("  Scheduler  [green]running[/green]")
        else:
            console.print("  Scheduler  [red]NOT RUNNING[/red]")

        # Check for updates (unless disabled)
        if not no_update_check:
            update_info = check_for_update(__version__)
            if update_info:
                console.print()
                console.print(
                    f"  [yellow]Update available: "
                    f"{update_info.current_version} \u2192 {update_info.latest_version}[/yellow]"
                )
                console.print("  Run: [cyan]nextdns-blocker update[/cyan]")

        console.print()

        # Summary line
        mismatch_count = len(mismatches)
        summary = f"{blocked_count} blocked  \u00b7  {allowed_count} allowed"
        if mismatch_count == 0:
            summary += "  \u00b7  \u2713"
        else:
            summary += f"  \u00b7  \u26a0 {mismatch_count}"

        console.print(f"  [bold]{summary}[/bold]")

        # Show mismatches (always - this is the important stuff)
        if mismatches:
            console.print()
            console.print("  [bold red]Mismatches:[/bold red]")
            for m in mismatches:
                console.print(
                    f"    [red]\u2717[/red] {m['domain']:<25} "
                    f"should be {m['expected']} (currently: {m['current']})"
                )

        # Protected domains (compact)
        if protected_domains:
            console.print()
            protected_str = ", ".join(protected_domains)
            console.print(f"  [blue]Protected:[/blue] {protected_str}")

        # Allowlist summary
        if allowlist:
            total_scheduled = allowlist_scheduled_active + allowlist_scheduled_inactive
            if total_scheduled > 0:
                # Show breakdown when there are scheduled entries
                parts = []
                if allowlist_always_active > 0:
                    parts.append(f"{allowlist_always_active} always active")
                if total_scheduled > 0:
                    sched_detail = (
                        f"{total_scheduled} scheduled "
                        f"([green]{allowlist_scheduled_active} active[/green], "
                        f"[dim]{allowlist_scheduled_inactive} inactive[/dim])"
                    )
                    parts.append(sched_detail)
                console.print(f"  [dim]Allowlist:[/dim] {', '.join(parts)}")
            else:
                # Simple display when all entries are always-active
                console.print(f"  [dim]Allowlist:[/dim] {allowlist_always_active} active")

        # NextDNS Parental Control section
        parental_control = client.get_parental_control()
        if parental_control is not None:
            # Get active categories
            categories = parental_control.get("categories", [])
            active_categories = [c["id"] for c in categories if c.get("active", False)]

            # Get active services
            services = parental_control.get("services", [])
            active_services = [s["id"] for s in services if s.get("active", False)]

            # Get settings
            safe_search = parental_control.get("safeSearch", False)
            youtube_restricted = parental_control.get("youtubeRestrictedMode", False)
            block_bypass = parental_control.get("blockBypass", False)

            # Only show section if there's something configured
            has_parental_config = (
                active_categories
                or active_services
                or any([safe_search, youtube_restricted, block_bypass])
            )

            if has_parental_config:
                console.print()
                console.print("  [bold]NextDNS Parental Control:[/bold]")

                if active_categories:
                    cat_list = ", ".join(active_categories)
                    console.print(
                        f"    Categories: [cyan]{cat_list}[/cyan] ({len(active_categories)} active)"
                    )

                if active_services:
                    svc_list = ", ".join(active_services)
                    console.print(
                        f"    Services: [cyan]{svc_list}[/cyan] ({len(active_services)} active)"
                    )

                # Show settings
                settings_parts = []
                if safe_search:
                    settings_parts.append("[green]safe_search \u2713[/green]")
                else:
                    settings_parts.append("[dim]safe_search \u2717[/dim]")

                if youtube_restricted:
                    settings_parts.append("[green]youtube_restricted \u2713[/green]")
                else:
                    settings_parts.append("[dim]youtube_restricted \u2717[/dim]")

                if block_bypass:
                    settings_parts.append("[green]block_bypass \u2713[/green]")
                else:
                    settings_parts.append("[dim]block_bypass \u2717[/dim]")

                console.print(f"    Settings: {', '.join(settings_parts)}")

        # Scheduler not running warning
        if not scheduler_ok:
            console.print()
            console.print("  [yellow]Run: nextdns-blocker watchdog install[/yellow]")

        # Detailed list (only with --list flag)
        if show_list:
            console.print()
            console.print("  [bold]Domains:[/bold]")
            for domain_config in domains:
                domain = domain_config["domain"]
                is_blocked = client.is_blocked(domain)
                status_icon = "\U0001f534" if is_blocked else "\U0001f7e2"

                domain_delay = domain_config.get("unblock_delay")
                if domain_delay == "never":
                    delay_flag = " [blue]\\[never][/blue]"
                elif domain_delay and domain_delay != "0":
                    delay_flag = f" [cyan]\\[{domain_delay}][/cyan]"
                else:
                    delay_flag = ""

                console.print(f"    {status_icon} {domain}{delay_flag}")

            if allowlist:
                console.print()
                console.print("  [bold]Allowlist:[/bold]")
                for item in allowlist:
                    domain = item["domain"]
                    is_allowed = client.is_allowed(domain)
                    has_schedule = item.get("schedule") is not None
                    status_icon = "[green]\u2713[/green]" if is_allowed else "[dim]\u25cb[/dim]"
                    schedule_flag = " [cyan]\\[scheduled][/cyan]" if has_schedule else ""
                    console.print(f"    {status_icon} {domain}{schedule_flag}")

        console.print()

    except ConfigurationError as e:
        console.print(f"\n  [red]Config error: {e}[/red]\n")
        sys.exit(1)


@click.command()
@click.option(
    "--config-dir",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Config directory (default: auto-detect)",
)
def health(config_dir: Optional[Path]) -> None:
    """Perform health checks."""
    checks_passed = 0
    checks_total = 0

    console.print("\n  [bold]Health Check[/bold]")
    console.print("  [bold]------------[/bold]")

    # Check config
    checks_total += 1
    try:
        config = load_config(config_dir)
        console.print("  [green][\u2713][/green] Configuration loaded")
        checks_passed += 1
    except ConfigurationError as e:
        console.print(f"  [red][\u2717][/red] Configuration: {e}")
        sys.exit(1)

    # Check domains (from database)
    checks_total += 1
    try:
        domains, allowlist = load_domains(config["script_dir"])
        console.print(
            f"  [green][\u2713][/green] Domains loaded ({len(domains)} domains, {len(allowlist)} allowlist)"
        )
        checks_passed += 1
    except ConfigurationError as e:
        console.print(f"  [red][\u2717][/red] Domains: {e}")
        sys.exit(1)

    # Check API connectivity
    checks_total += 1
    client = NextDNSClient(
        config["api_key"], config["profile_id"], config["timeout"], config["retries"]
    )
    denylist = client.get_denylist()
    if denylist is not None:
        console.print(
            f"  [green][\u2713][/green] API connectivity ({len(denylist)} items in denylist)"
        )
        checks_passed += 1
    else:
        console.print("  [red][\u2717][/red] API connectivity failed")

    # Check database
    checks_total += 1
    try:
        db_path = db.get_db_path()
        if db_path.exists():
            console.print(f"  [green][\u2713][/green] Database initialized ({db_path})")
            checks_passed += 1
        else:
            console.print("  [red][\u2717][/red] Database not initialized")
    except Exception as e:
        console.print(f"  [red][\u2717][/red] Database error: {e}")

    # Check log directory
    checks_total += 1
    try:
        ensure_log_dir()
        log_dir = get_log_dir()
        if log_dir.exists() and log_dir.is_dir():
            console.print(f"  [green][\u2713][/green] Log directory: {log_dir}")
            checks_passed += 1
        else:
            console.print("  [red][\u2717][/red] Log directory not accessible")
    except (OSError, PermissionError) as e:
        console.print(f"  [red][\u2717][/red] Log directory: {e}")

    # Summary
    console.print(f"\n  Result: {checks_passed}/{checks_total} checks passed")
    if checks_passed == checks_total:
        console.print("  Status: [green]HEALTHY[/green]\n")
    else:
        console.print("  Status: [red]DEGRADED[/red]\n")
        sys.exit(1)


def register_status(main_group: click.Group) -> None:
    """Register status and health commands with the main CLI group."""
    main_group.add_command(status)
    main_group.add_command(health)
