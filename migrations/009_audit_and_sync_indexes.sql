-- Indexes for schedule-based queries (sync performance)
CREATE INDEX IF NOT EXISTS idx_blocked_domains_schedule ON blocked_domains(schedule) WHERE schedule IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_allowed_domains_schedule ON allowed_domains(schedule) WHERE schedule IS NOT NULL;

-- Indexes for in_nextdns sync state queries
CREATE INDEX IF NOT EXISTS idx_blocked_domains_in_nextdns ON blocked_domains(in_nextdns);
CREATE INDEX IF NOT EXISTS idx_allowed_domains_in_nextdns ON allowed_domains(in_nextdns);

-- Index for audit log target_id lookups (e.g., "show all audit for domain X")
CREATE INDEX IF NOT EXISTS idx_audit_target_id ON audit_log(target_id);
