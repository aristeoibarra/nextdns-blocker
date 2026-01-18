---
title: Pending Actions
description: Queued operations with configurable delays
---

Pending actions are queued operations that execute after a delay, creating friction against impulsive decisions.

## What are Pending Actions?

When you unblock a domain with a delay configured:

1. **Request**: `unblock reddit.com`
2. **Queue**: Pending action created
3. **Wait**: Delay period (30m, 4h, 24h)
4. **Execute**: Domain automatically unblocked

During the wait, you can change your mind and cancel.

## Creating Pending Actions

Pending actions are created automatically when:

```bash
# Domain has unblock_delay: "24h"
nextdns-blocker unblock bumble.com
```

Output:
```
Unblock scheduled for 'bumble.com'
Delay: 24h
Execute at: 2024-01-16 14:30:00
ID: pnd_20240115_143000_a1b2c3

Use 'pending list' to view or 'pending cancel <ID>' to abort
```

## Viewing Pending Actions

### List All

```bash
nextdns-blocker pending list
```

Output:
```
Pending Actions (2)

ID                              Domain         Execute At            Remaining
─────────────────────────────────────────────────────────────────────────────
pnd_20240115_143000_a1b2c3      bumble.com     2024-01-16 14:30:00   23h 45m
pnd_20240115_150000_d4e5f6      twitter.com    2024-01-15 19:00:00   4h 30m
```

### View Details

```bash
nextdns-blocker pending show pnd_20240115_143000_a1b2c3
```

Output:
```
Pending Action Details
━━━━━━━━━━━━━━━━━━━━━━

ID: pnd_20240115_143000_a1b2c3

Domain: bumble.com
Description: Dating app

Created: 2024-01-15 14:30:00
Delay: 24h
Execute at: 2024-01-16 14:30:00

Status: pending
Remaining: 23 hours, 45 minutes
```

### Include History

```bash
nextdns-blocker pending list --all
```

Shows executed and cancelled actions too.

## Cancelling Actions

Changed your mind? Cancel before execution:

```bash
nextdns-blocker pending cancel pnd_20240115_143000_a1b2c3
```

Output:
```
Cancel pending unblock for 'bumble.com'?

Created: 2024-01-15 14:30:00
Would execute: 2024-01-16 14:30:00
Remaining: 23 hours, 45 minutes

Cancel? [y/N]: y
✓ Pending action cancelled
```

### Skip Confirmation

```bash
nextdns-blocker pending cancel pnd_20240115_143000_a1b2c3 -y
```

## Action ID Format

IDs follow this pattern:
```
pnd_YYYYMMDD_HHMMSS_random6
```

- `pnd_` - Prefix indicating pending action
- `YYYYMMDD` - Date created (year, month, day)
- `HHMMSS` - Time created (hour, minute, second)
- `random6` - 6-character alphanumeric suffix (lowercase letters and digits)

Example: `pnd_20251215_143022_a1b2c3`

### Partial IDs

If unique, you can use just the random part:

```bash
nextdns-blocker pending show a1b2c3
nextdns-blocker pending cancel a1b2c3
```

## Lifecycle

### States

| State | Description |
|-------|-------------|
| `pending` | Waiting to execute |
| `executed` | Successfully unblocked |
| `cancelled` | User cancelled |

### Flow

```
                    ┌─────────────┐
                    │   Created   │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ▼            │            ▼
       ┌──────────┐        │     ┌──────────┐
       │ Cancelled│        │     │ Executed │
       └──────────┘        │     └──────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │   Cleanup   │
                    │  (7 days)   │
                    └─────────────┘
```

## Processing

### When Actions Execute

1. Watchdog runs sync every 2 minutes
2. Sync checks pending actions
3. Actions with `execute_at ≤ now` are processed
4. Domain is removed from NextDNS denylist
5. Action marked as `executed`
6. Discord notification sent (if enabled)

### Requirements

- Watchdog must be running
- Panic mode must be inactive
- Action not cancelled

## Pending Actions During Panic Mode

When panic mode is active:

| Aspect | Behavior |
|--------|----------|
| New actions | Cannot create (`unblock` hidden) |
| Existing actions | Timers continue |
| Execution | Skipped |
| Cancellation | Still allowed |

After panic expires:
- Pending actions resume processing
- Due actions execute immediately

## Storage

### Location

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.local/share/nextdns-blocker/pending.json` |
| Windows | `%LOCALAPPDATA%\nextdns-blocker\pending.json` |

### Format

```json
{
  "actions": [
    {
      "id": "pnd_20240115_143000_a1b2c3",
      "domain": "bumble.com",
      "created_at": "2024-01-15T14:30:00",
      "execute_at": "2024-01-16T14:30:00",
      "delay": "24h",
      "status": "pending"
    }
  ]
}
```

### Concurrency

File uses atomic writes with locking:
- Prevents corruption
- Safe for concurrent access
- Backup created before writes

## Cleanup

Old actions are automatically cleaned:

| Status | Retention |
|--------|-----------|
| `executed` | 7 days |
| `cancelled` | 7 days |
| `pending` | Until executed/cancelled |

Cleanup runs during daily sync.

## Tab Completion

With shell completion enabled:

```bash
nextdns-blocker pending cancel pnd_<TAB>
# Shows available action IDs
```

## Troubleshooting

### Action not executing

1. **Check watchdog**:
   ```bash
   nextdns-blocker watchdog status
   ```

2. **Check panic mode**:
   ```bash
   nextdns-blocker panic status
   ```

3. **Check action status**:
   ```bash
   nextdns-blocker pending show <ID>
   ```

4. **Force sync**:
   ```bash
   nextdns-blocker config sync --verbose
   ```

### Duplicate actions

Each `unblock` request creates a new action:

```bash
# See all actions
nextdns-blocker pending list

# Cancel duplicates
nextdns-blocker pending cancel <older-id> -y
```

### Cannot find action

Action might be:
- Already executed
- Already cancelled
- Cleaned up (>7 days old)

Check history:
```bash
nextdns-blocker pending list --all
```

### pending.json corrupted

Reset the file:

```bash
# Backup
mv ~/.local/share/nextdns-blocker/pending.json ~/.local/share/nextdns-blocker/pending.json.bak

# Recreate
echo '{"actions":[]}' > ~/.local/share/nextdns-blocker/pending.json
```

## Best Practices

1. **Use appropriate delays** - Match to content risk level
2. **Check pending list regularly** - Know what's queued
3. **Cancel when urge passes** - That's the point
4. **Don't rush cancellation** - Wait a bit before cancelling
5. **Review after execution** - Was access really needed?
