---
title: allowlist / denylist
description: Manage NextDNS lists with bulk operations
---

NextDNS Blocker provides two command groups for managing domain lists with full CRUD operations: `allowlist` and `denylist`.

## Command Groups

### denylist

Manage NextDNS denylist (blocked domains).

| Subcommand | Description |
|------------|-------------|
| `denylist list` | List all domains in the denylist |
| `denylist add` | Add one or more domains |
| `denylist remove` | Remove one or more domains |
| `denylist export` | Export to JSON or CSV |
| `denylist import` | Import from file |

### allowlist

Manage NextDNS allowlist (whitelisted domains).

| Subcommand | Description |
|------------|-------------|
| `allowlist list` | List all domains in the allowlist |
| `allowlist add` | Add one or more domains |
| `allowlist remove` | Remove one or more domains |
| `allowlist export` | Export to JSON or CSV |
| `allowlist import` | Import from file |

## denylist Commands

### denylist list

List all domains currently in your NextDNS denylist.

```bash
nextdns-blocker denylist list
```

Output:
```
Denylist

Domain               Active
────────────────────────────
reddit.com           Yes
twitter.com          Yes
instagram.com        Yes
tiktok.com           No

Total: 4 domains
```

### denylist add

Add one or more domains to the denylist.

```bash
nextdns-blocker denylist add DOMAIN [DOMAIN ...]
```

Example:
```bash
nextdns-blocker denylist add reddit.com twitter.com instagram.com
```

Output:
```
  + reddit.com
  + twitter.com
  + instagram.com

  Added 3 domain(s) to denylist
```

### denylist remove

Remove one or more domains from the denylist.

```bash
nextdns-blocker denylist remove DOMAIN [DOMAIN ...]
```

Example:
```bash
nextdns-blocker denylist remove reddit.com
```

Output:
```
  - reddit.com

  Removed 1 domain(s) from denylist
```

### denylist export

Export denylist to a file.

```bash
nextdns-blocker denylist export [--format json|csv] [-o FILE]
```

Options:

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | json | Output format (json or csv) |
| `-o, --output` | stdout | Output file path |

Examples:
```bash
# Export to JSON file
nextdns-blocker denylist export -o denylist.json

# Export to CSV
nextdns-blocker denylist export --format csv -o denylist.csv

# Print to stdout
nextdns-blocker denylist export
```

JSON format:
```json
[
  {"domain": "reddit.com", "active": true},
  {"domain": "twitter.com", "active": true}
]
```

CSV format:
```csv
domain,active
reddit.com,True
twitter.com,True
```

### denylist import

Import domains from a file.

```bash
nextdns-blocker denylist import FILE [--dry-run]
```

Options:

| Option | Description |
|--------|-------------|
| `--dry-run` | Preview what would be imported |

Supported formats:
- **JSON**: Array of strings or objects with `domain` field
- **CSV**: Must have `domain` column, optional `active` column
- **Plain text**: One domain per line (lines starting with `#` are ignored)

Examples:
```bash
# Preview import
nextdns-blocker denylist import domains.json --dry-run

# Import from file
nextdns-blocker denylist import domains.txt
```

Output:
```
  Importing 25 domains...

  Added: 20
  Skipped (existing): 5
  Failed: 0
```

## allowlist Commands

### allowlist list

List all domains currently in your NextDNS allowlist.

```bash
nextdns-blocker allowlist list
```

Output:
```
Allowlist

Domain               Active
────────────────────────────
aws.amazon.com       Yes
github.com           Yes

Total: 2 domains
```

### allowlist add

Add one or more domains to the allowlist.

```bash
nextdns-blocker allowlist add DOMAIN [DOMAIN ...]
```

Example:
```bash
nextdns-blocker allowlist add github.com stackoverflow.com
```

Output:
```
  + github.com
  + stackoverflow.com

  Added 2 domain(s) to allowlist
```

### allowlist remove

Remove one or more domains from the allowlist.

```bash
nextdns-blocker allowlist remove DOMAIN [DOMAIN ...]
```

Example:
```bash
nextdns-blocker allowlist remove github.com
```

Output:
```
  - github.com

  Removed 1 domain(s) from allowlist
```

### allowlist export

Export allowlist to a file.

```bash
nextdns-blocker allowlist export [--format json|csv] [-o FILE]
```

Example:
```bash
nextdns-blocker allowlist export -o allowlist.json
```

### allowlist import

Import domains from a file.

```bash
nextdns-blocker allowlist import FILE [--dry-run]
```

Example:
```bash
nextdns-blocker allowlist import work-domains.txt
```

---

## Commands: allow / disallow

The single-domain `allow` and `disallow` commands are available for quick operations.

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
   nextdns-blocker config push
   ```

### Domain not in allowlist after allow

Check for API errors:

```bash
nextdns-blocker config push --verbose
```

Verify credentials:

```bash
nextdns-blocker init
```
