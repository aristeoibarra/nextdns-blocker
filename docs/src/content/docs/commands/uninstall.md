---
title: uninstall
description: Completely remove NextDNS Blocker and all its data
---

The `uninstall` command performs a complete removal of NextDNS Blocker, including scheduled jobs, configuration files, and all data.

## Usage

```bash
nextdns-blocker uninstall [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |
| `--help` | Show help message |

## What It Removes

### 1. Scheduled Jobs

Removes all automatic sync jobs:
- **macOS**: Unloads and deletes launchd plist files
- **Linux**: Removes cron entries
- **Windows**: Deletes Task Scheduler tasks

### 2. Configuration Directory

Deletes the entire config directory containing:
- `.env` file (API credentials)
- `config.json` (domain configuration)
- Any backup files

Default locations:
- **macOS/Linux**: `~/.config/nextdns-blocker/`
- **Windows**: `%APPDATA%\nextdns-blocker\`

### 3. Data Directory

Deletes the data directory containing:
- Audit logs
- Cache files
- Pending actions state

Default locations:
- **macOS/Linux**: `~/.local/share/nextdns-blocker/`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\`

## Example

### Interactive Uninstall

```bash
nextdns-blocker uninstall
```

Output:
```
  NextDNS Blocker Uninstall
  -------------------------

  This will permanently delete:
    • Scheduled jobs (watchdog)
    • Config: /Users/you/.config/nextdns-blocker
    • Data: /Users/you/.local/share/nextdns-blocker

  Are you sure you want to continue? [y/N]: y

  Removing...
    [1/3] Removing scheduled jobs...
          Done
    [2/3] Removing config directory...
          Done
    [3/3] Removing data directory...
          Done

  Uninstall complete!
  To remove the package itself, run:
    brew uninstall nextdns-blocker  (Homebrew)
    pipx uninstall nextdns-blocker  (pipx)
    pip uninstall nextdns-blocker   (pip)
```

### Silent Uninstall

Skip the confirmation prompt:

```bash
nextdns-blocker uninstall --yes
```

## Complete Removal

After running `uninstall`, remove the package itself:

### Homebrew

```bash
brew uninstall nextdns-blocker
```

### pipx

```bash
pipx uninstall nextdns-blocker
```

### pip

```bash
pip uninstall nextdns-blocker
```

## What Remains After Uninstall

The `uninstall` command removes all NextDNS Blocker data, but:

1. **NextDNS account unchanged** - Your NextDNS profile and denylist remain
2. **Domains still blocked** - Manually added domains stay in NextDNS
3. **Package still installed** - You need to remove it separately

### To Clear NextDNS Denylist

Before uninstalling, you can clear all blocked domains:

```bash
# Edit config to empty blocklist
nextdns-blocker config edit
# Remove all entries from blocklist

# Run sync to remove from NextDNS
nextdns-blocker config push

# Then uninstall
nextdns-blocker uninstall
```

Or manually clear via [NextDNS Dashboard](https://my.nextdns.io).

## Reinstalling

To reinstall after uninstalling:

```bash
# Reinstall package
brew install nextdns-blocker  # or pipx/pip

# Run setup wizard
nextdns-blocker init
```

You'll need to reconfigure everything from scratch.

## Backup Before Uninstall

To save your configuration before uninstalling:

```bash
# Backup config
cp ~/.config/nextdns-blocker/config.json ~/nextdns-backup.json
cp ~/.config/nextdns-blocker/.env ~/nextdns-backup.env

# Uninstall
nextdns-blocker uninstall
```

## Scripting

For automated deployments:

```bash
#!/bin/bash
# Complete removal script
nextdns-blocker uninstall --yes
pip uninstall nextdns-blocker --yes
echo "NextDNS Blocker completely removed"
```

## Troubleshooting

### Permission denied

```
[2/3] Removing config directory...
      Error: Permission denied
```

**Solution**: Check file ownership or run with appropriate permissions.

### Scheduled jobs warning

```
[1/3] Removing scheduled jobs...
      Warning: Job not found
```

This is normal if the watchdog was never installed or was already removed.

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Uninstall successful (or cancelled) |
| 1 | Error during removal (partial uninstall) |

## Related Commands

| Command | Description |
|---------|-------------|
| `watchdog uninstall` | Remove only scheduled jobs |
| `init` | Set up fresh installation |
| `fix` | Repair without removing |
