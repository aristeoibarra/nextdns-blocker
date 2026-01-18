---
title: Productivity Setup
description: Configure NextDNS Blocker for maximum work focus
---

This guide helps you set up NextDNS Blocker for a productive work environment, blocking distractions during focus hours while allowing reasonable breaks.

## Overview

**Goal**: Minimize distractions during work hours

**Strategy**:
- Block social media and entertainment during work
- Allow access during lunch break
- Full access in evenings and weekends
- Moderate unblock delays for friction

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
      "domain": "reddit.com",
      "description": "Social media - breaks only",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "23:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "08:00", "end": "23:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "twitter.com",
      "description": "News/social - evenings only",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
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
      "domain": "youtube.com",
      "description": "Streaming - limited access",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "19:00", "end": "22:00"}
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
      "domain": "instagram.com",
      "description": "Social media - high friction",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "12:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "tiktok.com",
      "description": "Time sink - weekends only",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "14:00", "end": "20:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": [
    {
      "domain": "github.com",
      "description": "Work resource"
    },
    {
      "domain": "stackoverflow.com",
      "description": "Work resource"
    },
    {
      "domain": "docs.google.com",
      "description": "Work documents"
    }
  ]
}
```

## Understanding the Schedule

### Weekday Structure

```
00:00 ─────────────────────────────────────────────── 23:59
       BLOCKED │  LUNCH  │    BLOCKED    │  EVENING  │
       ────────┼─────────┼───────────────┼───────────┼──
       00-12:00│12:00-13:00│   13:00-18:00│18:00-23:00│
```

### Weekend Structure

```
00:00 ─────────────────────────────────────────────── 23:59
       SLEEP  │         AVAILABLE                    │
       ───────┼──────────────────────────────────────┼──
       00-08:00│           08:00-23:00               │
```

## Customization

### Adjust Work Hours

If you work different hours, modify the blocked periods:

```json
// Early bird (6 AM - 3 PM)
"time_ranges": [
  {"start": "11:00", "end": "12:00"},  // Late morning break
  {"start": "15:00", "end": "22:00"}   // After work
]

// Night owl (11 AM - 8 PM)
"time_ranges": [
  {"start": "14:00", "end": "15:00"},  // Afternoon break
  {"start": "20:00", "end": "01:00"}   // After work
]
```

### Add More Sites

Common additions:

```json
// News sites
{"domain": "news.ycombinator.com", "unblock_delay": "30m", ...},
{"domain": "cnn.com", "unblock_delay": "0", ...},

// Shopping
{"domain": "amazon.com", "unblock_delay": "30m", ...},
{"domain": "ebay.com", "unblock_delay": "30m", ...},

// Other social
{"domain": "facebook.com", "unblock_delay": "4h", ...},
{"domain": "linkedin.com", "unblock_delay": "0", ...}
```

### Adjust Friction

| Site Risk | Recommended Delay |
|-----------|-------------------|
| Low (news) | `"0"` |
| Moderate (social) | `"30m"` |
| High (addictive) | `"4h"` |
| Very High | `"24h"` |

## Setup Steps

### 1. Install NextDNS Blocker

```bash
brew install nextdns-blocker  # or pip install
nextdns-blocker init
```

### 2. Apply Configuration

```bash
# Copy template
cp examples/work-focus.json ~/.config/nextdns-blocker/config.json

# Or create from scratch
nextdns-blocker config edit
# Paste the configuration above
```

### 3. Set Your Timezone

```bash
nextdns-blocker config set timezone America/New_York
```

### 4. Validate

```bash
nextdns-blocker config validate
```

### 5. Test with Dry Run

```bash
nextdns-blocker config push --dry-run -v
```

### 6. Install Watchdog

```bash
nextdns-blocker watchdog install
```

### 7. Verify

```bash
nextdns-blocker status
```

## Tips for Success

### Start Gradual

Begin with few sites and shorter blocks:
1. Week 1: Block 2-3 sites during morning
2. Week 2: Add afternoon blocking
3. Week 3: Add more sites
4. Week 4: Increase delays

### Use Panic Mode

When deadline pressure hits:

```bash
nextdns-blocker panic 120  # 2 hours of focus
```

### Review Weekly

Check what's working:
- Are you attempting many unblocks?
- Which sites cause most friction?
- Are schedules aligned with actual work patterns?

### Don't Overblock

Leave legitimate work tools accessible:
- Documentation sites
- Development tools
- Communication (Slack, Teams) if needed

## Troubleshooting

### "I need access for work"

Add to allowlist:
```bash
nextdns-blocker allow important-work-site.com
```

### "Schedule doesn't match my hours"

Adjust and test:
```bash
nextdns-blocker config edit
nextdns-blocker config push --dry-run
```

### "Too restrictive"

Reduce friction gradually:
1. Increase available hours
2. Reduce unblock delays
3. Remove some sites from blocklist
