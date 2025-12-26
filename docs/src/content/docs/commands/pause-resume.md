---
title: pause / resume
description: Temporarily suspend and restore domain blocking
---

The `pause` and `resume` commands let you temporarily suspend blocking without changing your configuration.

## pause

Temporarily suspends all blocking for a specified duration.

### Usage

```bash
nextdns-blocker pause [MINUTES]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `MINUTES` | 30 | Duration to pause blocking |

### Examples

```bash
# Pause for 30 minutes (default)
nextdns-blocker pause

# Pause for 1 hour
nextdns-blocker pause 60

# Pause for 15 minutes
nextdns-blocker pause 15
```

### Output

```
Blocking paused for 30 minutes
Resumes at: 2024-01-15 15:00:00

Use 'resume' to end pause early
```

### Behavior During Pause

When paused:
- **Sync still runs** every 2 minutes
- Domains that should be blocked are **not blocked**
- Domains already in denylist remain (no unblocking action)
- Status shows "PAUSED" for affected domains

### Pause Expiration

When the pause expires:
- Next sync run re-evaluates all domains
- Domains outside their schedule are blocked again
- No notification is sent

## resume

Immediately ends a pause and resumes normal blocking.

### Usage

```bash
nextdns-blocker resume
```

### Output

```
Blocking resumed

Next sync will re-apply schedules
```

### Behavior

1. Clears the pause state
2. Does **not** trigger an immediate sync
3. Next scheduled sync (within 2 minutes) applies blocks

To immediately apply blocks after resume:

```bash
nextdns-blocker resume && nextdns-blocker sync
```

## Use Cases

### Quick Break

Need a short break to access a blocked site:

```bash
# 15-minute break
nextdns-blocker pause 15

# Do what you need to do...

# Done early? Resume blocking
nextdns-blocker resume
```

### Temporary Full Access

Need unrestricted access for a meeting or task:

```bash
# Pause for the meeting duration
nextdns-blocker pause 60

# Meeting done
nextdns-blocker resume
```

### Emergency Access

For genuine emergencies, consider using [unblock](/commands/unblock/) for specific domains instead of pausing everything.

## Pause vs Other Methods

| Method | Scope | Duration | Friction |
|--------|-------|----------|----------|
| `pause` | All domains | Temporary | None |
| `unblock` | One domain | Varies | Delay-based |
| `allow` | One domain | Permanent | None |
| Config edit | Any | Permanent | Manual |

### When to Use Pause

- Quick breaks
- Temporary full access
- Testing/debugging

### When NOT to Use Pause

- Regular access to specific domains → Use schedules
- Permanent exceptions → Use allowlist
- Emergency situations → Use `unblock` or edit config

## Limitations

### Cannot Extend Pause

To extend, you must pause again:

```bash
# Already paused for 30 min, need more time
nextdns-blocker pause 60  # Resets to 60 min from now
```

### Pause is User-Specific

Pause state is stored locally. If you have multiple machines syncing to the same NextDNS profile, pause only affects the local machine.

### Panic Mode Overrides Pause

If panic mode is activated while paused:
- Pause is ignored
- All domains are blocked
- `pause` command becomes hidden

## State Storage

Pause state is stored in:
- **macOS/Linux**: `~/.local/share/nextdns-blocker/.paused`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\.paused`

The file contains an ISO 8601 timestamp of when the pause expires.

## Troubleshooting

### Pause not working

1. Check if panic mode is active:
   ```bash
   nextdns-blocker status
   ```

2. Verify pause state exists:
   ```bash
   cat ~/.local/share/nextdns-blocker/.paused
   ```

3. Force resume and try again:
   ```bash
   nextdns-blocker resume
   nextdns-blocker pause 30
   ```

### Domain still blocked during pause

The domain might be:
- In the NextDNS denylist from before the pause
- Blocked by a NextDNS category/service (not managed by this tool)

Run sync to clear:
```bash
nextdns-blocker sync
```

### Resume not re-blocking

Resume doesn't trigger an immediate sync. Either:

```bash
# Wait for next automatic sync (within 2 min)
# Or force sync now:
nextdns-blocker resume && nextdns-blocker sync
```
