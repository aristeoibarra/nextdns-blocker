---
title: File Locations
description: Where NextDNS Blocker stores files on each platform
---

NextDNS Blocker stores files in platform-appropriate locations following XDG and Windows conventions.

## Directory Overview

| Type | macOS/Linux | Windows |
|------|-------------|---------|
| Config | `~/.config/nextdns-blocker/` | `%APPDATA%\nextdns-blocker\` |
| Data | `~/.local/share/nextdns-blocker/` | `%LOCALAPPDATA%\nextdns-blocker\` |
| Logs | `~/.local/share/nextdns-blocker/logs/` | `%LOCALAPPDATA%\nextdns-blocker\logs\` |
| Cache | `~/.cache/nextdns-blocker/` | `%LOCALAPPDATA%\nextdns-blocker\cache\` |

## Configuration Directory

### Location

| Platform | Path |
|----------|------|
| macOS | `~/.config/nextdns-blocker/` |
| Linux | `~/.config/nextdns-blocker/` |
| Windows | `C:\Users\<user>\AppData\Roaming\nextdns-blocker\` |

### Contents

| File | Purpose | Permissions |
|------|---------|-------------|
| `config.json` | Domain schedules, blocklist, allowlist | 0600 |
| `.env` | API credentials, environment settings | 0600 |

### View Path

```bash
# macOS/Linux
echo ~/.config/nextdns-blocker/

# Windows PowerShell
echo $env:APPDATA\nextdns-blocker\
```

## Data Directory

### Location

| Platform | Path |
|----------|------|
| macOS | `~/.local/share/nextdns-blocker/` |
| Linux | `~/.local/share/nextdns-blocker/` |
| Windows | `C:\Users\<user>\AppData\Local\nextdns-blocker\` |

### Contents

| File | Purpose | Description |
|------|---------|-------------|
| `.paused` | Pause state | ISO timestamp when pause expires |
| `.panic` | Panic state | ISO timestamp when panic expires |
| `.pin_hash` | PIN protection | Salted hash of PIN (if enabled) |
| `.pin_session` | PIN session | Session expiration timestamp |
| `.pin_attempts` | PIN attempts | Failed attempt tracking for lockout |
| `.cannot_disable_lock` | Protection lock | Persistent cannot_disable state |
| `pending.json` | Pending actions | Queue of delayed unblocks |
| `unlock_requests.json` | Unlock requests | Pending unlock requests for protected items |
| `logs/` | Log directory | Application and audit logs |

### View Path

```bash
# macOS/Linux
echo ~/.local/share/nextdns-blocker/

# Windows PowerShell
echo $env:LOCALAPPDATA\nextdns-blocker\
```

## Log Directory

### Location

| Platform | Path |
|----------|------|
| macOS | `~/.local/share/nextdns-blocker/logs/` |
| Linux | `~/.local/share/nextdns-blocker/logs/` |
| Windows | `C:\Users\<user>\AppData\Local\nextdns-blocker\logs\` |

### Contents

| File | Purpose | Rotation |
|------|---------|----------|
| `app.log` | Application events | Daily, 7 days |
| `audit.log` | Block/unblock actions | Weekly, 12 weeks |
| `cron.log` | Watchdog sync output | Daily, 7 days |
| `wd.log` | Watchdog self-check | Daily, 7 days |
| `sync.log` | Sync operation details | Daily, 7 days |

## Scheduler Locations

### macOS (launchd)

| File | Path |
|------|------|
| Sync job | `~/Library/LaunchAgents/com.nextdns-blocker.sync.plist` |
| Watchdog job | `~/Library/LaunchAgents/com.nextdns-blocker.watchdog.plist` |

### Linux (cron)

Entries in user's crontab:
```bash
crontab -l
```

### Windows (Task Scheduler)

Tasks visible in:
- `taskschd.msc` GUI
- `schtasks /query` command

Task names:
- `NextDNS-Blocker-Sync`
- `NextDNS-Blocker-Watchdog`

## File Formats

### config.json

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [...],
  "allowlist": [...]
}
```

### .env

```bash
NEXTDNS_API_KEY=your_key
NEXTDNS_PROFILE_ID=your_id
API_TIMEOUT=10
```

### pending.json

```json
{
  "actions": [
    {
      "id": "pnd_20240115_143000_a1b2c3",
      "domain": "example.com",
      "created_at": "2024-01-15T14:30:00",
      "execute_at": "2024-01-16T14:30:00",
      "delay": "24h",
      "status": "pending"
    }
  ]
}
```

### .paused / .panic

Plain text ISO 8601 timestamp:
```
2024-01-15T15:30:00
```

## XDG Compliance

On Linux, NextDNS Blocker respects XDG environment variables:

| Variable | Default | Used For |
|----------|---------|----------|
| `XDG_CONFIG_HOME` | `~/.config` | Configuration |
| `XDG_DATA_HOME` | `~/.local/share` | Data and logs |
| `XDG_CACHE_HOME` | `~/.cache` | Cache |

Example override:
```bash
export XDG_CONFIG_HOME=/custom/config
nextdns-blocker init  # Uses /custom/config/nextdns-blocker/
```

## Backup Recommendations

### Essential Files

Always backup:
- `config.json` - Your schedules and settings
- `.env` - Your credentials

### Optional Files

May want to backup:
- `pending.json` - Pending unblock actions
- `audit.log` - History of actions

### Backup Command

```bash
# macOS/Linux
tar -czf nextdns-backup.tar.gz \
  ~/.config/nextdns-blocker/ \
  ~/.local/share/nextdns-blocker/pending.json

# Windows PowerShell
Compress-Archive -Path "$env:APPDATA\nextdns-blocker", "$env:LOCALAPPDATA\nextdns-blocker\pending.json" -DestinationPath nextdns-backup.zip
```

## Permissions

### Unix (macOS/Linux)

| File | Permissions | Meaning |
|------|-------------|---------|
| `.env` | `0600` | Owner read/write only |
| `config.json` | `0600` | Owner read/write only |
| `*.log` | `0644` | Owner read/write, others read |

### Windows

Files are created with user-only ACL by default.

## Cleanup

### Remove All Data

```bash
# macOS/Linux
rm -rf ~/.config/nextdns-blocker
rm -rf ~/.local/share/nextdns-blocker
rm -rf ~/.cache/nextdns-blocker

# Windows PowerShell
Remove-Item -Recurse "$env:APPDATA\nextdns-blocker"
Remove-Item -Recurse "$env:LOCALAPPDATA\nextdns-blocker"
```

### Keep Config, Remove State

```bash
# macOS/Linux
rm ~/.local/share/nextdns-blocker/.paused
rm ~/.local/share/nextdns-blocker/.panic
echo '{"actions":[]}' > ~/.local/share/nextdns-blocker/pending.json
```
