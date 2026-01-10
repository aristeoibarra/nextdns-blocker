---
title: Features Overview
description: Explore the key features of NextDNS Blocker
---

NextDNS Blocker provides powerful features for managing domain access and building healthier digital habits.

## Core Features

### Schedule-Based Blocking

Define when each domain is accessible:
- Per-domain schedules
- Multiple time ranges per day
- Different schedules for weekdays/weekends
- Overnight schedule support

[Learn about schedules →](/configuration/schedules/)

### Unblock Delays

Add friction against impulsive unblocking:
- Configurable delays (30m, 4h, 24h)
- Protected domains (`never`)
- Pending action management
- Easy cancellation

[Learn about unblock delays →](/configuration/unblock-delay/)

## Automation Features

### [Watchdog](/features/watchdog/)

Automatic synchronization:
- Runs every 2 minutes
- Self-healing (restores if deleted)
- Platform-native schedulers
- Can be temporarily disabled

### [Pending Actions](/features/pending-actions/)

Queued operations:
- Delayed unblock requests
- View pending queue
- Cancel before execution
- Automatic cleanup

## Safety Features

### [Panic Mode](/features/panic-mode/)

Emergency lockdown:
- Instant blocking of all domains
- Hidden dangerous commands
- Cannot be disabled early
- Extendable duration

## Security Features

### [PIN Protection](/reference/security/)

Optional authentication layer:
- Protect sensitive commands
- Session-based verification
- Brute-force protection
- Delayed PIN removal (24h)

### [Protection Module](/reference/security/)

Addiction safety features:
- Locked items cannot be removed immediately
- Unlock requests require waiting period
- Pending unlock can be cancelled
- Auto-panic configuration

## Communication Features

### [Notifications](/features/notifications/)

Real-time alerts via multiple channels:
- Discord webhooks with rich embeds
- Telegram bot notifications
- Slack incoming webhooks
- Ntfy push notifications
- macOS native notifications

## Productivity Features

### [Shell Completion](/features/shell-completion/)

Tab completion for:
- Commands and subcommands
- Domain names from config
- Pending action IDs
- Bash, Zsh, and Fish support

### [Dry Run Mode](/features/dry-run/)

Preview without changes:
- See what sync would do
- Test schedule logic
- Validate configuration
- Debug issues safely

### [Usage Analytics](/commands/stats/)

Track blocking patterns:
- Domain-level statistics
- Effectiveness scores
- Hourly activity patterns
- CSV export for analysis

## Feature Matrix

| Feature | Purpose | Command |
|---------|---------|---------|
| Schedules | Automatic access control | `config sync` |
| Delays | Impulse protection | `unblock` |
| Watchdog | Auto-sync | `watchdog install` |
| Panic Mode | Emergency lockdown | `panic 60` |
| PIN Protection | Command authentication | `protection pin set` |
| Notifications | Real-time alerts | (automatic) |
| Analytics | Usage patterns | `stats` |
| Completion | Productivity | `completion bash` |
| Dry Run | Safe testing | `sync --dry-run` |

## Feature Interactions

### Panic Mode + Everything

Panic mode overrides all other features:
- Schedules ignored
- Unblock delays irrelevant (`unblock` hidden)
- Allowlist sync skipped
- Pending actions paused

### Pause + Sync

During pause:
- Sync runs normally
- Blocking actions skipped
- Resume re-enables blocking

### Watchdog + Pending Actions

Watchdog processes pending actions:
- Checks every 2 minutes
- Executes due actions
- Cleans up old actions

### PIN + Protected Commands

When PIN is enabled:
- Sensitive commands require verification
- Session lasts 30 minutes
- Lockout after failed attempts
- Works alongside panic mode

## Enabling Features

| Feature | How to Enable |
|---------|---------------|
| Schedules | Add to `config.json` |
| Delays | Set `unblock_delay` in config |
| Watchdog | `watchdog install` |
| Panic Mode | `panic DURATION` |
| PIN Protection | `protection pin set` |
| Notifications | Add to `config.json` |
| Analytics | Automatic (uses audit log) |
| Completion | `completion bash/zsh/fish` |
| Dry Run | `--dry-run` flag |
