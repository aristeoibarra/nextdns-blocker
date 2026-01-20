---
title: nextdns
description: Manage NextDNS Parental Control categories and services
sidebar:
  order: 11
---

The `nextdns` command group manages NextDNS Parental Control features including categories (gambling, porn, etc.) and services (TikTok, Netflix, etc.).

## Commands

### list

List configured categories and services.

```bash
# Show from config.json
nextdns-blocker nextdns list

# Show live status from NextDNS API
nextdns-blocker nextdns list --remote
```

**Options:**
- `--remote` - Fetch live status from NextDNS API instead of config file
- `--config-dir PATH` - Config directory (default: auto-detect)

### status

Show current Parental Control status from NextDNS API.

```bash
nextdns-blocker nextdns status
```

Displays:
- Global settings (safe_search, youtube_restricted_mode, block_bypass)
- Active categories
- Active services

### add-category

Activate a Parental Control category (start blocking).

```bash
nextdns-blocker nextdns add-category <CATEGORY_ID>
```

**Valid category IDs:** `porn`, `gambling`, `dating`, `piracy`, `social-networks`

**Example:**
```bash
nextdns-blocker nextdns add-category gambling
```

### remove-category

Deactivate a Parental Control category (stop blocking).

```bash
nextdns-blocker nextdns remove-category <CATEGORY_ID>
```

**Example:**
```bash
nextdns-blocker nextdns remove-category gambling
```

### add-service

Activate a Parental Control service (start blocking).

```bash
nextdns-blocker nextdns add-service <SERVICE_ID>
```

**Example:**
```bash
nextdns-blocker nextdns add-service tiktok
nextdns-blocker nextdns add-service fortnite
```

### remove-service

Deactivate a Parental Control service (stop blocking).

```bash
nextdns-blocker nextdns remove-service <SERVICE_ID>
```

**Example:**
```bash
nextdns-blocker nextdns remove-service tiktok
```

### categories

Show all valid NextDNS category IDs.

```bash
nextdns-blocker nextdns categories
```

Output:
```
Valid NextDNS Category IDs
-------------------------
  - dating
  - gambling
  - piracy
  - porn
  - social-networks
```

### services

Show all valid NextDNS service IDs grouped by type.

```bash
nextdns-blocker nextdns services
```

Output shows 43 services organized by category:
- Social & Messaging (20 services)
- Streaming (9 services)
- Gaming (8 services)
- Dating (1 service)
- Other (5 services)

## Examples

### Block TikTok immediately

```bash
nextdns-blocker nextdns add-service tiktok
```

### Check what's currently blocked

```bash
nextdns-blocker nextdns status
```

### Unblock Netflix for the evening

```bash
nextdns-blocker nextdns remove-service netflix
```

### See all available services

```bash
nextdns-blocker nextdns services
```

## See Also

- [NextDNS Parental Control Feature](/features/nextdns-parental-control/) - Complete configuration guide
- [Sync Command](/commands/sync/) - Automatic schedule-based sync
