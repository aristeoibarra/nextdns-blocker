---
title: config
description: Manage NextDNS Blocker configuration files
---

The `config` command group provides subcommands for viewing, editing, and validating your configuration.

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `show` | Display current configuration |
| `edit` | Open config in your editor |
| `validate` | Validate configuration syntax |
| `set` | Set configuration values |
| `sync` | Synchronize domain states based on schedules |

## config show

Display the current configuration in a readable format.

### Usage

```bash
nextdns-blocker config show
```

### Output

```
Configuration
━━━━━━━━━━━━━

Settings:
  Timezone: America/New_York
  Editor: vim

Blocklist (3 domains):
  reddit.com
    Description: Social media
    Unblock delay: 30m
    Schedule: Mon-Fri 12:00-13:00, 18:00-22:00
              Sat-Sun 10:00-23:00

  twitter.com
    Description: News
    Unblock delay: 0
    Schedule: Mon-Fri 18:00-22:00
              Sat-Sun (always)

  gambling-site.com
    Description: Always blocked
    Unblock delay: never
    Schedule: null (always blocked)

Allowlist (1 domain):
  aws.amazon.com
    Description: Work resource
    Schedule: null (always allowed)
```

## config edit

Open the configuration file in your text editor.

### Usage

```bash
nextdns-blocker config edit
```

### Behavior

1. Opens `config.json` in your configured editor
2. Falls back to `$EDITOR` environment variable
3. Falls back to `nano`, `vim`, or `notepad` (Windows)

### Setting Your Editor

```bash
# Set in config
nextdns-blocker config set editor code

# Or via environment variable
export EDITOR=vim
```

### After Editing

Changes take effect on the next sync (within 2 minutes) or immediately if you run:

```bash
nextdns-blocker config sync
```

## config validate

Validate the configuration file syntax and structure.

### Usage

```bash
nextdns-blocker config validate
```

### Output (Success)

```
Configuration valid ✓

Summary:
  Blocklist: 3 domains
  Allowlist: 1 domain
  Timezone: America/New_York
```

### Output (Error)

```
Configuration error ✗

Line 15: Invalid time format "25:00"
  Expected format: HH:MM (00:00-23:59)

Line 22: Unknown day name "monnday"
  Valid days: monday, tuesday, wednesday, thursday, friday, saturday, sunday
```

### What Gets Validated

| Check | Description |
|-------|-------------|
| JSON syntax | Valid JSON format |
| Required fields | Domain, version |
| Domain format | Valid domain names |
| Schedule format | Valid days and times |
| Time format | HH:MM (24-hour) |
| Day names | Lowercase weekday names |
| Unblock delay | Valid delay values |
| No duplicates | Domain not in both lists |

## config set

Set specific configuration values without opening an editor.

### Usage

```bash
nextdns-blocker config set KEY VALUE
```

### Supported Keys

| Key | Values | Description |
|-----|--------|-------------|
| `timezone` | IANA timezone | Schedule evaluation timezone |
| `editor` | Editor command | Editor for `config edit` |

### Examples

```bash
# Set timezone
nextdns-blocker config set timezone America/Los_Angeles

# Set editor
nextdns-blocker config set editor vim
nextdns-blocker config set editor "code --wait"
nextdns-blocker config set editor nano
```

### Timezone Examples

```bash
# US timezones
nextdns-blocker config set timezone America/New_York
nextdns-blocker config set timezone America/Chicago
nextdns-blocker config set timezone America/Denver
nextdns-blocker config set timezone America/Los_Angeles

# Europe
nextdns-blocker config set timezone Europe/London
nextdns-blocker config set timezone Europe/Paris
nextdns-blocker config set timezone Europe/Berlin

# Asia
nextdns-blocker config set timezone Asia/Tokyo
nextdns-blocker config set timezone Asia/Shanghai

# Other
nextdns-blocker config set timezone UTC
```

See [Timezone Configuration](/configuration/timezone/) for more details.

## config sync

The primary command for synchronizing domain states based on configured schedules.

### Usage

```bash
nextdns-blocker config sync [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview changes without applying them |
| `-v, --verbose` | Show detailed output |
| `--help` | Show help message |

### Examples

```bash
# Basic sync
nextdns-blocker config sync

# Preview changes
nextdns-blocker config sync --dry-run

# Verbose output
nextdns-blocker config sync -v
```

See [sync command reference](/commands/sync/) for complete documentation.

## Configuration File Locations

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.config/nextdns-blocker/config.json` |
| Windows | `%APPDATA%\nextdns-blocker\config.json` |

## Configuration Structure

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [
    {
      "domain": "example.com",
      "description": "Optional description",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [...]
      }
    }
  ],
  "allowlist": [
    {
      "domain": "exception.example.com",
      "description": "Always accessible"
    }
  ]
}
```

See [Configuration Reference](/configuration/) for complete documentation.

## Troubleshooting

### "Configuration file not found"

Run the setup wizard:

```bash
nextdns-blocker init
```

### "Invalid JSON syntax"

Use a JSON validator:

```bash
python3 -m json.tool config.json
```

Or use [jsonlint.com](https://jsonlint.com).

### "Editor not found"

Set your editor explicitly:

```bash
nextdns-blocker config set editor nano
```

Or set the `$EDITOR` environment variable in your shell profile.

### Changes not taking effect

Force a sync:

```bash
nextdns-blocker config sync
```

Or check for validation errors:

```bash
nextdns-blocker config validate
```
