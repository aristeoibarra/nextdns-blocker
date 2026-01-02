---
title: Your First Sync
description: Run your first synchronization and understand what happens
---

With your configuration in place, it's time to run your first sync and see NextDNS Blocker in action.

## Understanding Sync

The `config sync` command:
1. Reads your `config.json` blocklist
2. Evaluates each domain against the current time and its schedule
3. Adds/removes domains from your NextDNS denylist accordingly
4. Processes any pending unblock actions

## Run a Dry Run First

Before making actual changes, preview what would happen:

```bash
nextdns-blocker config sync --dry-run
```

Output example:

```
DRY RUN - No changes will be made

Evaluating domains at 2024-01-15 14:30:00 (America/New_York)...

  reddit.com
    Schedule: Mon-Fri 12:00-13:00, 18:00-22:00
    Current: Outside available hours
    Action: Would BLOCK

  twitter.com
    Schedule: Always available on weekends
    Current: Within available hours
    Action: Would UNBLOCK

Summary: 1 would block, 1 would unblock
```

## Run the Actual Sync

When you're ready to apply changes:

```bash
nextdns-blocker config sync
```

Output:

```
Syncing domains...
  reddit.com: BLOCKED
  twitter.com: UNBLOCKED
Sync complete: 1 blocked, 1 unblocked
```

### Verbose Mode

For more detailed output:

```bash
nextdns-blocker config sync --verbose
```

Or use the shorthand:

```bash
nextdns-blocker config sync -v
```

This shows:
- Current timezone and time
- Each domain's schedule evaluation
- API calls made
- Cache hits/misses

## Check Current Status

After syncing, verify the current state:

```bash
nextdns-blocker status
```

Output:

```
NextDNS Blocker Status
━━━━━━━━━━━━━━━━━━━━━━

Time: 2024-01-15 14:30:00 America/New_York

Blocklist (2 domains):
  ✗ reddit.com      BLOCKED   (until 18:00)
  ✓ twitter.com     AVAILABLE (until 22:00)

Allowlist (1 domain):
  ✓ aws.amazon.com  ALLOWED   (always)

System:
  Watchdog: Active
  Panic Mode: Inactive
  Pending Actions: 0
```

## What Gets Synced

### Blocklist Behavior

| Condition | Action | Result |
|-----------|--------|--------|
| Outside schedule | Block | Added to NextDNS denylist |
| Within schedule | Unblock | Removed from denylist |
| No schedule (`null`) | Always block | Permanent denylist entry |

### Allowlist Behavior

| Condition | Action | Result |
|-----------|--------|--------|
| No schedule | Always allow | Permanent allowlist entry |
| Within schedule | Allow | Added to NextDNS allowlist |
| Outside schedule | Remove | Removed from allowlist |

## Automatic Sync with Watchdog

Manual syncing works, but the watchdog automates this:

```bash
# Install watchdog (runs config sync every 2 minutes)
nextdns-blocker watchdog install

# Check watchdog status
nextdns-blocker watchdog status

# View watchdog logs
tail -f ~/.local/share/nextdns-blocker/logs/cron.log
```

The watchdog:
- Runs `config sync` every 2 minutes
- Restores itself if removed
- Logs all activity
- Can be temporarily disabled

## Common Issues

### "No domains configured"

Your blocklist is empty. Add domains:

```bash
nextdns-blocker config edit
```

### "API authentication failed"

Your credentials are invalid. Re-run setup:

```bash
nextdns-blocker init
```

### "Domain already in denylist"

The domain was manually added to NextDNS. NextDNS Blocker will manage it going forward, but you can verify in the NextDNS dashboard.

### "Rate limit exceeded"

Too many API calls. Wait a minute and try again. The tool has built-in rate limiting, but rapid manual syncs can exceed limits.

## Next Steps

- [Configure more domains](/configuration/blocklist/)
- [Set up unblock delays](/configuration/unblock-delay/)
- [Enable notifications](/features/notifications/)
- [Learn about panic mode](/features/panic-mode/)
