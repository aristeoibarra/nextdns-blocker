---
title: Filtering Priority
description: Understanding how NextDNS processes allowlist, denylist, and parental control blocks
sidebar:
  order: 7
---

NextDNS processes filtering rules in a specific order. Understanding this priority helps you configure exceptions correctly.

## Priority Order

NextDNS evaluates requests in this order (highest to lowest priority):

| Priority | Source | Result | Managed By |
|----------|--------|--------|------------|
| 1 (Highest) | **Allowlist** | ALLOWED | NextDNS Blocker |
| 2 | Denylist | BLOCKED | NextDNS Blocker |
| 3 | Parental Control (categories/services) | BLOCKED | NextDNS Blocker + NextDNS |
| 4 | Privacy blocklists (OISD, etc.) | BLOCKED | NextDNS dashboard |
| 5 | Security features | BLOCKED | NextDNS dashboard |
| 6 | Normal resolution | ALLOWED | DNS |

**Key point:** Allowlist always wins. If a domain is in the allowlist, it will be accessible regardless of any other blocking rules.

## How It Works

When a DNS request is made:

1. NextDNS first checks the **Allowlist** - if matched, request is immediately allowed
2. Then checks the **Denylist** - if matched, request is blocked
3. Then checks **Parental Control** categories and services - if matched, blocked
4. Then checks **Privacy blocklists** configured in your profile
5. Then applies **Security features** (threat intelligence, etc.)
6. If none match, the request resolves normally

## Practical Examples

### Example 1: Discord Exception to Gaming Category

**Scenario**: You want to block all gaming sites but allow Discord for communication.

```json
{
  "nextdns": {
    "categories": [
      {
        "id": "gaming",
        "description": "Block gaming sites",
        "unblock_delay": "never"
      }
    ]
  },
  "allowlist": [
    {
      "domain": "discord.com",
      "description": "Exception to gaming block - needed for team communication"
    }
  ]
}
```

**Result**:
- Steam, Fortnite, Roblox, etc. → **Blocked** (by gaming category)
- Discord → **Allowed** (allowlist overrides category block)

### Example 2: Work Exception During Social Media Block

**Scenario**: Social networks are blocked, but you need LinkedIn for work.

```json
{
  "nextdns": {
    "categories": [
      {
        "id": "social-networks",
        "description": "Block social media",
        "unblock_delay": "4h"
      }
    ]
  },
  "allowlist": [
    {
      "domain": "linkedin.com",
      "description": "Professional networking - always accessible"
    }
  ]
}
```

**Result**:
- Facebook, Instagram, Twitter, etc. → **Blocked**
- LinkedIn → **Allowed**

### Example 3: Scheduled Exception

**Scenario**: Streaming is blocked via category, but allow Netflix during evenings.

```json
{
  "nextdns": {
    "services": [
      {
        "id": "netflix",
        "description": "Netflix - blocked by default",
        "unblock_delay": "2h"
      }
    ],
    "categories": [
      {
        "id": "streaming",
        "description": "No streaming during work",
        "unblock_delay": "never"
      }
    ]
  },
  "allowlist": [
    {
      "domain": "netflix.com",
      "description": "Allow Netflix evenings only",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [{"start": "19:00", "end": "23:00"}]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [{"start": "10:00", "end": "23:00"}]
          }
        ]
      }
    }
  ]
}
```

**Result**:
- Netflix during work hours → **Blocked** (allowlist not active)
- Netflix during evening hours → **Allowed** (scheduled allowlist active)

### Example 4: Subdomain Exception

**Scenario**: Block Amazon shopping but allow AWS Console.

```json
{
  "blocklist": [
    {
      "domain": "amazon.com",
      "description": "No shopping during work",
      "schedule": null
    }
  ],
  "allowlist": [
    {
      "domain": "aws.amazon.com",
      "description": "AWS Console - work resource"
    }
  ]
}
```

**Result**:
- amazon.com → **Blocked**
- www.amazon.com → **Blocked** (inherits from parent)
- aws.amazon.com → **Allowed** (allowlist)
- console.aws.amazon.com → **Allowed** (inherits from allowlist entry)

## Common Patterns

### Block Category, Allow Specific Services

Block an entire category but allow specific services:

```json
{
  "nextdns": {
    "categories": [
      {"id": "social-networks", "unblock_delay": "never"}
    ]
  },
  "allowlist": [
    {"domain": "discord.com", "description": "Team communication"},
    {"domain": "slack.com", "description": "Work messaging"}
  ]
}
```

### Block Service, Allow Related Resources

Block a service but allow its developer/API resources:

```json
{
  "nextdns": {
    "services": [
      {"id": "youtube", "unblock_delay": "4h"}
    ]
  },
  "allowlist": [
    {"domain": "developers.google.com", "description": "API documentation"}
  ]
}
```

### Temporary Full Access

Use scheduled allowlist for temporary unrestricted access:

```json
{
  "allowlist": [
    {
      "domain": "problematic-site.com",
      "description": "Allow during lunch break only",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [{"start": "12:00", "end": "13:00"}]
          }
        ]
      }
    }
  ]
}
```

## Important Notes

### DNS Cache

After modifying the allowlist, DNS changes may take time to propagate:

```bash
# Force sync
nextdns-blocker config push

# Clear local DNS cache
# macOS
sudo dscacheutil -flushcache

# Linux
sudo systemctl restart systemd-resolved

# Windows
ipconfig /flushdns
```

### Privacy Blocklists

NextDNS privacy blocklists (OISD, AdGuard, etc.) are configured in the NextDNS dashboard, not through NextDNS Blocker. If these are blocking a domain you need:

1. Add the domain to your allowlist in NextDNS Blocker
2. Or add it directly in NextDNS dashboard

Both methods work because allowlist has highest priority.

## Troubleshooting

### Domain Still Blocked After Allowlist

1. **Verify sync completed:**
   ```bash
   nextdns-blocker config push
   nextdns-blocker status
   ```

2. **Check if domain is in allowlist:**
   ```bash
   nextdns-blocker config show | grep -A2 "domain_name"
   ```

3. **Verify in NextDNS dashboard:**
   - Check Allowlist section
   - Verify the domain appears

4. **Clear DNS cache** (see above)

### Scheduled Allowlist Not Activating

1. **Check timezone:**
   ```bash
   nextdns-blocker config show | grep timezone
   ```

2. **Verify current time is within schedule**

### Conflicting Rules

If you have the same domain in multiple lists:
- Exact duplicates (same domain in blocklist AND allowlist) → **Validation error**
- Subdomain relationships (parent in blocklist, subdomain in allowlist) → **Allowed** with warning
