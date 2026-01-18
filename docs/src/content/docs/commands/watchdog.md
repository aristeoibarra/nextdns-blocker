---
title: watchdog
description: Manage automatic synchronization with platform-specific schedulers
---

The `watchdog` command group manages automatic synchronization using your platform's native scheduler.

## Overview

The watchdog:
- Runs `config push` every 2 minutes
- Uses platform-native schedulers (launchd, cron, Task Scheduler)
- Restores itself if removed
- Can be temporarily disabled

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `status` | Check scheduler status |
| `install` | Create scheduled sync jobs |
| `uninstall` | Remove scheduled jobs |
| `enable` | Re-enable after disable |
| `disable` | Temporarily disable |

## watchdog status

Check if the watchdog is running and view its status.

### Usage

```bash
nextdns-blocker watchdog status
```

### Output

```
Watchdog Status
━━━━━━━━━━━━━━━

Platform: macOS (launchd)
Status: Active ✓

Jobs:
  NextDNS-Blocker-Sync
    Schedule: Every 2 minutes
    Last run: 2024-01-15 14:28:00
    Next run: 2024-01-15 14:30:00

  NextDNS-Blocker-Watchdog
    Schedule: Every 5 minutes
    Purpose: Ensures sync job exists
```

### Status Values

| Status | Meaning |
|--------|---------|
| Active | Jobs are scheduled and running |
| Inactive | Jobs not installed |
| Disabled | Temporarily disabled by user |
| Error | Jobs exist but have issues |

## watchdog install

Create the scheduled synchronization jobs.

### Usage

```bash
nextdns-blocker watchdog install
```

### Output

```
Installing watchdog jobs...

Platform: macOS (launchd)

Creating jobs:
  ✓ NextDNS-Blocker-Sync (every 2 minutes)
  ✓ NextDNS-Blocker-Watchdog (every 5 minutes)

Jobs installed successfully
Location: ~/Library/LaunchAgents/

Run 'watchdog status' to verify
```

### Platform-Specific Behavior

| Platform | Scheduler | Location |
|----------|-----------|----------|
| macOS | launchd | `~/Library/LaunchAgents/` |
| Linux | cron | `crontab -l` |
| Windows | Task Scheduler | View in `taskschd.msc` |

## watchdog uninstall

Remove the scheduled jobs.

### Usage

```bash
nextdns-blocker watchdog uninstall
```

### Output

```
Removing watchdog jobs...

  ✓ NextDNS-Blocker-Sync removed
  ✓ NextDNS-Blocker-Watchdog removed

Watchdog uninstalled
Automatic syncing is now disabled
```

### When to Uninstall

- Before uninstalling NextDNS Blocker
- When switching to Docker or another deployment
- For debugging issues

## watchdog enable

Re-enable the watchdog after it was disabled.

### Usage

```bash
nextdns-blocker watchdog enable
```

### Output

```
Watchdog enabled ✓
Automatic syncing will resume immediately
```

## watchdog disable

Temporarily disable the watchdog.

### Usage

```bash
nextdns-blocker watchdog disable [HOURS]
```

### Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `HOURS` | Permanent | Hours to disable (1-24) |

### Examples

```bash
# Disable for 1 hour
nextdns-blocker watchdog disable 1

# Disable for 4 hours
nextdns-blocker watchdog disable 4

# Disable permanently (until manually enabled)
nextdns-blocker watchdog disable
```

### Output

```
Watchdog disabled for 4 hours
Re-enables at: 2024-01-15 18:30:00

Use 'watchdog enable' to re-enable early
```

### Use Cases

- Debugging sync issues
- Testing configuration changes manually
- Temporarily managing blocking manually

## How Watchdog Works

### Sync Job

Runs every 2 minutes:
1. Executes `nextdns-blocker config push`
2. Logs output to `cron.log`
3. Handles errors gracefully

### Watchdog Job

Runs every 5 minutes:
1. Checks if sync job exists
2. Recreates sync job if missing
3. Logs recovery events to `wd.log`

This self-healing mechanism ensures blocking continues even if the sync job is accidentally deleted.

## Log Files

| Log | Purpose | Location |
|-----|---------|----------|
| `cron.log` | Sync execution output | `~/.local/share/nextdns-blocker/logs/` |
| `wd.log` | Watchdog events | `~/.local/share/nextdns-blocker/logs/` |

### Viewing Logs

```bash
# Sync logs
tail -f ~/.local/share/nextdns-blocker/logs/cron.log

# Watchdog logs
tail -f ~/.local/share/nextdns-blocker/logs/wd.log
```

## Platform-Specific Details

### macOS (launchd)

Jobs are created as property list files:

```bash
# View installed jobs
ls ~/Library/LaunchAgents/com.nextdns-blocker.*

# View job details
plutil -p ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist

# Manually load/unload
launchctl load ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist
launchctl unload ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist
```

### Linux (cron)

Jobs are added to your user's crontab:

```bash
# View cron jobs
crontab -l

# Expected entries
*/2 * * * * /path/to/nextdns-blocker config push >> ~/.local/share/nextdns-blocker/logs/cron.log 2>&1
*/5 * * * * /path/to/nextdns-blocker watchdog check >> ~/.local/share/nextdns-blocker/logs/wd.log 2>&1
```

### Windows (Task Scheduler)

Tasks are created in Task Scheduler:

```powershell
# List tasks
schtasks /query /tn "NextDNS-Blocker-Sync"
schtasks /query /tn "NextDNS-Blocker-Watchdog"

# Open Task Scheduler GUI
taskschd.msc

# Manually run
schtasks /run /tn "NextDNS-Blocker-Sync"
```

## Troubleshooting

### Watchdog not running

1. Check status:
   ```bash
   nextdns-blocker watchdog status
   ```

2. Reinstall:
   ```bash
   nextdns-blocker watchdog uninstall
   nextdns-blocker watchdog install
   ```

### Sync not executing

1. Check logs:
   ```bash
   tail -20 ~/.local/share/nextdns-blocker/logs/cron.log
   ```

2. Test sync manually:
   ```bash
   nextdns-blocker config push --verbose
   ```

3. Check scheduler service:
   ```bash
   # Linux
   systemctl status cron

   # macOS
   launchctl list | grep nextdns
   ```

### Jobs keep disappearing

This might indicate permission issues. Check:

1. Crontab permissions (Linux)
2. LaunchAgents folder permissions (macOS)
3. Task Scheduler service is running (Windows)

The watchdog job should automatically restore the sync job, but if both are disappearing, there's a system issue.
