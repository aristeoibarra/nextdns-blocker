---
title: Panic Mode
description: Emergency lockdown for crisis situations
---

Panic mode is an emergency feature that immediately blocks all domains and prevents bypassing.

## What is Panic Mode?

Panic mode is designed for crisis moments when you need absolute protection:

- **All domains blocked** regardless of schedule
- **Dangerous commands hidden** (`unblock`, `pause`, `allow`)
- **Cannot be disabled** until timer expires
- **Minimum 15 minutes** to prevent abuse

## When to Use

### Good Use Cases

- Feeling strong urges to access blocked content
- Recognizing you're in a vulnerable state
- After a "slip" to prevent further access
- Before a known trigger event
- When willpower is low

### Examples

| Situation | Recommended Duration |
|-----------|---------------------|
| Quick urge | 30-60 minutes |
| After a slip | 2-4 hours |
| Bad day | 4-8 hours |
| Weekend protection | 24-48 hours |

## Activating Panic Mode

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

## During Panic Mode

### What's Blocked

Every domain in your blocklist is blocked, regardless of:
- Schedule (available hours ignored)
- Current time
- Pending unblock actions

### Hidden Commands

These commands become invisible:

| Command | Why Hidden |
|---------|------------|
| `unblock` | Would bypass panic |
| `pause` | Would pause blocking |
| `resume` | Not relevant |
| `allow` | Would create exceptions |
| `disallow` | Consistency |

Attempting to run them:

```bash
nextdns-blocker unblock reddit.com
# Error: Command 'unblock' is not available during panic mode
```

### What Still Works

- `status` - Check current state
- `config sync` - Runs but only blocks
- `config show` - View configuration
- `watchdog status` - Check automation
- `panic extend` - Add more time
- `panic status` - Check remaining time

## Checking Status

```bash
nextdns-blocker panic status
```

Output when active:
```
Panic Mode Status
━━━━━━━━━━━━━━━━━

Status: ACTIVE ⚠️

Activated: 2024-01-15 14:30:00
Expires: 2024-01-15 15:30:00
Remaining: 45 minutes

Hidden commands: unblock, pause, resume, allow, disallow
```

## Extending Duration

Need more protection? Extend:

```bash
nextdns-blocker panic extend 30
```

Output:
```
Panic mode extended by 30 minutes
New expiration: 2024-01-15 16:00:00
Remaining: 75 minutes
```

## Sync Behavior

During panic mode, sync:

1. **Blocks all domains** - Ignores schedules
2. **Skips unblocks** - No automatic unblocking
3. **Skips allowlist** - No exceptions
4. **Pauses pending actions** - Won't execute

This ensures complete lockdown.

## Pending Actions

Pending unblock actions during panic:
- **Timers continue** - Time still passes
- **Execution skipped** - Actions don't run
- **Resume after** - Execute when panic ends

## Why Can't I Cancel?

**This is intentional.**

The effectiveness of panic mode comes from its inescapability:
- No "just this once" temptation
- Can't talk yourself out of it
- Forces waiting

If you could cancel, you would during weak moments.

## After Panic Expires

When panic mode ends:
1. Normal schedule evaluation resumes
2. Hidden commands become visible
3. Allowlist sync resumes
4. Pending actions execute (if due)

## Technical Details

### State Storage

Panic state stored in:
- **macOS/Linux**: `~/.local/share/nextdns-blocker/.panic`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\.panic`

Contains ISO 8601 expiration timestamp.

### Minimum Duration

15 minutes minimum prevents:
- Accidental very short panics
- Using panic as quick pause
- Abuse of the feature

## Troubleshooting

### Panic not blocking domains

1. Force sync:
   ```bash
   nextdns-blocker sync
   ```

2. Check watchdog:
   ```bash
   nextdns-blocker watchdog status
   ```

### Domains still accessible

Might be:
- Cached in browser (clear cache)
- Cached in OS DNS (flush DNS)
- Not using NextDNS

Flush DNS:
```bash
# macOS
sudo dscacheutil -flushcache

# Linux
sudo systemctl restart systemd-resolved

# Windows
ipconfig /flushdns
```

### Need to end early (emergency)

**Not recommended**, but possible:

```bash
# Delete panic file (macOS/Linux)
rm ~/.local/share/nextdns-blocker/.panic

# Delete panic file (Windows)
del %LOCALAPPDATA%\nextdns-blocker\.panic
```

This defeats the purpose. Only use for genuine emergencies.

## Best Practices

1. **Use proactively** - Before urges peak, not during
2. **Start with longer durations** - Better safe than sorry
3. **Extend freely** - No shame in needing more time
4. **Combine with schedules** - Panic is backup, not primary
5. **Tell someone** - Accountability helps
