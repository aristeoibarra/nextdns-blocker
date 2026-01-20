---
title: Unblock Delay
description: Add friction against impulsive unblocking with configurable delays
---

Unblock delays create friction between requesting access and receiving it, helping resist impulsive decisions.

## Concept

When you try to unblock a domain with a delay configured:

1. **Request**: You run `unblock domain.com`
2. **Queue**: A pending action is created
3. **Wait**: The delay period passes
4. **Execute**: Domain is unblocked automatically

During the wait, you can cancel if the urge passes.

## Configuration

Set in `config.json` for each domain:

```json
{
  "blocklist": [
    {
      "domain": "reddit.com",
      "unblock_delay": "30m"
    }
  ]
}
```

## Valid Values

### Common Presets

| Value | Delay | Use Case |
|-------|-------|----------|
| `"0"` | Instant | Low-risk sites |
| `"30m"` | 30 minutes | Moderate friction |
| `"4h"` | 4 hours | High friction |
| `"24h"` | 24 hours | Maximum friction |
| `"never"` | Cannot unblock | Harmful content |

### Flexible Duration Format

You can use any duration with these formats:

| Format | Examples | Description |
|--------|----------|-------------|
| `{n}m` | `"15m"`, `"45m"`, `"90m"` | Minutes |
| `{n}h` | `"1h"`, `"2h"`, `"8h"`, `"12h"` | Hours |
| `{n}d` | `"1d"`, `"2d"`, `"7d"` | Days |

Examples of valid custom delays:

```json
{
  "blocklist": [
    {
      "domain": "quick-check.com",
      "unblock_delay": "15m"
    },
    {
      "domain": "gaming-site.com",
      "unblock_delay": "90m"
    },
    {
      "domain": "streaming.com",
      "unblock_delay": "2h"
    },
    {
      "domain": "dating-app.com",
      "unblock_delay": "2d"
    },
    {
      "domain": "weekly-reset.com",
      "unblock_delay": "7d"
    }
  ]
}
```

## Behavior by Value

### Instant (`"0"`)

```bash
nextdns-blocker unblock reddit.com
```

Output:
```
Unblocking reddit.com...
✓ reddit.com unblocked
```

Immediate access, no delay.

### Timed Delays (`"30m"`, `"4h"`, `"24h"`)

```bash
nextdns-blocker unblock bumble.com
```

Output:
```
Unblock scheduled for 'bumble.com'
Delay: 24h
Execute at: 2024-01-16 14:30:00
ID: pnd_20240115_143000_a1b2c3

Use 'pending list' to view or 'pending cancel <ID>' to abort
```

### Protected (`"never"`)

```bash
nextdns-blocker unblock gambling-site.com
```

Output:
```
✗ Cannot unblock 'gambling-site.com'
  This domain is protected (unblock_delay: never)
```

No way to manually unblock.

## Why Use Delays?

### Research Background

Studies show that cravings typically:
- Peak within minutes
- Fade significantly after 20-30 minutes
- Often disappear entirely after a few hours

### Friction Creates Space

The delay:
1. **Interrupts autopilot** - You can't access impulsively
2. **Creates reflection time** - Do you really need this?
3. **Allows cancellation** - Changed your mind? Cancel it
4. **Reduces regret** - Deliberate choices feel better

## Recommended Settings

### By Content Type

| Content | Recommended | Reasoning |
|---------|-------------|-----------|
| Social media | `"30m"` | Quick impulse control |
| Gaming platforms | `"4h"` | Longer to resist gaming sessions |
| Streaming | `"30m"` to `"4h"` | Depends on addiction level |
| Dating apps | `"4h"` to `"24h"` | High impulse, high regret |
| Gambling | `"never"` | No legitimate need |
| Adult content | `"never"` | Harmful, no exceptions |

### By Risk Level

| Risk | Delay | Description |
|------|-------|-------------|
| Low | `"0"` | Useful but not problematic |
| Moderate | `"30m"` | Sometimes problematic |
| High | `"4h"` | Often problematic |
| Very High | `"24h"` | Frequently problematic |
| Maximum | `"never"` | Always problematic |

## Managing Pending Actions

### List Pending

```bash
nextdns-blocker pending list
```

### View Details

```bash
nextdns-blocker pending show <ID>
```

### Cancel

```bash
nextdns-blocker pending cancel <ID>
```

See [pending command](/commands/pending/) for details.

## Examples

### Productivity Setup

```json
{
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media - moderate friction",
      "unblock_delay": "30m",
      "schedule": {...}
    },
    {
      "domain": "twitter.com",
      "description": "News - low friction",
      "unblock_delay": "0",
      "schedule": {...}
    },
    {
      "domain": "youtube.com",
      "description": "Streaming - high friction",
      "unblock_delay": "4h",
      "schedule": {...}
    }
  ]
}
```

### Recovery Setup

```json
{
  "blocklist": [
    {
      "domain": "gambling-site.com",
      "description": "Protected - no access",
      "unblock_delay": "never",
      "schedule": null
    },
    {
      "domain": "casino.com",
      "description": "Protected - no access",
      "unblock_delay": "never",
      "schedule": null
    },
    {
      "domain": "dating-app.com",
      "description": "Maximum friction",
      "unblock_delay": "24h",
      "schedule": null
    }
  ]
}
```

### Parental Control

```json
{
  "blocklist": [
    {
      "domain": "social-media.com",
      "description": "Child account - parental approval needed",
      "unblock_delay": "never",
      "schedule": {...}
    },
    {
      "domain": "gaming-site.com",
      "description": "Gaming - must wait",
      "unblock_delay": "4h",
      "schedule": {...}
    }
  ]
}
```

## Delays and Schedules

Unblock delay and schedule are independent:

- **Schedule**: Automatic access during certain hours
- **Delay**: Friction for manual unblocking

Example:
```json
{
  "domain": "reddit.com",
  "unblock_delay": "30m",
  "schedule": {
    "available_hours": [
      {"days": ["saturday"], "time_ranges": [{"start": "10:00", "end": "22:00"}]}
    ]
  }
}
```

- Saturday 10am-10pm: Auto-unblocked by schedule
- Other times: Manual unblock requires 30-minute wait

## Bypass Considerations

### Legitimate Bypasses

Some situations may need immediate access:
- Emergency requiring blocked information
- Work necessity during blocked time
- Schedule misconfiguration

Options:
1. Edit config to temporarily reduce delay
2. Wait for delay (as designed)
3. Add domain to allowlist temporarily

### Preventing Abuse

To make bypass harder:
1. Use `"never"` for harmful content
2. Don't keep delay settings memorized

## Troubleshooting

### Pending action not executing

1. Check watchdog is running:
   ```bash
   nextdns-blocker watchdog status
   ```

2. Force sync:
   ```bash
   nextdns-blocker config push
   ```

### Changed my mind but can't cancel

If action already executed:
- Re-block via schedule (wait for next sync)
- Or use `nextdns-blocker config push` to re-apply rules

### Need to change delay for domain

Edit configuration:

```bash
nextdns-blocker config edit
# Change unblock_delay value
# Save and exit
```

Changes affect future unblock requests, not existing pending actions.
