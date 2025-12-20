---
title: Platform Overview
description: NextDNS Blocker platform support and differences
---

NextDNS Blocker runs on macOS, Linux, Windows, and Docker with platform-specific optimizations.

## Supported Platforms

| Platform | Scheduler | Status |
|----------|-----------|--------|
| macOS | launchd | Full support |
| Linux | cron | Full support |
| Windows | Task Scheduler | Full support |
| WSL | cron | Full support |
| Docker | Built-in cron | Full support |

## Platform Detection

NextDNS Blocker automatically detects your platform and uses the appropriate scheduler:

```bash
nextdns-blocker watchdog status
```

Shows:
```
Platform: macOS (launchd)
# or
Platform: Linux (cron)
# or
Platform: Windows (Task Scheduler)
```

## Key Differences

### File Locations

| Component | macOS/Linux | Windows |
|-----------|-------------|---------|
| Config | `~/.config/nextdns-blocker/` | `%APPDATA%\nextdns-blocker\` |
| Data | `~/.local/share/nextdns-blocker/` | `%LOCALAPPDATA%\nextdns-blocker\` |
| Logs | `~/.local/share/nextdns-blocker/logs/` | `%LOCALAPPDATA%\nextdns-blocker\logs\` |

### Scheduler Behavior

| Aspect | macOS | Linux | Windows |
|--------|-------|-------|---------|
| Service | launchd | cron | Task Scheduler |
| Interval | 2 minutes | 2 minutes | 2 minutes |
| User scope | Per-user | Per-user | Per-user |
| Boot start | Automatic | Requires config | Automatic |

### File Permissions

| Platform | Sensitive Files |
|----------|-----------------|
| macOS/Linux | `chmod 600` (owner only) |
| Windows | User ACL (default) |

## Platform Guides

### [macOS](/platforms/macos/)
- launchd configuration
- Homebrew installation
- System permissions
- Troubleshooting

### [Linux](/platforms/linux/)
- cron setup
- Distribution specifics
- systemd integration
- WSL considerations

### [Windows](/platforms/windows/)
- Task Scheduler setup
- PowerShell installer
- Path considerations
- Troubleshooting

### [Docker](/platforms/docker/)
- Container setup
- docker-compose configuration
- Environment variables
- Persistent storage

## Installation Quick Reference

### macOS

```bash
brew tap aristeoibarra/tap
brew install nextdns-blocker
nextdns-blocker init
nextdns-blocker watchdog install
```

### Linux

```bash
pip install nextdns-blocker
nextdns-blocker init
nextdns-blocker watchdog install
```

### Windows

```powershell
pip install nextdns-blocker
nextdns-blocker init
nextdns-blocker watchdog install
```

Or use the PowerShell installer:
```powershell
irm https://raw.githubusercontent.com/aristeoibarra/nextdns-blocker/main/install.ps1 | iex
```

### Docker

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
cp .env.example .env
cp config.json.example config.json
docker compose up -d
```

## Cross-Platform Considerations

### Configuration Portability

`config.json` is portable across platforms:
- Same format everywhere
- Copy between machines
- Version control friendly

`.env` may need adjustment:
- Timezone detection differs
- Path formats vary

### Timezone Handling

| Platform | Auto-Detection |
|----------|----------------|
| macOS | `/etc/localtime` symlink |
| Linux | `/etc/localtime` symlink |
| Windows | `tzutil /g` command |
| Docker | `TZ` environment variable |

### Command Differences

Commands are identical across platforms. Only internal behavior differs:
- Path separators handled automatically
- File permissions adapted to platform
- Scheduler commands platform-specific
