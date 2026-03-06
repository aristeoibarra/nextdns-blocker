-- App blocking: domain-to-app mappings and blocked app state tracking

CREATE TABLE app_mappings (
    domain      TEXT NOT NULL,
    bundle_id   TEXT NOT NULL,
    app_name    TEXT NOT NULL,
    auto        INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL,
    PRIMARY KEY (domain, bundle_id)
) STRICT;

CREATE INDEX idx_app_mappings_bundle ON app_mappings (bundle_id);

CREATE TABLE blocked_apps (
    bundle_id      TEXT PRIMARY KEY,
    app_name       TEXT NOT NULL,
    original_path  TEXT NOT NULL,
    blocked_path   TEXT NOT NULL,
    source_domain  TEXT,
    blocked_at     INTEGER NOT NULL
) STRICT;
