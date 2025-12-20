---
title: macOS
description: NextDNS Blocker setup and usage on macOS
---

NextDNS Blocker has excellent support for macOS, using launchd for scheduling.

## Installation

### Homebrew (Recommended)

```bash
# Add tap
brew tap aristeoibarra/tap

# Install
brew install nextdns-blocker

# Verify
nextdns-blocker --version
```

### pip

```bash
pip3 install nextdns-blocker
```

### pipx (Isolated)

```bash
pipx install nextdns-blocker
```

## Setup

```bash
# Initialize configuration
nextdns-blocker init

# Configure domains
nextdns-blocker config edit

# Install watchdog
nextdns-blocker watchdog install
```

## launchd Integration

### How It Works

NextDNS Blocker creates launchd jobs for automatic syncing:

| Job | Purpose | Interval |
|-----|---------|----------|
| `com.nextdns-blocker.sync` | Run sync | Every 2 minutes |
| `com.nextdns-blocker.watchdog` | Self-heal | Every 5 minutes |

### Job Location

```
~/Library/LaunchAgents/
├── com.nextdns-blocker.sync.plist
└── com.nextdns-blocker.watchdog.plist
```

### Managing Jobs

```bash
# Check status
nextdns-blocker watchdog status

# View loaded jobs
launchctl list | grep nextdns

# Unload job manually
launchctl unload ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist

# Load job manually
launchctl load ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist
```

### Job Contents

Example plist:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "...">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nextdns-blocker.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/nextdns-blocker</string>
        <string>sync</string>
    </array>
    <key>StartInterval</key>
    <integer>120</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>~/.local/share/nextdns-blocker/logs/cron.log</string>
    <key>StandardErrorPath</key>
    <string>~/.local/share/nextdns-blocker/logs/cron.log</string>
</dict>
</plist>
```

## File Locations

| Component | Path |
|-----------|------|
| Config | `~/.config/nextdns-blocker/config.json` |
| Environment | `~/.config/nextdns-blocker/.env` |
| Logs | `~/.local/share/nextdns-blocker/logs/` |
| State | `~/.local/share/nextdns-blocker/` |
| launchd jobs | `~/Library/LaunchAgents/` |

## Timezone Detection

macOS timezone is detected from:

```bash
# System timezone link
readlink /etc/localtime
# Returns: /var/db/timezone/zoneinfo/America/New_York
```

To verify:
```bash
nextdns-blocker config show | grep timezone
```

## Homebrew Updates

```bash
# Update formula
brew update

# Upgrade package
brew upgrade nextdns-blocker

# After upgrade, reinstall watchdog if needed
nextdns-blocker watchdog install
```

## Permissions

### Full Disk Access

Some operations may require Full Disk Access:

1. Open **System Preferences** → **Security & Privacy**
2. Go to **Privacy** tab
3. Select **Full Disk Access**
4. Add **Terminal** (or your terminal app)

### Gatekeeper

If blocked by Gatekeeper:
1. Open **System Preferences** → **Security & Privacy**
2. Click **Open Anyway** if prompted

## DNS Cache

Flush DNS cache after blocking changes:

```bash
sudo dscacheutil -flushcache
sudo killall -HUP mDNSResponder
```

## Troubleshooting

### launchd Jobs Not Running

```bash
# Check if loaded
launchctl list | grep nextdns

# Check for errors
cat ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist

# Check logs
tail -50 ~/.local/share/nextdns-blocker/logs/cron.log
```

### Command Not Found

```bash
# Check PATH
echo $PATH

# Common Homebrew paths
# Apple Silicon: /opt/homebrew/bin
# Intel: /usr/local/bin

# Add to PATH if needed (in ~/.zshrc)
export PATH="/opt/homebrew/bin:$PATH"
```

### Permissions Errors

```bash
# Fix config permissions
chmod 600 ~/.config/nextdns-blocker/.env
chmod 600 ~/.config/nextdns-blocker/config.json
```

### Jobs Disappearing

If launchd jobs keep disappearing:

1. Check for cleanup tools (CleanMyMac, etc.)
2. Add exclusion for `com.nextdns-blocker.*`
3. The watchdog job should auto-restore sync job

### Python Not Found

```bash
# Check Python version
python3 --version

# If using Homebrew Python
brew install python@3.11

# Link if needed
brew link python@3.11
```

## Apple Silicon Notes

### Homebrew Path

Apple Silicon Macs use `/opt/homebrew/bin`:

```bash
# Check path
which nextdns-blocker
# Should show: /opt/homebrew/bin/nextdns-blocker
```

### Rosetta Not Required

NextDNS Blocker is pure Python and runs natively on Apple Silicon.

## Uninstalling

```bash
# Remove watchdog jobs
nextdns-blocker watchdog uninstall

# Remove via Homebrew
brew uninstall nextdns-blocker

# Remove configuration (optional)
rm -rf ~/.config/nextdns-blocker

# Remove data (optional)
rm -rf ~/.local/share/nextdns-blocker
```
