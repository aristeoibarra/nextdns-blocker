"""Sync implementation for NextDNS Blocker."""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

from .cli_formatter import console
from .client import NextDNSClient
from .common import audit_log
from .config import (
    load_config,
    load_domains,
    load_nextdns_config,
)
from .exceptions import ConfigurationError
from .notifications import (
    EventType,
    NotificationManager,
    get_notification_manager,
)
from .scheduler import ScheduleEvaluator

logger = logging.getLogger(__name__)


def _sync_denylist(
    domains: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize denylist domains based on schedules.

    SQLite is the single source of truth. This function:
    1. Syncs local domains to remote (add/remove based on schedule)
    2. Removes any remote domains not in local config

    Args:
        domains: List of domain configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (blocked_count, unblocked_count)
    """
    blocked_count = 0
    unblocked_count = 0

    # Build set of local domains for fast lookup
    local_domains = {d["domain"] for d in domains}

    # Sync local domains to remote
    for domain_config in domains:
        domain = domain_config["domain"]
        should_block = evaluator.should_block_domain(domain_config)
        is_blocked = client.is_blocked(domain)

        if should_block and not is_blocked:
            # Domain should be blocked but isn't
            if dry_run:
                console.print(f"  [yellow]Would BLOCK: {domain}[/yellow]")
            else:
                success, was_added = client.block(domain)
                if success and was_added:
                    audit_log("BLOCK", domain)
                    nm.queue(EventType.BLOCK, domain)
                    blocked_count += 1

        elif not should_block and is_blocked:
            # Domain should be unblocked
            unblocked = _handle_unblock(
                domain, domain_config, domains, client, config, dry_run, verbose, nm
            )
            if unblocked:
                unblocked_count += 1

    # Remove remote domains not in local config (SQLite is source of truth)
    remote_denylist = client.get_denylist() or []
    for remote_entry in remote_denylist:
        remote_domain = remote_entry.get("id", "")
        if not remote_domain or remote_domain in local_domains:
            continue
        if dry_run:
            console.print(f"  [red]Would REMOVE from remote: {remote_domain}[/red]")
        else:
            success, was_removed = client.unblock(remote_domain)
            if success and was_removed:
                audit_log("SYNC_CLEANUP", f"{remote_domain} reason=not_in_local")
                if verbose:
                    console.print(f"  [red]Removed from remote: {remote_domain}[/red]")
                unblocked_count += 1

    return blocked_count, unblocked_count


def _handle_unblock(
    domain: str,
    domain_config: dict[str, Any],
    domains: list[dict[str, Any]],
    client: "NextDNSClient",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    nm: "NotificationManager",
) -> bool:
    """
    Handle unblocking a domain with delay logic.

    Args:
        domain: Domain name to unblock
        domain_config: Domain configuration dict
        domains: All domain configurations (for delay lookup)
        client: NextDNS API client
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        nm: NotificationManager for queuing notifications

    Returns:
        True if domain was unblocked immediately, False otherwise
    """
    from .config import get_unblock_delay, parse_unblock_delay_seconds
    from .pending import create_pending_action, get_pending_for_domain

    # Check unblock_delay for this domain
    domain_delay = get_unblock_delay(domains, domain)

    # Handle 'never' - cannot unblock
    if domain_delay == "never":
        if verbose:
            console.print(f"  [blue]Cannot unblock (never): {domain}[/blue]")
        return False

    delay_seconds = parse_unblock_delay_seconds(domain_delay or "0")

    # Handle delayed unblock
    if delay_seconds and delay_seconds > 0 and domain_delay is not None:
        existing = get_pending_for_domain(domain)
        if existing:
            if verbose:
                console.print(f"  [yellow]Already pending: {domain}[/yellow]")
            return False

        if dry_run:
            console.print(
                f"  [yellow]Would schedule UNBLOCK: {domain} (delay: {domain_delay})[/yellow]"
            )
        else:
            action = create_pending_action(domain, domain_delay, requested_by="sync")
            if action and verbose:
                console.print(f"  [yellow]Scheduled unblock: {domain} ({domain_delay})[/yellow]")
        return False

    # Immediate unblock (no delay)
    if dry_run:
        console.print(f"  [green]Would UNBLOCK: {domain}[/green]")
        return False
    else:
        success, was_removed = client.unblock(domain)
        if success and was_removed:
            audit_log("UNBLOCK", domain)
            nm.queue(EventType.UNBLOCK, domain)
            return True
    return False


def _sync_allowlist(
    allowlist: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize allowlist domains based on schedules.

    SQLite is the single source of truth. This function:
    1. Syncs local allowlist to remote (add/remove based on schedule)
    2. Removes any remote allowlist entries not in local config

    Args:
        allowlist: List of allowlist configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration (for webhook URL)
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (allowed_count, disallowed_count)
    """
    allowed_count = 0
    disallowed_count = 0

    # Build set of local allowlist domains for fast lookup
    local_allowed_domains = {d["domain"] for d in allowlist}

    # Sync local allowlist to remote
    for allowlist_config in allowlist:
        domain = allowlist_config["domain"]
        should_allow = evaluator.should_allow_domain(allowlist_config)
        is_allowed = client.is_allowed(domain)

        if should_allow and not is_allowed:
            # Should be in allowlist but isn't - add it
            if dry_run:
                console.print(f"  [green]Would ADD to allowlist: {domain}[/green]")
            else:
                success, was_added = client.allow(domain)
                if success and was_added:
                    audit_log("ALLOW", domain)
                    nm.queue(EventType.ALLOW, domain)
                    allowed_count += 1

        elif not should_allow and is_allowed:
            # Should NOT be in allowlist but is - remove it
            if dry_run:
                console.print(f"  [yellow]Would REMOVE from allowlist: {domain}[/yellow]")
            else:
                success, was_removed = client.disallow(domain)
                if success and was_removed:
                    audit_log("DISALLOW", domain)
                    nm.queue(EventType.DISALLOW, domain)
                    disallowed_count += 1

    # Remove remote allowlist entries not in local config (SQLite is source of truth)
    remote_allowlist = client.get_allowlist() or []
    for remote_entry in remote_allowlist:
        remote_domain = remote_entry.get("id", "")
        if not remote_domain or remote_domain in local_allowed_domains:
            continue
        if dry_run:
            console.print(f"  [red]Would REMOVE from remote allowlist: {remote_domain}[/red]")
        else:
            success, was_removed = client.disallow(remote_domain)
            if success and was_removed:
                audit_log("SYNC_CLEANUP", f"{remote_domain} reason=not_in_local type=allowlist")
                if verbose:
                    console.print(f"  [red]Removed from remote allowlist: {remote_domain}[/red]")
                disallowed_count += 1

    return allowed_count, disallowed_count


def _sync_nextdns_categories(
    categories: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize NextDNS Parental Control categories based on schedules.

    SQLite is the single source of truth. This function:
    1. Syncs local categories to remote (activate/deactivate based on schedule)
    2. Deactivates any remote active categories not in local config

    When schedule says "available" (should_block=False) -> deactivate category
    When schedule says "blocked" (should_block=True) -> activate category

    Args:
        categories: List of NextDNS category configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (activated_count, deactivated_count)
    """
    activated_count = 0
    deactivated_count = 0

    # Build set of local category IDs for fast lookup
    local_category_ids = {c["id"] for c in categories}

    # Sync local categories to remote
    for category_config in categories:
        category_id = category_config["id"]
        should_block = evaluator.should_block(category_config.get("schedule"))
        is_active = client.is_category_active(category_id)

        # Handle API errors
        if is_active is None:
            if verbose:
                console.print(f"  [red]Failed to check category status: {category_id}[/red]")
            continue

        if should_block and not is_active:
            # Should be blocking but isn't - activate
            if dry_run:
                console.print(f"  [red]Would ACTIVATE category: {category_id}[/red]")
            else:
                if client.activate_category(category_id):
                    audit_log("PC_ACTIVATE", f"category:{category_id}")
                    nm.queue(EventType.PC_ACTIVATE, f"category:{category_id}")
                    activated_count += 1

        elif not should_block and is_active:
            # Should be available but is blocking - deactivate
            if dry_run:
                console.print(f"  [green]Would DEACTIVATE category: {category_id}[/green]")
            else:
                if client.deactivate_category(category_id):
                    audit_log("PC_DEACTIVATE", f"category:{category_id}")
                    nm.queue(EventType.PC_DEACTIVATE, f"category:{category_id}")
                    deactivated_count += 1

    # Deactivate remote active categories not in local config (SQLite is source of truth)
    remote_categories = client.get_parental_control_categories() or []
    for remote_cat in remote_categories:
        category_id = remote_cat.get("id", "")
        is_active = remote_cat.get("active", False)
        if not category_id or category_id in local_category_ids or not is_active:
            continue
        if dry_run:
            console.print(f"  [red]Would DEACTIVATE remote category: {category_id}[/red]")
        else:
            if client.deactivate_category(category_id):
                audit_log("SYNC_CLEANUP", f"category:{category_id} reason=not_in_local")
                if verbose:
                    console.print(f"  [red]Deactivated remote category: {category_id}[/red]")
                deactivated_count += 1

    return activated_count, deactivated_count


def _sync_nextdns_services(
    services: list[dict[str, Any]],
    client: "NextDNSClient",
    evaluator: "ScheduleEvaluator",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
    nm: "NotificationManager",
) -> tuple[int, int]:
    """
    Synchronize NextDNS Parental Control services based on schedules.

    SQLite is the single source of truth. This function:
    1. Syncs local services to remote (activate/deactivate based on schedule)
    2. Deactivates any remote active services not in local config

    When schedule says "available" (should_block=False) -> deactivate service
    When schedule says "blocked" (should_block=True) -> activate service

    Args:
        services: List of NextDNS service configurations
        client: NextDNS API client
        evaluator: Schedule evaluator
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output
        nm: NotificationManager for queuing notifications

    Returns:
        Tuple of (activated_count, deactivated_count)
    """
    activated_count = 0
    deactivated_count = 0

    # Build set of local service IDs for fast lookup
    local_service_ids = {s["id"] for s in services}

    # Sync local services to remote
    for service_config in services:
        service_id = service_config["id"]
        should_block = evaluator.should_block(service_config.get("schedule"))
        is_active = client.is_service_active(service_id)

        # Handle API errors
        if is_active is None:
            if verbose:
                console.print(f"  [red]Failed to check service status: {service_id}[/red]")
            continue

        if should_block and not is_active:
            # Should be blocking but isn't - activate
            if dry_run:
                console.print(f"  [red]Would ACTIVATE service: {service_id}[/red]")
            else:
                if client.activate_service(service_id):
                    audit_log("PC_ACTIVATE", f"service:{service_id}")
                    nm.queue(EventType.PC_ACTIVATE, f"service:{service_id}")
                    activated_count += 1

        elif not should_block and is_active:
            # Should be available but is blocking - deactivate
            if dry_run:
                console.print(f"  [green]Would DEACTIVATE service: {service_id}[/green]")
            else:
                if client.deactivate_service(service_id):
                    audit_log("PC_DEACTIVATE", f"service:{service_id}")
                    nm.queue(EventType.PC_DEACTIVATE, f"service:{service_id}")
                    deactivated_count += 1

    # Deactivate remote active services not in local config (SQLite is source of truth)
    remote_services = client.get_parental_control_services() or []
    for remote_svc in remote_services:
        service_id = remote_svc.get("id", "")
        is_active = remote_svc.get("active", False)
        if not service_id or service_id in local_service_ids or not is_active:
            continue
        if dry_run:
            console.print(f"  [red]Would DEACTIVATE remote service: {service_id}[/red]")
        else:
            if client.deactivate_service(service_id):
                audit_log("SYNC_CLEANUP", f"service:{service_id} reason=not_in_local")
                if verbose:
                    console.print(f"  [red]Deactivated remote service: {service_id}[/red]")
                deactivated_count += 1

    return activated_count, deactivated_count


def _sync_nextdns_parental_control(
    nextdns_config: dict[str, Any],
    client: "NextDNSClient",
    config: dict[str, Any],
    dry_run: bool,
    verbose: bool,
) -> bool:
    """
    Sync NextDNS Parental Control global settings.

    Args:
        nextdns_config: The 'nextdns' section from config
        client: NextDNS API client
        config: Application configuration
        dry_run: If True, only show what would be done
        verbose: If True, show detailed output

    Returns:
        True if sync was successful
    """
    parental_control = nextdns_config.get("parental_control")
    if not parental_control:
        return True

    safe_search = parental_control.get("safe_search")
    youtube_restricted = parental_control.get("youtube_restricted_mode")
    block_bypass = parental_control.get("block_bypass")

    # Get current state from NextDNS to compare
    current = client.get_parental_control()
    if current is None:
        logger.warning("Could not fetch current parental control state")
        return False

    # Build list of settings that need to change
    changes: list[str] = []
    if safe_search is not None and current.get("safeSearch") != safe_search:
        changes.append(f"safe_search={safe_search}")
    if (
        youtube_restricted is not None
        and current.get("youtubeRestrictedMode") != youtube_restricted
    ):
        changes.append(f"youtube_restricted_mode={youtube_restricted}")
    if block_bypass is not None and current.get("blockBypass") != block_bypass:
        changes.append(f"block_bypass={block_bypass}")

    if not changes:
        logger.debug("Parental control settings already in sync")
        return True

    if dry_run:
        console.print(f"  [yellow]Would UPDATE parental control: {', '.join(changes)}[/yellow]")
        return True

    if client.update_parental_control(
        safe_search=safe_search,
        youtube_restricted_mode=youtube_restricted,
        block_bypass=block_bypass,
    ):
        if verbose:
            console.print("  [green]Updated parental control settings[/green]")
        return True

    console.print("  [red]Failed to update parental control settings[/red]")
    return False


def _print_sync_summary(
    blocked_count: int,
    unblocked_count: int,
    allowed_count: int,
    disallowed_count: int,
    verbose: bool,
    pc_activated: int = 0,
    pc_deactivated: int = 0,
) -> None:
    """Print sync operation summary."""
    has_changes = (
        blocked_count
        or unblocked_count
        or allowed_count
        or disallowed_count
        or pc_activated
        or pc_deactivated
    )
    if has_changes:
        parts = []
        if blocked_count or unblocked_count:
            parts.append(
                f"[red]{blocked_count} blocked[/red], [green]{unblocked_count} unblocked[/green]"
            )
        if allowed_count or disallowed_count:
            parts.append(
                f"[green]{allowed_count} allowed[/green], [yellow]{disallowed_count} disallowed[/yellow]"
            )
        if pc_activated or pc_deactivated:
            parts.append(
                f"[magenta]{pc_activated} PC activated[/magenta], [cyan]{pc_deactivated} PC deactivated[/cyan]"
            )
        console.print(f"  Sync: {', '.join(parts)}")
    elif verbose:
        console.print("  Sync: [green]No changes needed[/green]")


def sync_impl(
    dry_run: bool,
    verbose: bool,
    config_dir: Optional[Path],
) -> None:
    """
    Synchronize domain blocking with schedules.

    This is the implementation function called by config_cli.py.
    """
    from .cli import setup_logging

    setup_logging(verbose)

    try:
        config = load_config(config_dir)
        domains, allowlist = load_domains(config["script_dir"])

        # Load NextDNS Parental Control config (optional)
        nextdns_config = load_nextdns_config(config["script_dir"])

        client = NextDNSClient(
            config["api_key"], config["profile_id"], config["timeout"], config["retries"]
        )
        evaluator = ScheduleEvaluator(config["timezone"])

        if dry_run:
            console.print("\n  [yellow]DRY RUN MODE - No changes will be made[/yellow]\n")

        # =========================================================================
        # SYNC ORDER: Denylist first, then Allowlist, then Parental Control
        #
        # This order matters because NextDNS processes allowlist with higher
        # priority. By syncing denylist first, we ensure blocks are applied
        # before exceptions. The allowlist sync then adds/removes exceptions.
        #
        # Priority in NextDNS (highest to lowest):
        # 1. Allowlist (always wins - bypasses everything)
        # 2. Denylist (your custom blocks)
        # 3. Third-party blocklists (OISD, HaGeZi, etc.)
        # 4. Security features (Threat Intelligence, NRDs, etc.)
        # 5. Parental Control (categories and services)
        # =========================================================================

        # Use NotificationManager context for batched notifications
        nm = get_notification_manager()
        with nm.sync_context(config["profile_id"], config):
            # Sync denylist domains
            blocked_count, unblocked_count = _sync_denylist(
                domains, client, evaluator, config, dry_run, verbose, nm
            )

            # Sync allowlist (schedule-aware)
            allowed_count, disallowed_count = _sync_allowlist(
                allowlist, client, evaluator, config, dry_run, verbose, nm
            )

            # Sync NextDNS Parental Control (if configured)
            pc_activated = 0
            pc_deactivated = 0
            if nextdns_config:
                # Sync global parental control settings
                _sync_nextdns_parental_control(nextdns_config, client, config, dry_run, verbose)

                # Sync categories
                nextdns_categories = nextdns_config.get("categories", [])
                if nextdns_categories:
                    cat_activated, cat_deactivated = _sync_nextdns_categories(
                        nextdns_categories,
                        client,
                        evaluator,
                        config,
                        dry_run,
                        verbose,
                        nm,
                    )
                    pc_activated += cat_activated
                    pc_deactivated += cat_deactivated

                # Sync services
                nextdns_services = nextdns_config.get("services", [])
                if nextdns_services:
                    svc_activated, svc_deactivated = _sync_nextdns_services(
                        nextdns_services,
                        client,
                        evaluator,
                        config,
                        dry_run,
                        verbose,
                        nm,
                    )
                    pc_activated += svc_activated
                    pc_deactivated += svc_deactivated

            # Print summary
            if not dry_run:
                _print_sync_summary(
                    blocked_count,
                    unblocked_count,
                    allowed_count,
                    disallowed_count,
                    verbose,
                    pc_activated,
                    pc_deactivated,
                )

    except ConfigurationError as e:
        console.print(f"  [red]Config error: {e}[/red]")
        sys.exit(1)
