---
title: Log Files
description: Understanding NextDNS Blocker log files and rotation
---

NextDNS Blocker maintains several log files for monitoring, debugging, and auditing.

## Log Location

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.local/share/nextdns-blocker/logs/` |
| Windows | `%LOCALAPPDATA%\nextdns-blocker\logs\` |

## Log Files

### app.log

**Purpose**: General application events

**Contents**:
- Startup/shutdown
- Configuration loading
- Errors and warnings
- Debug information (when verbose)

**Example**:
```
2024-01-15 14:30:00 INFO Starting sync
2024-01-15 14:30:01 INFO Loaded 5 domains from blocklist
2024-01-15 14:30:02 INFO Blocked reddit.com (outside schedule)
2024-01-15 14:30:02 INFO Sync complete: 1 blocked, 0 unblocked
```

**Rotation**: Daily, 7 days retention

### audit.log

**Purpose**: Security-relevant actions

**Contents**:
- Domain blocks
- Domain unblocks
- Panic mode activation
- Pending action creation/cancellation
- Allowlist changes

**Example**:
```
2024-01-15 14:30:00 BLOCK reddit.com reason="outside schedule"
2024-01-15 18:00:00 UNBLOCK reddit.com reason="within schedule"
2024-01-15 20:00:00 PANIC_START duration=60 expires="2024-01-15 21:00:00"
2024-01-15 21:00:00 PANIC_END
```

**Rotation**: Weekly, 12 weeks retention

### cron.log

**Purpose**: Watchdog sync execution output

**Contents**:
- Output from scheduled sync runs
- Errors from cron/launchd/Task Scheduler
- Timestamps of each run

**Example**:
```
=== 2024-01-15 14:30:00 ===
Syncing domains...
  reddit.com: BLOCKED
Sync complete: 1 blocked, 0 unblocked

=== 2024-01-15 14:32:00 ===
Syncing domains...
Sync complete: 0 blocked, 0 unblocked
```

**Rotation**: Daily, 7 days retention

### wd.log

**Purpose**: Watchdog self-check events

**Contents**:
- Watchdog status checks
- Job restoration events
- Self-healing activity

**Example**:
```
2024-01-15 14:35:00 CHECK Sync job exists: yes
2024-01-15 14:40:00 CHECK Sync job exists: yes
2024-01-15 14:45:00 RESTORE Sync job was missing, restored
```

**Rotation**: Daily, 7 days retention

### sync.log

**Purpose**: Detailed sync operation logs

**Contents**:
- API calls made
- Cache hits/misses
- Schedule evaluations
- Domain state changes

**Rotation**: Daily, 7 days retention

## Viewing Logs

### Recent Entries

```bash
# macOS/Linux
tail -50 ~/.local/share/nextdns-blocker/logs/app.log

# Windows PowerShell
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\app.log" -Tail 50
```

### Follow in Real-Time

```bash
# macOS/Linux
tail -f ~/.local/share/nextdns-blocker/logs/app.log

# Windows PowerShell
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\app.log" -Wait
```

### Search Logs

```bash
# Find all blocks
grep BLOCK ~/.local/share/nextdns-blocker/logs/audit.log

# Find errors
grep ERROR ~/.local/share/nextdns-blocker/logs/app.log

# Find specific domain
grep reddit.com ~/.local/share/nextdns-blocker/logs/*.log
```

## Log Levels

| Level | Description |
|-------|-------------|
| DEBUG | Detailed debugging (verbose mode) |
| INFO | Normal operation |
| WARNING | Potential issues |
| ERROR | Errors that affect operation |
| CRITICAL | Severe errors |

### Enable Debug Logging

```bash
nextdns-blocker config push --verbose
```

## Log Rotation

### Built-in Rotation

NextDNS Blocker uses Python's `RotatingFileHandler`:
- Rotates when file exceeds size limit
- Keeps specified number of backups

### Manual Rotation Setup

For system-level rotation, use logrotate (Linux):

```bash
# /etc/logrotate.d/nextdns-blocker
/home/*/.local/share/nextdns-blocker/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644
}
```

Run setup script:
```bash
chmod +x setup-logrotate.sh
./setup-logrotate.sh
```

## Log Analysis

### Count Actions

```bash
# Count blocks today
grep "$(date +%Y-%m-%d)" ~/.local/share/nextdns-blocker/logs/audit.log | grep -c BLOCK

# Count unblocks this week
grep UNBLOCK ~/.local/share/nextdns-blocker/logs/audit.log | wc -l
```

### Find Patterns

```bash
# Most blocked domains
grep BLOCK ~/.local/share/nextdns-blocker/logs/audit.log | \
  awk '{print $3}' | sort | uniq -c | sort -rn | head -10

# Panic mode usage
grep PANIC ~/.local/share/nextdns-blocker/logs/audit.log
```

### Time-Based Analysis

```bash
# Actions in last hour
grep "$(date +%Y-%m-%d\ %H)" ~/.local/share/nextdns-blocker/logs/audit.log

# Weekend activity
grep -E "(Sat|Sun)" ~/.local/share/nextdns-blocker/logs/audit.log
```

## Privacy Considerations

### What's Logged

- Domain names
- Timestamps
- Action types
- Error messages

### What's NOT Logged

- API credentials
- Full configuration
- IP addresses
- User data

### Cleaning Logs

```bash
# Clear all logs
rm ~/.local/share/nextdns-blocker/logs/*.log

# Clear old logs (keep last 3 days)
find ~/.local/share/nextdns-blocker/logs -name "*.log" -mtime +3 -delete
```

## Troubleshooting with Logs

### Sync Issues

```bash
tail -100 ~/.local/share/nextdns-blocker/logs/cron.log
```

Look for:
- API errors
- Timeout messages
- Configuration errors

### Watchdog Issues

```bash
tail -50 ~/.local/share/nextdns-blocker/logs/wd.log
```

Look for:
- Job restoration events
- Missing job warnings

### Unexpected Behavior

```bash
# Enable verbose and capture
nextdns-blocker config push --verbose 2>&1 | tee debug.log
```

Share `debug.log` when reporting issues (redact API key).
