-- Add source column to audit_log for tracking who/what triggered each action.
-- Values: cli, schedule, watchdog, preflight, pending, retry, system
ALTER TABLE audit_log ADD COLUMN source TEXT NOT NULL DEFAULT 'cli';
CREATE INDEX idx_audit_source ON audit_log(source);
