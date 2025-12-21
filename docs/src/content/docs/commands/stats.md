---
title: stats
description: Show usage statistics from the audit log
---

The `stats` command displays usage statistics by analyzing the audit log, showing counts of different actions performed over time.

## Usage

```bash
nextdns-blocker stats
```

## Example Output

```bash
nextdns-blocker stats
```

Output:
```
  Statistics
  ----------
    BLOCK: 245
    PANIC_ACTIVATED: 3
    PANIC_ENDED: 3
    PAUSE: 12
    PENDING_CREATED: 8
    PENDING_EXECUTED: 6
    RESUME: 12
    SYNC: 1847
    UNBLOCK: 42

  Total entries: 2178
```

## What It Shows

The stats command parses the audit log and counts occurrences of each action type:

| Action | Description |
|--------|-------------|
| `BLOCK` | Domain was added to denylist |
| `UNBLOCK` | Domain was removed from denylist |
| `SYNC` | Sync command was executed |
| `PAUSE` | Blocking was paused |
| `RESUME` | Blocking was resumed |
| `PANIC_ACTIVATED` | Panic mode was activated |
| `PANIC_ENDED` | Panic mode expired or was cancelled |
| `PENDING_CREATED` | Unblock request with delay was created |
| `PENDING_EXECUTED` | Pending unblock was executed |
| `PENDING_CANCELLED` | Pending unblock was cancelled |

## Use Cases

### Track Usage Patterns

See how often you:
- Pause blocking (impulse control measure)
- Use panic mode (emergency situations)
- Request unblocks (potential friction points)

### Measure Effectiveness

Compare block vs unblock counts:
- High unblock count may indicate schedules need adjustment
- Frequent pauses may suggest overly restrictive settings

### Monitor System Health

Check sync counts to verify:
- Watchdog is running (regular sync entries)
- System is active (entries accumulating)

## Audit Log Location

Statistics are derived from the audit log at:

- **macOS/Linux**: `~/.local/share/nextdns-blocker/logs/audit.log`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\logs\audit.log`

## Audit Log Format

Each line in the audit log follows this format:

```
2024-01-15T14:30:00 | ACTION | details
```

For watchdog entries:

```
2024-01-15T14:30:00 | WD | ACTION | details
```

## No Audit Log

If no audit log exists:

```bash
nextdns-blocker stats
```

Output:
```
  Statistics
  ----------
  No audit log found
```

This happens when:
- Fresh installation (no actions yet)
- Audit log was deleted
- Data directory doesn't exist

## Privacy

The audit log contains:
- Timestamps of actions
- Action types
- Domain names (for block/unblock)

It does NOT contain:
- Browsing history
- DNS queries
- Personal information

## Clearing Statistics

To reset statistics, delete the audit log:

```bash
rm ~/.local/share/nextdns-blocker/logs/audit.log
```

Or uninstall and reinstall:

```bash
nextdns-blocker uninstall
nextdns-blocker init
```

## Scripting

Extract specific stats for automation:

```bash
# Get sync count
nextdns-blocker stats | grep SYNC

# Check if system is active
if nextdns-blocker stats | grep -q "SYNC"; then
    echo "System is active"
fi
```

## Limitations

- No date filtering (shows all-time stats)
- No graphing or visualization
- Counts only, no averages or trends

For advanced analysis, parse the audit log directly:

```bash
# Count syncs in last 24 hours
grep "$(date -v-1d +%Y-%m-%d)" ~/.local/share/nextdns-blocker/logs/audit.log | grep SYNC | wc -l
```

## Related

- [Log Files Reference](/reference/log-files/) - Audit log details
- [health](/commands/health/) - System health checks
