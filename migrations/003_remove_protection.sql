-- Remove protection-related tables and columns
DROP TABLE IF EXISTS pin_config;
DROP TABLE IF EXISTS pin_sessions;
DROP TABLE IF EXISTS pin_lockout;
DROP TABLE IF EXISTS unlock_requests;

-- Remove is_locked column from categories
-- SQLite doesn't support DROP COLUMN before 3.35, so recreate the table
CREATE TABLE IF NOT EXISTS categories_new (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,
    description TEXT,
    schedule    TEXT,
    created_at  INTEGER NOT NULL,
    updated_at  INTEGER NOT NULL
) STRICT;

INSERT INTO categories_new (id, name, description, schedule, created_at, updated_at)
    SELECT id, name, description, schedule, created_at, updated_at FROM categories;

DROP TABLE categories;
ALTER TABLE categories_new RENAME TO categories;
