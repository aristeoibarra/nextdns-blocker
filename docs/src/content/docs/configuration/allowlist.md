---
title: Allowlist
description: Configure domain exceptions and scheduled allowlist entries
---

The allowlist creates exceptions to blocking, allowing specific domains to remain accessible.

## Basic Entry

```json
{
  "allowlist": [
    {
      "domain": "aws.amazon.com",
      "description": "Work resource - always accessible"
    }
  ]
}
```

## Entry Fields

### domain (required)

The domain to allow.

```json
{"domain": "aws.amazon.com"}
```

### description (optional)

Human-readable note.

```json
{
  "domain": "aws.amazon.com",
  "description": "AWS Console for work"
}
```

### schedule (optional)

When the allowlist entry is active. Default is `null` (always allowed).

```json
{
  "domain": "youtube.com",
  "description": "Entertainment - evenings only",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [{"start": "20:00", "end": "22:00"}]
      }
    ]
  }
}
```

## Allowlist Behavior

### Without Schedule (null)

Always in NextDNS allowlist:

| State | Always |
|-------|--------|
| NextDNS | In allowlist 24/7 |
| Access | Always allowed |

### With Schedule

Time-based allowlist membership:

| Time | Within Schedule | Outside Schedule |
|------|-----------------|------------------|
| NextDNS | In allowlist | Not in allowlist |
| Access | Allowed | Subject to other blocks |

**Note:** This is the inverse of blocklist behavior.

## Use Cases

### Subdomain Exceptions

Block parent domain, allow specific subdomain:

```json
{
  "blocklist": [
    {"domain": "amazon.com", "schedule": null}
  ],
  "allowlist": [
    {"domain": "aws.amazon.com", "description": "Work resource"}
  ]
}
```

Result:
- `amazon.com` → Blocked
- `www.amazon.com` → Blocked (inherits from parent)
- `aws.amazon.com` → **Allowed**
- `console.aws.amazon.com` → **Allowed** (inherits from allowlist)

### Override Category Blocks

When NextDNS blocks a domain via category (e.g., "Streaming"):

```json
{
  "allowlist": [
    {
      "domain": "youtube.com",
      "description": "Allow during evenings despite streaming category",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [{"start": "19:00", "end": "22:00"}]
          }
        ]
      }
    }
  ]
}
```

### Work Resources

Always-accessible work domains:

```json
{
  "allowlist": [
    {"domain": "github.com", "description": "Code hosting"},
    {"domain": "stackoverflow.com", "description": "Development help"},
    {"domain": "docs.google.com", "description": "Documentation"}
  ]
}
```

### Educational Resources

```json
{
  "allowlist": [
    {"domain": "wikipedia.org", "description": "Reference"},
    {"domain": "khanacademy.org", "description": "Learning"},
    {"domain": "coursera.org", "description": "Courses"}
  ]
}
```

## Priority Rules

NextDNS processes lists with these priorities:

| Priority | Source | Result |
|----------|--------|--------|
| 1 (Highest) | Allowlist | ALLOWED |
| 2 | Blocklist/Denylist | BLOCKED |
| 3 | Category/Service blocks | BLOCKED |
| 4 | Default | ALLOWED |

**Key point:** Allowlist always wins.

## Managing Allowlist

### Add via CLI

```bash
nextdns-blocker allow aws.amazon.com
```

Creates a permanent (no schedule) entry.

### Remove via CLI

```bash
nextdns-blocker disallow aws.amazon.com
```

### Add with Schedule

Edit configuration directly:

```bash
nextdns-blocker config edit
```

### View Allowlist

```bash
nextdns-blocker status
```

Or:

```bash
nextdns-blocker config show
```

## Scheduled Allowlist Examples

### Streaming - Evenings

```json
{
  "domain": "netflix.com",
  "description": "Streaming - blocked by category, allow evenings",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [{"start": "20:00", "end": "22:30"}]
      },
      {
        "days": ["saturday", "sunday"],
        "time_ranges": [{"start": "14:00", "end": "23:00"}]
      }
    ]
  }
}
```

### Social Learning - Weekdays

```json
{
  "domain": "youtube.com",
  "description": "Educational content during study hours",
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
        "time_ranges": [{"start": "09:00", "end": "15:00"}]
      }
    ]
  }
}
```

### Late Night - Weekends

```json
{
  "domain": "twitch.tv",
  "description": "Gaming streams on weekend nights",
  "schedule": {
    "available_hours": [
      {
        "days": ["friday", "saturday"],
        "time_ranges": [{"start": "22:00", "end": "02:00"}]
      }
    ]
  }
}
```

## Allowlist During Panic Mode

When panic mode is active:

- `allow` command is **hidden**
- `disallow` command is **hidden**
- Scheduled allowlist sync is **completely skipped**
- Existing allowlist entries remain but aren't updated

This prevents bypassing emergency lockdown via allowlist.

## Validation Rules

### No Duplicate Exact Domains

A domain cannot be in both lists:

```json
// ❌ Invalid
{
  "blocklist": [{"domain": "reddit.com"}],
  "allowlist": [{"domain": "reddit.com"}]
}
```

### Subdomain Relationships Allowed

This is valid (with a warning):

```json
{
  "blocklist": [{"domain": "amazon.com"}],
  "allowlist": [{"domain": "aws.amazon.com"}]
}
```

## Troubleshooting

### Domain still blocked after allow

1. **Force sync:**
   ```bash
   nextdns-blocker config sync
   ```

2. **Clear DNS cache:**
   ```bash
   # macOS
   sudo dscacheutil -flushcache

   # Linux
   sudo systemctl restart systemd-resolved

   # Windows
   ipconfig /flushdns
   ```

3. **Check for category blocks in NextDNS dashboard**

### Scheduled allowlist not working

1. **Check timezone:**
   ```bash
   nextdns-blocker config show | grep timezone
   ```

2. **Verify current time is within schedule**

3. **Check for panic mode:**
   ```bash
   nextdns-blocker panic status
   ```

### allow command hidden

Panic mode is active:

```bash
nextdns-blocker panic status
```

Wait for expiration or don't try to bypass emergency protection.
