"""Migration script to convert JSON files to SQLite database.

This script migrates existing data from JSON files to the new SQLite database.
It should be run once during the upgrade process.

Usage:
    python -m nextdns_blocker.migrate_to_sqlite
    nextdns-blocker db migrate  # After CLI integration
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir

from . import database as db
from .common import APP_NAME, get_log_dir
from .config import get_config_dir

logger = logging.getLogger(__name__)


# =============================================================================
# FILE PATHS
# =============================================================================


def get_config_json_path() -> Path:
    """Get the config.json file path.

    Searches in multiple locations:
    1. get_config_dir() (CWD if .env+config.json exist, else XDG)
    2. XDG config directory explicitly
    3. Current working directory
    """
    # Try standard config directory first
    config_dir_path = get_config_dir() / "config.json"
    if config_dir_path.exists():
        return config_dir_path

    # Try XDG config directory explicitly
    from platformdirs import user_config_dir

    xdg_path = Path(user_config_dir(APP_NAME)) / "config.json"
    if xdg_path.exists():
        return xdg_path

    # Try CWD
    cwd_path = Path.cwd() / "config.json"
    if cwd_path.exists():
        return cwd_path

    # Return standard path even if it doesn't exist
    return config_dir_path


def get_pending_json_path() -> Path:
    """Get the pending.json file path."""
    return Path(user_data_dir(APP_NAME)) / "pending.json"


def get_unlock_requests_json_path() -> Path:
    """Get the unlock_requests.json file path."""
    return get_log_dir() / "unlock_requests.json"


def get_retry_queue_json_path() -> Path:
    """Get the retry_queue.json file path."""
    return Path(user_data_dir(APP_NAME)) / "retry_queue.json"


def get_audit_log_path() -> Path:
    """Get the audit.log file path."""
    return get_log_dir() / "audit.log"


# =============================================================================
# MIGRATION FUNCTIONS
# =============================================================================


def load_json_file(path: Path) -> Optional[Any]:
    """Load a JSON file, returning None if it doesn't exist or is invalid."""
    if not path.exists():
        logger.info(f"File not found: {path}")
        return None

    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {path}: {e}")
        return None
    except OSError as e:
        logger.error(f"Failed to read {path}: {e}")
        return None


def migrate_config(config_data: dict[str, Any]) -> int:
    """
    Migrate config.json data to SQLite.

    Returns the number of items migrated.
    """
    count = 0

    # Migrate settings
    if "settings" in config_data:
        settings = config_data["settings"]
        db.set_config("settings", settings)
        count += 1

    # Migrate protection settings
    if "protection" in config_data:
        db.set_config("protection", config_data["protection"])
        count += 1

    # Migrate notifications
    if "notifications" in config_data:
        db.set_config("notifications", config_data["notifications"])
        count += 1

    # Migrate version
    if "version" in config_data:
        db.set_config("version", config_data["version"])
        count += 1

    # Migrate schedules
    if "schedules" in config_data:
        for name, schedule_data in config_data["schedules"].items():
            db.add_schedule(name, schedule_data)
            count += 1

    # Migrate blocklist
    if "blocklist" in config_data:
        for entry in config_data["blocklist"]:
            db.add_blocked_domain(
                domain=entry["domain"],
                description=entry.get("description"),
                locked=entry.get("locked", False),
                unblock_delay=entry.get("unblock_delay", "4h"),
                schedule=entry.get("schedule"),
            )
            count += 1

    # Migrate allowlist
    if "allowlist" in config_data:
        for entry in config_data["allowlist"]:
            db.add_allowed_domain(
                domain=entry["domain"],
                description=entry.get("description"),
                schedule=entry.get("schedule"),
                suppress_subdomain_warning=entry.get("suppress_subdomain_warning", False),
            )
            count += 1

    # Migrate user-defined categories
    if "categories" in config_data:
        for cat in config_data["categories"]:
            db.add_category(
                category_id=cat["id"],
                description=cat.get("description"),
                unblock_delay=cat.get("unblock_delay", "0"),
                schedule=cat.get("schedule"),
                locked=cat.get("locked", False),
                domains=cat.get("domains", []),
            )
            count += 1

    # Migrate NextDNS settings
    if "nextdns" in config_data:
        nextdns = config_data["nextdns"]

        # Migrate parental control settings
        if "parental_control" in nextdns:
            db.set_config("nextdns_parental_control", nextdns["parental_control"])
            count += 1

        # Migrate NextDNS categories
        if "categories" in nextdns:
            for cat in nextdns["categories"]:
                db.set_nextdns_category(
                    category_id=cat["id"],
                    description=cat.get("description"),
                    unblock_delay=cat.get("unblock_delay", "never"),
                    schedule=cat.get("schedule"),
                    locked=cat.get("locked", True),
                )
                count += 1

        # Migrate NextDNS services
        if "services" in nextdns:
            for svc in nextdns["services"]:
                db.set_nextdns_service(
                    service_id=svc["id"],
                    description=svc.get("description"),
                    unblock_delay=svc.get("unblock_delay", "0"),
                    schedule=svc.get("schedule"),
                    locked=svc.get("locked", False),
                )
                count += 1

    return count


def migrate_pending_actions(pending_data: dict[str, Any]) -> int:
    """
    Migrate pending.json data to SQLite.

    Returns the number of items migrated.
    """
    count = 0
    actions = pending_data.get("pending_actions", [])

    for action in actions:
        db.add_pending_action(
            action_id=action["id"],
            action=action.get("action", "unblock"),
            domain=action["domain"],
            created_at=action["created_at"],
            execute_at=action["execute_at"],
            delay=action.get("delay", "0"),
            requested_by=action.get("requested_by", "cli"),
        )

        # Update status if not pending
        status = action.get("status", "pending")
        if status != "pending":
            db.update_pending_action_status(action["id"], status, action.get("executed_at"))

        count += 1

    return count


def migrate_unlock_requests(requests: list[dict[str, Any]]) -> int:
    """
    Migrate unlock_requests.json data to SQLite.

    Returns the number of items migrated.
    """
    count = 0

    for req in requests:
        db.add_unlock_request(
            request_id=req["id"],
            item_type=req["item_type"],
            item_id=req["item_id"],
            created_at=req["created_at"],
            execute_at=req["execute_at"],
            delay_hours=req["delay_hours"],
            reason=req.get("reason"),
        )

        # Update status if not pending
        status = req.get("status", "pending")
        if status != "pending":
            db.update_unlock_request_status(req["id"], status, req.get("executed_at"))

        count += 1

    return count


def migrate_retry_queue(retry_data: dict[str, Any]) -> int:
    """
    Migrate retry_queue.json data to SQLite.

    Returns the number of items migrated.
    """
    count = 0
    entries = retry_data.get("retry_entries", [])

    for entry in entries:
        db.add_retry_entry(
            entry_id=entry["id"],
            domain=entry["domain"],
            action=entry["action"],
            error_type=entry.get("error_type", "unknown"),
            error_msg=entry.get("error_msg", ""),
            created_at=entry.get(
                "created_at", entry.get("first_attempt", datetime.now().isoformat())
            ),
            next_retry_at=entry.get("next_retry_at", datetime.now().isoformat()),
            attempt_count=entry.get("attempt_count", 1),
            backoff_seconds=entry.get("backoff_seconds", 60),
        )
        count += 1

    return count


def migrate_audit_log(audit_path: Path, max_lines: int = 10000) -> int:
    """
    Migrate audit.log to SQLite.

    Args:
        audit_path: Path to the audit.log file
        max_lines: Maximum number of lines to migrate (most recent)

    Returns the number of entries migrated.
    """
    if not audit_path.exists():
        logger.info(f"Audit log not found: {audit_path}")
        return 0

    count = 0

    # Regex pattern to parse audit log lines
    # Format: TIMESTAMP | [PREFIX] | ACTION | DETAIL
    # or: TIMESTAMP | ACTION | DETAIL
    pattern = re.compile(
        r"^(?P<timestamp>[\d\-T:.]+)\s*\|\s*"
        r"(?:(?P<prefix>[A-Z]+)\s*\|\s*)?"
        r"(?P<action>[A-Z_]+)\s*\|\s*"
        r"(?P<detail>.*)$"
    )

    try:
        with open(audit_path, encoding="utf-8") as f:
            lines = f.readlines()

        # Take only the last max_lines
        lines = lines[-max_lines:] if len(lines) > max_lines else lines

        for line in lines:
            line = line.strip()
            if not line:
                continue

            match = pattern.match(line)
            if match:
                timestamp = match.group("timestamp")
                prefix = match.group("prefix")
                action = match.group("action")
                detail = match.group("detail")

                # Combine prefix and action if prefix exists
                event_type = f"{prefix}_{action}" if prefix else action

                # Parse domain from detail if present
                domain = None
                metadata = {}

                # Common patterns: "domain.com" or "action_id domain.com key=value"
                detail_parts = detail.split()
                if detail_parts:
                    # First part is usually domain or ID
                    first_part = detail_parts[0]
                    if "." in first_part and not first_part.startswith("delay="):
                        domain = first_part
                    elif len(detail_parts) > 1 and "." in detail_parts[1]:
                        domain = detail_parts[1]
                        metadata["id"] = first_part

                    # Parse key=value pairs
                    for part in detail_parts:
                        if "=" in part:
                            key, value = part.split("=", 1)
                            metadata[key] = value

                db.add_audit_log(
                    event_type=event_type,
                    domain=domain,
                    metadata=metadata if metadata else None,
                    created_at=timestamp,
                )
                count += 1
            else:
                # Log line didn't match pattern - store as raw
                logger.debug(f"Unparsed audit line: {line[:100]}")

    except OSError as e:
        logger.error(f"Failed to read audit log: {e}")

    return count


# =============================================================================
# MAIN MIGRATION
# =============================================================================


def run_migration(
    dry_run: bool = False,
    skip_audit: bool = False,
    backup: bool = True,
) -> dict[str, int]:
    """
    Run the full migration from JSON to SQLite.

    Args:
        dry_run: If True, don't actually write to database
        skip_audit: If True, skip migrating audit.log (can be large)
        backup: If True, create backups of JSON files before migration

    Returns:
        Dictionary with counts of migrated items per category
    """
    results = {
        "config": 0,
        "pending_actions": 0,
        "unlock_requests": 0,
        "retry_queue": 0,
        "audit_log": 0,
    }

    if not dry_run:
        # Initialize database
        db.init_database()

    # Migrate config.json
    config_path = get_config_json_path()
    config_data = load_json_file(config_path)
    if config_data:
        if backup and not dry_run:
            _backup_file(config_path)
        if not dry_run:
            results["config"] = migrate_config(config_data)
        else:
            results["config"] = _count_config_items(config_data)
        logger.info(f"Migrated {results['config']} config items")

    # Migrate pending.json
    pending_path = get_pending_json_path()
    pending_data = load_json_file(pending_path)
    if pending_data:
        if backup and not dry_run:
            _backup_file(pending_path)
        if not dry_run:
            results["pending_actions"] = migrate_pending_actions(pending_data)
        else:
            results["pending_actions"] = len(pending_data.get("pending_actions", []))
        logger.info(f"Migrated {results['pending_actions']} pending actions")

    # Migrate unlock_requests.json
    unlock_path = get_unlock_requests_json_path()
    unlock_data = load_json_file(unlock_path)
    if unlock_data:
        if backup and not dry_run:
            _backup_file(unlock_path)
        # unlock_requests.json is a list, not a dict
        if isinstance(unlock_data, list):
            if not dry_run:
                results["unlock_requests"] = migrate_unlock_requests(unlock_data)
            else:
                results["unlock_requests"] = len(unlock_data)
        logger.info(f"Migrated {results['unlock_requests']} unlock requests")

    # Migrate retry_queue.json
    retry_path = get_retry_queue_json_path()
    retry_data = load_json_file(retry_path)
    if retry_data:
        if backup and not dry_run:
            _backup_file(retry_path)
        if not dry_run:
            results["retry_queue"] = migrate_retry_queue(retry_data)
        else:
            results["retry_queue"] = len(retry_data.get("retry_entries", []))
        logger.info(f"Migrated {results['retry_queue']} retry queue entries")

    # Migrate audit.log
    if not skip_audit:
        audit_path = get_audit_log_path()
        if audit_path.exists():
            if backup and not dry_run:
                _backup_file(audit_path)
            if not dry_run:
                results["audit_log"] = migrate_audit_log(audit_path)
            else:
                # Count lines for dry run
                try:
                    with open(audit_path) as f:
                        results["audit_log"] = sum(1 for _ in f)
                except OSError:
                    results["audit_log"] = 0
            logger.info(f"Migrated {results['audit_log']} audit log entries")

    return results


def _count_config_items(config_data: dict[str, Any]) -> int:
    """Count total items in config for dry run."""
    count = 0
    count += 1 if "settings" in config_data else 0
    count += 1 if "protection" in config_data else 0
    count += 1 if "notifications" in config_data else 0
    count += len(config_data.get("schedules", {}))
    count += len(config_data.get("blocklist", []))
    count += len(config_data.get("allowlist", []))
    count += len(config_data.get("categories", []))
    if "nextdns" in config_data:
        nextdns = config_data["nextdns"]
        count += 1 if "parental_control" in nextdns else 0
        count += len(nextdns.get("categories", []))
        count += len(nextdns.get("services", []))
    return count


def _backup_file(path: Path) -> Optional[Path]:
    """Create a backup of a file with .pre-sqlite suffix."""
    if not path.exists():
        return None

    backup_path = path.with_suffix(path.suffix + ".pre-sqlite")
    try:
        import shutil

        shutil.copy2(path, backup_path)
        logger.info(f"Backed up {path.name} to {backup_path.name}")
        return backup_path
    except OSError as e:
        logger.warning(f"Failed to backup {path}: {e}")
        return None


def check_migration_needed() -> bool:
    """Check if migration is needed (JSON files exist but DB is empty)."""
    # Check if any JSON files exist
    json_files = [
        get_config_json_path(),
        get_pending_json_path(),
        get_unlock_requests_json_path(),
        get_retry_queue_json_path(),
    ]

    json_exists = any(f.exists() for f in json_files)

    if not json_exists:
        return False

    # Check if database is empty
    if not db.database_exists():
        return True

    db.init_database()

    # Check if config table is empty
    config = db.get_all_config()
    if not config:
        return True

    return False


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> int:
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate NextDNS Blocker data from JSON to SQLite")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without making changes",
    )
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Skip migrating audit.log (can be large)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Don't create backups of JSON files",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
    )

    if args.dry_run:
        print("DRY RUN - No changes will be made\n")

    print(f"Database path: {db.get_db_path()}")
    print()

    results = run_migration(
        dry_run=args.dry_run,
        skip_audit=args.skip_audit,
        backup=not args.no_backup,
    )

    print("\n=== Migration Summary ===")
    print(f"Config items:      {results['config']}")
    print(f"Pending actions:   {results['pending_actions']}")
    print(f"Unlock requests:   {results['unlock_requests']}")
    print(f"Retry queue:       {results['retry_queue']}")
    print(f"Audit log entries: {results['audit_log']}")
    print()

    total = sum(results.values())
    if args.dry_run:
        print(f"Would migrate {total} total items")
    else:
        print(f"Successfully migrated {total} total items")
        print(f"\nDatabase size: {db.get_database_size():,} bytes")

    return 0


if __name__ == "__main__":
    sys.exit(main())
