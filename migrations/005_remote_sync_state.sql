-- Track whether each domain is currently active in the NextDNS API.
-- Set to 1 when a domain is confirmed pushed to NextDNS, 0 when removed or never pushed.
-- Allows the watchdog schedule sync to skip GET requests entirely on most cycles.
ALTER TABLE blocked_domains ADD COLUMN in_nextdns INTEGER NOT NULL DEFAULT 0;
ALTER TABLE allowed_domains ADD COLUMN in_nextdns INTEGER NOT NULL DEFAULT 0;
