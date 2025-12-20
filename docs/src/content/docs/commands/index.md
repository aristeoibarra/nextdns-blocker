---
title: Commands Overview
description: Complete reference for all NextDNS Blocker CLI commands
---

NextDNS Blocker provides a comprehensive set of commands organized into logical groups.

## Command Structure

```
nextdns-blocker [OPTIONS] COMMAND [ARGS]
```

### Global Options

| Option | Description |
|--------|-------------|
| `--version` | Show version and exit |
| `--no-color` | Disable colored output |
| `--help` | Show help message |

## Main Commands

| Command | Description |
|---------|-------------|
| [`sync`](/commands/sync/) | Synchronize domain states based on schedules |
| [`status`](/commands/status/) | Show current blocking status |
| [`pause`](/commands/pause-resume/) | Temporarily pause all blocking |
| [`resume`](/commands/pause-resume/) | Resume blocking after pause |
| [`unblock`](/commands/unblock/) | Request manual domain unblock |
| [`update`](/commands/update/) | Check for and install updates |

## Command Groups

### config

Manage configuration files.

| Subcommand | Description |
|------------|-------------|
| [`config show`](/commands/config/) | Display current configuration |
| [`config edit`](/commands/config/) | Open config in editor |
| [`config validate`](/commands/config/) | Validate configuration syntax |
| [`config set`](/commands/config/) | Set configuration values |
| [`config sync`](/commands/config/) | Sync domains (alias for root sync) |

### watchdog

Manage automatic synchronization.

| Subcommand | Description |
|------------|-------------|
| [`watchdog status`](/commands/watchdog/) | Check scheduler status |
| [`watchdog install`](/commands/watchdog/) | Create scheduled sync jobs |
| [`watchdog uninstall`](/commands/watchdog/) | Remove scheduled jobs |
| [`watchdog enable`](/commands/watchdog/) | Re-enable after disable |
| [`watchdog disable`](/commands/watchdog/) | Temporarily disable |

### panic

Emergency lockdown mode.

| Subcommand | Description |
|------------|-------------|
| [`panic MINUTES`](/commands/panic/) | Activate panic mode |
| [`panic status`](/commands/panic/) | Check panic mode status |
| [`panic extend`](/commands/panic/) | Extend panic duration |

### pending

Manage pending unblock actions.

| Subcommand | Description |
|------------|-------------|
| [`pending list`](/commands/pending/) | List pending actions |
| [`pending show`](/commands/pending/) | Show action details |
| [`pending cancel`](/commands/pending/) | Cancel pending action |

### Allowlist Commands

| Command | Description |
|---------|-------------|
| [`allow`](/commands/allowlist/) | Add domain to allowlist |
| [`disallow`](/commands/allowlist/) | Remove domain from allowlist |

## Quick Reference

### Daily Usage

```bash
# Check what's blocked
nextdns-blocker status

# Quick break (pause 30 min)
nextdns-blocker pause

# Done with break
nextdns-blocker resume

# Emergency mode
nextdns-blocker panic 60
```

### Management

```bash
# Edit domains
nextdns-blocker config edit

# Force sync now
nextdns-blocker sync

# Check watchdog
nextdns-blocker watchdog status
```

### Troubleshooting

```bash
# Preview changes
nextdns-blocker sync --dry-run

# Verbose output
nextdns-blocker sync -v

# Validate config
nextdns-blocker config validate
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Configuration error |
| 3 | API error |
| 4 | Validation error |

See [Exit Codes Reference](/reference/exit-codes/) for complete details.
