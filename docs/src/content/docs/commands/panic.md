---
title: panic
description: Emergency lockdown mode for crisis situations
---

The `panic` command activates an emergency lockdown that immediately blocks all domains and hides dangerous commands.

## Overview

Panic mode is designed for crisis moments when you need absolute protection against impulsive access. It:

- **Immediately blocks** all configured domains
- **Hides** commands like `unblock`, `pause`, `allow`
- **Cannot be disabled** until the timer expires
- **Minimum duration** of 15 minutes

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `panic DURATION` | Activate panic mode |
| `panic status` | Check panic mode status |
| `panic extend MINUTES` | Extend panic duration |

## panic DURATION

Activate panic mode for the specified duration.

### Usage

```bash
nextdns-blocker panic DURATION
```

### Duration Formats

| Format | Example | Description |
|--------|---------|-------------|
| Minutes | `60` | 60 minutes |
| Minutes | `30m` | 30 minutes |
| Hours | `2h` | 2 hours |
| Days | `1d` | 1 day |

### Examples

```bash
# Activate for 1 hour
nextdns-blocker panic 60

# Activate for 30 minutes
nextdns-blocker panic 30m

# Activate for 4 hours
nextdns-blocker panic 4h

# Activate for 1 day
nextdns-blocker panic 1d
```

### Output

```
⚠️  PANIC MODE ACTIVATED

Duration: 60 minutes
Expires at: 2024-01-15 15:30:00

All domains are now blocked.
The following commands are disabled:
  - unblock
  - pause
  - resume
  - allow
  - disallow

Panic mode cannot be cancelled.
Wait for expiration or use 'panic extend' to add more time.
```

### Minimum Duration

Panic mode requires a minimum of 15 minutes to be effective:

```bash
nextdns-blocker panic 10
```

Output:
```
Error: Minimum panic duration is 15 minutes
```

## panic status

Check the current panic mode status.

### Usage

```bash
nextdns-blocker panic status
```

### Output (Active)

```
Panic Mode Status
━━━━━━━━━━━━━━━━━

Status: ACTIVE ⚠️

Activated: 2024-01-15 14:30:00
Expires: 2024-01-15 15:30:00
Remaining: 45 minutes

Hidden commands:
  - unblock
  - pause
  - resume
  - allow
  - disallow
```

### Output (Inactive)

```
Panic Mode Status
━━━━━━━━━━━━━━━━━

Status: Inactive

Use 'panic DURATION' to activate
Example: nextdns-blocker panic 60
```

## panic extend

Extend the current panic mode duration.

### Usage

```bash
nextdns-blocker panic extend MINUTES
```

### Example

```bash
# Add 30 more minutes
nextdns-blocker panic extend 30
```

### Output

```
Panic mode extended by 30 minutes
New expiration: 2024-01-15 16:00:00
Remaining: 75 minutes
```

### Requirements

- Panic mode must be active
- Extension adds to remaining time

## What Happens During Panic Mode

### All Domains Blocked

Every domain in your blocklist is immediately added to the NextDNS denylist, regardless of schedule:

```
Before panic:
  reddit.com: AVAILABLE (within schedule)
  twitter.com: BLOCKED
  youtube.com: AVAILABLE (within schedule)

After panic:
  reddit.com: BLOCKED (panic override)
  twitter.com: BLOCKED
  youtube.com: BLOCKED (panic override)
```

### Commands Hidden

These commands are completely hidden from help and tab completion:

| Command | Why Hidden |
|---------|------------|
| `unblock` | Would bypass panic |
| `pause` | Would pause blocking |
| `resume` | Not needed (already forced) |
| `allow` | Would add exceptions |
| `disallow` | Not dangerous but hidden for consistency |

Attempting to run them directly:

```bash
nextdns-blocker unblock reddit.com
```

Output:
```
Error: Command 'unblock' is not available during panic mode
Panic mode expires at: 2024-01-15 15:30:00
```

### Sync Behavior

During panic mode, sync:
- Blocks all domains regardless of schedule
- Skips unblock processing
- Skips allowlist sync (prevents bypasses)
- Processes pending action cancellation (cleanup only)

### Pending Actions

Pending unblock actions are **paused** during panic mode:
- Their timers continue
- But execution is skipped
- They resume processing after panic expires

## Why Panic Mode?

Panic mode is based on behavioral psychology research:

1. **Crisis Moments**: During moments of weakness, you need absolute protection
2. **No Loopholes**: Hidden commands prevent "just this once" thinking
3. **Time-Based**: You know it will end, reducing desperation
4. **Extendable**: If needed, you can add more time

### Recommended Use Cases

| Situation | Recommended Duration |
|-----------|---------------------|
| Feeling tempted | 30-60 minutes |
| After a slip | 2-4 hours |
| Bad day | 4-8 hours |
| Weekend protection | 24-48 hours |
| Recovery period | Multiple days |

## Panic Mode vs Other Features

| Feature | Purpose | Can Disable |
|---------|---------|-------------|
| Panic mode | Crisis protection | No |
| Pause | Quick break | Yes |
| Schedule | Regular access | Via config |
| Allowlist | Permanent exceptions | Yes |

## State Storage

Panic state is stored in:
- **macOS/Linux**: `~/.local/share/nextdns-blocker/.panic`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\.panic`

The file contains an ISO 8601 timestamp of expiration.

## Troubleshooting

### Cannot activate panic mode

Check for existing panic:

```bash
nextdns-blocker panic status
```

### Panic mode not blocking

Force a sync:

```bash
nextdns-blocker sync
```

Check watchdog is running:

```bash
nextdns-blocker watchdog status
```

### Need to end panic early

**This is intentionally not possible.** Panic mode's effectiveness comes from its inescapability.

Options:
- Wait for expiration
- In extreme emergencies, delete the `.panic` file (not recommended)

### Domains still accessible

They might be:
- Cached in your browser (clear cache)
- Cached in your OS DNS (flush DNS)
- Not going through NextDNS (check DNS settings)

```bash
# macOS: Flush DNS
sudo dscacheutil -flushcache

# Linux
sudo systemctl restart systemd-resolved

# Windows
ipconfig /flushdns
```
