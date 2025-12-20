---
title: Timezone
description: Configure timezone for accurate schedule evaluation
---

The timezone setting determines how schedules are evaluated. A 9 AM schedule uses 9 AM in your configured timezone.

## Configuration

### In config.json

```json
{
  "settings": {
    "timezone": "America/New_York"
  }
}
```

### Via CLI

```bash
nextdns-blocker config set timezone America/Los_Angeles
```

## Auto-Detection

During `init`, timezone is automatically detected:

| Platform | Method |
|----------|--------|
| macOS | `/etc/localtime` symlink |
| Linux | `/etc/localtime` symlink |
| Windows | `tzutil /g` command |
| Fallback | `TZ` environment variable |
| Default | `UTC` |

## Common Timezones

### United States

| City | Timezone |
|------|----------|
| New York | `America/New_York` |
| Chicago | `America/Chicago` |
| Denver | `America/Denver` |
| Phoenix | `America/Phoenix` |
| Los Angeles | `America/Los_Angeles` |
| Anchorage | `America/Anchorage` |
| Honolulu | `Pacific/Honolulu` |

### Europe

| City | Timezone |
|------|----------|
| London | `Europe/London` |
| Paris | `Europe/Paris` |
| Berlin | `Europe/Berlin` |
| Madrid | `Europe/Madrid` |
| Rome | `Europe/Rome` |
| Amsterdam | `Europe/Amsterdam` |
| Moscow | `Europe/Moscow` |

### Asia/Pacific

| City | Timezone |
|------|----------|
| Tokyo | `Asia/Tokyo` |
| Shanghai | `Asia/Shanghai` |
| Hong Kong | `Asia/Hong_Kong` |
| Singapore | `Asia/Singapore` |
| Sydney | `Australia/Sydney` |
| Auckland | `Pacific/Auckland` |
| Dubai | `Asia/Dubai` |
| Mumbai | `Asia/Kolkata` |

### Americas

| City | Timezone |
|------|----------|
| Toronto | `America/Toronto` |
| Vancouver | `America/Vancouver` |
| Mexico City | `America/Mexico_City` |
| São Paulo | `America/Sao_Paulo` |
| Buenos Aires | `America/Argentina/Buenos_Aires` |

### Other

| Zone | Timezone |
|------|----------|
| UTC | `UTC` |
| GMT | `Etc/GMT` |

## IANA Timezone Database

NextDNS Blocker uses IANA timezone names. Full list:
[List of tz database time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)

### Format

- Region/City format: `America/New_York`
- Always use underscores: `New_York` not `New York`
- Case sensitive (typically capitalized)

## How Timezone Affects Schedules

### Example Schedule

```json
{
  "schedule": {
    "available_hours": [
      {
        "days": ["monday"],
        "time_ranges": [{"start": "09:00", "end": "17:00"}]
      }
    ]
  }
}
```

### With Different Timezones

| Timezone | Available At | In UTC |
|----------|--------------|--------|
| `America/New_York` | 9 AM - 5 PM ET | 14:00 - 22:00 UTC |
| `America/Los_Angeles` | 9 AM - 5 PM PT | 17:00 - 01:00 UTC |
| `Europe/London` | 9 AM - 5 PM GMT | 09:00 - 17:00 UTC |
| `Asia/Tokyo` | 9 AM - 5 PM JST | 00:00 - 08:00 UTC |

### Daylight Saving Time

IANA timezones automatically handle DST:

- `America/New_York` switches between EST and EDT
- `Europe/London` switches between GMT and BST
- Schedules adjust automatically

## Viewing Current Timezone

### In Status

```bash
nextdns-blocker status
```

Shows current time with timezone:
```
Time: 2024-01-15 14:30:00 America/New_York
```

### In Config

```bash
nextdns-blocker config show | grep timezone
```

## Changing Timezone

### Method 1: CLI

```bash
nextdns-blocker config set timezone Europe/London
```

### Method 2: Edit Config

```bash
nextdns-blocker config edit
```

Change the timezone value and save.

### Method 3: Re-run Init

```bash
nextdns-blocker init
```

Re-detects system timezone.

## Multi-Timezone Considerations

### Traveling

When traveling across timezones:

1. **Keep original timezone** - Schedules stay consistent
2. **Update to local timezone** - Schedules adjust to local time

Recommendation: Keep your "home" timezone for consistency.

### Remote Work

If you work with teams in different timezones:

1. Configure for your local timezone
2. Adjust schedules to account for meeting times
3. Consider using UTC if working globally

## Troubleshooting

### Wrong time shown in status

1. Check configured timezone:
   ```bash
   nextdns-blocker config show | grep timezone
   ```

2. Verify system timezone:
   ```bash
   # macOS/Linux
   date

   # Windows
   tzutil /g
   ```

3. Update if mismatched:
   ```bash
   nextdns-blocker config set timezone America/New_York
   ```

### Schedule not matching expectations

1. **Check timezone is correct**

2. **Verify 24-hour time**:
   - 6 PM = `18:00`
   - 9 AM = `09:00`

3. **Check day name**:
   - Use lowercase: `monday`
   - Verify correct day

### "Unknown timezone" error

1. Check spelling (case sensitive)
2. Use Region/City format
3. Consult IANA timezone list

```bash
# Valid
nextdns-blocker config set timezone America/New_York

# Invalid
nextdns-blocker config set timezone EST
nextdns-blocker config set timezone Eastern
nextdns-blocker config set timezone new_york
```

### DST transition issues

IANA timezones handle DST automatically. If you see issues:

1. Update `tzdata` package:
   ```bash
   pip install --upgrade tzdata
   ```

2. Ensure Python 3.9+ (uses zoneinfo)

## Technical Details

### Implementation

NextDNS Blocker uses Python's `zoneinfo` module (Python 3.9+):

```python
from zoneinfo import ZoneInfo
tz = ZoneInfo("America/New_York")
```

### Timezone Data

Timezone data comes from:
- System tzdata on macOS/Linux
- `tzdata` Python package (bundled)

### Validation

Valid timezones are checked against the IANA database during:
- `config set timezone`
- `config validate`
- `init`
