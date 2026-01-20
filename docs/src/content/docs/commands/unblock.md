---
title: unblock
description: Request manual unblocking of a specific domain
---

The `unblock` command requests a manual unblock for a specific domain, respecting configured delays.

## Usage

```bash
nextdns-blocker unblock DOMAIN
```

## Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `DOMAIN` | Yes | The domain to unblock |

## Behavior

The behavior depends on the domain's `unblock_delay` setting:

### Instant Unblock (`"0"`)

```bash
nextdns-blocker unblock reddit.com
```

Output:
```
Unblocking reddit.com...
✓ reddit.com unblocked
```

The domain is immediately removed from the NextDNS denylist.

### Delayed Unblock (`"30m"`, `"4h"`, `"24h"`)

```bash
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

The unblock is queued as a pending action and will execute when the delay expires.

### Protected Domain (`"never"`)

```bash
nextdns-blocker unblock gambling-site.com
```

Output:
```
✗ Cannot unblock 'gambling-site.com'
  This domain is protected (unblock_delay: never)
```

Protected domains cannot be unblocked manually.

## Unblock Delay Reference

| Value | Behavior | Use Case |
|-------|----------|----------|
| `"0"` | Instant | Low-risk sites |
| `"30m"` | 30-minute delay | Moderate friction |
| `"4h"` | 4-hour delay | High friction |
| `"24h"` | 24-hour delay | Maximum friction |
| `"never"` | Cannot unblock | Harmful content |

## Managing Pending Unblocks

### List Pending Actions

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

### Cancel Pending Action

Changed your mind? Cancel before it executes:

```bash
nextdns-blocker pending cancel pnd_20240115_143000_a1b2c3
```

Output:
```
Cancel pending unblock for 'bumble.com'? [y/N]: y
✓ Pending action cancelled
```

Or skip confirmation:

```bash
nextdns-blocker pending cancel pnd_20240115_143000_a1b2c3 -y
```

## Why Unblock Delays?

Research shows cravings typically fade within 20-30 minutes. By adding friction:

1. **Impulse Protection**: The delay creates time to reconsider
2. **Conscious Decision**: You must actively wait, not just click
3. **Easy Cancellation**: If the urge passes, cancel the pending action
4. **Still Accessible**: Legitimate needs can still be met

### Recommended Delays

| Content Type | Recommended Delay |
|--------------|-------------------|
| Social media | 30m - 4h |
| Gaming | 30m - 4h |
| Streaming | 30m - 24h |
| Dating apps | 4h - 24h |
| Gambling | never |
| Adult content | never |

## Unblock and Schedules

Unblocking is separate from schedules:

- **Unblock**: Manual, one-time access
- **Schedule**: Automatic, recurring access

If you unblock a domain:
- It's removed from the denylist
- Next sync (within 2 min) will re-block it if outside schedule
- For longer access, add to allowlist or edit the schedule

### Keeping Domain Unblocked

To prevent re-blocking after unblock:

```bash
# Option 1: Add to allowlist
nextdns-blocker allow reddit.com

# Option 2: Edit schedule to include current time
nextdns-blocker config edit
```

## Tab Completion

With shell completion enabled, domain names auto-complete:

```bash
nextdns-blocker unblock red<TAB>
# Completes to: nextdns-blocker unblock reddit.com
```

See [Shell Completion](/features/shell-completion/) to enable.

## Troubleshooting

### "Domain not in blocklist"

The domain isn't configured in your `config.json`:

```bash
nextdns-blocker config show | grep domain
```

### "Domain not currently blocked"

The domain is within its available hours or already unblocked:

```bash
nextdns-blocker status | grep <domain>
```

### Pending action not executing

1. Check watchdog is running:
   ```bash
   nextdns-blocker watchdog status
   ```

2. Check pending action details:
   ```bash
   nextdns-blocker pending show <ID>
   ```

3. Force sync:
   ```bash
   nextdns-blocker config push
   ```
