CREATE INDEX IF NOT EXISTS idx_category_domains_domain ON category_domains(domain);
CREATE INDEX IF NOT EXISTS idx_hosts_entries_source ON hosts_entries(source_domain);
