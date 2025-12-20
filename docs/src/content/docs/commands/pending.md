---
title: pending
description: Manage pending unblock actions with delays
---

The `pending` command group manages queued unblock actions that are waiting for their delay to expire.

## Overview

When you attempt to unblock a domain that has an `unblock_delay` configured, the unblock is queued as a pending action. This creates friction against impulsive decisions.

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `list` | List all pending actions |
| `show` | Show details of a specific action |
| `cancel` | Cancel a pending action |

## pending list

List all pending unblock actions.

### Usage

```bash
nextdns-blocker pending list [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--all` | Include expired/executed actions |

### Output

```
Pending Actions (2)

ID                              Domain         Execute At            Remaining
─────────────────────────────────────────────────────────────────────────────
pnd_20240115_143000_a1b2c3      bumble.com     2024-01-16 14:30:00   23h 45m
pnd_20240115_150000_d4e5f6      twitter.com    2024-01-15 19:00:00   4h 30m
```

### With --all Flag

```bash
nextdns-blocker pending list --all
```

Shows additional columns for status:

```
Pending Actions (4)

ID                              Domain         Execute At            Status
─────────────────────────────────────────────────────────────────────────────
pnd_20240115_143000_a1b2c3      bumble.com     2024-01-16 14:30:00   pending
pnd_20240115_150000_d4e5f6      twitter.com    2024-01-15 19:00:00   pending
pnd_20240115_100000_g7h8i9      reddit.com     2024-01-15 10:30:00   executed
pnd_20240114_200000_j0k1l2      instagram.com  2024-01-15 08:00:00   cancelled
```

### No Pending Actions

```
No pending actions

Pending actions are created when you run:
  nextdns-blocker unblock <domain>

For domains with unblock_delay > "0"
```

## pending show

Show detailed information about a specific pending action.

### Usage

```bash
nextdns-blocker pending show ACTION_ID
```

### Example

```bash
nextdns-blocker pending show pnd_20240115_143000_a1b2c3
```

### Output

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

To cancel:
  nextdns-blocker pending cancel pnd_20240115_143000_a1b2c3
```

### Action ID Format

Action IDs follow the pattern:
```
pnd_YYYYMMDD_HHMMSS_RANDOM
```

- `pnd_` - Prefix indicating pending action
- `YYYYMMDD` - Date created
- `HHMMSS` - Time created
- `RANDOM` - 6-character random suffix

You can use a partial ID if it's unique:

```bash
nextdns-blocker pending show a1b2c3
```

## pending cancel

Cancel a pending unblock action.

### Usage

```bash
nextdns-blocker pending cancel ACTION_ID [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |

### Example

```bash
nextdns-blocker pending cancel pnd_20240115_143000_a1b2c3
```

### Output

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

Output:
```
✓ Cancelled pending unblock for 'bumble.com'
```

### Tab Completion

With shell completion enabled, action IDs auto-complete:

```bash
nextdns-blocker pending cancel pnd_<TAB>
# Shows available action IDs
```

## How Pending Actions Work

### Creation

1. User runs `unblock <domain>`
2. Domain has `unblock_delay` > "0"
3. Pending action is created with execute time = now + delay
4. Action is stored in `pending.json`

### Execution

1. Sync runs (every 2 minutes)
2. Checks for pending actions with execute time ≤ now
3. Executes the unblock (removes from NextDNS denylist)
4. Marks action as executed
5. Sends Discord notification (if enabled)

### Cancellation

1. User runs `pending cancel <ID>`
2. Action is marked as cancelled
3. Will not execute even if time passes
4. Old cancelled actions are cleaned up daily

## Pending Actions During Panic Mode

When panic mode is active:

- **New pending actions**: Cannot be created (`unblock` is hidden)
- **Existing pending actions**: Paused (not executed)
- **Cancellation**: Still possible (cleanup allowed)

After panic expires:
- Pending actions resume processing
- Actions past their execute time are processed immediately

## Storage

Pending actions are stored in:
- **macOS/Linux**: `~/.local/share/nextdns-blocker/pending.json`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\pending.json`

### File Format

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

### File Locking

The file uses atomic writes with file locking to prevent corruption from concurrent access.

## Cleanup

Old pending actions are automatically cleaned up:

- **Executed actions**: Kept for 7 days
- **Cancelled actions**: Kept for 7 days
- **Daily cleanup**: Runs via watchdog

Manual cleanup:

```bash
# Force cleanup by triggering sync
nextdns-blocker sync
```

## Troubleshooting

### Action not executing

1. Check watchdog is running:
   ```bash
   nextdns-blocker watchdog status
   ```

2. Check action details:
   ```bash
   nextdns-blocker pending show <ID>
   ```

3. Check for panic mode:
   ```bash
   nextdns-blocker panic status
   ```

4. Force sync:
   ```bash
   nextdns-blocker sync --verbose
   ```

### Cannot cancel action

- Action might already be executed
- Check with `pending show <ID>`

### Duplicate pending actions

Each unblock request creates a new pending action. Cancel duplicates:

```bash
nextdns-blocker pending list
nextdns-blocker pending cancel <older-ID> -y
```

### Pending.json corrupted

If the file is corrupted:

```bash
# Backup and recreate
mv ~/.local/share/nextdns-blocker/pending.json ~/.local/share/nextdns-blocker/pending.json.bak
echo '{"actions":[]}' > ~/.local/share/nextdns-blocker/pending.json
```
