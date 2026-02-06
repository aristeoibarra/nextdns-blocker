"""SQLite database module for NextDNS Blocker.

This module provides a centralized database layer replacing the previous
JSON file storage. It offers ACID guarantees, proper concurrency handling,
and efficient querying capabilities.

Database location: ~/.local/share/nextdns-blocker/nextdns-blocker.db
"""

import contextlib
import json
import logging
import sqlite3
import threading
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from platformdirs import user_data_dir

from .common import APP_NAME

logger = logging.getLogger(__name__)

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

DB_FILENAME = "nextdns-blocker.db"

# Thread-local storage for connections
_local = threading.local()


def get_db_path() -> Path:
    """Get the database file path."""
    return Path(user_data_dir(APP_NAME)) / DB_FILENAME


# =============================================================================
# DATABASE SCHEMA
# =============================================================================

SCHEMA_SQL = """
-- Configuration as key-value with JSON support
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,  -- JSON for complex values
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Blocked domains
CREATE TABLE IF NOT EXISTS blocked_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    description TEXT,
    locked INTEGER DEFAULT 0,  -- SQLite doesn't have BOOLEAN, use 0/1
    unblock_delay TEXT DEFAULT '4h',
    schedule TEXT,  -- JSON or schedule reference name
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Allowed domains
CREATE TABLE IF NOT EXISTS allowed_domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    description TEXT,
    schedule TEXT,  -- JSON or schedule reference name
    suppress_subdomain_warning INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- User-defined categories (domain groups)
CREATE TABLE IF NOT EXISTS categories (
    id TEXT PRIMARY KEY,
    description TEXT,
    unblock_delay TEXT DEFAULT '0',
    schedule TEXT,  -- JSON or schedule reference name
    locked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Category domains (many-to-many)
CREATE TABLE IF NOT EXISTS category_domains (
    category_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (category_id, domain),
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- NextDNS native categories configuration
CREATE TABLE IF NOT EXISTS nextdns_categories (
    id TEXT PRIMARY KEY,  -- porn, gambling, dating, etc.
    description TEXT,
    unblock_delay TEXT DEFAULT 'never',
    schedule TEXT,
    locked INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- NextDNS native services configuration
CREATE TABLE IF NOT EXISTS nextdns_services (
    id TEXT PRIMARY KEY,  -- amazon, facebook, twitter, etc.
    description TEXT,
    unblock_delay TEXT DEFAULT '0',
    schedule TEXT,
    locked INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Schedule templates
CREATE TABLE IF NOT EXISTS schedules (
    name TEXT PRIMARY KEY,
    schedule_data TEXT NOT NULL,  -- JSON: {available_hours: [...], blocked_hours: [...]}
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Pending actions
CREATE TABLE IF NOT EXISTS pending_actions (
    id TEXT PRIMARY KEY,  -- pnd_{YYYYMMDD}_{HHMMSS}_{random}
    action TEXT NOT NULL,  -- unblock, block, allow, disallow
    domain TEXT NOT NULL,
    created_at TEXT NOT NULL,
    execute_at TEXT NOT NULL,
    delay TEXT NOT NULL,  -- Original delay string (4h, 24h, etc.)
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, executed, cancelled
    requested_by TEXT DEFAULT 'cli',
    executed_at TEXT,
    cancelled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_pending_execute_at ON pending_actions(execute_at);

-- Unlock requests
CREATE TABLE IF NOT EXISTS unlock_requests (
    id TEXT PRIMARY KEY,
    item_type TEXT NOT NULL,  -- category, service, domain, pin
    item_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    execute_at TEXT NOT NULL,
    delay_hours INTEGER NOT NULL,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending, executed, cancelled, expired
    executed_at TEXT,
    cancelled_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_unlock_status ON unlock_requests(status);
CREATE INDEX IF NOT EXISTS idx_unlock_execute_at ON unlock_requests(execute_at);

-- Retry queue
CREATE TABLE IF NOT EXISTS retry_queue (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    action TEXT NOT NULL,  -- block, unblock, allow, disallow
    error_type TEXT NOT NULL,
    error_msg TEXT,
    attempt_count INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    next_retry_at TEXT NOT NULL,
    backoff_seconds INTEGER DEFAULT 60
);

CREATE INDEX IF NOT EXISTS idx_retry_next ON retry_queue(next_retry_at);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    domain TEXT,
    metadata TEXT,  -- JSON for additional context
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_date ON audit_log(created_at);

-- Daily stats aggregation
CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,  -- YYYY-MM-DD
    blocks INTEGER DEFAULT 0,
    unblocks INTEGER DEFAULT 0,
    panic_activations INTEGER DEFAULT 0,
    focus_sessions INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- PIN protection
CREATE TABLE IF NOT EXISTS pin_protection (
    key TEXT PRIMARY KEY,  -- 'hash', 'session_expires', 'failed_attempts'
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


# =============================================================================
# CONNECTION MANAGEMENT
# =============================================================================


def get_connection() -> sqlite3.Connection:
    """
    Get a thread-local database connection.

    Returns a connection with WAL mode enabled for better concurrent access.
    Each thread gets its own connection to avoid threading issues.
    """
    if not hasattr(_local, "connection") or _local.connection is None:
        db_path = get_db_path()
        db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Enable dict-like row access

        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys=ON")
        # Optimize for performance
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

        _local.connection = conn

    return _local.connection  # type: ignore[no-any-return]


def close_connection() -> None:
    """Close the thread-local database connection."""
    if hasattr(_local, "connection") and _local.connection is not None:
        _local.connection.close()
        _local.connection = None


@contextlib.contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """
    Context manager for database transactions.

    Usage:
        with transaction() as conn:
            conn.execute("INSERT INTO ...")
            conn.execute("UPDATE ...")
        # Automatically commits on success, rolls back on exception
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# =============================================================================
# SCHEMA MANAGEMENT
# =============================================================================


def init_database() -> None:
    """Initialize the database schema.

    Uses CREATE TABLE IF NOT EXISTS, so it's safe to call multiple times.
    New tables are added automatically. For column changes, delete the DB.
    """
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    logger.debug("Database schema initialized")

    # Auto-vacuum if needed
    try:
        auto_vacuum_if_needed()
    except Exception as e:
        logger.warning("Auto-vacuum check failed: %s", e)


# =============================================================================
# CONFIG OPERATIONS
# =============================================================================


def get_config(key: str, default: Any = None) -> Any:
    """Get a configuration value by key."""
    conn = get_connection()
    cursor = conn.execute("SELECT value FROM config WHERE key = ?", (key,))
    row = cursor.fetchone()
    if row is None:
        return default
    try:
        return json.loads(row["value"])
    except (json.JSONDecodeError, TypeError):
        return row["value"]


def set_config(key: str, value: Any) -> None:
    """Set a configuration value."""
    conn = get_connection()
    json_value = json.dumps(value) if not isinstance(value, str) else value
    conn.execute(
        """
        INSERT INTO config (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
        """,
        (key, json_value),
    )
    conn.commit()


def get_all_config() -> dict[str, Any]:
    """Get all configuration values as a dictionary."""
    conn = get_connection()
    cursor = conn.execute("SELECT key, value FROM config")
    result = {}
    for row in cursor:
        try:
            result[row["key"]] = json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            result[row["key"]] = row["value"]
    return result


def delete_config(key: str) -> bool:
    """Delete a configuration value. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM config WHERE key = ?", (key,))
    conn.commit()
    return cursor.rowcount > 0


# =============================================================================
# BLOCKED DOMAINS OPERATIONS
# =============================================================================


def add_blocked_domain(
    domain: str,
    description: Optional[str] = None,
    locked: bool = False,
    unblock_delay: str = "4h",
    schedule: Optional[Union[str, dict[str, Any]]] = None,
) -> int:
    """Add a domain to the blocklist. Returns the row ID."""
    conn = get_connection()
    schedule_json = json.dumps(schedule) if isinstance(schedule, dict) else schedule
    cursor = conn.execute(
        """
        INSERT INTO blocked_domains (domain, description, locked, unblock_delay, schedule)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            locked = excluded.locked,
            unblock_delay = excluded.unblock_delay,
            schedule = excluded.schedule,
            updated_at = datetime('now')
        """,
        (domain, description, int(locked), unblock_delay, schedule_json),
    )
    conn.commit()
    return cursor.lastrowid or 0


def remove_blocked_domain(domain: str) -> bool:
    """Remove a domain from the blocklist. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM blocked_domains WHERE domain = ?", (domain,))
    conn.commit()
    return cursor.rowcount > 0


def get_blocked_domain(domain: str) -> Optional[dict[str, Any]]:
    """Get a blocked domain by name."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM blocked_domains WHERE domain = ?", (domain,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_all_blocked_domains() -> list[dict[str, Any]]:
    """Get all blocked domains."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM blocked_domains ORDER BY domain")
    return [dict(row) for row in cursor]


def is_domain_blocked(domain: str) -> bool:
    """Check if a domain is in the blocklist."""
    conn = get_connection()
    cursor = conn.execute("SELECT 1 FROM blocked_domains WHERE domain = ? LIMIT 1", (domain,))
    return cursor.fetchone() is not None


# =============================================================================
# ALLOWED DOMAINS OPERATIONS
# =============================================================================


def add_allowed_domain(
    domain: str,
    description: Optional[str] = None,
    schedule: Optional[Union[str, dict[str, Any]]] = None,
    suppress_subdomain_warning: bool = False,
) -> int:
    """Add a domain to the allowlist. Returns the row ID."""
    conn = get_connection()
    schedule_json = json.dumps(schedule) if isinstance(schedule, dict) else schedule
    cursor = conn.execute(
        """
        INSERT INTO allowed_domains (domain, description, schedule, suppress_subdomain_warning)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(domain) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            schedule = excluded.schedule,
            suppress_subdomain_warning = excluded.suppress_subdomain_warning,
            updated_at = datetime('now')
        """,
        (domain, description, schedule_json, int(suppress_subdomain_warning)),
    )
    conn.commit()
    return cursor.lastrowid or 0


def remove_allowed_domain(domain: str) -> bool:
    """Remove a domain from the allowlist. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM allowed_domains WHERE domain = ?", (domain,))
    conn.commit()
    return cursor.rowcount > 0


def get_allowed_domain(domain: str) -> Optional[dict[str, Any]]:
    """Get an allowed domain by name."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM allowed_domains WHERE domain = ?", (domain,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_all_allowed_domains() -> list[dict[str, Any]]:
    """Get all allowed domains."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM allowed_domains ORDER BY domain")
    return [dict(row) for row in cursor]


def is_domain_allowed(domain: str) -> bool:
    """Check if a domain is in the allowlist."""
    conn = get_connection()
    cursor = conn.execute("SELECT 1 FROM allowed_domains WHERE domain = ? LIMIT 1", (domain,))
    return cursor.fetchone() is not None


# =============================================================================
# CATEGORY OPERATIONS
# =============================================================================


def add_category(
    category_id: str,
    description: Optional[str] = None,
    unblock_delay: str = "0",
    schedule: Optional[Union[str, dict[str, Any]]] = None,
    locked: bool = False,
    domains: Optional[list[str]] = None,
) -> None:
    """Add or update a user-defined category."""
    schedule_json = json.dumps(schedule) if isinstance(schedule, dict) else schedule

    with transaction() as conn:
        conn.execute(
            """
            INSERT INTO categories (id, description, unblock_delay, schedule, locked)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                description = COALESCE(excluded.description, description),
                unblock_delay = excluded.unblock_delay,
                schedule = excluded.schedule,
                locked = excluded.locked,
                updated_at = datetime('now')
            """,
            (category_id, description, unblock_delay, schedule_json, int(locked)),
        )

        if domains is not None:
            # Replace all domains for this category
            conn.execute("DELETE FROM category_domains WHERE category_id = ?", (category_id,))
            for domain in domains:
                conn.execute(
                    "INSERT INTO category_domains (category_id, domain) VALUES (?, ?)",
                    (category_id, domain),
                )


def remove_category(category_id: str) -> bool:
    """Remove a category. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
    conn.commit()
    return cursor.rowcount > 0


def get_category(category_id: str) -> Optional[dict[str, Any]]:
    """Get a category with its domains."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM categories WHERE id = ?", (category_id,))
    row = cursor.fetchone()
    if row is None:
        return None

    result = dict(row)
    # Get associated domains
    cursor = conn.execute(
        "SELECT domain FROM category_domains WHERE category_id = ? ORDER BY domain",
        (category_id,),
    )
    result["domains"] = [r["domain"] for r in cursor]
    return result


def get_all_categories() -> list[dict[str, Any]]:
    """Get all categories with their domains."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM categories ORDER BY id")
    categories = []
    for row in cursor:
        cat = dict(row)
        domain_cursor = conn.execute(
            "SELECT domain FROM category_domains WHERE category_id = ? ORDER BY domain",
            (cat["id"],),
        )
        cat["domains"] = [r["domain"] for r in domain_cursor]
        categories.append(cat)
    return categories


def add_domain_to_category(category_id: str, domain: str) -> bool:
    """Add a domain to a category. Returns True if added."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO category_domains (category_id, domain) VALUES (?, ?)",
            (category_id, domain),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_domain_from_category(category_id: str, domain: str) -> bool:
    """Remove a domain from a category. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute(
        "DELETE FROM category_domains WHERE category_id = ? AND domain = ?",
        (category_id, domain),
    )
    conn.commit()
    return cursor.rowcount > 0


# =============================================================================
# PENDING ACTIONS OPERATIONS
# =============================================================================


def add_pending_action(
    action_id: str,
    action: str,
    domain: str,
    created_at: str,
    execute_at: str,
    delay: str,
    requested_by: str = "cli",
) -> None:
    """Add a pending action."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO pending_actions (id, action, domain, created_at, execute_at, delay, requested_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (action_id, action, domain, created_at, execute_at, delay, requested_by),
    )
    conn.commit()


def get_pending_action(action_id: str) -> Optional[dict[str, Any]]:
    """Get a pending action by ID."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM pending_actions WHERE id = ?", (action_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_pending_actions(status: str = "pending") -> list[dict[str, Any]]:
    """Get all pending actions with a given status."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM pending_actions WHERE status = ? ORDER BY execute_at",
        (status,),
    )
    return [dict(row) for row in cursor]


def get_executable_pending_actions(before: Optional[str] = None) -> list[dict[str, Any]]:
    """Get pending actions ready to be executed."""
    conn = get_connection()
    if before is None:
        before = datetime.now().isoformat()
    cursor = conn.execute(
        """
        SELECT * FROM pending_actions
        WHERE status = 'pending' AND execute_at <= ?
        ORDER BY execute_at
        """,
        (before,),
    )
    return [dict(row) for row in cursor]


def update_pending_action_status(
    action_id: str, status: str, executed_at: Optional[str] = None
) -> bool:
    """Update the status of a pending action."""
    conn = get_connection()
    if status == "executed":
        executed_at = executed_at or datetime.now().isoformat()
        cursor = conn.execute(
            "UPDATE pending_actions SET status = ?, executed_at = ? WHERE id = ?",
            (status, executed_at, action_id),
        )
    elif status == "cancelled":
        cursor = conn.execute(
            "UPDATE pending_actions SET status = ?, cancelled_at = datetime('now') WHERE id = ?",
            (status, action_id),
        )
    else:
        cursor = conn.execute(
            "UPDATE pending_actions SET status = ? WHERE id = ?",
            (status, action_id),
        )
    conn.commit()
    return cursor.rowcount > 0


def cancel_pending_action(action_id: str) -> bool:
    """Cancel a pending action."""
    return update_pending_action_status(action_id, "cancelled")


# =============================================================================
# UNLOCK REQUESTS OPERATIONS
# =============================================================================


def add_unlock_request(
    request_id: str,
    item_type: str,
    item_id: str,
    created_at: str,
    execute_at: str,
    delay_hours: int,
    reason: Optional[str] = None,
) -> None:
    """Add an unlock request."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO unlock_requests
            (id, item_type, item_id, created_at, execute_at, delay_hours, reason)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (request_id, item_type, item_id, created_at, execute_at, delay_hours, reason),
    )
    conn.commit()


def get_unlock_request(request_id: str) -> Optional[dict[str, Any]]:
    """Get an unlock request by ID."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM unlock_requests WHERE id = ?", (request_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_unlock_requests(status: str = "pending") -> list[dict[str, Any]]:
    """Get all unlock requests with a given status."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM unlock_requests WHERE status = ? ORDER BY execute_at",
        (status,),
    )
    return [dict(row) for row in cursor]


def get_executable_unlock_requests(before: Optional[str] = None) -> list[dict[str, Any]]:
    """Get unlock requests ready to be executed."""
    conn = get_connection()
    if before is None:
        before = datetime.now().isoformat()
    cursor = conn.execute(
        """
        SELECT * FROM unlock_requests
        WHERE status = 'pending' AND execute_at <= ?
        ORDER BY execute_at
        """,
        (before,),
    )
    return [dict(row) for row in cursor]


def update_unlock_request_status(
    request_id: str, status: str, executed_at: Optional[str] = None
) -> bool:
    """Update the status of an unlock request."""
    conn = get_connection()
    if status == "executed":
        executed_at = executed_at or datetime.now().isoformat()
        cursor = conn.execute(
            "UPDATE unlock_requests SET status = ?, executed_at = ? WHERE id = ?",
            (status, executed_at, request_id),
        )
    elif status == "cancelled":
        cursor = conn.execute(
            "UPDATE unlock_requests SET status = ?, cancelled_at = datetime('now') WHERE id = ?",
            (status, request_id),
        )
    else:
        cursor = conn.execute(
            "UPDATE unlock_requests SET status = ? WHERE id = ?",
            (status, request_id),
        )
    conn.commit()
    return cursor.rowcount > 0


# =============================================================================
# RETRY QUEUE OPERATIONS
# =============================================================================


def add_retry_entry(
    entry_id: str,
    domain: str,
    action: str,
    error_type: str,
    error_msg: str,
    created_at: str,
    next_retry_at: str,
    attempt_count: int = 1,
    backoff_seconds: int = 60,
) -> None:
    """Add an entry to the retry queue."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO retry_queue
            (id, domain, action, error_type, error_msg, attempt_count, created_at, next_retry_at, backoff_seconds)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            attempt_count = excluded.attempt_count,
            next_retry_at = excluded.next_retry_at,
            backoff_seconds = excluded.backoff_seconds
        """,
        (
            entry_id,
            domain,
            action,
            error_type,
            error_msg,
            attempt_count,
            created_at,
            next_retry_at,
            backoff_seconds,
        ),
    )
    conn.commit()


def get_retry_entry(entry_id: str) -> Optional[dict[str, Any]]:
    """Get a retry queue entry by ID."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM retry_queue WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_retryable_entries(before: Optional[str] = None) -> list[dict[str, Any]]:
    """Get retry entries ready to be retried."""
    conn = get_connection()
    if before is None:
        before = datetime.now().isoformat()
    cursor = conn.execute(
        "SELECT * FROM retry_queue WHERE next_retry_at <= ? ORDER BY next_retry_at",
        (before,),
    )
    return [dict(row) for row in cursor]


def remove_retry_entry(entry_id: str) -> bool:
    """Remove an entry from the retry queue."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM retry_queue WHERE id = ?", (entry_id,))
    conn.commit()
    return cursor.rowcount > 0


def clear_retry_queue() -> int:
    """Clear all entries from the retry queue. Returns count of removed entries."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM retry_queue")
    conn.commit()
    return cursor.rowcount


# =============================================================================
# AUDIT LOG OPERATIONS
# =============================================================================


def add_audit_log(
    event_type: str,
    domain: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
    created_at: Optional[str] = None,
) -> int:
    """Add an entry to the audit log. Returns the row ID."""
    conn = get_connection()
    metadata_json = json.dumps(metadata) if metadata else None
    if created_at:
        cursor = conn.execute(
            "INSERT INTO audit_log (event_type, domain, metadata, created_at) VALUES (?, ?, ?, ?)",
            (event_type, domain, metadata_json, created_at),
        )
    else:
        cursor = conn.execute(
            "INSERT INTO audit_log (event_type, domain, metadata) VALUES (?, ?, ?)",
            (event_type, domain, metadata_json),
        )
    conn.commit()
    return cursor.lastrowid or 0


def get_audit_logs(
    event_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Get audit log entries with optional filtering."""
    conn = get_connection()

    query = "SELECT * FROM audit_log WHERE 1=1"
    params: list[Any] = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)

    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date)

    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor = conn.execute(query, params)
    results = []
    for row in cursor:
        entry = dict(row)
        if entry.get("metadata"):
            with contextlib.suppress(json.JSONDecodeError):
                entry["metadata"] = json.loads(entry["metadata"])
        results.append(entry)
    return results


def count_audit_logs(
    event_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> int:
    """Count audit log entries with optional filtering."""
    conn = get_connection()

    query = "SELECT COUNT(*) FROM audit_log WHERE 1=1"
    params: list[Any] = []

    if event_type:
        query += " AND event_type = ?"
        params.append(event_type)

    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)

    if end_date:
        query += " AND created_at <= ?"
        params.append(end_date)

    cursor = conn.execute(query, params)
    result = cursor.fetchone()
    return int(result[0]) if result else 0


# =============================================================================
# DAILY STATS OPERATIONS
# =============================================================================


def increment_daily_stat(date: str, stat_name: str, amount: int = 1) -> None:
    """Increment a daily statistic."""
    conn = get_connection()
    # Valid stat names
    valid_stats = {"blocks", "unblocks", "panic_activations", "focus_sessions"}
    if stat_name not in valid_stats:
        raise ValueError(f"Invalid stat name: {stat_name}")

    conn.execute(
        f"""
        INSERT INTO daily_stats (date, {stat_name}, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(date) DO UPDATE SET
            {stat_name} = {stat_name} + ?,
            updated_at = datetime('now')
        """,  # nosec B608 - stat_name is validated against whitelist above
        (date, amount, amount),
    )
    conn.commit()


def get_daily_stats(date: str) -> Optional[dict[str, Any]]:
    """Get statistics for a specific date."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM daily_stats WHERE date = ?", (date,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_stats_range(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Get statistics for a date range."""
    conn = get_connection()
    cursor = conn.execute(
        "SELECT * FROM daily_stats WHERE date >= ? AND date <= ? ORDER BY date",
        (start_date, end_date),
    )
    return [dict(row) for row in cursor]


# =============================================================================
# NEXTDNS CATEGORIES/SERVICES OPERATIONS
# =============================================================================


def set_nextdns_category(
    category_id: str,
    description: Optional[str] = None,
    unblock_delay: str = "never",
    schedule: Optional[Union[str, dict[str, Any]]] = None,
    locked: bool = True,
) -> None:
    """Set a NextDNS native category configuration."""
    conn = get_connection()
    schedule_json = json.dumps(schedule) if isinstance(schedule, dict) else schedule
    conn.execute(
        """
        INSERT INTO nextdns_categories (id, description, unblock_delay, schedule, locked)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            unblock_delay = excluded.unblock_delay,
            schedule = excluded.schedule,
            locked = excluded.locked,
            updated_at = datetime('now')
        """,
        (category_id, description, unblock_delay, schedule_json, int(locked)),
    )
    conn.commit()


def get_nextdns_category(category_id: str) -> Optional[dict[str, Any]]:
    """Get a NextDNS native category configuration."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM nextdns_categories WHERE id = ?", (category_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_all_nextdns_categories() -> list[dict[str, Any]]:
    """Get all NextDNS native category configurations."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM nextdns_categories ORDER BY id")
    return [dict(row) for row in cursor]


def set_nextdns_service(
    service_id: str,
    description: Optional[str] = None,
    unblock_delay: str = "0",
    schedule: Optional[Union[str, dict[str, Any]]] = None,
    locked: bool = False,
) -> None:
    """Set a NextDNS native service configuration."""
    conn = get_connection()
    schedule_json = json.dumps(schedule) if isinstance(schedule, dict) else schedule
    conn.execute(
        """
        INSERT INTO nextdns_services (id, description, unblock_delay, schedule, locked)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            description = COALESCE(excluded.description, description),
            unblock_delay = excluded.unblock_delay,
            schedule = excluded.schedule,
            locked = excluded.locked,
            updated_at = datetime('now')
        """,
        (service_id, description, unblock_delay, schedule_json, int(locked)),
    )
    conn.commit()


def get_nextdns_service(service_id: str) -> Optional[dict[str, Any]]:
    """Get a NextDNS native service configuration."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM nextdns_services WHERE id = ?", (service_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_all_nextdns_services() -> list[dict[str, Any]]:
    """Get all NextDNS native service configurations."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM nextdns_services ORDER BY id")
    return [dict(row) for row in cursor]


def remove_nextdns_category(category_id: str) -> bool:
    """Remove a NextDNS native category. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM nextdns_categories WHERE id = ?", (category_id,))
    conn.commit()
    return cursor.rowcount > 0


def remove_nextdns_service(service_id: str) -> bool:
    """Remove a NextDNS native service. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM nextdns_services WHERE id = ?", (service_id,))
    conn.commit()
    return cursor.rowcount > 0


# =============================================================================
# SCHEDULES OPERATIONS
# =============================================================================


def add_schedule(name: str, schedule_data: dict[str, Any]) -> None:
    """Add or update a schedule template."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO schedules (name, schedule_data)
        VALUES (?, ?)
        ON CONFLICT(name) DO UPDATE SET
            schedule_data = excluded.schedule_data,
            updated_at = datetime('now')
        """,
        (name, json.dumps(schedule_data)),
    )
    conn.commit()


def get_schedule(name: str) -> Optional[dict[str, Any]]:
    """Get a schedule template by name."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM schedules WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row is None:
        return None
    result = dict(row)
    with contextlib.suppress(json.JSONDecodeError):
        result["schedule_data"] = json.loads(result["schedule_data"])
    return result


def get_all_schedules() -> dict[str, dict[str, Any]]:
    """Get all schedule templates as a dictionary keyed by name."""
    conn = get_connection()
    cursor = conn.execute("SELECT * FROM schedules ORDER BY name")
    result = {}
    for row in cursor:
        entry = dict(row)
        with contextlib.suppress(json.JSONDecodeError):
            entry["schedule_data"] = json.loads(entry["schedule_data"])
        result[entry["name"]] = entry["schedule_data"]
    return result


def remove_schedule(name: str) -> bool:
    """Remove a schedule template. Returns True if removed."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM schedules WHERE name = ?", (name,))
    conn.commit()
    return cursor.rowcount > 0


# =============================================================================
# PIN PROTECTION OPERATIONS
# =============================================================================


def get_pin_value(key: str) -> Optional[str]:
    """Get a PIN protection value by key (hash, session_expires, failed_attempts)."""
    conn = get_connection()
    cursor = conn.execute("SELECT value FROM pin_protection WHERE key = ?", (key,))
    row = cursor.fetchone()
    return row["value"] if row else None


def set_pin_value(key: str, value: str) -> None:
    """Set a PIN protection value."""
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO pin_protection (key, value, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = excluded.value,
            updated_at = datetime('now')
        """,
        (key, value),
    )
    conn.commit()


def delete_pin_value(key: str) -> bool:
    """Delete a PIN protection value. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM pin_protection WHERE key = ?", (key,))
    conn.commit()
    return cursor.rowcount > 0


def clear_all_pin_data() -> None:
    """Clear all PIN protection data (hash, session, attempts)."""
    conn = get_connection()
    conn.execute("DELETE FROM pin_protection")
    conn.commit()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def execute_query(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Execute a raw SQL query and return results as a list of dicts."""
    conn = get_connection()
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor]


def database_exists() -> bool:
    """Check if the database file exists."""
    return get_db_path().exists()


def get_database_size() -> int:
    """Get the database file size in bytes."""
    path = get_db_path()
    return path.stat().st_size if path.exists() else 0


def vacuum_database() -> None:
    """Vacuum the database to reclaim space and record timestamp."""
    conn = get_connection()
    conn.execute("VACUUM")
    conn.execute("""
        INSERT INTO config (key, value, updated_at)
        VALUES ('last_vacuum', datetime('now'), datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value = datetime('now'),
            updated_at = datetime('now')
        """)
    conn.commit()
    logger.info("Database vacuumed")


AUTO_VACUUM_INTERVAL_DAYS = 30


def auto_vacuum_if_needed() -> None:
    """Run VACUUM if it hasn't been done in AUTO_VACUUM_INTERVAL_DAYS days."""
    conn = get_connection()
    cursor = conn.execute("SELECT value FROM config WHERE key = 'last_vacuum'")
    row = cursor.fetchone()
    if row is None:
        vacuum_database()
        return
    try:
        last_vacuum = datetime.fromisoformat(row["value"])
        if (datetime.now() - last_vacuum).days >= AUTO_VACUUM_INTERVAL_DAYS:
            vacuum_database()
    except (ValueError, TypeError):
        vacuum_database()


def backup_database(backup_dir: Optional[Path] = None, max_backups: int = 3) -> Path:
    """Create a backup of the database using sqlite3 backup API.

    Args:
        backup_dir: Directory for backups. Defaults to db parent dir / backups.
        max_backups: Maximum number of backup files to retain.

    Returns:
        Path to the created backup file.
    """
    import sqlite3 as _sqlite3

    db_path = get_db_path()
    if backup_dir is None:
        backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"nextdns-blocker_{timestamp}.db"

    src = _sqlite3.connect(str(db_path))
    try:
        dst = _sqlite3.connect(str(backup_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    logger.info("Database backed up to %s", backup_path)

    # Rotate old backups
    backups = sorted(backup_dir.glob("nextdns-blocker_*.db"))
    while len(backups) > max_backups:
        oldest = backups.pop(0)
        oldest.unlink()
        logger.info("Removed old backup: %s", oldest)

    return backup_path


def auto_backup() -> None:
    """Create a backup before destructive operations."""
    try:
        if get_db_path().exists():
            backup_database()
    except Exception as e:
        logger.warning("Auto-backup failed: %s", e)


def export_to_json() -> dict[str, Any]:
    """Export the entire database to a JSON-compatible dictionary."""
    return {
        "config": get_all_config(),
        "blocked_domains": get_all_blocked_domains(),
        "allowed_domains": get_all_allowed_domains(),
        "categories": get_all_categories(),
        "nextdns_categories": get_all_nextdns_categories(),
        "nextdns_services": get_all_nextdns_services(),
        "schedules": get_all_schedules(),
        "pending_actions": get_pending_actions("pending"),
        "unlock_requests": get_unlock_requests("pending"),
    }


def get_full_config_dict() -> dict[str, Any]:
    """
    Build the full configuration as a single dict (same shape as exported config JSON).
    Used by config edit, validate, and sync pull/push.
    """
    schedules = get_all_schedules()
    blocklist = []
    for r in get_all_blocked_domains():
        s = r.get("schedule")
        if isinstance(s, str) and s.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                s = json.loads(s)
        blocklist.append(
            {
                "domain": r["domain"],
                "description": r.get("description"),
                "locked": bool(r.get("locked", 0)),
                "unblock_delay": r.get("unblock_delay") or "4h",
                "schedule": s,
            }
        )
    allowlist = []
    for r in get_all_allowed_domains():
        s = r.get("schedule")
        if isinstance(s, str) and s.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                s = json.loads(s)
        allowlist.append(
            {
                "domain": r["domain"],
                "description": r.get("description"),
                "schedule": s,
                "suppress_subdomain_warning": bool(r.get("suppress_subdomain_warning", 0)),
            }
        )
    categories = []
    for r in get_all_categories():
        s = r.get("schedule")
        if isinstance(s, str) and s.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                s = json.loads(s)
        categories.append(
            {
                "id": r["id"],
                "description": r.get("description"),
                "unblock_delay": r.get("unblock_delay") or "0",
                "schedule": s,
                "locked": bool(r.get("locked", 0)),
                "domains": r.get("domains", []),
            }
        )
    nextdns_cats = []
    for r in get_all_nextdns_categories():
        s = r.get("schedule")
        if isinstance(s, str) and s.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                s = json.loads(s)
        nextdns_cats.append(
            {
                "id": r["id"],
                "description": r.get("description"),
                "unblock_delay": r.get("unblock_delay") or "never",
                "schedule": s,
                "locked": bool(r.get("locked", 1)),
            }
        )
    nextdns_svcs = []
    for r in get_all_nextdns_services():
        s = r.get("schedule")
        if isinstance(s, str) and s.strip().startswith("{"):
            with contextlib.suppress(json.JSONDecodeError):
                s = json.loads(s)
        nextdns_svcs.append(
            {
                "id": r["id"],
                "description": r.get("description"),
                "unblock_delay": r.get("unblock_delay") or "0",
                "schedule": s,
                "locked": bool(r.get("locked", 0)),
            }
        )
    return {
        "version": get_config("version") or "1.0",
        "settings": get_config("settings") or {},
        "protection": get_config("protection") or {},
        "notifications": get_config("notifications") or {},
        "schedules": schedules,
        "nextdns": {
            "parental_control": get_config("parental_control") or {},
            "categories": nextdns_cats,
            "services": nextdns_svcs,
        },
        "categories": categories,
        "blocklist": blocklist,
        "allowlist": allowlist,
    }


def save_full_config_dict(config: dict[str, Any]) -> None:
    """
    Replace database content with the given full config dict (same shape as exported config).
    Clears existing domain/schedule/nextdns data and repopulates.
    """
    conn = get_connection()
    conn.execute("DELETE FROM blocked_domains")
    conn.execute("DELETE FROM allowed_domains")
    conn.execute("DELETE FROM category_domains")
    conn.execute("DELETE FROM categories")
    conn.execute("DELETE FROM nextdns_categories")
    conn.execute("DELETE FROM nextdns_services")
    conn.execute("DELETE FROM schedules")
    conn.commit()

    set_config("version", config.get("version", "1.0"))
    set_config("settings", config.get("settings") or {})
    set_config("notifications", config.get("notifications") or {})
    set_config("protection", config.get("protection") or {})
    set_config("parental_control", (config.get("nextdns") or {}).get("parental_control") or {})

    for name, schedule_data in (config.get("schedules") or {}).items():
        if isinstance(schedule_data, dict):
            add_schedule(name, schedule_data)

    nextdns = config.get("nextdns") or {}
    for c in nextdns.get("categories") or []:
        sid = c.get("id")
        if not sid:
            continue
        sched = c.get("schedule")
        if isinstance(sched, dict):
            sched = json.dumps(sched)
        set_nextdns_category(
            sid,
            c.get("description"),
            c.get("unblock_delay", "never"),
            sched,
            c.get("locked", True),
        )
    for s in nextdns.get("services") or []:
        sid = s.get("id")
        if not sid:
            continue
        sched = s.get("schedule")
        if isinstance(sched, dict):
            sched = json.dumps(sched)
        set_nextdns_service(
            sid,
            s.get("description"),
            s.get("unblock_delay", "0"),
            sched,
            s.get("locked", False),
        )
    for cat in config.get("categories") or []:
        cid = cat.get("id")
        if not cid:
            continue
        add_category(
            cid,
            cat.get("description"),
            cat.get("unblock_delay", "0"),
            cat.get("schedule"),
            cat.get("locked", False),
            cat.get("domains") or [],
        )
    for b in config.get("blocklist") or []:
        domain = b.get("domain")
        if not domain:
            continue
        sched = b.get("schedule")
        add_blocked_domain(
            domain,
            b.get("description"),
            b.get("locked", False),
            b.get("unblock_delay", "4h"),
            sched,
        )
    for a in config.get("allowlist") or []:
        domain = a.get("domain")
        if not domain:
            continue
        add_allowed_domain(
            domain,
            a.get("description"),
            a.get("schedule"),
            a.get("suppress_subdomain_warning", False),
        )
    set_config("migrated", True)


def config_has_domains() -> bool:
    """Return True if the database has domain config (blocklist, categories, or allowlist)."""
    if get_config("migrated") is not None:
        return True
    conn = get_connection()
    for table, _col in (
        ("blocked_domains", "domain"),
        ("categories", "id"),
        ("allowed_domains", "domain"),
    ):
        cursor = conn.execute(f"SELECT 1 FROM {table} LIMIT 1")  # nosec B608
        if cursor.fetchone() is not None:
            return True
    return False


def import_config_from_json(path: Path) -> None:
    """
    One-time import from a JSON config file into the database.

    Populates config key-value, blocked_domains, allowed_domains, categories,
    schedules, nextdns_categories, nextdns_services. Sets config key 'migrated' when done.
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("Config must be a JSON object")

    set_config("version", data.get("version", "1.0"))
    set_config("settings", data.get("settings") or {})
    set_config("notifications", data.get("notifications") or {})
    set_config("protection", data.get("protection") or {})
    nextdns = data.get("nextdns") or {}
    set_config("parental_control", nextdns.get("parental_control") or {})

    for name, schedule_data in (data.get("schedules") or {}).items():
        if isinstance(schedule_data, dict):
            add_schedule(name, schedule_data)

    for c in nextdns.get("categories") or []:
        sid = c.get("id")
        if not sid:
            continue
        sched = c.get("schedule")
        if isinstance(sched, dict):
            sched = json.dumps(sched)
        set_nextdns_category(
            sid,
            c.get("description"),
            c.get("unblock_delay", "never"),
            sched,
            c.get("locked", True),
        )

    for s in nextdns.get("services") or []:
        sid = s.get("id")
        if not sid:
            continue
        sched = s.get("schedule")
        if isinstance(sched, dict):
            sched = json.dumps(sched)
        set_nextdns_service(
            sid,
            s.get("description"),
            s.get("unblock_delay", "0"),
            sched,
            s.get("locked", False),
        )

    for cat in data.get("categories") or []:
        cid = cat.get("id")
        if not cid:
            continue
        sched = cat.get("schedule")
        add_category(
            cid,
            cat.get("description"),
            cat.get("unblock_delay", "0"),
            sched,
            cat.get("locked", False),
            cat.get("domains") or [],
        )

    for b in data.get("blocklist") or []:
        domain = b.get("domain")
        if not domain:
            continue
        sched = b.get("schedule")
        add_blocked_domain(
            domain,
            b.get("description"),
            b.get("locked", False),
            b.get("unblock_delay", "4h"),
            sched,
        )

    for a in data.get("allowlist") or []:
        domain = a.get("domain")
        if not domain:
            continue
        add_allowed_domain(
            domain,
            a.get("description"),
            a.get("schedule"),
            a.get("suppress_subdomain_warning", False),
        )

    set_config("migrated", True)
