---
title: Dry Run Mode
description: Preview changes without applying them
---

Dry run mode lets you see what sync would do without making any actual changes to NextDNS.

## Usage

```bash
nextdns-blocker config sync --dry-run
```

Or combined with verbose:

```bash
nextdns-blocker config sync --dry-run --verbose
nextdns-blocker config sync --dry-run -v
```

## Output

### Basic Dry Run

```bash
nextdns-blocker config sync --dry-run
```

Output:
```
DRY RUN - No changes will be made

Evaluating domains at 2024-01-15 14:30:00 (America/New_York)...

  reddit.com
    Action: Would BLOCK (outside available hours)

  twitter.com
    Action: Would UNBLOCK (within schedule)

  youtube.com
    Action: No change (already blocked)

Summary: 1 would block, 1 would unblock, 1 unchanged
```

### Verbose Dry Run

```bash
nextdns-blocker config sync --dry-run --verbose
```

Output:
```
DRY RUN - No changes will be made

Loading configuration...
  Config: ~/.config/nextdns-blocker/config.json
  Timezone: America/New_York
  Current time: 2024-01-15 14:30:00 (Monday)

Fetching current denylist from NextDNS...
  Would fetch: GET /profiles/abc123/denylist
  (Using cached data for dry run)

Evaluating blocklist (3 domains)...

  reddit.com
    Description: Social media
    Unblock delay: 30m
    Schedule check:
      Day: monday ✓
      Time: 14:30
      Available ranges: 12:00-13:00, 18:00-22:00
      Current time in range: NO
      Result: OUTSIDE available hours
    Current state: Not in denylist
    Action: Would BLOCK
    Would call: PUT /profiles/abc123/denylist/reddit.com

  twitter.com
    Description: News
    Schedule check:
      Day: monday ✓
      Time: 14:30
      Available ranges: 09:00-17:00
      Current time in range: YES
      Result: WITHIN available hours
    Current state: In denylist
    Action: Would UNBLOCK
    Would call: DELETE /profiles/abc123/denylist/twitter.com

  youtube.com
    Description: Streaming
    Schedule: null (always blocked)
    Current state: In denylist
    Action: No change needed

Evaluating allowlist (1 domain)...

  aws.amazon.com
    Schedule: null (always allowed)
    Current state: In allowlist
    Action: No change needed

Processing pending actions...
  pnd_20240115_100000_a1b2c3: Not due yet (executes in 30 min)

DRY RUN Summary:
  Would block: 1 domain
  Would unblock: 1 domain
  Unchanged: 2 domains
  Pending actions: 0 would execute
```

## Use Cases

### Testing Schedule Logic

Before relying on schedules, verify they work as expected:

```bash
# Check what would happen right now
nextdns-blocker config sync --dry-run

# Expected output shows:
# - Which domains are within schedule
# - Which are outside schedule
# - Time-based reasoning
```

### After Editing Config

Preview changes before they apply:

```bash
# Edit configuration
nextdns-blocker config edit

# Preview what would change
nextdns-blocker config sync --dry-run

# If satisfied, run real sync
nextdns-blocker config sync
```

### Debugging Issues

When domains aren't blocking/unblocking as expected:

```bash
nextdns-blocker config sync --dry-run --verbose
```

Check:
- Timezone is correct
- Day evaluation matches current day
- Time ranges include current time
- Schedule logic is correct

### Testing Timezone

After changing timezone:

```bash
nextdns-blocker config set timezone America/Los_Angeles
nextdns-blocker config sync --dry-run -v
```

Verify times are evaluated in new timezone.

### Before Critical Changes

Before modifying protected domains or critical schedules:

```bash
nextdns-blocker config sync --dry-run
```

Ensure nothing unexpected will happen.

## What Dry Run Doesn't Do

### No API Calls

Dry run does NOT:
- Add domains to NextDNS denylist
- Remove domains from denylist
- Modify allowlist
- Execute pending actions
- Send Discord notifications

### Still Reads Config

Dry run DOES:
- Read `config.json`
- Read `.env`
- Read pending actions
- Evaluate schedules
- Show what would happen

## Dry Run + Other Features

### With Panic Mode

During panic mode, dry run shows:
```
DRY RUN - PANIC MODE ACTIVE

All domains would be blocked regardless of schedule.

  reddit.com: Would BLOCK (panic override)
  twitter.com: Would BLOCK (panic override)
  youtube.com: Would BLOCK (already blocked)
```

### With Pause

During pause, dry run shows:
```
DRY RUN - BLOCKING PAUSED

Domains that would be blocked are shown but won't be blocked until resume.

  reddit.com: Would BLOCK (but paused)
  twitter.com: AVAILABLE
```

### Pending Actions

Dry run shows pending actions that would execute:
```
Processing pending actions...
  pnd_20240115_100000_a1b2c3: Would execute (24h delay elapsed)
    Domain: bumble.com
    Would call: DELETE /profiles/abc123/denylist/bumble.com
```

## Best Practices

### Always Dry Run First

Before your first sync:
```bash
nextdns-blocker config sync --dry-run
```

### After Any Config Change

```bash
nextdns-blocker config edit
nextdns-blocker config sync --dry-run
# If good:
nextdns-blocker config sync
```

### When Debugging

```bash
nextdns-blocker config sync --dry-run --verbose 2>&1 | less
```

Review output carefully for issues.

### Check at Boundary Times

Test at schedule boundaries:
- Just before available hours start
- Just after available hours end
- Midnight (for overnight schedules)

## Troubleshooting with Dry Run

### Domain Should Be Blocked But Isn't

```bash
nextdns-blocker config sync --dry-run -v | grep -A10 "domain.com"
```

Check:
- Schedule shows "OUTSIDE available hours"
- Action shows "Would BLOCK"

### Schedule Seems Wrong

```bash
nextdns-blocker config sync --dry-run -v
```

Verify:
- Current time shown is correct
- Timezone is correct
- Day name matches
- Time ranges are correct

### Pending Action Not Executing

```bash
nextdns-blocker config sync --dry-run -v | grep -A5 "pending"
```

Check:
- Action is listed
- Execute time has passed
- Shows "Would execute"
