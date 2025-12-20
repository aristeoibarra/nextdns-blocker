---
title: Windows
description: NextDNS Blocker setup and usage on Windows
---

NextDNS Blocker fully supports Windows, using Task Scheduler for automatic syncing.

## Installation

### PowerShell Installer (Recommended)

```powershell
# Download and run installer
irm https://raw.githubusercontent.com/aristeoibarra/nextdns-blocker/main/install.ps1 | iex
```

The installer:
1. Checks for Python
2. Installs nextdns-blocker via pip
3. Runs the setup wizard
4. Configures Task Scheduler

### pip

```powershell
pip install nextdns-blocker
```

### From Source

```powershell
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
pip install -e .
```

## Setup

```powershell
# Initialize configuration
nextdns-blocker init

# Configure domains
nextdns-blocker config edit

# Install watchdog
nextdns-blocker watchdog install
```

## Task Scheduler Integration

### How It Works

NextDNS Blocker creates scheduled tasks:

| Task | Purpose | Interval |
|------|---------|----------|
| `NextDNS-Blocker-Sync` | Run sync | Every 2 minutes |
| `NextDNS-Blocker-Watchdog` | Self-heal | Every 5 minutes |

### Viewing Tasks

```powershell
# Command line
schtasks /query /tn "NextDNS-Blocker-Sync"
schtasks /query /tn "NextDNS-Blocker-Watchdog"

# GUI
taskschd.msc
```

### Managing Tasks

```powershell
# Check status via CLI
nextdns-blocker watchdog status

# Run task manually
schtasks /run /tn "NextDNS-Blocker-Sync"

# Delete task manually (if needed)
schtasks /delete /tn "NextDNS-Blocker-Sync" /f
```

## File Locations

| Component | Path |
|-----------|------|
| Config | `%APPDATA%\nextdns-blocker\config.json` |
| Environment | `%APPDATA%\nextdns-blocker\.env` |
| Logs | `%LOCALAPPDATA%\nextdns-blocker\logs\` |
| State | `%LOCALAPPDATA%\nextdns-blocker\` |

### Viewing Paths

```powershell
# Config directory
explorer $env:APPDATA\nextdns-blocker

# Data directory
explorer $env:LOCALAPPDATA\nextdns-blocker
```

## Timezone Detection

Windows timezone is detected via:

```powershell
tzutil /g
# Returns: Eastern Standard Time
```

Mapped to IANA format (e.g., `America/New_York`).

## PowerShell Notes

### Execution Policy

If scripts are blocked:

```powershell
# Check current policy
Get-ExecutionPolicy

# Allow scripts for current user
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Running Commands

```powershell
# Standard execution
nextdns-blocker status

# If not in PATH
python -m nextdns_blocker status
```

## Path Configuration

### Adding to PATH

If `nextdns-blocker` isn't found:

```powershell
# Find installation location
pip show nextdns-blocker

# Common locations:
# %USERPROFILE%\AppData\Local\Programs\Python\Python311\Scripts
# %USERPROFILE%\AppData\Roaming\Python\Python311\Scripts

# Add to PATH (PowerShell)
$env:Path += ";$env:USERPROFILE\AppData\Local\Programs\Python\Python311\Scripts"

# Permanent (User Environment Variables)
# System Properties → Advanced → Environment Variables → Path → Edit
```

## DNS Cache

Flush Windows DNS cache:

```powershell
ipconfig /flushdns
```

## Viewing Logs

```powershell
# Application log
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\app.log" -Tail 50

# Sync log
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\sync.log" -Tail 50

# Follow logs
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\app.log" -Wait
```

## Troubleshooting

### Task Scheduler Not Running

```powershell
# Check Task Scheduler service
Get-Service Schedule

# Start if stopped
Start-Service Schedule

# Check task status
schtasks /query /tn "NextDNS-Blocker-Sync" /v
```

### Command Not Found

```powershell
# Check if Python is in PATH
python --version

# Try running via Python
python -m nextdns_blocker status

# Find pip installation
pip show nextdns-blocker | Select-String Location
```

### Paths with Spaces

Windows usernames with spaces are handled automatically. If issues occur:

```powershell
# Check for special characters in username
$env:USERNAME

# Avoid characters: < > | & " '
```

### Access Denied Errors

Run PowerShell as Administrator for initial setup:

1. Right-click PowerShell
2. Select "Run as administrator"
3. Run `nextdns-blocker watchdog install`

### Python Not Found

1. Download from [python.org](https://www.python.org/downloads/)
2. During install, check **"Add Python to PATH"**
3. Restart PowerShell

### Tasks Disappearing

If scheduled tasks keep disappearing:

1. Check antivirus software
2. Check Group Policy restrictions
3. Ensure Task Scheduler service is running

The watchdog task should restore the sync task automatically.

## Windows Defender

If blocked by Windows Defender:

1. Open Windows Security
2. Go to Virus & threat protection
3. Manage settings → Exclusions
4. Add exclusion for:
   - `%APPDATA%\nextdns-blocker\`
   - `%LOCALAPPDATA%\nextdns-blocker\`
   - Python installation directory

## File Permissions

Windows uses ACLs instead of Unix permissions:
- Config files are created with user-only access
- No special chmod needed
- Check file properties for permissions

## Uninstalling

```powershell
# Remove scheduled tasks
nextdns-blocker watchdog uninstall

# Or manually
schtasks /delete /tn "NextDNS-Blocker-Sync" /f
schtasks /delete /tn "NextDNS-Blocker-Watchdog" /f

# Remove package
pip uninstall nextdns-blocker

# Remove configuration
Remove-Item -Recurse "$env:APPDATA\nextdns-blocker"

# Remove data
Remove-Item -Recurse "$env:LOCALAPPDATA\nextdns-blocker"
```

## Running at Startup

Task Scheduler tasks run when you log in. For service-level operation (before login), you'd need:

1. Create a Windows Service wrapper
2. Use NSSM (Non-Sucking Service Manager)
3. Or accept user-session-only operation

For most use cases, user-session operation is sufficient.
