---
title: Gaming Schedule
description: Manage gaming time with balanced access rules
---

This guide helps manage gaming platform access with reasonable limits while still allowing enjoyment.

## Overview

**Goal**: Enjoy gaming without it taking over

**Strategy**:
- Block gaming during work/school hours
- Allow evenings and weekends
- Moderate friction to prevent binges
- Special allowances for multiplayer sessions

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
      "domain": "store.steampowered.com",
      "description": "Steam store - prevent impulse purchases",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday"],
            "time_ranges": [
              {"start": "19:00", "end": "22:00"}
            ]
          },
          {
            "days": ["friday"],
            "time_ranges": [
              {"start": "18:00", "end": "23:59"}
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
      "domain": "epicgames.com",
      "description": "Epic Games store",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday"],
            "time_ranges": [
              {"start": "19:00", "end": "22:00"}
            ]
          },
          {
            "days": ["friday"],
            "time_ranges": [
              {"start": "18:00", "end": "23:59"}
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
      "domain": "twitch.tv",
      "description": "Game streaming",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday"],
            "time_ranges": [
              {"start": "20:00", "end": "22:00"}
            ]
          },
          {
            "days": ["friday"],
            "time_ranges": [
              {"start": "19:00", "end": "23:59"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "12:00", "end": "23:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "discord.com",
      "description": "Gaming chat",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "17:00", "end": "23:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "09:00", "end": "23:59"}
            ]
          }
        ]
      }
    },
    {
      "domain": "reddit.com",
      "description": "Gaming subreddits temptation",
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
      "description": "Gaming videos",
      "unblock_delay": "0",
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
              {"start": "09:00", "end": "23:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "origin.com",
      "description": "EA launcher",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["friday", "saturday", "sunday"],
            "time_ranges": [
              {"start": "17:00", "end": "23:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "battle.net",
      "description": "Blizzard launcher",
      "unblock_delay": "4h",
      "schedule": {
        "available_hours": [
          {
            "days": ["friday", "saturday", "sunday"],
            "time_ranges": [
              {"start": "17:00", "end": "23:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": []
}
```

## Understanding the Schedule

### Weekday Gaming

```
00:00 ─────────────────────────────────────────────── 23:59
      BLOCKED     │     GAMING     │    BLOCKED
      ────────────┼────────────────┼────────────
         00-19:00 │    19:00-22:00 │    22:00-24
```

**Why stop at 10 PM?**
- Sleep is important
- Prevents "just one more game" at midnight
- Fresh for next day

### Friday Night Special

```
00:00 ─────────────────────────────────────────────── 23:59
      BLOCKED     │        LATE GAMING
      ────────────┼─────────────────────────────────
         00-18:00 │           18:00-23:59
```

Extended hours to reward week completion.

### Weekend Freedom

```
00:00 ─────────────────────────────────────────────── 23:59
 SLEEP │            GAMING ALL DAY            │ SLEEP
 ──────┼──────────────────────────────────────┼──────
 00-10 │              10:00-23:00             │ 23-24
```

## Platform-Specific Notes

### Steam

**Why block the store?**
- Prevents impulse purchases
- Limits browsing when you should work
- 4h delay = time to reconsider purchases

**Note**: Games you own still work locally.

### Discord

**More lenient because**:
- Friends communication
- Coordination for multiplayer
- 30m delay = quick friction

### Twitch

**Why shorter hours weekdays?**
- Passive consumption
- Easy to binge
- Limited to after dinner

## Multiplayer Sessions

### Scheduled Raid Nights

If your guild/clan has scheduled events:

```json
// Add specific times
{
  "days": ["wednesday"],  // Raid night
  "time_ranges": [
    {"start": "20:00", "end": "23:00"}
  ]
}
```

### Spontaneous Gaming

For unplanned sessions with friends:

```bash
# If Discord is blocked, start the delay
nextdns-blocker unblock discord.com
# Wait for delay to complete, then coordinate
```

Or add to allowlist temporarily:
```bash
nextdns-blocker allow discord.com
# After session:
nextdns-blocker disallow discord.com
```

## New Game Releases

### Launch Day Strategy

When a new game releases:

**Option 1**: Plan ahead
- Schedule vacation day
- Weekend release = normal weekend access

**Option 2**: Temporary adjustment
```bash
nextdns-blocker config edit
# Increase hours temporarily
# Revert after launch week
```

**Option 3**: Accept the delay
- 4h delay means you can still play
- Just can't impulse-buy immediately

## Preventing Binges

### Hard Stop Times

Schedules end at specific times:
- Weekdays: 10 PM
- Weekends: 11 PM

After that, blocking resumes automatically.

### Morning Protection

No gaming until after 10 AM weekends:
- Ensures breakfast
- Prevents all-day sessions starting at 6 AM

### The 4-Hour Delay

For game stores:
- Can't impulse-buy at 2 AM
- Time to research reviews
- Price comparisons
- Sleep on it

## Adjusting for Life Changes

### During Busy Periods

Exams, deadlines, etc.:

```bash
# Use panic mode
nextdns-blocker panic 8h  # Full day focus

# Or reduce schedule
nextdns-blocker config edit
# Limit to weekends only temporarily
```

### During Vacations

More relaxed:

```bash
nextdns-blocker config edit
# Increase available hours temporarily
```

### Permanent Changes

If schedule doesn't fit life:

1. Track which times you want access
2. Adjust config to match actual needs
3. Keep some friction (delays)

## Tips for Healthy Gaming

### Set Session Limits

Even when available:
- Set phone timer for breaks
- Hydrate and stretch
- 2-hour max sessions

### Social Gaming > Solo

Prioritize:
- Multiplayer with friends
- Co-op experiences
- Community events

Over:
- Solo grinding
- Endless open-world roaming
- Autoplayed content

### Quality Over Quantity

Use blocked time to:
- Research games you actually want
- Read reviews thoughtfully
- Maintain a backlog (not buy everything)

## Troubleshooting

### "I missed guild raid"

Add raid times to schedule:
```bash
nextdns-blocker config edit
```

### "Friend invited me to play"

Quick options:
```bash
# If discord blocked, start the delay timer
nextdns-blocker unblock discord.com

# Or add to allowlist temporarily
nextdns-blocker allow discord.com
```

### "4h delay is too long"

For casual gamers, reduce:
```json
"unblock_delay": "30m"
```

But keep some friction for stores to prevent impulse purchases.
