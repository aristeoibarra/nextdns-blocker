---
title: fix
description: Automatically repair common issues with NextDNS Blocker
---

The `fix` command is a one-stop repair tool that diagnoses and fixes common issues with NextDNS Blocker. It reinstalls the scheduler, runs a sync, and verifies shell completion.

## Usage

```bash
nextdns-blocker fix
```

## What It Does

The fix command runs through 5 repair steps:

### Step 1: Check Configuration

Verifies that:
- `.env` file exists and is readable
- Required variables are present
- Configuration is valid

If this fails, you need to run `nextdns-blocker init` first.

### Step 2: Detect Installation

Identifies how NextDNS Blocker was installed:
- **module**: Running as Python module (`python -m nextdns_blocker`)
- **pipx**: Installed via pipx
- **system**: Installed via Homebrew or system pip

This determines how to invoke commands for repair.

### Step 3: Reinstall Scheduler

Removes and reinstalls the watchdog scheduler:
- **macOS**: Unloads and reloads launchd agents
- **Linux**: Removes and recreates cron jobs
- **Windows**: Deletes and recreates Task Scheduler tasks

This fixes issues where:
- Scheduler was corrupted
- System update broke scheduled tasks
- Scheduler was accidentally removed

### Step 4: Run Sync

Executes a full sync to:
- Apply current configuration
- Update NextDNS denylist
- Process any pending actions

This ensures the system is in a consistent state.

### Step 5: Check Shell Completion

Verifies and installs shell completion:
- Detects current shell (bash, zsh, fish)
- Checks if completion is installed
- Installs if missing (non-Windows only)

## Example

```bash
nextdns-blocker fix
```

Output:
```
  NextDNS Blocker Fix
  -------------------

  [1/5] Checking configuration...
        Config: OK
  [2/5] Detecting installation...
        Type: pipx
  [3/5] Reinstalling scheduler...
        Scheduler: OK
  [4/5] Running sync...
        Sync: OK
  [5/5] Checking shell completion...
        Completion: OK

  Fix complete!
```

## When to Use

Run `fix` when:

- **Sync stops working** - Scheduler may be broken
- **After OS update** - System tasks may need reinstalling
- **After package upgrade** - Paths may have changed
- **Watchdog not running** - Quick way to reinstall
- **Something feels wrong** - General repair tool

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All repairs successful |
| 1 | Configuration error (run `init` first) |
| 1 | Scheduler installation failed |

## Comparison with Other Commands

| Command | Purpose |
|---------|---------|
| `health` | Diagnose issues (read-only) |
| `fix` | Repair issues (makes changes) |
| `init` | Initial setup |
| `watchdog install` | Install scheduler only |

## Troubleshooting

### Config: FAILED

```
[1/5] Checking configuration...
      Config: FAILED - Missing .env file
```

**Solution**: Run `nextdns-blocker init` to set up configuration.

### Scheduler: FAILED

```
[3/5] Reinstalling scheduler...
      Scheduler: FAILED - Permission denied
```

**Solutions**:
- Check you have permission to create scheduled tasks
- On macOS: May need to allow in System Preferences > Security
- On Linux: Check crontab access

### Sync: FAILED

```
[4/5] Running sync...
      Sync: FAILED - API error
```

**Solutions**:
- Check internet connection
- Verify API credentials with `nextdns-blocker health`
- Check NextDNS service status

### Sync: TIMEOUT

```
[4/5] Running sync...
      Sync: TIMEOUT
```

**Solutions**:
- Check internet connection stability
- Increase API timeout in `.env`: `API_TIMEOUT=30`

## Automation

Use in maintenance scripts:

```bash
#!/bin/bash
# Weekly maintenance
nextdns-blocker fix && echo "Maintenance complete"
```

## What Fix Does NOT Do

The `fix` command does not:
- Modify your `config.json` (domain configuration)
- Change your `.env` settings
- Update the package itself (use `update` for that)
- Clear logs or data files

For complete removal and fresh start, use `nextdns-blocker uninstall`.
