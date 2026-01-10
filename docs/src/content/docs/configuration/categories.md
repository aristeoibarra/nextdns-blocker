---
title: Categories
description: Group domains with shared schedules and settings
---

Categories allow you to group related domains that share the same schedule and unblock delay. Instead of repeating configuration for each domain, define it once in the category.

## Basic Structure

```json
{
  "categories": [
    {
      "id": "social-media",
      "description": "Social networks",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [{"start": "10:00", "end": "22:00"}]
          }
        ]
      },
      "domains": ["facebook.com", "instagram.com", "tiktok.com"]
    }
  ]
}
```

## Category Fields

### id (required)

Unique identifier for the category.

**Rules:**
- Must start with a lowercase letter
- Only lowercase letters, numbers, and hyphens allowed
- Maximum 50 characters

```json
{"id": "social-media"}
```

**Valid examples:**
- `social-media`
- `gambling`
- `streaming-video`
- `work-tools`

**Invalid examples:**
- `Social-Media` (uppercase)
- `123social` (starts with number)
- `-social` (starts with hyphen)
- `social_media` (underscore not allowed)

### domains (required)

Array of domains in this category.

```json
{
  "id": "streaming",
  "domains": ["netflix.com", "hbomax.com", "disneyplus.com"]
}
```

**Notes:**
- Each domain inherits the category's schedule and unblock_delay
- A domain can only belong to one category
- A domain cannot be in both a category and the blocklist

### description (optional)

Human-readable description of the category.

```json
{
  "id": "gambling",
  "description": "Betting and casino sites - always blocked"
}
```

### unblock_delay (optional)

Friction before manual unblocking. Default is `"0"`.

```json
{
  "id": "social-media",
  "unblock_delay": "4h"
}
```

Supports flexible duration format:

| Format | Description |
|--------|-------------|
| `"0"` | Instant unblock |
| `"30m"` | 30 minutes |
| `"2h"` | 2 hours |
| `"1d"` | 1 day |
| `"never"` | Cannot unblock |

See [Unblock Delay](/configuration/unblock-delay/) for details.

### schedule (optional)

When domains in this category are accessible. Default is `null` (always blocked).

```json
{
  "id": "streaming",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [{"start": "19:00", "end": "23:00"}]
      },
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "10:00", "end": "23:00"}]
      }
    ]
  }
}
```

See [Schedules](/configuration/schedules/) for details.

## Common Patterns

### Social Media (Limited Hours)

```json
{
  "id": "social-media",
  "description": "Social networks - evenings and weekends",
  "unblock_delay": "4h",
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
        "time_ranges": [{"start": "10:00", "end": "23:00"}]
      }
    ]
  },
  "domains": ["instagram.com", "tiktok.com", "snapchat.com", "twitter.com"]
}
```

### Gambling (Never Unblockable)

```json
{
  "id": "gambling",
  "description": "Betting and casino sites - permanently blocked",
  "unblock_delay": "never",
  "schedule": null,
  "domains": ["stake.com", "caliente.mx", "bet365.com", "draftkings.com"]
}
```

### Streaming (Evenings Only)

```json
{
  "id": "streaming",
  "description": "Video streaming - evenings and weekends",
  "unblock_delay": "2h",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [{"start": "19:00", "end": "23:00"}]
      },
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "10:00", "end": "23:00"}]
      }
    ]
  },
  "domains": ["netflix.com", "hbomax.com", "disneyplus.com", "primevideo.com"]
}
```

### Gaming (Weekends Only)

```json
{
  "id": "gaming",
  "description": "Gaming platforms - weekends only",
  "unblock_delay": "4h",
  "schedule": {
    "available_hours": [
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "10:00", "end": "22:00"}]
      }
    ]
  },
  "domains": ["store.steampowered.com", "epicgames.com", "gog.com"]
}
```

## Categories vs Blocklist

| Feature | Categories | Blocklist |
|---------|------------|-----------|
| **Grouping** | Multiple domains share settings | Each domain configured individually |
| **Best for** | Related domains with same schedule | Unique schedules per domain |
| **Configuration** | Define once, apply to all | Repeat for each domain |

### When to Use Categories

- Multiple domains need the same schedule
- You want to organize domains logically
- Easier maintenance of related domains

### When to Use Blocklist

- Each domain needs unique settings
- One-off domains that don't fit a group
- Legacy configurations

## Managing Categories

### List Categories

```bash
nextdns-blocker category list
```

Output:
```
Categories (3)

ID              Domains   Delay    Description
──────────────────────────────────────────────────────────────
social-media    4         4h       Social networks
gambling        3         never    Betting and casino sites
streaming       4         2h       Video streaming
```

### Show Category Details

```bash
nextdns-blocker category show social-media
```

Output:
```
Category: social-media
━━━━━━━━━━━━━━━━━━━━━━

Description: Social networks
Unblock Delay: 4h

Schedule:
  Mon-Fri: 12:00-13:00, 18:00-22:00
  Sat-Sun: 10:00-23:00

Domains (4):
  - instagram.com
  - tiktok.com
  - snapchat.com
  - twitter.com
```

### Create Category

```bash
nextdns-blocker category create gaming -d "Gaming platforms"
nextdns-blocker category create gambling --delay never
```

### Add Domain to Category

```bash
nextdns-blocker category add social-media reddit.com
```

### Remove Domain from Category

```bash
nextdns-blocker category remove social-media reddit.com
```

### Delete Category

```bash
nextdns-blocker category delete gaming
```

See [category command](/commands/category/) for full reference.

## Validation Rules

### Unique Domain Placement

A domain cannot appear in:
- Multiple categories
- Both a category and the blocklist

```json
// ❌ Invalid - domain in two categories
{
  "categories": [
    {"id": "social", "domains": ["twitter.com"]},
    {"id": "news", "domains": ["twitter.com"]}
  ]
}
```

### Unique Category IDs

Each category must have a unique ID:

```json
// ❌ Invalid - duplicate ID
{
  "categories": [
    {"id": "social", "domains": ["facebook.com"]},
    {"id": "social", "domains": ["twitter.com"]}
  ]
}
```

### Validate Configuration

```bash
nextdns-blocker config validate
```

## Subdomain Handling

### Automatic Inheritance

Blocking `amazon.com` in a category blocks:
- `amazon.com`
- `www.amazon.com`
- `smile.amazon.com`
- `*.amazon.com`

### Subdomain Exceptions

Use allowlist for exceptions:

```json
{
  "categories": [
    {
      "id": "shopping",
      "domains": ["amazon.com"]
    }
  ],
  "allowlist": [
    {"domain": "aws.amazon.com", "description": "Work resource"}
  ]
}
```

Result:
- `amazon.com` → Blocked (per schedule)
- `www.amazon.com` → Blocked
- `aws.amazon.com` → Always allowed

## Sync Behavior

When sync runs:

1. Categories are expanded into individual domain entries
2. Each domain inherits the category's schedule and unblock_delay
3. Domains are evaluated against NextDNS denylist

```bash
# Preview sync
nextdns-blocker config sync --dry-run

# Force sync
nextdns-blocker config sync
```

## Migration from Blocklist

To convert blocklist entries to a category:

**Before (blocklist):**
```json
{
  "blocklist": [
    {"domain": "facebook.com", "unblock_delay": "4h", "schedule": {...}},
    {"domain": "twitter.com", "unblock_delay": "4h", "schedule": {...}},
    {"domain": "instagram.com", "unblock_delay": "4h", "schedule": {...}}
  ]
}
```

**After (category):**
```json
{
  "categories": [
    {
      "id": "social-media",
      "unblock_delay": "4h",
      "schedule": {...},
      "domains": ["facebook.com", "twitter.com", "instagram.com"]
    }
  ],
  "blocklist": []
}
```

## Complete Example

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York"
  },
  "categories": [
    {
      "id": "social-media",
      "description": "Social networks and messaging",
      "unblock_delay": "4h",
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
            "time_ranges": [{"start": "10:00", "end": "23:00"}]
          }
        ]
      },
      "domains": ["instagram.com", "tiktok.com", "snapchat.com"]
    },
    {
      "id": "gambling",
      "description": "Gambling and betting - never unblockable",
      "unblock_delay": "never",
      "schedule": null,
      "domains": ["stake.com", "caliente.mx", "bet365.com"]
    },
    {
      "id": "streaming",
      "description": "Video streaming - evenings only",
      "unblock_delay": "2h",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [{"start": "19:00", "end": "23:00"}]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [{"start": "10:00", "end": "23:00"}]
          }
        ]
      },
      "domains": ["netflix.com", "hbomax.com", "disneyplus.com"]
    }
  ],
  "blocklist": [],
  "allowlist": [
    {"domain": "aws.amazon.com", "description": "Work resource"}
  ]
}
```
