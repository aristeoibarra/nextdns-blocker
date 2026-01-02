---
title: Schedules
description: Configure time-based domain availability rules
---

Schedules define when domains are accessible. Outside scheduled hours, domains are blocked.

## Basic Concept

```
Schedule = "When can I access this domain?"
```

- **Within schedule**: Domain is UNBLOCKED
- **Outside schedule**: Domain is BLOCKED
- **No schedule (`null`)**: Always BLOCKED

## Schedule Structure

```json
{
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
```

## Common Patterns

### Always Blocked

No access at any time:

```json
{
  "domain": "gambling-site.com",
  "schedule": null
}
```

Or simply omit the schedule field.

### Always Available

Access 24/7 (useful in blocklist for management without blocking):

```json
{
  "domain": "work-tool.com",
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

### Weekday Work Hours

Monday-Friday, 9 AM to 5 PM:

```json
{
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

### Weekends Only

Saturday and Sunday, all day:

```json
{
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

Lunch break and evening:

```json
{
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

### Different Days, Different Times

Weekdays vs weekends:

```json
{
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

Crossing midnight (e.g., Friday night gaming):

```json
{
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

**Important:** The day refers to when the window *starts*:
- Friday 22:00-02:00 = Friday 10 PM to Saturday 2 AM
- Saturday 22:00-02:00 = Saturday 10 PM to Sunday 2 AM

## Time Format

Use 24-hour format: `HH:MM`

| 12-hour | 24-hour |
|---------|---------|
| 12:00 AM | `00:00` |
| 6:00 AM | `06:00` |
| 12:00 PM | `12:00` |
| 6:00 PM | `18:00` |
| 11:59 PM | `23:59` |

## Day Names

Use lowercase full names:

- `monday`
- `tuesday`
- `wednesday`
- `thursday`
- `friday`
- `saturday`
- `sunday`

## Schedule Logic

### How Evaluation Works

1. Get current day and time (in configured timezone)
2. Find matching day rules in `available_hours`
3. Check if current time falls within any `time_ranges`
4. If yes → UNBLOCK, if no → BLOCK

### Multiple Rules

Rules are evaluated with OR logic:

```json
{
  "available_hours": [
    {"days": ["monday"], "time_ranges": [{"start": "09:00", "end": "17:00"}]},
    {"days": ["friday"], "time_ranges": [{"start": "09:00", "end": "12:00"}]}
  ]
}
```

This means: "Available Monday 9-5 OR Friday 9-12"

### Overlapping Ranges

Overlapping time ranges work fine:

```json
{
  "time_ranges": [
    {"start": "08:00", "end": "12:00"},
    {"start": "10:00", "end": "14:00"}
  ]
}
```

Effectively becomes 8:00-14:00.

## Timezone

Schedules use the configured timezone:

```json
{
  "settings": {
    "timezone": "America/New_York"
  }
}
```

A schedule for 9:00 AM evaluates at 9:00 AM Eastern Time.

See [Timezone Configuration](/configuration/timezone/) for details.

## Real-World Examples

### Social Media (Productivity)

Limited access during work hours:

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
        "time_ranges": [
          {"start": "10:00", "end": "23:00"}
        ]
      }
    ]
  }
}
```

### Gaming (Student)

Weekday evenings, more on weekends:

```json
{
  "domain": "store.steampowered.com",
  "description": "Gaming - after homework",
  "unblock_delay": "4h",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday"],
        "time_ranges": [
          {"start": "19:00", "end": "21:00"}
        ]
      },
      {
        "days": ["friday"],
        "time_ranges": [
          {"start": "18:00", "end": "23:00"}
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
}
```

### Streaming (Family)

Evening entertainment only:

```json
{
  "domain": "netflix.com",
  "description": "Streaming - evening family time",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        "time_ranges": [
          {"start": "19:00", "end": "22:00"}
        ]
      }
    ]
  }
}
```

## Debugging Schedules

### Check Current State

```bash
nextdns-blocker status
```

Shows when each domain will transition.

### Dry Run at Specific Time

```bash
nextdns-blocker config sync --dry-run --verbose
```

Shows detailed schedule evaluation.

### Common Issues

**Domain blocked when it shouldn't be:**
1. Check timezone is correct
2. Verify current day matches schedule
3. Check time ranges include current time

**Domain available when it should be blocked:**
1. Check for overlapping rules
2. Verify no typos in day names
3. Ensure schedule isn't `null`
