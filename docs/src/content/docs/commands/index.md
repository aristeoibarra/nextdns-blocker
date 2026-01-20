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
| [`config push`](/commands/sync/) | Synchronize domain states based on schedules |
| [`status`](/commands/status/) | Show current blocking status |
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
| [`config push`](/commands/config/) | Synchronize domain states based on schedules |
| [`config diff`](/commands/config/) | Show differences between local and remote |
| [`config pull`](/commands/config/) | Fetch domains from NextDNS to local config |

### watchdog

Manage automatic synchronization.

| Subcommand | Description |
|------------|-------------|
| [`watchdog status`](/commands/watchdog/) | Check scheduler status |
| [`watchdog install`](/commands/watchdog/) | Create scheduled sync jobs |
| [`watchdog uninstall`](/commands/watchdog/) | Remove scheduled jobs |
| [`watchdog enable`](/commands/watchdog/) | Re-enable after disable |
| [`watchdog disable`](/commands/watchdog/) | Temporarily disable |

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

### denylist

Manage NextDNS denylist (blocked domains).

| Subcommand | Description |
|------------|-------------|
| [`denylist list`](/commands/allowlist/) | List all denylist domains |
| [`denylist add`](/commands/allowlist/) | Add domains to denylist |
| [`denylist remove`](/commands/allowlist/) | Remove domains from denylist |
| [`denylist export`](/commands/allowlist/) | Export to JSON or CSV |
| [`denylist import`](/commands/allowlist/) | Import from file |

### allowlist

Manage NextDNS allowlist (whitelisted domains).

| Subcommand | Description |
|------------|-------------|
| [`allowlist list`](/commands/allowlist/) | List all allowlist domains |
| [`allowlist add`](/commands/allowlist/) | Add domains to allowlist |
| [`allowlist remove`](/commands/allowlist/) | Remove domains from allowlist |
| [`allowlist export`](/commands/allowlist/) | Export to JSON or CSV |
| [`allowlist import`](/commands/allowlist/) | Import from file |

### Legacy Allowlist Commands

| Command | Description |
|---------|-------------|
| [`allow`](/commands/allowlist/) | Add domain to allowlist |
| [`disallow`](/commands/allowlist/) | Remove domain from allowlist |

### protection

Manage addiction protection features.

| Subcommand | Description |
|------------|-------------|
| [`protection status`](/reference/security/) | Show protection status and locked items |
| [`protection unlock-request`](/reference/security/) | Request to unlock a protected item |
| [`protection cancel`](/reference/security/) | Cancel a pending unlock request |
| [`protection list`](/reference/security/) | List pending unlock requests |
| [`protection pin set`](/reference/security/) | Set or change PIN |
| [`protection pin status`](/reference/security/) | Show PIN status |
| [`protection pin verify`](/reference/security/) | Verify PIN and start session |
| [`protection pin remove`](/reference/security/) | Remove PIN (with 24h delay) |

### stats

View usage statistics and patterns.

| Subcommand | Description |
|------------|-------------|
| [`stats`](/commands/stats/) | Show summary statistics |
| [`stats domains`](/commands/stats/) | Show top blocked domains |
| [`stats hours`](/commands/stats/) | Show hourly activity patterns |
| [`stats actions`](/commands/stats/) | Show action breakdown |
| [`stats export`](/commands/stats/) | Export to CSV |

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
```

### Management

```bash
# Edit domains
nextdns-blocker config edit

# Force sync now
nextdns-blocker config push

# Check watchdog
nextdns-blocker watchdog status
```

### Troubleshooting

```bash
# Validate config
nextdns-blocker config validate

# Preview changes
nextdns-blocker config push --dry-run

# Verbose output
nextdns-blocker config push -v

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
