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

## Setup Commands

| Command | Description |
|---------|-------------|
| [`init`](/commands/init/) | Initialize configuration with interactive wizard |
| [`config validate`](/commands/validate/) | Validate configuration files before deployment |
| [`completion`](/commands/completion/) | Generate shell completion script |

## Main Commands

| Command | Description |
|---------|-------------|
| [`config sync`](/commands/sync/) | Synchronize domain states based on schedules |
| [`status`](/commands/status/) | Show current blocking status |
| [`pause`](/commands/pause-resume/) | Temporarily pause all blocking |
| [`resume`](/commands/pause-resume/) | Resume blocking after pause |
| [`unblock`](/commands/unblock/) | Request manual domain unblock |
| [`update`](/commands/update/) | Check for and install updates |

## Diagnostic & Maintenance Commands

| Command | Description |
|---------|-------------|
| [`health`](/commands/health/) | Run system health checks |
| [`fix`](/commands/fix/) | Auto-repair common issues |
| [`stats`](/commands/stats/) | Show usage statistics |
| [`test-notifications`](/commands/test-notifications/) | Test Discord integration |
| [`uninstall`](/commands/uninstall/) | Completely remove NextDNS Blocker |

## Command Groups

### config

Manage configuration files.

| Subcommand | Description |
|------------|-------------|
| [`config show`](/commands/config/) | Display current configuration |
| [`config edit`](/commands/config/) | Open config in editor |
| [`config validate`](/commands/config/) | Validate configuration syntax |
| [`config set`](/commands/config/) | Set configuration values |
| [`config sync`](/commands/config/) | Synchronize domain states based on schedules |

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

### category

Manage domain categories.

| Subcommand | Description |
|------------|-------------|
| [`category list`](/commands/category/) | List all categories |
| [`category show`](/commands/category/) | Show category details |
| [`category create`](/commands/category/) | Create new category |
| [`category add`](/commands/category/) | Add domain to category |
| [`category remove`](/commands/category/) | Remove domain from category |
| [`category delete`](/commands/category/) | Delete category |

### nextdns

Manage NextDNS Parental Control.

| Subcommand | Description |
|------------|-------------|
| [`nextdns list`](/commands/nextdns/) | List configured items |
| [`nextdns status`](/commands/nextdns/) | Show Parental Control status |
| [`nextdns add-category`](/commands/nextdns/) | Activate category |
| [`nextdns remove-category`](/commands/nextdns/) | Deactivate category |
| [`nextdns add-service`](/commands/nextdns/) | Activate service |
| [`nextdns remove-service`](/commands/nextdns/) | Deactivate service |
| [`nextdns categories`](/commands/nextdns/) | Show valid category IDs |
| [`nextdns services`](/commands/nextdns/) | Show valid service IDs |

### Allowlist Commands

| Command | Description |
|---------|-------------|
| [`allow`](/commands/allowlist/) | Add domain to allowlist |
| [`disallow`](/commands/allowlist/) | Remove domain from allowlist |

## Quick Reference

### First Time Setup

```bash
# Initialize configuration
nextdns-blocker init

# Install scheduler
nextdns-blocker watchdog install

# Verify setup
nextdns-blocker status
```

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
nextdns-blocker config sync

# Check watchdog
nextdns-blocker watchdog status
```

### Troubleshooting

```bash
# Validate config
nextdns-blocker config validate

# Preview changes
nextdns-blocker config sync --dry-run

# Verbose output
nextdns-blocker config sync -v

# Run health checks
nextdns-blocker health

# Auto-fix common issues
nextdns-blocker fix

# View usage statistics
nextdns-blocker stats

# Test Discord notifications
nextdns-blocker test-notifications
```

### Shell Completion

```bash
# Bash
eval "$(nextdns-blocker completion bash)"

# Zsh
eval "$(nextdns-blocker completion zsh)"

# Fish
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
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
