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

## Communication Features

### [Discord Notifications](/features/notifications/)

Real-time alerts:
- Block/unblock events
- Panic mode activation
- Pending action status
- Color-coded embeds

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

## Feature Matrix

| Feature | Purpose | Command |
|---------|---------|---------|
| Schedules | Automatic access control | `config sync` |
| Delays | Impulse protection | `unblock` |
| Watchdog | Auto-sync | `watchdog install` |
| Panic Mode | Emergency lockdown | `panic 60` |
| Notifications | Real-time alerts | (automatic) |
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

## Enabling Features

| Feature | How to Enable |
|---------|---------------|
| Schedules | Add to `config.json` |
| Delays | Set `unblock_delay` in config |
| Watchdog | `watchdog install` |
| Panic Mode | `panic DURATION` |
| Notifications | Configure `.env` |
| Completion | `completion bash/zsh/fish` |
| Dry Run | `--dry-run` flag |
