-- Schema V1: nextdns-blocker-rs
-- All tables use STRICT mode (SQLite 3.37+)
-- Timestamps are Unix epoch integers

-- Schema migrations tracking
CREATE TABLE IF NOT EXISTS schema_migrations (
    version  INTEGER PRIMARY KEY,
    name     TEXT NOT NULL,
    applied_at INTEGER NOT NULL
) STRICT;

-- Blocked domains (denylist)
CREATE TABLE IF NOT EXISTS blocked_domains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL UNIQUE,
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    description TEXT,
    category    TEXT,
    schedule    TEXT,  -- JSON schedule or NULL
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_blocked_domains_domain ON blocked_domains(domain);
CREATE INDEX IF NOT EXISTS idx_blocked_domains_category ON blocked_domains(category);
CREATE INDEX IF NOT EXISTS idx_blocked_domains_active ON blocked_domains(active);

-- Allowed domains (allowlist)
CREATE TABLE IF NOT EXISTS allowed_domains (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain      TEXT NOT NULL UNIQUE,
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    description TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_allowed_domains_domain ON allowed_domains(domain);

-- Categories (user-defined domain groups)
CREATE TABLE IF NOT EXISTS categories (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    schedule    TEXT,  -- JSON schedule or NULL
    is_locked   INTEGER NOT NULL DEFAULT 0 CHECK (is_locked IN (0, 1)),
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
) STRICT;

-- Category-domain mapping
CREATE TABLE IF NOT EXISTS category_domains (
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    domain      TEXT NOT NULL,
    created_at  INTEGER NOT NULL,
    PRIMARY KEY (category_id, domain)
) STRICT;

-- NextDNS native categories (parental control)
CREATE TABLE IF NOT EXISTS nextdns_categories (
    id         TEXT PRIMARY KEY,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at INTEGER NOT NULL
) STRICT;

-- NextDNS native services
CREATE TABLE IF NOT EXISTS nextdns_services (
    id         TEXT PRIMARY KEY,
    active     INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    created_at INTEGER NOT NULL
) STRICT;

-- Pending actions (scheduled domain operations)
CREATE TABLE IF NOT EXISTS pending_actions (
    id           TEXT PRIMARY KEY,
    action       TEXT NOT NULL CHECK (action IN ('add', 'remove')),
    domain       TEXT,
    list_type    TEXT NOT NULL CHECK (list_type IN ('denylist', 'allowlist', 'category', 'service')),
    scheduled_at INTEGER NOT NULL,
    execute_at   INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'executing', 'completed', 'cancelled', 'failed')),
    description  TEXT,
    created_at   INTEGER NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_pending_status ON pending_actions(status);
CREATE INDEX IF NOT EXISTS idx_pending_execute_at ON pending_actions(execute_at);

-- Retry queue (failed API operations)
CREATE TABLE IF NOT EXISTS retry_queue (
    id           TEXT PRIMARY KEY,
    action       TEXT NOT NULL,
    domain       TEXT,
    list_type    TEXT NOT NULL,
    payload      TEXT,  -- JSON payload
    attempts     INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    last_error   TEXT,
    next_retry_at INTEGER NOT NULL,
    created_at   INTEGER NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_retry_next ON retry_queue(next_retry_at);
CREATE INDEX IF NOT EXISTS idx_retry_domain_action ON retry_queue(domain, action);

-- Unlock requests (for protected items)
CREATE TABLE IF NOT EXISTS unlock_requests (
    id           TEXT PRIMARY KEY,
    target_type  TEXT NOT NULL CHECK (target_type IN ('domain', 'category', 'service')),
    target_id    TEXT NOT NULL,
    reason       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'denied', 'expired')),
    requested_at INTEGER NOT NULL,
    resolved_at  INTEGER
) STRICT;

CREATE INDEX IF NOT EXISTS idx_unlock_status ON unlock_requests(status);

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    details     TEXT,  -- JSON details
    timestamp   INTEGER NOT NULL
) STRICT;

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);

-- Daily statistics
CREATE TABLE IF NOT EXISTS daily_stats (
    date            TEXT PRIMARY KEY,  -- YYYY-MM-DD
    domains_blocked INTEGER NOT NULL DEFAULT 0,
    domains_allowed INTEGER NOT NULL DEFAULT 0,
    sync_count      INTEGER NOT NULL DEFAULT 0,
    api_errors      INTEGER NOT NULL DEFAULT 0
) STRICT;

-- PIN storage
CREATE TABLE IF NOT EXISTS pin_config (
    id           INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    pin_hash     TEXT NOT NULL,
    created_at   INTEGER NOT NULL,
    updated_at   INTEGER NOT NULL
) STRICT;

-- PIN sessions
CREATE TABLE IF NOT EXISTS pin_sessions (
    id         TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL,
    expires_at INTEGER NOT NULL
) STRICT;

-- PIN lockout tracking
CREATE TABLE IF NOT EXISTS pin_lockout (
    id              INTEGER PRIMARY KEY CHECK (id = 1),  -- singleton row
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until    INTEGER,
    last_attempt_at INTEGER
) STRICT;

-- Key-value config store (for runtime settings)
CREATE TABLE IF NOT EXISTS kv_config (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at INTEGER NOT NULL
) STRICT;
