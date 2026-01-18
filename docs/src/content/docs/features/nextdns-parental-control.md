---
title: NextDNS Parental Control
description: Block entire categories and services using NextDNS native Parental Control API
sidebar:
  order: 6
---

NextDNS Blocker integrates with **NextDNS Parental Control API** to block entire categories (gambling, porn, etc.) and services (TikTok, Netflix, Fortnite, etc.) with schedule-based control.

## Why Use Parental Control?

Instead of manually blocking individual domains, NextDNS Parental Control:

- **Blocks all domains** associated with a service (e.g., all TikTok CDNs, APIs, etc.)
- **Stays up-to-date** as NextDNS maintains the domain lists
- **Reduces configuration** - no need to find and block each domain yourself
- **Works with schedules** - same schedule format as blocklist domains

## Configuration

Add a `nextdns` section to your `config.json`:

```json
{
  "nextdns": {
    "parental_control": {
      "safe_search": true,
      "youtube_restricted_mode": false,
      "block_bypass": true
    },
    "categories": [
      {
        "id": "gambling",
        "description": "Betting sites - always blocked",
        "unblock_delay": "never"
      }
    ],
    "services": [
      {
        "id": "tiktok",
        "description": "TikTok - evenings only",
        "unblock_delay": "4h",
        "schedule": {
          "available_hours": [
            {
              "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
              "time_ranges": [{"start": "18:00", "end": "22:00"}]
            }
          ]
        }
      }
    ]
  }
}
```

## Global Settings

The `parental_control` object configures global NextDNS settings:

| Setting | Type | Description |
|---------|------|-------------|
| `safe_search` | boolean | Force SafeSearch on Google, Bing, DuckDuckGo, YouTube |
| `youtube_restricted_mode` | boolean | Enable YouTube Restricted Mode |
| `block_bypass` | boolean | Block VPNs, proxies, and alternative DNS services |

## Valid Category IDs

NextDNS supports 7 native categories:

| Category ID | Description |
|-------------|-------------|
| `porn` | Adult/pornographic content |
| `gambling` | Betting and gambling sites |
| `dating` | Dating apps and websites |
| `piracy` | Piracy and torrent sites |
| `social-networks` | Social networking platforms |
| `gaming` | Gaming platforms and services |
| `video-streaming` | Video streaming services |

## Valid Service IDs

NextDNS supports 43 services across multiple categories:

### Social & Messaging
`facebook`, `instagram`, `twitter`, `tiktok`, `snapchat`, `whatsapp`, `telegram`, `messenger`, `discord`, `signal`, `skype`, `mastodon`, `bereal`, `vk`, `tumblr`, `pinterest`, `reddit`, `9gag`, `imgur`, `google-chat`

### Streaming
`youtube`, `netflix`, `disneyplus`, `hbomax`, `primevideo`, `hulu`, `twitch`, `vimeo`, `dailymotion`

### Gaming
`fortnite`, `minecraft`, `roblox`, `leagueoflegends`, `steam`, `blizzard`, `xboxlive`, `playstation-network`

### Dating
`tinder`

### Other
`spotify`, `amazon`, `ebay`, `zoom`, `chatgpt`

## Schedule Format

Categories and services support the same schedule format as blocklist domains:

```json
{
  "id": "netflix",
  "schedule": {
    "available_hours": [
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [
          {"start": "10:00", "end": "22:00"}
        ]
      }
    ]
  }
}
```

When **outside** the available hours, the service/category is **blocked**.

## CLI Commands

### List configured and active items

```bash
# Show from config.json
nextdns-blocker nextdns list

# Show live status from NextDNS API
nextdns-blocker nextdns list --remote
```

### Manually control categories

```bash
# Activate (start blocking)
nextdns-blocker nextdns add-category gambling

# Deactivate (stop blocking)
nextdns-blocker nextdns remove-category gambling
```

### Manually control services

```bash
# Activate (start blocking)
nextdns-blocker nextdns add-service tiktok

# Deactivate (stop blocking)
nextdns-blocker nextdns remove-service tiktok
```

### View valid IDs

```bash
# Show all valid category IDs
nextdns-blocker nextdns categories

# Show all valid service IDs (grouped by type)
nextdns-blocker nextdns services
```

### Check current status

```bash
nextdns-blocker nextdns status
```

## Sync Behavior

When you run `nextdns-blocker config push` (or the watchdog runs it automatically):

1. **Categories** are activated/deactivated based on their schedule
2. **Services** are activated/deactivated based on their schedule
3. **Global settings** (safe_search, etc.) are applied

During **panic mode**:
- Activations continue (blocks are maintained)
- Deactivations are skipped (prevents removing blocks)

## Example: Complete Configuration

```json
{
  "nextdns": {
    "parental_control": {
      "safe_search": true,
      "youtube_restricted_mode": false,
      "block_bypass": true
    },
    "categories": [
      {
        "id": "gambling",
        "description": "Always blocked",
        "unblock_delay": "never"
      },
      {
        "id": "porn",
        "description": "Always blocked",
        "unblock_delay": "never"
      }
    ],
    "services": [
      {
        "id": "tiktok",
        "description": "Evenings and weekends",
        "unblock_delay": "4h",
        "schedule": {
          "available_hours": [
            {
              "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
              "time_ranges": [{"start": "18:00", "end": "22:00"}]
            },
            {
              "days": ["saturday", "sunday"],
              "time_ranges": [{"start": "10:00", "end": "23:00"}]
            }
          ]
        }
      },
      {
        "id": "fortnite",
        "description": "Weekends only",
        "unblock_delay": "1h",
        "schedule": {
          "available_hours": [
            {
              "days": ["saturday", "sunday"],
              "time_ranges": [{"start": "10:00", "end": "22:00"}]
            }
          ]
        }
      },
      {
        "id": "netflix",
        "description": "After 7pm only",
        "unblock_delay": "2h",
        "schedule": {
          "available_hours": [
            {
              "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
              "time_ranges": [{"start": "19:00", "end": "23:00"}]
            }
          ]
        }
      }
    ]
  }
}
```

## Difference from Categories (blocklist grouping)

Don't confuse `nextdns.categories` with the top-level `categories` in config.json:

| Feature | `nextdns.categories` | Top-level `categories` |
|---------|---------------------|----------------------|
| Source | NextDNS Parental Control API | Your custom groups |
| Domains | Managed by NextDNS | You define the domains |
| IDs | Fixed (7 options) | Any custom ID |
| Use case | Block entire content types | Group your domains |

You can use both together for maximum control.
