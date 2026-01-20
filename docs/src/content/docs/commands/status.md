---
title: status
description: Show current blocking status for all configured domains
---

The `status` command provides a comprehensive overview of the current state of NextDNS Blocker.

## Usage

```bash
nextdns-blocker status
```

## Output

```
NextDNS Blocker Status
━━━━━━━━━━━━━━━━━━━━━━

Time: 2024-01-15 14:30:00 America/New_York

Blocklist (3 domains):
  ✗ reddit.com        BLOCKED    (until 18:00)
  ✗ twitter.com       BLOCKED    (until 18:00)
  ✓ youtube.com       AVAILABLE  (until 22:00)

Allowlist (2 domains):
  ✓ aws.amazon.com    ALLOWED    (always)
  ✗ netflix.com       REMOVED    (until 20:00)

System:
  Watchdog: Active (next sync in 1m 23s)
  Panic Mode: Inactive
  Pending Actions: 1

Pending:
  pnd_20240115_143000_a1b2c3
    Domain: bumble.com
    Executes: 2024-01-15 15:00:00 (in 30 minutes)
```

## Status Indicators

### Domain Status

| Icon | Status | Meaning |
|------|--------|---------|
| ✗ | BLOCKED | Domain is in NextDNS denylist |
| ✓ | AVAILABLE | Domain is accessible |
| ✓ | ALLOWED | Domain is in NextDNS allowlist |
| ✗ | REMOVED | Domain removed from allowlist |

### Time Information

For blocked domains, shows when they'll become available:
- `(until 18:00)` - Will unblock at 6 PM
- `(always)` - No schedule, always blocked
- `(never)` - Protected domain

For available domains, shows when blocking resumes:
- `(until 22:00)` - Will block at 10 PM
- `(always)` - No schedule, never blocked

## System Status

### Watchdog

| Status | Meaning |
|--------|---------|
| Active | Scheduled sync is running |
| Inactive | No scheduled sync |
| Disabled | Temporarily disabled |

### Panic Mode

| Status | Meaning |
|--------|---------|
| Inactive | Normal operation |
| Active (Xm remaining) | Emergency lockdown active |

## Pending Actions

Shows queued unblock requests:
- Action ID
- Target domain
- Execution time
- Time remaining

## Combining with Other Commands

### Quick Status Check

```bash
# One-liner status
nextdns-blocker status | head -20
```

### Machine-Readable Output

While not directly supported, you can parse output:

```bash
# Check if specific domain is blocked
nextdns-blocker status | grep -q "reddit.com.*BLOCKED" && echo "Blocked"
```

### Watch Status

Monitor status in real-time:

```bash
watch -n 30 nextdns-blocker status
```

## Troubleshooting

### Status shows stale data

Force a fresh sync:

```bash
nextdns-blocker config push
nextdns-blocker status
```

### Watchdog shows inactive

Check and reinstall:

```bash
nextdns-blocker watchdog status
nextdns-blocker watchdog install
```

### Domain status doesn't match NextDNS dashboard

There might be a sync delay. Run:

```bash
nextdns-blocker config push --verbose
```

Check for API errors in the output.
