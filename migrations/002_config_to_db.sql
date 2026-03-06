-- Migration V2: Move config.json settings into kv_config table
-- Default values match previous ParentalControl defaults

INSERT OR IGNORE INTO kv_config (key, value, updated_at)
VALUES
    ('timezone', 'UTC', strftime('%s', 'now')),
    ('safe_search', 'true', strftime('%s', 'now')),
    ('youtube_restricted_mode', 'false', strftime('%s', 'now')),
    ('block_bypass', 'true', strftime('%s', 'now'));
