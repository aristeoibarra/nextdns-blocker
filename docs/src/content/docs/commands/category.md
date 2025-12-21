---
title: category
description: Manage domain categories
---

The `category` command group manages domain categories - groups of domains that share the same schedule and unblock delay.

## Overview

Categories simplify configuration by letting you define settings once and apply them to multiple domains.

## Subcommands

| Subcommand | Description |
|------------|-------------|
| `list` | List all categories |
| `show` | Show category details |
| `create` | Create a new category |
| `add` | Add domain to category |
| `remove` | Remove domain from category |
| `delete` | Delete a category |

## category list

List all configured categories.

### Usage

```bash
nextdns-blocker category list
```

### Output

```
Categories (3)

ID              Domains   Delay    Description
──────────────────────────────────────────────────────────────
social-media    4         4h       Social networks
gambling        3         never    Betting and casino sites
streaming       4         2h       Video streaming
```

### No Categories

```
No categories configured

Create a category:
  nextdns-blocker category create <id> [-d "description"]
```

## category show

Show detailed information about a category.

### Usage

```bash
nextdns-blocker category show CATEGORY_ID
```

### Example

```bash
nextdns-blocker category show social-media
```

### Output

```
Category: social-media
━━━━━━━━━━━━━━━━━━━━━━

Description: Social networks
Unblock Delay: 4h

Schedule:
  Mon-Fri: 12:00-13:00, 18:00-22:00
  Sat-Sun: 10:00-23:00

Domains (4):
  - instagram.com
  - tiktok.com
  - snapchat.com
  - twitter.com
```

### Category Not Found

```bash
nextdns-blocker category show nonexistent
```

Output:
```
Error: Category 'nonexistent' not found
```

### Case Insensitive

Category IDs are case-insensitive for lookups:

```bash
nextdns-blocker category show SOCIAL-MEDIA
# Works the same as: category show social-media
```

## category create

Create a new category.

### Usage

```bash
nextdns-blocker category create CATEGORY_ID [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-d, --description TEXT` | Description for the category |
| `--delay TEXT` | Unblock delay (e.g., 30m, 4h, 1d, never) |

### Examples

**Basic creation:**
```bash
nextdns-blocker category create gaming
```

**With description:**
```bash
nextdns-blocker category create gaming -d "Gaming platforms"
```

**With delay:**
```bash
nextdns-blocker category create gambling --delay never
```

**Full options:**
```bash
nextdns-blocker category create streaming -d "Video streaming" --delay 2h
```

### Output

```
Created category 'gaming'

Add domains with:
  nextdns-blocker category add gaming <domain>
```

### Validation Errors

**Invalid ID format:**
```bash
nextdns-blocker category create Invalid-ID
```
```
Error: Invalid category ID 'Invalid-ID'
Must start with lowercase letter, contain only lowercase letters, numbers, and hyphens
```

**Category exists:**
```bash
nextdns-blocker category create social-media
```
```
Error: Category 'social-media' already exists
```

**Invalid delay:**
```bash
nextdns-blocker category create test --delay invalid
```
```
Error: Invalid delay format 'invalid'
Valid formats: 0, 30m, 1h, 4h, 24h, 1d, never
```

### ID Requirements

- Must start with a lowercase letter
- Only lowercase letters, numbers, and hyphens
- Maximum 50 characters

**Valid:** `social-media`, `gaming`, `work-tools`, `category123`

**Invalid:** `Social-Media`, `123gaming`, `-category`, `gaming_sites`

## category add

Add a domain to a category.

### Usage

```bash
nextdns-blocker category add CATEGORY_ID DOMAIN
```

### Example

```bash
nextdns-blocker category add social-media reddit.com
```

### Output

```
Added 'reddit.com' to category 'social-media'
```

### Validation Errors

**Domain already in category:**
```bash
nextdns-blocker category add social-media facebook.com
```
```
Domain 'facebook.com' already exists in category 'social-media'
```

**Invalid domain format:**
```bash
nextdns-blocker category add social-media "invalid domain!"
```
```
Error: Invalid domain format 'invalid domain!'
```

**Category not found:**
```bash
nextdns-blocker category add nonexistent test.com
```
```
Error: Category 'nonexistent' not found
```

### Panic Mode

Adding domains is blocked during panic mode:

```bash
nextdns-blocker category add social-media test.com
```
```
Error: Cannot modify categories during panic mode
```

## category remove

Remove a domain from a category.

### Usage

```bash
nextdns-blocker category remove CATEGORY_ID DOMAIN [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |

### Example

```bash
nextdns-blocker category remove social-media reddit.com
```

### Output

```
Remove 'reddit.com' from category 'social-media'? [y/N]: y
Removed 'reddit.com' from category 'social-media'
```

### Skip Confirmation

```bash
nextdns-blocker category remove social-media reddit.com -y
```

### Validation Errors

**Domain not in category:**
```bash
nextdns-blocker category remove social-media unknown.com
```
```
Error: Domain 'unknown.com' not found in category 'social-media'
```

## category delete

Delete a category entirely.

### Usage

```bash
nextdns-blocker category delete CATEGORY_ID [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `-y, --yes` | Skip confirmation prompt |

### Example

```bash
nextdns-blocker category delete streaming
```

### Output

```
Delete category 'streaming'? (2 domains will be removed) [y/N]: y
Deleted category 'streaming'
```

### Skip Confirmation

```bash
nextdns-blocker category delete streaming -y
```

### Validation Errors

**Category not found:**
```bash
nextdns-blocker category delete nonexistent
```
```
Error: Category 'nonexistent' not found
```

### Panic Mode

Deleting categories is blocked during panic mode:

```bash
nextdns-blocker category delete gaming -y
```
```
Error: Cannot modify categories during panic mode
```

## Workflow Examples

### Set Up Social Media Blocking

```bash
# Create the category
nextdns-blocker category create social-media -d "Social networks" --delay 4h

# Add domains
nextdns-blocker category add social-media facebook.com
nextdns-blocker category add social-media instagram.com
nextdns-blocker category add social-media twitter.com
nextdns-blocker category add social-media tiktok.com

# Verify
nextdns-blocker category show social-media

# Edit config to add schedule
nextdns-blocker config edit
```

### Reorganize Domains

```bash
# List current categories
nextdns-blocker category list

# Move domain from one category to another
nextdns-blocker category remove streaming youtube.com -y
nextdns-blocker category add social-media youtube.com

# Verify
nextdns-blocker category show social-media
```

### Clean Up Categories

```bash
# Remove unused domains
nextdns-blocker category remove gaming oldgame.com -y

# Delete empty category
nextdns-blocker category delete old-category -y
```

## Related

- [Categories Configuration](/configuration/categories/) - Full configuration reference
- [Blocklist](/configuration/blocklist/) - Individual domain configuration
- [Schedules](/configuration/schedules/) - Time-based access rules
