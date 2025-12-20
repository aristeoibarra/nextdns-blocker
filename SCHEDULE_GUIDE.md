# Schedule Configuration Guide

This guide explains how to configure domain schedules in `config.json`.

## Basic Structure

```json
{
  "blocklist": [
    {
      "domain": "example.com",
      "description": "Optional description",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday"],
            "time_ranges": [
              {"start": "09:00", "end": "17:00"}
            ]
          }
        ]
      }
    }
  ]
}
```

## Schedule Options

### Always Blocked

To keep a domain always blocked, set `schedule` to `null` or omit it:

```json
{
  "domain": "always-blocked.com",
  "description": "This domain is always blocked",
  "schedule": null
}
```

### Always Available

To keep a domain always available (never blocked), use a 24/7 schedule:

```json
{
  "domain": "always-open.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "time_ranges": [
          {"start": "00:00", "end": "23:59"}
        ]
      }
    ]
  }
}
```

### Weekday Schedule

Available Monday-Friday during work hours:

```json
{
  "domain": "work-site.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [
          {"start": "09:00", "end": "17:00"}
        ]
      }
    ]
  }
}
```

### Weekend Schedule

Available only on weekends:

```json
{
  "domain": "weekend-only.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [
          {"start": "08:00", "end": "23:00"}
        ]
      }
    ]
  }
}
```

### Multiple Time Ranges

Available during lunch and evening hours:

```json
{
  "domain": "break-time.com",
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

### Different Schedules per Day

Different availability on weekdays vs weekends:

```json
{
  "domain": "mixed-schedule.com",
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
}
```

### Overnight Schedule

For time ranges that cross midnight (e.g., Friday night gaming):

```json
{
  "domain": "late-night.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["friday", "saturday"],
        "time_ranges": [
          {"start": "22:00", "end": "02:00"}
        ]
      }
    ]
  }
}
```

**Note:** When using overnight schedules, the day refers to when the window starts. A Friday 22:00-02:00 window means Friday 22:00 to Saturday 02:00.

## Time Format

- Use 24-hour format: `HH:MM`
- Hours: 00-23
- Minutes: 00-59
- Examples: `"09:00"`, `"13:30"`, `"23:59"`, `"00:00"`

## Day Names

Use lowercase day names:
- `monday`
- `tuesday`
- `wednesday`
- `thursday`
- `friday`
- `saturday`
- `sunday`

## Timezone

The schedule respects the timezone configured in `.env`:

```bash
TIMEZONE=America/Mexico_City
```

See [list of valid timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Complete Example

```json
{
  "domains": [
    {
      "domain": "reddit.com",
      "description": "Reddit - limited access",
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
      "description": "Twitter - blocked during work",
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
              {"start": "00:00", "end": "23:59"}
            ]
          }
        ]
      }
    },
    {
      "domain": "gambling-site.com",
      "description": "Always blocked",
      "schedule": null
    }
  ]
}
```

## Validation

Before running, validate your JSON syntax:

```bash
python3 -m json.tool config.json
```

The application also validates:
- Domain names are not empty
- Day names are valid
- Time ranges have both `start` and `end`

## Troubleshooting

### Domain not blocking/unblocking

1. Check the current time matches your schedule
2. Verify timezone in `.env` is correct
3. Run `nextdns-blocker status` to see current state
4. Check logs: `tail -f ~/.local/share/nextdns-blocker/logs/app.log`

### Invalid JSON

Common issues:
- Missing comma between entries
- Trailing comma after last entry
- Unquoted strings

Use [jsonlint.com](https://jsonlint.com) to validate.

### Schedule not taking effect

Changes take effect on the next sync (every 2 minutes). To force:

```bash
nextdns-blocker sync
```

## Allowlist Schedules

Allowlist entries now support schedules, enabling time-based allowlisting for domains blocked by NextDNS categories or services.

### Use Case

When NextDNS blocks domains via:
- **Categories** (e.g., "Streaming" blocks youtube.com, netflix.com)
- **Services/Apps** (e.g., "TikTok" blocks multiple tiktok domains)

You can use scheduled allowlist entries to temporarily unblock these domains during specific hours.

### Allowlist Schedule Behavior

| Schedule | Behavior |
|----------|----------|
| `null` or missing | Always in allowlist (24/7) |
| defined | Only in allowlist during scheduled hours |

**Logic (inverse of blocklist)**:
- **Outside schedule**: Domain is NOT in allowlist → category/service blocks it
- **During schedule**: Domain IS in allowlist → unblocked

### Example: Streaming in Evening Only

```json
{
  "allowlist": [
    {
      "domain": "youtube.com",
      "description": "Streaming - blocked by category, allow evenings",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [{ "start": "20:00", "end": "22:30" }]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [{ "start": "10:00", "end": "23:00" }]
          }
        ]
      }
    },
    {
      "domain": "aws.amazon.com",
      "description": "AWS Console - always accessible (no schedule)"
    }
  ]
}
```

In this example:
- **youtube.com**: Only accessible during evenings (weekdays 20:00-22:30, weekends 10:00-23:00)
- **aws.amazon.com**: Always accessible (no schedule = always in allowlist)

### Overnight Ranges

Allowlist schedules support overnight ranges just like blocklist schedules:

```json
{
  "domain": "netflix.com",
  "description": "Streaming - late night only",
  "schedule": {
    "available_hours": [
      {
        "days": ["friday", "saturday"],
        "time_ranges": [{ "start": "22:00", "end": "02:00" }]
      }
    ]
  }
}
```

This allows Netflix on Friday and Saturday nights from 10 PM to 2 AM.
