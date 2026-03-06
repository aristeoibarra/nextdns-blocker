CREATE TABLE hosts_entries (
    domain        TEXT PRIMARY KEY,
    ip            TEXT NOT NULL DEFAULT '0.0.0.0',
    source_domain TEXT,
    added_at      INTEGER NOT NULL
) STRICT;
