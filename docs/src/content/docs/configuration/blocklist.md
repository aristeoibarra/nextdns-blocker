---
title: Blocklist
description: Configure domains to block and their schedules
---

The blocklist defines which domains to manage and when they should be blocked.

## Basic Entry

```json
{
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [...]
      }
    }
  ]
}
```

## Entry Fields

### domain (required)

The domain to manage.

```json
{"domain": "reddit.com"}
```

**Notes:**
- Blocking `reddit.com` also blocks subdomains (`www.reddit.com`, `old.reddit.com`)
- Use the root domain for comprehensive blocking
- Add subdomain exceptions to allowlist if needed

### description (optional)

Human-readable note about the domain.

```json
{
  "domain": "reddit.com",
  "description": "Social media - productivity drain"
}
```

### unblock_delay (optional)

Friction before manual unblocking. Default is `"0"`.

```json
{
  "domain": "reddit.com",
  "unblock_delay": "30m"
}
```

| Value | Behavior |
|-------|----------|
| `"0"` | Instant unblock |
| `"30m"` | 30-minute wait |
| `"4h"` | 4-hour wait |
| `"24h"` | 24-hour wait |
| `"never"` | Cannot unblock |

See [Unblock Delay](/configuration/unblock-delay/) for details.

### schedule (optional)

When the domain is accessible. Default is `null` (always blocked).

```json
{
  "domain": "reddit.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "10:00", "end": "22:00"}]
      }
    ]
  }
}
```

See [Schedules](/configuration/schedules/) for details.

## Blocking Behavior

### With Schedule

| Time | Within Schedule | Outside Schedule |
|------|-----------------|------------------|
| State | UNBLOCKED | BLOCKED |
| NextDNS | Not in denylist | In denylist |

### Without Schedule (null)

| State | Always |
|-------|--------|
| State | BLOCKED |
| NextDNS | Always in denylist |

## Common Patterns

### Always Blocked (Protected)

```json
{
  "domain": "gambling-site.com",
  "description": "Always blocked - harmful content",
  "unblock_delay": "never",
  "schedule": null
}
```

### Work Hours Only

```json
{
  "domain": "slack.com",
  "description": "Work communication - work hours only",
  "unblock_delay": "0",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [{"start": "09:00", "end": "18:00"}]
      }
    ]
  }
}
```

### Breaks and Evenings

```json
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
        "time_ranges": [{"start": "10:00", "end": "23:00"}]
      }
    ]
  }
}
```

### Weekends Only

```json
{
  "domain": "store.steampowered.com",
  "description": "Gaming - weekends only",
  "unblock_delay": "4h",
  "schedule": {
    "available_hours": [
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "10:00", "end": "22:00"}]
      }
    ]
  }
}
```

## Domain Categories

### Social Media

```json
{
  "blocklist": [
    {"domain": "reddit.com", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "twitter.com", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "facebook.com", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "instagram.com", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "tiktok.com", "unblock_delay": "4h", "schedule": {...}}
  ]
}
```

### Gaming

```json
{
  "blocklist": [
    {"domain": "store.steampowered.com", "unblock_delay": "4h", "schedule": {...}},
    {"domain": "epicgames.com", "unblock_delay": "4h", "schedule": {...}},
    {"domain": "twitch.tv", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "discord.com", "unblock_delay": "30m", "schedule": {...}}
  ]
}
```

### Streaming

```json
{
  "blocklist": [
    {"domain": "netflix.com", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "youtube.com", "unblock_delay": "0", "schedule": {...}},
    {"domain": "hulu.com", "unblock_delay": "30m", "schedule": {...}},
    {"domain": "disneyplus.com", "unblock_delay": "30m", "schedule": {...}}
  ]
}
```

### Harmful Content

```json
{
  "blocklist": [
    {"domain": "gambling-site.com", "unblock_delay": "never", "schedule": null},
    {"domain": "casino-site.com", "unblock_delay": "never", "schedule": null},
    {"domain": "betting-site.com", "unblock_delay": "never", "schedule": null}
  ]
}
```

## Subdomain Handling

### Automatic Inheritance

Blocking `amazon.com` blocks:
- `amazon.com`
- `www.amazon.com`
- `smile.amazon.com`
- `*.amazon.com`

### Subdomain Exceptions

Use allowlist for exceptions:

```json
{
  "blocklist": [
    {"domain": "amazon.com", "schedule": null}
  ],
  "allowlist": [
    {"domain": "aws.amazon.com", "description": "Work resource"}
  ]
}
```

Result:
- `amazon.com` → Blocked
- `www.amazon.com` → Blocked
- `aws.amazon.com` → Allowed

## Validation

### Valid Domain Format

- ✅ `reddit.com`
- ✅ `old.reddit.com`
- ✅ `api.example.co.uk`
- ❌ `https://reddit.com` (no protocol)
- ❌ `reddit.com/` (no trailing slash)
- ❌ Empty string

### No Duplicates

A domain cannot be in both blocklist and allowlist:

```json
// ❌ Invalid
{
  "blocklist": [{"domain": "reddit.com"}],
  "allowlist": [{"domain": "reddit.com"}]
}
```

### Validate Configuration

```bash
nextdns-blocker config validate
```

## Managing Blocklist

### Add Domain (CLI)

Currently, use `config edit`:

```bash
nextdns-blocker config edit
```

### View Blocklist

```bash
nextdns-blocker config show
```

### Check Domain Status

```bash
nextdns-blocker status
```

## Sync Behavior

After editing blocklist:

1. Save `config.json`
2. Wait for auto-sync (within 2 minutes)
3. Or force sync: `nextdns-blocker config sync`

Use dry run to preview:

```bash
nextdns-blocker config sync --dry-run
```
