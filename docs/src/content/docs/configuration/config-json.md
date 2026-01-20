---
title: config.json Structure
description: Complete reference for the config.json file format
---

The `config.json` file defines your domain schedules, blocklist, and allowlist.

## File Location

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.config/nextdns-blocker/config.json` |
| Windows | `%APPDATA%\nextdns-blocker\config.json` |

## Structure Overview

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": { ... },
      "macos": { ... }
    }
  },
  "blocklist": [
    {
      "domain": "example.com",
      "description": "Optional description",
      "unblock_delay": "30m",
      "schedule": { ... }
    }
  ],
  "allowlist": [
    {
      "domain": "allowed.example.com",
      "description": "Optional description",
      "schedule": null
    }
  ]
}
```

## Root Fields

### version

Configuration file version. Currently `"1.0"`.

```json
{
  "version": "1.0"
}
```

### settings

Global settings for NextDNS Blocker.

```json
{
  "settings": {
    "timezone": "America/New_York",
    "editor": "vim"
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `timezone` | string | Auto-detected | IANA timezone for schedules |
| `editor` | string | `$EDITOR` | Editor for `config edit` |

### notifications

Configuration for notification channels.

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/..."
      },
      "macos": {
        "enabled": true,
        "sound": true
      }
    }
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Master switch for all notifications |
| `channels` | object | `{}` | Channel-specific configurations |

**Discord Channel:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | Yes | Enable Discord notifications |
| `webhook_url` | string | Yes | Full Discord webhook URL |

**macOS Channel:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable macOS native notifications |
| `sound` | boolean | `true` | Play sound with notification |

See [Notifications](/features/notifications/) for complete setup guide.

### blocklist

Array of domains to manage blocking for.

```json
{
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media",
      "unblock_delay": "30m",
      "schedule": { ... }
    }
  ]
}
```

See [Blocklist Configuration](/configuration/blocklist/) for details.

### allowlist

Array of domains to keep accessible (exceptions).

```json
{
  "allowlist": [
    {
      "domain": "aws.amazon.com",
      "description": "Work resource"
    }
  ]
}
```

See [Allowlist Configuration](/configuration/allowlist/) for details.

### nextdns

Configuration for NextDNS Parental Control categories and services.

```json
{
  "nextdns": {
    "parental_control": {
      "safe_search": true,
      "youtube_restricted_mode": true,
      "block_bypass": true
    },
    "categories": [
      {
        "id": "gambling",
        "locked": true,
        "schedule": null
      }
    ],
    "services": [
      {
        "id": "tiktok",
        "schedule": {
          "available_hours": [...]
        }
      }
    ]
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `parental_control` | object | Global Parental Control settings |
| `categories` | array | NextDNS native categories (gambling, porn, dating, etc.) |
| `services` | array | NextDNS native services (tiktok, youtube, reddit, etc.) |

**Valid category IDs:** `porn`, `gambling`, `dating`, `piracy`, `social-networks`, `gaming`, `video-streaming`

### protection

Addiction protection features including unlock delays.

```json
{
  "protection": {
    "unlock_delay_hours": 48
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `unlock_delay_hours` | int | 48 | Default delay for unlock requests (min 24h) |

## Domain Entry Fields

Both blocklist and allowlist entries share these fields:

### domain (required)

The domain name to manage.

```json
{
  "domain": "reddit.com"
}
```

**Validation:**
- Cannot be empty
- Must be a valid domain format
- No protocol prefix (`https://`)
- No trailing slash

**Examples:**
- ✅ `reddit.com`
- ✅ `www.reddit.com`
- ✅ `api.example.co.uk`
- ❌ `https://reddit.com`
- ❌ `reddit.com/`
- ❌ `` (empty)

### description (optional)

Human-readable description.

```json
{
  "domain": "reddit.com",
  "description": "Social media - limited access during work"
}
```

Shown in `status` and `config show` output.

### schedule (optional)

Time-based availability rules.

```json
{
  "domain": "reddit.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [
          {"start": "12:00", "end": "13:00"},
          {"start": "18:00", "end": "22:00"}
        ]
      }
    ]
  }
}
```

See [Schedules](/configuration/schedules/) for complete documentation.

**Special values:**
- `null` - Always blocked (blocklist) or always allowed (allowlist)
- Omitted - Same as `null`

### unblock_delay (blocklist only)

Friction before manual unblocking.

```json
{
  "domain": "reddit.com",
  "unblock_delay": "30m"
}
```

See [Unblock Delay](/configuration/unblock-delay/) for details.

**Valid values:**
- `"0"` - Instant
- `"30m"` - 30 minutes
- `"4h"` - 4 hours
- `"24h"` - 24 hours
- `"never"` - Protected

## Schedule Structure

### available_hours

Array of day/time rules defining when a domain is accessible.

```json
{
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "friday"],
        "time_ranges": [
          {"start": "09:00", "end": "17:00"}
        ]
      }
    ]
  }
}
```

### days

Array of weekday names (lowercase).

```json
{
  "days": ["monday", "tuesday", "wednesday", "thursday", "friday"]
}
```

**Valid values:**
- `monday`
- `tuesday`
- `wednesday`
- `thursday`
- `friday`
- `saturday`
- `sunday`

### time_ranges

Array of time windows.

```json
{
  "time_ranges": [
    {"start": "09:00", "end": "12:00"},
    {"start": "13:00", "end": "17:00"}
  ]
}
```

**Format:** 24-hour time `HH:MM`
- Hours: `00` to `23`
- Minutes: `00` to `59`

**Examples:**
- `"09:00"` - 9:00 AM
- `"13:30"` - 1:30 PM
- `"23:59"` - 11:59 PM
- `"00:00"` - Midnight

## Complete Example

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": "code --wait"
  },
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/123456/abcdef..."
      },
      "macos": {
        "enabled": true,
        "sound": true
      }
    }
  },
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media - breaks only",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "22:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "23:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "twitter.com",
      "description": "News - evenings only",
      "unblock_delay": "0",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "18:00", "end": "21:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "gambling-site.com",
      "description": "Always blocked - protected",
      "unblock_delay": "never",
      "schedule": null
    }
  ],
  "allowlist": [
    {
      "domain": "aws.amazon.com",
      "description": "Work resource - always accessible"
    },
    {
      "domain": "youtube.com",
      "description": "Entertainment - evenings only",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "22:00"}
            ]
          }
        ]
      }
    }
  ]
}
```

## Validation

### Validate Syntax

```bash
nextdns-blocker config validate
```

### Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| Invalid JSON | Syntax error | Check commas, quotes, brackets |
| Unknown field | Typo in field name | Use correct field names |
| Invalid time | Wrong format | Use `HH:MM` (24-hour) |
| Invalid day | Wrong day name | Use lowercase full names |
| Duplicate domain | Same domain in both lists | Remove from one list |

### JSON Validation Tools

```bash
# Python
python3 -m json.tool config.json

# Online
# https://jsonlint.com
```

## Editing

### Via Command

```bash
nextdns-blocker config edit
```

### Direct Edit

```bash
# macOS/Linux
nano ~/.config/nextdns-blocker/config.json

# Windows
notepad %APPDATA%\nextdns-blocker\config.json
```

### After Editing

Changes take effect on next sync (within 2 minutes) or immediately:

```bash
nextdns-blocker config push
```
