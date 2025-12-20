---
title: Watchdog
description: Automatic synchronization with self-healing capabilities
---

The watchdog ensures your blocking rules are enforced automatically, even if something tries to disable it.

## What is the Watchdog?

The watchdog is a background process that:

1. **Runs sync every 2 minutes** - Enforces your schedules
2. **Self-heals** - Restores itself if deleted
3. **Uses native schedulers** - launchd, cron, Task Scheduler
4. **Logs activity** - Track what's happening

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     Platform Scheduler                       │
│              (launchd / cron / Task Scheduler)              │
└─────────────────────────────────────────────────────────────┘
                    │                    │
                    ▼                    ▼
         ┌─────────────────┐   ┌─────────────────┐
         │    Sync Job     │   │  Watchdog Job   │
         │  (every 2 min)  │   │  (every 5 min)  │
         └─────────────────┘   └─────────────────┘
                    │                    │
                    ▼                    ▼
         ┌─────────────────┐   ┌─────────────────┐
         │ nextdns-blocker │   │  Check if sync  │
         │      sync       │   │   job exists    │
         └─────────────────┘   └─────────────────┘
                                        │
                                        ▼
                               ┌─────────────────┐
                               │  Restore sync   │
                               │  job if missing │
                               └─────────────────┘
```

### Two Jobs

1. **Sync Job**: Runs `nextdns-blocker sync` every 2 minutes
2. **Watchdog Job**: Checks sync job exists every 5 minutes, restores if missing

## Installing Watchdog

```bash
nextdns-blocker watchdog install
```

Output:
```
Installing watchdog jobs...

Platform: macOS (launchd)

Creating jobs:
  ✓ NextDNS-Blocker-Sync (every 2 minutes)
  ✓ NextDNS-Blocker-Watchdog (every 5 minutes)

Jobs installed successfully
```

## Checking Status

```bash
nextdns-blocker watchdog status
```

Output:
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

## Platform-Specific Details

### macOS (launchd)

Jobs created as plist files:

**Location**: `~/Library/LaunchAgents/`

**Files**:
- `com.nextdns-blocker.sync.plist`
- `com.nextdns-blocker.watchdog.plist`

**Commands**:
```bash
# View jobs
ls ~/Library/LaunchAgents/com.nextdns-blocker.*

# Check status
launchctl list | grep nextdns

# Manual load/unload
launchctl load ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist
launchctl unload ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist
```

### Linux (cron)

Jobs added to user crontab:

**View**:
```bash
crontab -l
```

**Expected entries**:
```
*/2 * * * * /path/to/nextdns-blocker sync >> ~/.local/share/nextdns-blocker/logs/cron.log 2>&1
*/5 * * * * /path/to/nextdns-blocker watchdog check >> ~/.local/share/nextdns-blocker/logs/wd.log 2>&1
```

**Check cron service**:
```bash
systemctl status cron
# or
systemctl status crond
```

### Windows (Task Scheduler)

Tasks created in Task Scheduler:

**View**:
```powershell
# Command line
schtasks /query /tn "NextDNS-Blocker-Sync"
schtasks /query /tn "NextDNS-Blocker-Watchdog"

# GUI
taskschd.msc
```

**Manual run**:
```powershell
schtasks /run /tn "NextDNS-Blocker-Sync"
```

## Disabling Temporarily

Need to pause automatic syncing:

```bash
# Disable for 1 hour
nextdns-blocker watchdog disable 1

# Disable for 4 hours
nextdns-blocker watchdog disable 4

# Disable permanently (until re-enabled)
nextdns-blocker watchdog disable
```

### Re-enabling

```bash
nextdns-blocker watchdog enable
```

## Uninstalling

Remove all watchdog jobs:

```bash
nextdns-blocker watchdog uninstall
```

Use before:
- Uninstalling NextDNS Blocker
- Switching to Docker deployment
- Debugging issues

## Log Files

### Sync Log

Output from sync executions:

```bash
tail -f ~/.local/share/nextdns-blocker/logs/cron.log
```

### Watchdog Log

Watchdog events (job restoration):

```bash
tail -f ~/.local/share/nextdns-blocker/logs/wd.log
```

### Log Locations

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.local/share/nextdns-blocker/logs/` |
| Windows | `%LOCALAPPDATA%\nextdns-blocker\logs\` |

## Self-Healing

### How It Works

1. Watchdog job runs every 5 minutes
2. Checks if sync job exists
3. If missing, recreates it
4. Logs recovery event

### Why Self-Healing?

Prevents circumvention:
- Manual deletion of cron jobs
- Accidental removal
- System cleanup tools
- Other users on shared systems

### Recovery Log

```
2024-01-15 14:35:00 - Sync job missing, restoring...
2024-01-15 14:35:01 - Sync job restored successfully
```

## Troubleshooting

### Watchdog not running

1. **Check status**:
   ```bash
   nextdns-blocker watchdog status
   ```

2. **Reinstall**:
   ```bash
   nextdns-blocker watchdog uninstall
   nextdns-blocker watchdog install
   ```

3. **Check scheduler service**:
   ```bash
   # Linux
   systemctl status cron

   # macOS
   launchctl list | grep nextdns
   ```

### Sync not executing

1. **Check logs**:
   ```bash
   tail -20 ~/.local/share/nextdns-blocker/logs/cron.log
   ```

2. **Test manually**:
   ```bash
   nextdns-blocker sync --verbose
   ```

3. **Check executable path**:
   ```bash
   which nextdns-blocker
   ```

### Permission issues

**macOS**:
- Grant Full Disk Access to Terminal (System Preferences → Security)

**Linux**:
- Check crontab ownership
- Verify executable permissions

**Windows**:
- Run PowerShell as Administrator for initial setup
- Check Task Scheduler permissions

### Jobs keep disappearing

Both jobs disappearing indicates system-level issue:

1. Check antivirus/security software
2. Verify user has scheduler access
3. Check for system cleanup tools
4. Review system logs for errors

## Best Practices

1. **Always install watchdog** - Manual sync is unreliable
2. **Check status weekly** - Verify it's running
3. **Monitor logs** - Catch issues early
4. **Don't disable long-term** - Re-enable after debugging
5. **Test after system updates** - May need reinstall
