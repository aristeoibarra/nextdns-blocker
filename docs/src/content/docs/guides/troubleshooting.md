---
title: Troubleshooting
description: Diagnose and fix common NextDNS Blocker issues
---

This guide helps you diagnose and resolve common issues with NextDNS Blocker.

## Quick Diagnostics

Run these commands to gather information:

```bash
# Check overall status
nextdns-blocker status

# Validate configuration
nextdns-blocker config validate

# Check watchdog
nextdns-blocker watchdog status

# Preview sync behavior
nextdns-blocker config push --dry-run --verbose
```

## Common Issues

### Domain Not Blocking

**Symptoms**: Domain accessible when it should be blocked

**Diagnosis**:
```bash
# Check domain status
nextdns-blocker status | grep domain.com

# Check schedule evaluation
nextdns-blocker config push --dry-run -v | grep -A10 domain.com
```

**Common causes and fixes**:

1. **Within scheduled hours**
   - Check current time vs schedule
   - Verify timezone is correct

2. **Domain in allowlist**
   ```bash
   nextdns-blocker config show | grep -A2 allowlist
   nextdns-blocker disallow domain.com
   ```

3. **DNS cache**
   ```bash
   # macOS
   sudo dscacheutil -flushcache

   # Linux
   sudo systemctl restart systemd-resolved

   # Windows
   ipconfig /flushdns
   ```

5. **Browser cache**
   - Clear browser cache
   - Try incognito/private window

### Domain Not Unblocking

**Symptoms**: Domain blocked when it should be accessible

**Diagnosis**:
```bash
nextdns-blocker config push --dry-run -v | grep -A10 domain.com
```

**Common causes**:

1. **Outside scheduled hours**
   - Verify current time
   - Check timezone setting

2. **Watchdog not running**
   ```bash
   nextdns-blocker watchdog status
   nextdns-blocker watchdog install
   ```

3. **Sync not running**
   ```bash
   nextdns-blocker config push --verbose
   ```

### Watchdog Not Working

**Symptoms**: Automatic sync not happening

**Diagnosis**:
```bash
nextdns-blocker watchdog status
```

**Fixes by platform**:

**macOS**:
```bash
# Check launchd
launchctl list | grep nextdns

# Reinstall
nextdns-blocker watchdog uninstall
nextdns-blocker watchdog install

# Check logs
tail -20 ~/.local/share/nextdns-blocker/logs/cron.log
```

**Linux**:
```bash
# Check cron
crontab -l | grep nextdns

# Check cron service
systemctl status cron

# Reinstall
nextdns-blocker watchdog uninstall
nextdns-blocker watchdog install
```

**Windows**:
```powershell
# Check tasks
schtasks /query /tn "NextDNS-Blocker-Sync"

# Check Task Scheduler service
Get-Service Schedule

# Reinstall
nextdns-blocker watchdog uninstall
nextdns-blocker watchdog install
```

### API Errors

**Symptoms**: "API error", "Authentication failed", timeouts

**Diagnosis**:
```bash
nextdns-blocker config push --verbose
```

**Fixes**:

1. **Invalid credentials**
   ```bash
   # Re-run setup
   nextdns-blocker init
   ```

2. **Timeout errors**
   ```bash
   # Increase timeout in .env
   API_TIMEOUT=30
   ```

3. **Rate limiting**
   - Wait 60 seconds
   - Check `RATE_LIMIT_*` settings

4. **Network issues**
   ```bash
   # Test connectivity
   curl -I https://api.nextdns.io
   ```

### Configuration Errors

**Symptoms**: "Invalid configuration", validation failures

**Diagnosis**:
```bash
nextdns-blocker config validate
```

**Common issues**:

1. **Invalid JSON**
   ```bash
   # Check JSON syntax
   python3 -m json.tool ~/.config/nextdns-blocker/config.json
   ```

2. **Invalid time format**
   - Use `HH:MM` (24-hour)
   - `09:00` not `9:00`
   - `18:00` not `6:00 PM`

3. **Invalid day names**
   - Use lowercase: `monday` not `Monday`
   - Full names: `wednesday` not `wed`

4. **Duplicate domains**
   - Same domain can't be in blocklist AND allowlist

### Pending Actions Not Executing

**Symptoms**: Queued unblocks not happening

**Diagnosis**:
```bash
nextdns-blocker pending list
nextdns-blocker pending show <ID>
```

**Checks**:

1. **Execution time not reached**
   - Check "Execute at" time

2. **Watchdog not running**
   ```bash
   nextdns-blocker watchdog status
   ```

3. **Force processing**
   ```bash
   nextdns-blocker config push --verbose
   ```

### Wrong Timezone

**Symptoms**: Schedule times don't match expected behavior

**Diagnosis**:
```bash
nextdns-blocker config show | grep timezone
date  # Compare system time
```

**Fix**:
```bash
nextdns-blocker config set timezone America/New_York
```

## Log Files

### Locations

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.local/share/nextdns-blocker/logs/` |
| Windows | `%LOCALAPPDATA%\nextdns-blocker\logs\` |

### Log Files

| File | Contents |
|------|----------|
| `app.log` | Application events |
| `audit.log` | Block/unblock actions |
| `cron.log` | Watchdog sync output |
| `wd.log` | Watchdog self-check |

### Viewing Logs

```bash
# Recent application logs
tail -50 ~/.local/share/nextdns-blocker/logs/app.log

# Recent sync activity
tail -50 ~/.local/share/nextdns-blocker/logs/cron.log

# Follow logs in real-time
tail -f ~/.local/share/nextdns-blocker/logs/app.log
```

## State Files

### Locations

| File | Purpose | Location |
|------|---------|----------|
| `pending.json` | Pending actions | `~/.local/share/nextdns-blocker/` |

### Resetting State

**Reset pending actions**:
```bash
echo '{"actions":[]}' > ~/.local/share/nextdns-blocker/pending.json
```

## Complete Reset

If all else fails, reset everything:

```bash
# 1. Uninstall watchdog
nextdns-blocker watchdog uninstall

# 2. Remove state files
rm -rf ~/.local/share/nextdns-blocker/

# 3. Remove config (optional - loses settings)
rm -rf ~/.config/nextdns-blocker/

# 4. Reinstall
pip install --force-reinstall nextdns-blocker

# 5. Run setup
nextdns-blocker init

# 6. Restore config
nextdns-blocker config edit

# 7. Install watchdog
nextdns-blocker watchdog install
```

## Getting Help

### Information to Include

When reporting issues, include:

```bash
# Version
nextdns-blocker --version

# Platform
uname -a  # or systeminfo on Windows

# Status
nextdns-blocker status

# Validation
nextdns-blocker config validate

# Recent logs
tail -50 ~/.local/share/nextdns-blocker/logs/app.log
```

### Where to Report

- GitHub Issues: [github.com/aristeoibarra/nextdns-blocker/issues](https://github.com/aristeoibarra/nextdns-blocker/issues)

### Before Reporting

1. Check this troubleshooting guide
2. Search existing issues
3. Try `--verbose` flag for more info
4. Include relevant logs and config (redact API key!)
