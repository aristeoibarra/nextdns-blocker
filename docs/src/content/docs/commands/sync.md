---
title: sync
description: Synchronize domain states based on configured schedules
---

:::caution[Command Moved]
The root `sync` command has been removed. Use `nextdns-blocker config sync` instead.
:::

The `config sync` command is the core of NextDNS Blocker. It evaluates each domain against its schedule and updates the NextDNS denylist accordingly.

## Usage

```bash
nextdns-blocker config sync [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without applying them |
| `-v, --verbose` | Show detailed output |
| `--help` | Show help message |

## Examples

### Basic Sync

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

### Dry Run

Preview what would happen without making changes:

```bash
nextdns-blocker config sync --dry-run
```

Output:
```
DRY RUN - No changes will be made

Evaluating domains at 2024-01-15 14:30:00 (America/New_York)...

  reddit.com
    Schedule: Mon-Fri 12:00-13:00, 18:00-22:00
    Current: Outside available hours
    Action: Would BLOCK

Summary: 1 would block, 0 would unblock
```

### Verbose Output

Get detailed information about each step:

```bash
nextdns-blocker config sync --verbose
```

Output:
```
Loading configuration...
  Config: ~/.config/nextdns-blocker/config.json
  Timezone: America/New_York
  Current time: 2024-01-15 14:30:00

Fetching current denylist from NextDNS...
  Cache: MISS (fetching fresh data)
  API call: GET /profiles/abc123/denylist
  Response: 200 OK (3 domains)

Evaluating blocklist (2 domains)...

  reddit.com
    Description: Social media
    Unblock delay: 30m
    Schedule check:
      Day: monday ✓
      Time: 14:30
      Available ranges: 12:00-13:00, 18:00-22:00
      Result: OUTSIDE available hours
    Current state: Not in denylist
    Action: BLOCK
    API call: PUT /profiles/abc123/denylist/reddit.com
    Response: 200 OK

  twitter.com
    Description: News
    Schedule: Always available on weekends
    Schedule check:
      Day: monday
      Result: Not a weekend day, checking weekday schedule...
      Available ranges: 18:00-22:00
      Result: OUTSIDE available hours
    Current state: In denylist
    Action: No change needed

Processing pending actions...
  No pending actions to process

Sync complete
  Blocked: 1
  Unblocked: 0
  Unchanged: 1
  Duration: 0.8s
```

## What Sync Does

### 1. Load Configuration

Reads `config.json` and validates:
- Domain formats
- Schedule syntax
- Timezone setting

### 2. Check Current State

Fetches the current denylist from NextDNS API:
- Uses intelligent caching (configurable TTL)
- Respects rate limits

### 3. Evaluate Each Domain

For each domain in your blocklist:
1. Get the current day and time (in configured timezone)
2. Check if current time falls within `available_hours`
3. Determine if domain should be blocked or unblocked

### 4. Apply Changes

- **Block**: Add domain to NextDNS denylist
- **Unblock**: Remove domain from NextDNS denylist
- Uses exponential backoff on failures

### 5. Process Pending Actions

Checks for pending unblock actions that are due:
- Executes unblocks whose delay has elapsed
- Cleans up expired pending actions

### 6. Process Allowlist

Syncs allowlist entries:
- Adds scheduled entries during their available hours
- Removes scheduled entries outside their hours

## Automatic Sync

The watchdog runs `config sync` automatically every 2 minutes:

```bash
# Install watchdog
nextdns-blocker watchdog install

# Check status
nextdns-blocker watchdog status
```

See [Watchdog](/commands/watchdog/) for details.

## Sync During Panic Mode

When panic mode is active, sync behavior changes:
- All domains are **blocked** regardless of schedule
- Unblock actions are skipped
- Allowlist sync is skipped

This ensures emergency lockdown cannot be bypassed by scheduled unblocks.

## Sync During Pause

When paused:
- Sync runs normally
- Domains that should be blocked are **not blocked**
- When pause expires, next sync re-blocks them

## Caching

Sync uses intelligent caching to reduce API calls:

| Setting | Default | Description |
|---------|---------|-------------|
| `CACHE_TTL` | 60s | How long to cache denylist |

Configure in `.env`:
```bash
CACHE_TTL=120  # 2 minutes
```

## Rate Limiting

Built-in rate limiting prevents API abuse:

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_REQUESTS` | 30 | Max requests per window |
| `RATE_LIMIT_WINDOW` | 60s | Window duration |

## Troubleshooting

### Sync not making changes

1. Check dry-run output:
   ```bash
   nextdns-blocker config sync --dry-run -v
   ```

2. Verify timezone:
   ```bash
   nextdns-blocker config show | grep timezone
   ```

3. Check schedule logic matches current time

### API errors

1. Validate credentials:
   ```bash
   nextdns-blocker init  # Re-run setup
   ```

2. Check rate limits - wait 60 seconds

3. Check NextDNS service status

### Domain not blocking

1. Verify domain is in blocklist:
   ```bash
   nextdns-blocker config show
   ```

2. Check schedule - is it within available hours?

3. Check for pending pause:
   ```bash
   nextdns-blocker status
   ```
