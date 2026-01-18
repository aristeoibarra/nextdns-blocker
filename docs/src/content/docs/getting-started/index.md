---
title: Introduction
description: Welcome to NextDNS Blocker - automated domain blocking with intelligent scheduling
---

NextDNS Blocker is a command-line tool that automates domain blocking using the [NextDNS](https://nextdns.io) API. It goes beyond simple blocklists by offering **per-domain scheduling**, **unblock delays**, and **emergency lockdown modes**.

## What is NextDNS Blocker?

While NextDNS provides powerful DNS-level blocking, managing time-based access rules manually is tedious. NextDNS Blocker automates this process:

- **Define schedules** for when each domain should be accessible
- **Automatic enforcement** via a watchdog that syncs every 2 minutes
- **Friction-based protection** with configurable unblock delays
- **Emergency mode** for crisis situations

## Key Concepts

### Blocklist vs Denylist

- **Blocklist** (`config.json`): Your local configuration defining which domains to manage and their schedules
- **Denylist** (NextDNS): The actual list on NextDNS that blocks DNS resolution

NextDNS Blocker reads your blocklist and syncs it to the NextDNS denylist based on your schedules.

### Schedule-Based Blocking

Each domain can have unique availability hours:

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

- **Outside available hours**: Domain is added to NextDNS denylist (blocked)
- **During available hours**: Domain is removed from denylist (accessible)

### Unblock Delays

To prevent impulsive unblocking, you can configure delays:

| Delay | Behavior |
|-------|----------|
| `"0"` | Instant unblock |
| `"30m"` | Wait 30 minutes |
| `"4h"` | Wait 4 hours |
| `"24h"` | Wait 24 hours |
| `"never"` | Cannot be unblocked manually |

### Panic Mode

Emergency lockdown that:
- Immediately blocks all configured domains
- Hides dangerous commands (`unblock`, `allow`)
- Cannot be disabled until the timer expires

## Requirements

- **Python 3.9+** (3.10+ recommended)
- **NextDNS account** with API access
- **macOS, Linux, or Windows**

## Next Steps

1. [Install NextDNS Blocker](/getting-started/installation/)
2. [Run the setup wizard](/getting-started/quick-setup/)
3. [Perform your first sync](/getting-started/first-sync/)
