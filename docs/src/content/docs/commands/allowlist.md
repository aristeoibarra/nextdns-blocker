---
title: allow / disallow
description: Manage the NextDNS allowlist for domain exceptions
---

The `allow` and `disallow` commands manage the NextDNS allowlist, which creates exceptions to blocking.

## Overview

The allowlist is used to:
- **Create subdomain exceptions**: Allow `aws.amazon.com` while blocking `amazon.com`
- **Override category blocks**: Allow specific domains blocked by NextDNS categories
- **Permanent access**: Keep domains always accessible

## allow

Add a domain to the allowlist.

### Usage

```bash
nextdns-blocker allow DOMAIN
```

### Example

```bash
nextdns-blocker allow aws.amazon.com
```

### Output

```
Adding 'aws.amazon.com' to allowlist...
✓ Domain added to allowlist

Note: This creates a permanent exception.
For scheduled access, edit config.json directly.
```

### Behavior

1. Adds domain to NextDNS allowlist immediately
2. Adds domain to local `config.json` allowlist
3. Domain will remain in allowlist across syncs

### Scheduled Allowlist

The `allow` command creates permanent (always-allowed) entries. For time-based allowlist entries, edit `config.json`:

```bash
nextdns-blocker config edit
```

```json
{
  "allowlist": [
    {
      "domain": "youtube.com",
      "description": "Evening only",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [{"start": "20:00", "end": "22:30"}]
          }
        ]
      }
    }
  ]
}
```

## disallow

Remove a domain from the allowlist.

### Usage

```bash
nextdns-blocker disallow DOMAIN
```

### Example

```bash
nextdns-blocker disallow aws.amazon.com
```

### Output

```
Removing 'aws.amazon.com' from allowlist...
✓ Domain removed from allowlist
```

### Behavior

1. Removes domain from NextDNS allowlist immediately
2. Removes domain from local `config.json` allowlist
3. Domain is now subject to normal blocking rules

### Tab Completion

With shell completion enabled, allowlist domains auto-complete:

```bash
nextdns-blocker disallow aws<TAB>
# Completes to: nextdns-blocker disallow aws.amazon.com
```

## Allowlist vs Blocklist Priority

NextDNS processes lists with these priority rules:

| Priority | List | Result |
|----------|------|--------|
| 1 (Highest) | Allowlist | Domain is ALLOWED |
| 2 | Blocklist/Denylist | Domain is BLOCKED |
| 3 | Category blocks | Domain is BLOCKED |
| 4 | Default | Domain is ALLOWED |

### Key Points

- Allowlist **always wins** over blocklist
- Use for subdomain exceptions
- Use to override category blocks

## Use Cases

### Subdomain Exception

Block a domain but allow a specific subdomain:

```bash
# In config.json blocklist
{"domain": "amazon.com", "schedule": null}

# Allow the exception
nextdns-blocker allow aws.amazon.com
```

Result:
- `amazon.com` → Blocked
- `www.amazon.com` → Blocked (inherits from parent)
- `aws.amazon.com` → **Allowed** (allowlist override)
- `console.aws.amazon.com` → **Allowed** (inherits from allowlist)

### Override Category Block

If NextDNS blocks a domain via category (e.g., "Streaming"):

```bash
# Allow specific streaming site during certain hours
nextdns-blocker allow youtube.com
```

Or for scheduled access, edit config:

```json
{
  "allowlist": [
    {
      "domain": "youtube.com",
      "schedule": {
        "available_hours": [
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [{"start": "10:00", "end": "22:00"}]
          }
        ]
      }
    }
  ]
}
```

### Work Resources

Keep work-related domains always accessible:

```bash
nextdns-blocker allow docs.google.com
nextdns-blocker allow github.com
nextdns-blocker allow stackoverflow.com
```

## Allowlist During Panic Mode

When panic mode is active:

- The `allow` command is **hidden**
- The `disallow` command is **hidden**
- Scheduled allowlist sync is **skipped**
- This prevents bypassing emergency lockdown

After panic expires:
- Commands become available again
- Scheduled allowlist syncing resumes

## Viewing Allowlist

### Via Status

```bash
nextdns-blocker status
```

Shows:
```
Allowlist (2 domains):
  ✓ aws.amazon.com    ALLOWED    (always)
  ✓ youtube.com       ALLOWED    (until 22:30)
```

### Via Config

```bash
nextdns-blocker config show
```

Shows:
```
Allowlist (2 domains):
  aws.amazon.com
    Description: Work resource
    Schedule: null (always allowed)

  youtube.com
    Description: Evening entertainment
    Schedule: Sat-Sun 10:00-22:00
```

## Validation Rules

### Cannot Be in Both Lists

A domain cannot be in both blocklist and allowlist:

```bash
# If reddit.com is in blocklist
nextdns-blocker allow reddit.com
```

Output:
```
Error: 'reddit.com' is in the blocklist
Remove from blocklist first, or use a subdomain exception
```

### Subdomain Relationships Allowed

You can have:
- `amazon.com` in blocklist
- `aws.amazon.com` in allowlist

This is valid and will show a warning during config load.

## Troubleshooting

### Domain still blocked after allow

1. Check if domain is in blocklist:
   ```bash
   nextdns-blocker config show | grep <domain>
   ```

2. Clear DNS cache:
   ```bash
   # macOS
   sudo dscacheutil -flushcache

   # Linux
   sudo systemctl restart systemd-resolved

   # Windows
   ipconfig /flushdns
   ```

3. Force sync:
   ```bash
   nextdns-blocker sync
   ```

### allow command hidden

Panic mode is active. Check status:

```bash
nextdns-blocker panic status
```

Wait for panic to expire.

### Domain not in allowlist after allow

Check for API errors:

```bash
nextdns-blocker config sync --verbose
```

Verify credentials:

```bash
nextdns-blocker init
```
