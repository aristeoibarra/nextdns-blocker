-- Android remote blocking: tracks packages pushed to Firebase RTDB

CREATE TABLE android_package_mappings (
    domain       TEXT NOT NULL,
    package_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    auto         INTEGER NOT NULL DEFAULT 0,
    created_at   INTEGER NOT NULL,
    PRIMARY KEY (domain, package_name)
) STRICT;

CREATE INDEX idx_android_pkg_domain ON android_package_mappings (domain);

CREATE TABLE remote_android_blocked (
    package_name   TEXT PRIMARY KEY,
    domain         TEXT NOT NULL,
    device_id      TEXT NOT NULL,
    blocked_at     INTEGER NOT NULL,
    unblock_at     INTEGER,
    in_firebase    INTEGER NOT NULL DEFAULT 0,
    push_error     TEXT
) STRICT;

CREATE INDEX idx_android_blocked_domain ON remote_android_blocked (domain);
CREATE INDEX idx_android_blocked_pending ON remote_android_blocked (in_firebase) WHERE in_firebase = 0;
