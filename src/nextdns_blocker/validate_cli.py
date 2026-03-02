"""Validate implementation for NextDNS Blocker."""

import json as json_module
import sys
from pathlib import Path
from typing import Any, Optional

from . import database as db
from .cli_formatter import console
from .config import (
    _expand_categories,
    get_config_dir,
    validate_allowlist_config,
    validate_domain_config,
    validate_no_overlap,
)


def validate_impl(output_json: bool, config_dir: Optional[Path]) -> None:
    """
    Validate configuration before deployment.

    This is the implementation function called by config_cli.py.

    Validates config:
    - Valid domain formats
    - Valid schedule time formats (HH:MM)
    - No denylist/allowlist conflicts
    """
    # Determine config directory
    if config_dir is None:
        config_dir = get_config_dir()

    results: dict[str, Any] = {
        "valid": True,
        "checks": [],
        "errors": [],
        "warnings": [],
        "summary": {},
    }

    def add_check(name: str, passed: bool, detail: str = "") -> None:
        results["checks"].append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            results["valid"] = False

    def add_error(message: str) -> None:
        results["errors"].append(message)
        results["valid"] = False

    def add_warning(message: str) -> None:
        results["warnings"].append(message)

    # Check 1: database has configuration
    domains_data = None
    if db.config_has_domains():
        try:
            domains_data = db.get_full_config_dict()
            add_check("database", True, "config loaded")
        except Exception as e:
            add_check("database", False, str(e))
            add_error(f"Failed to load config from database: {e}")
    else:
        add_check("database", False, "no configuration")
        add_error("No configuration in database. Run 'nextdns-blocker init' to create one.")

    if domains_data is None:
        # Cannot proceed without valid domains data
        if output_json:
            console.print(json_module.dumps(results, indent=2))
        else:
            console.print("\n  [red]Configuration validation failed[/red]")
            for error in results["errors"]:
                console.print(f"  [red]\u2717[/red] {error}")
            console.print()
        sys.exit(1)

    # Check 2: Validate structure
    if not isinstance(domains_data, dict):
        add_error("Configuration must be a JSON object")
    elif "blocklist" not in domains_data:
        add_error("Missing 'blocklist' array in configuration")

    domains_list: list[dict[str, Any]] = []
    allowlist_list: list[dict[str, Any]] = []
    categories_list: list[dict[str, Any]] = []
    schedules_dict: dict[str, Any] = {}
    if isinstance(domains_data, dict):
        domains_list = domains_data.get("blocklist", [])
        allowlist_list = domains_data.get("allowlist", [])
        categories_list = domains_data.get("categories", [])
        schedules_dict = domains_data.get("schedules", {})

    # Get valid schedule template names for reference validation
    valid_schedule_names: set[str] = (
        set(schedules_dict.keys()) if isinstance(schedules_dict, dict) else set()
    )

    # Expand categories to get individual domain entries
    expanded_category_domains = _expand_categories(categories_list)
    total_domains = len(domains_list) + len(expanded_category_domains)
    categories_count = len(categories_list)

    # Update summary
    results["summary"]["domains_count"] = total_domains
    results["summary"]["allowlist_count"] = len(allowlist_list)

    # Check 3: Count and validate domains
    if total_domains > 0:
        if categories_count > 0:
            add_check(
                "domains configured",
                True,
                f"{total_domains} domains ({len(domains_list)} blocklist + {len(expanded_category_domains)} from {categories_count} categories)",
            )
        else:
            add_check("domains configured", True, f"{total_domains} domains")
    else:
        add_check("domains configured", False, "no domains found")

    # Check 4: Count allowlist entries
    if allowlist_list:
        add_check("allowlist entries", True, f"{len(allowlist_list)} entries")

    # Combine blocklist and expanded category domains for validation
    all_blocked_domains = domains_list + expanded_category_domains

    # Check 5: Count protected domains (unblock_delay="never")
    protected_domains = [d for d in all_blocked_domains if d.get("unblock_delay") == "never"]
    results["summary"]["protected_count"] = len(protected_domains)
    if protected_domains:
        add_check("protected domains", True, f"{len(protected_domains)} protected")

    # Check 6: Validate each domain configuration
    domain_errors: list[str] = []
    schedule_count = 0

    for idx, domain_config in enumerate(all_blocked_domains):
        errors = validate_domain_config(domain_config, idx, valid_schedule_names)
        domain_errors.extend(errors)
        if domain_config.get("schedule"):
            schedule_count += 1

    results["summary"]["schedules_count"] = schedule_count

    # Check 7: Validate allowlist entries
    for idx, allowlist_config in enumerate(allowlist_list):
        errors = validate_allowlist_config(allowlist_config, idx, valid_schedule_names)
        domain_errors.extend(errors)

    if domain_errors:
        add_check("domain formats", False, f"{len(domain_errors)} error(s)")
        for error in domain_errors:
            add_error(error)
    else:
        add_check("domain formats", True, "all valid")

    # Check 8: Validate schedules
    if schedule_count > 0:
        # Schedule validation is done as part of validate_domain_config
        # If we got here without errors, schedules are valid
        if not domain_errors:
            add_check("schedules", True, f"{schedule_count} schedule(s) valid")

    # Check 9: Check for denylist/allowlist conflicts
    overlap_errors = validate_no_overlap(domains_list, allowlist_list)
    if overlap_errors:
        add_check("no conflicts", False, f"{len(overlap_errors)} conflict(s)")
        for error in overlap_errors:
            add_error(error)
    else:
        add_check("no conflicts", True, "no denylist/allowlist conflicts")

    # Output results
    if output_json:
        console.print(json_module.dumps(results, indent=2))
    else:
        console.print()
        for check in results["checks"]:
            if check["passed"]:
                console.print(f"  [green]\u2713[/green] {check['name']}: {check['detail']}")
            else:
                console.print(f"  [red]\u2717[/red] {check['name']}: {check['detail']}")

        if results["errors"]:
            console.print(f"\n  [red]Configuration has {len(results['errors'])} error(s)[/red]")
            for error in results["errors"]:
                console.print(f"    \u2022 {error}")
        else:
            console.print("\n  [green]Configuration OK[/green]")

        console.print()

    sys.exit(0 if results["valid"] else 1)
