---
title: Parental Control
description: Set up protected blocking for children
---

This guide helps parents set up NextDNS Blocker with maximum protection for children's devices.

## Overview

**Goal**: Protect children from inappropriate content and excessive screen time

**Strategy**:
- Block harmful content permanently
- Limit entertainment to scheduled hours
- Use maximum friction to prevent bypass
- Combine with NextDNS category blocking

## Configuration

### Complete Example

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [
    {
      "domain": "youtube.com",
      "description": "Video streaming - limited hours",
      "unblock_delay": "never",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "16:00", "end": "18:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "12:00"},
              {"start": "14:00", "end": "18:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "tiktok.com",
      "description": "Short video app - weekends only",
      "unblock_delay": "never",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "17:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "instagram.com",
      "description": "Social media - weekends only",
      "unblock_delay": "never",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "17:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "snapchat.com",
      "description": "Messaging app - limited",
      "unblock_delay": "never",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "12:00", "end": "18:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "discord.com",
      "description": "Gaming chat - weekends",
      "unblock_delay": "never",
      "schedule": {
        "available_hours": [
          {
            "days": ["friday"],
            "time_ranges": [
              {"start": "18:00", "end": "21:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "20:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "reddit.com",
      "description": "Forum - blocked",
      "unblock_delay": "never",
      "schedule": null
    },
    {
      "domain": "twitter.com",
      "description": "Social media - blocked",
      "unblock_delay": "never",
      "schedule": null
    },
    {
      "domain": "twitch.tv",
      "description": "Game streaming - weekends only",
      "unblock_delay": "never",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "18:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": [
    {
      "domain": "khanacademy.org",
      "description": "Educational"
    },
    {
      "domain": "wikipedia.org",
      "description": "Educational"
    },
    {
      "domain": "scratch.mit.edu",
      "description": "Educational coding"
    },
    {
      "domain": "classroom.google.com",
      "description": "School"
    },
    {
      "domain": "docs.google.com",
      "description": "School work"
    }
  ]
}
```

## Key Features

### Protected Domains (`"never"`)

All domains use `unblock_delay: "never"`:
- Children cannot manually unblock
- Parent must edit config to change
- Maximum protection

### Limited Hours

Entertainment limited to:
- **Weekdays**: After school (4-6 PM)
- **Weekends**: Mid-day windows with breaks

### Always Blocked

Some sites remain always blocked:
- Reddit (unpredictable content)
- Twitter (adult content possible)
- Other inappropriate sites

### Educational Allowlist

Educational resources always accessible:
- Khan Academy
- Wikipedia
- School platforms

## Combining with NextDNS

### Category Blocking

In NextDNS dashboard, also enable:
- **Parental Control** → Block inappropriate categories
- **Security** → Block malware, phishing
- **Privacy** → Block trackers

### Services Blocking

Block by service in NextDNS:
- Adult content services
- VPN/Proxy services (prevent bypass)
- Anonymous browsing tools

NextDNS Blocker adds scheduled access on top of these blocks.

### Filtering Priority

NextDNS processes filtering rules in this order:

| Priority | Source | Result |
|----------|--------|--------|
| 1 (Highest) | **Allowlist** | ALLOWED |
| 2 | Denylist | BLOCKED |
| 3 | Parental Control (categories/services) | BLOCKED |
| 4 | Privacy blocklists | BLOCKED |
| 5 | Normal resolution | ALLOWED |

**Key point:** Allowlist always wins over any blocking rule.

### Exception Example: Discord with Gaming Block

Block the gaming category but allow Discord for communication:

```json
{
  "nextdns": {
    "categories": [
      {
        "id": "gaming",
        "description": "Block gaming sites",
        "unblock_delay": "never"
      }
    ]
  },
  "allowlist": [
    {
      "domain": "discord.com",
      "description": "Exception to gaming block - communication allowed"
    }
  ]
}
```

**Result**:
- Steam, Fortnite, Roblox, etc. → **Blocked** (by gaming category)
- Discord → **Allowed** (allowlist overrides category block)

This pattern is useful when a category blocks more than intended. See [Filtering Priority](/configuration/filtering-priority/) for more examples.

## Setup Steps

### 1. Set Up on Child's Device

Install NextDNS Blocker on the device you want to control:

```bash
pip install nextdns-blocker
nextdns-blocker init
```

### 2. Use Shared NextDNS Profile

Create a NextDNS profile specifically for children:
1. Create new profile at my.nextdns.io
2. Enable parental controls
3. Use that profile ID in setup

### 3. Apply Configuration

```bash
nextdns-blocker config edit
# Paste the configuration above
```

### 4. Install Watchdog

```bash
nextdns-blocker watchdog install
```

### 5. Secure the Installation

Protect against tampering:

**Hide terminal access** (age-appropriate):
- Younger children: Don't show terminal exists
- Older children: They'll find it eventually

**Protect config files**:
```bash
# Make config read-only
chmod 444 ~/.config/nextdns-blocker/config.json
```

**Monitor changes**:
- Check `audit.log` periodically
- Enable Discord notifications to parent's phone

### 6. Enable Notifications

Get alerts when blocking events occur:

```bash
# In .env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_NOTIFICATIONS_ENABLED=true
```

## Age-Appropriate Adjustments

### Young Children (Under 10)

```json
// Very limited access
"schedule": {
  "available_hours": [
    {
      "days": ["saturday", "sunday"],
      "time_ranges": [
        {"start": "10:00", "end": "11:00"},
        {"start": "15:00", "end": "16:00"}
      ]
    }
  ]
}
```

### Pre-Teens (10-12)

```json
// Moderate access
"schedule": {
  "available_hours": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "time_ranges": [
        {"start": "16:00", "end": "18:00"}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "time_ranges": [
        {"start": "10:00", "end": "18:00"}
      ]
    }
  ]
}
```

### Teenagers (13+)

```json
// More freedom with accountability
"schedule": {
  "available_hours": [
    {
      "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
      "time_ranges": [
        {"start": "16:00", "end": "21:00"}
      ]
    },
    {
      "days": ["saturday", "sunday"],
      "time_ranges": [
        {"start": "10:00", "end": "22:00"}
      ]
    }
  ]
}
```

Consider reducing `unblock_delay` to allow some autonomy:
```json
"unblock_delay": "4h"  // Instead of "never"
```

## Conversation Tips

### Explain the Rules

- Be transparent about what's blocked
- Explain why (not just "because I said so")
- Show them the schedule

### Gradual Trust

As they demonstrate responsibility:
1. Extend available hours
2. Reduce unblock delays
3. Remove some sites from blocklist

### Handle Pushback

When they complain:
- Listen to specific concerns
- Adjust if reasonable
- Stand firm on harmful content

## Troubleshooting

### Child Bypassed Blocking

Check how:
1. Different browser?
2. VPN/Proxy?
3. Mobile data instead of WiFi?

Solutions:
- Enable VPN blocking in NextDNS
- Apply NextDNS to all devices
- Use router-level DNS

### Homework Requires Blocked Site

Temporarily allow:
```bash
nextdns-blocker allow specific-site.com
```

Or adjust schedule for that site.

### Child Needs More Time

If legitimate need, adjust schedule:
```bash
nextdns-blocker config edit
# Increase hours, save
nextdns-blocker sync
```
