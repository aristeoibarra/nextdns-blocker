---
title: Why nextdns-blocker?
description: How nextdns-blocker solves common NextDNS limitations and community pain points
---

NextDNS is powerful for network-wide DNS filtering, but users frequently request features it doesn't natively support. **nextdns-blocker** fills these gaps.

## Community Pain Points → Solutions

These are real requests from NextDNS communities (Reddit, Help Center, GitHub):

| What Users Ask For | nextdns-blocker Solution |
|--------------------|--------------------------|
| "I want to block YouTube only during work hours" | [Per-domain scheduling](/configuration/schedules/) |
| "I need multiple recreation windows per day" | [Multiple time_ranges](/configuration/schedules/#multiple-time-ranges) |
| "I want a delay before I can unblock a site" | [Configurable unblock_delay](/configuration/unblock-delay/) |
| "I need an emergency button to block everything" | [Panic mode](/features/panic-mode/) |
| "I want different rules for weekdays vs weekends" | [Day-based scheduling](/configuration/schedules/#different-rules-per-day) |
| "I want to block gaming category but allow Discord" | [Allowlist priority](/configuration/filtering-priority/) |
| "I need to know when blocks change" | [Discord notifications](/features/notifications/) |
| "I want it to run automatically" | [Watchdog service](/features/watchdog/) |

## vs Alternatives

| Feature | nextdns-blocker | Browser Extensions | Native NextDNS |
|---------|-----------------|-------------------|----------------|
| Per-domain schedules | Yes | No | No |
| Network-wide (all devices) | Yes | No | Yes |
| Unblock delays (friction) | Yes | Some | No |
| Hard to bypass | Yes | No | Yes |
| Automated enforcement | Yes | No | No |
| Category + exception control | Yes | No | Partial |
| Emergency lockdown | Yes | No | No |

## Real Use Cases

### Digital Wellness / Addiction Recovery

For those building healthier digital habits:

- **Unblock delays** add friction against impulsive access
- **Panic mode** provides emergency lockdown when needed
- **Strict schedules** limit entertainment to specific windows
- **"never" unblock** makes certain blocks permanent

```json
{
  "domain": "reddit.com",
  "unblock_delay": "4h",
  "schedule": {
    "available_hours": [
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "18:00", "end": "22:00"}]
      }
    ]
  }
}
```

### Remote Work Productivity

Block distractions during work, allow them after:

- **Weekday/weekend differentiation** - stricter on workdays
- **Multiple windows** - lunch break + evening access
- **Work resources in allowlist** - never blocked

```json
{
  "blocklist": [
    {
      "domain": "twitter.com",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "23:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": [
    {"domain": "github.com"},
    {"domain": "stackoverflow.com"}
  ]
}
```

### Parental Control

Manage children's screen time:

- **Gaming only on weekends** - schedule-based access
- **Educational sites always allowed** - via allowlist
- **"never" unblock delay** - kids can't bypass
- **Category blocking** - block entire content types

See the [Parental Control Guide](/guides/parental-control/) for a complete setup.

### Focus Sessions

Temporary strict blocking during deep work:

```bash
# Block everything for 2 hours
nextdns-blocker panic 120
```

## What nextdns-blocker Does NOT Do

To set correct expectations:

- **Not a VPN** - Uses your existing NextDNS profile
- **Not a browser extension** - Works at DNS level, network-wide
- **Not real-time filtering** - Syncs every 2 minutes via watchdog
- **Requires NextDNS subscription** - Needs API access (free tier works)

## Getting Started

Ready to try it?

1. [Install nextdns-blocker](/getting-started/installation/)
2. [Quick Setup](/getting-started/quick-setup/) - 5 minutes to configure
3. [Your First Sync](/getting-started/first-sync/) - See it in action

Or explore specific features:
- [Schedules](/configuration/schedules/) - Time-based access control
- [Unblock Delay](/configuration/unblock-delay/) - Add friction
- [Panic Mode](/features/panic-mode/) - Emergency lockdown
