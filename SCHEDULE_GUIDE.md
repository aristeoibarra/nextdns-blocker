# NextDNS Blocker - Schedule Configuration Guide

## Overview

NextDNS Blocker now supports **per-domain schedule configuration**, allowing you to define specific time ranges when each domain is **available** (not blocked). Outside these time ranges, domains are automatically blocked.

## How It Works

- **Available Hours**: Define time ranges when a domain is ALLOWED
- **Outside Available Hours**: Domain is BLOCKED automatically
- **Per-Domain Configuration**: Each domain can have its own schedule
- **Multi-Range Support**: Multiple time ranges per day
- **Day-Specific**: Different schedules for different days of the week

## Configuration Format

### Using domains.json

Create a `domains.json` file in the installation directory with the following structure:

```json
{
  "domains": [
    {
      "domain": "example.com",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "09:00", "end": "12:00"},
              {"start": "14:00", "end": "18:00"}
            ]
          }
        ]
      }
    }
  ]
}
```

### Schedule Configuration

Each domain configuration includes:

- **domain**: The domain name (required)
- **schedule**: Schedule configuration (optional)
  - **available_hours**: Array of availability blocks
    - **days**: Array of day names (lowercase)
      - Valid values: `monday`, `tuesday`, `wednesday`, `thursday`, `friday`, `saturday`, `sunday`
    - **time_ranges**: Array of time range objects
      - **start**: Start time in HH:MM format (24-hour)
      - **end**: End time in HH:MM format (24-hour)

### Example: Per-Day Schedule

```json
{
  "domains": [
    {
      "domain": "example.com",
      "description": "Different schedule each day",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday"],
            "time_ranges": [{"start": "09:00", "end": "12:00"}]
          },
          {
            "days": ["tuesday"],
            "time_ranges": [{"start": "14:00", "end": "18:00"}]
          },
          {
            "days": ["wednesday"],
            "time_ranges": [{"start": "10:00", "end": "16:00"}]
          },
          {
            "days": ["thursday"],
            "time_ranges": [{"start": "08:00", "end": "11:30"}]
          },
          {
            "days": ["friday"],
            "time_ranges": [{"start": "13:00", "end": "17:00"}]
          },
          {
            "days": ["saturday"],
            "time_ranges": [{"start": "10:00", "end": "14:00"}]
          },
          {
            "days": ["sunday"],
            "time_ranges": [{"start": "16:00", "end": "20:00"}]
          }
        ]
      }
    }
  ]
}
```

### Example: Weekday vs Weekend Schedule

```json
{
  "domains": [
    {
      "domain": "reddit.com",
      "description": "Social media - limited during work days",
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
              {"start": "10:00", "end": "22:00"}
            ]
          }
        ]
      }
    }
  ]
}
```

### Example: Always Blocked

To always block a domain (no available hours), set schedule to `null`:

```json
{
  "domain": "facebook.com",
  "description": "Always blocked",
  "schedule": null
}
```

## Commands

### Sync (Recommended)

```bash
python3 nextdns_blocker.py sync
```

Synchronizes all domains based on their configured schedules. This is the main command and runs automatically every 10 minutes via cron.

### Status

```bash
python3 nextdns_blocker.py status
```

Shows the current blocking status of all domains.

### Force Block/Unblock

```bash
python3 nextdns_blocker.py block    # Force block all domains (ignores schedules)
python3 nextdns_blocker.py unblock  # Force unblock all domains (ignores schedules)
```

These commands force block/unblock all domains regardless of their schedules. Use for manual override only.

## Automatic Synchronization

When you run `install.sh`, the system automatically:

1. Validates your `domains.json` configuration
2. Sets up a cron job to run `sync` every 10 minutes
3. Continuously evaluates and applies domain schedules

### Cron Configuration

The installer creates:

```cron
*/10 * * * * cd ~/nextdns-blocker && /usr/bin/python3 nextdns_blocker.py sync >> ~/nextdns-blocker/logs/cron.log 2>&1
```

This ensures domains are automatically blocked/unblocked according to their schedules.

## Getting Started

### Setup Steps

1. Copy the example configuration:
   ```bash
   cp domains.json.example domains.json
   ```

2. Edit `domains.json` with your domains and schedules:
   ```bash
   nano domains.json
   ```

3. Test the configuration:
   ```bash
   python3 nextdns_blocker.py sync
   ```

4. Run the installer to set up automatic sync:
   ```bash
   ./install.sh
   ```

## Timezone Configuration

Set your timezone in the `.env` file:

```bash
TIMEZONE=America/Mexico_City
```

All schedule times are evaluated in this timezone.

## Logging

View sync activity:

```bash
tail -f ~/nextdns-blocker/logs/nextdns_blocker.log
tail -f ~/nextdns-blocker/logs/cron.log
```

## Troubleshooting

### Domains not blocking/unblocking

1. Check the sync is running:
   ```bash
   crontab -l
   ```

2. Verify schedule configuration:
   ```bash
   python3 nextdns_blocker.py sync
   ```

3. Check logs for errors:
   ```bash
   tail -f ~/nextdns-blocker/logs/nextdns_blocker.log
   ```

### JSON parsing errors

Validate your JSON syntax:
```bash
python3 -m json.tool domains.json
```

### Wrong timezone

Update `.env` file and re-run sync:
```bash
echo "TIMEZONE=Your/Timezone" >> .env
python3 nextdns_blocker.py sync
```

## Advanced Examples

### Multiple Time Ranges in One Day

```json
{
  "domain": "youtube.com",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [
          {"start": "07:00", "end": "08:00"},
          {"start": "12:00", "end": "13:00"},
          {"start": "20:00", "end": "23:00"}
        ]
      }
    ]
  }
}
```

### Midnight Crossing (Not Currently Supported)

Time ranges that cross midnight are **not supported** in the current version.

Instead of:
```json
{"start": "22:00", "end": "02:00"}  // DOESN'T WORK
```

Use two separate day configurations:
```json
{
  "days": ["monday"],
  "time_ranges": [{"start": "22:00", "end": "23:59"}]
},
{
  "days": ["tuesday"],
  "time_ranges": [{"start": "00:00", "end": "02:00"}]
}
```

## See Also

- Main README: Basic setup and configuration
- domains.json.example: Complete configuration examples
- .env file: Global settings and timezone
