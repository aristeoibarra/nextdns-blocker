---
title: Configuration Overview
description: Learn how to configure NextDNS Blocker
---

NextDNS Blocker uses two main configuration files:
- **`.env`**: API credentials and environment settings
- **`config.json`**: Domain schedules, blocklist, and allowlist

## Configuration Locations

| Platform | Location |
|----------|----------|
| macOS/Linux | `~/.config/nextdns-blocker/` |
| Windows | `%APPDATA%\nextdns-blocker\` |

## Quick Reference

### .env (Credentials)

```bash
# Required
NEXTDNS_API_KEY=your_api_key
NEXTDNS_PROFILE_ID=abc123

# Optional
API_TIMEOUT=10
API_RETRIES=3
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_NOTIFICATIONS_ENABLED=true
```

### config.json (Domains)

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [...],
  "allowlist": [...]
}
```

## Configuration Sections

| Section | Guide | Description |
|---------|-------|-------------|
| Environment | [Environment Variables](/configuration/env-variables/) | API keys, timeouts, notifications |
| Structure | [config.json](/configuration/config-json/) | File structure and fields |
| Schedules | [Schedules](/configuration/schedules/) | Time-based access rules |
| Blocklist | [Blocklist](/configuration/blocklist/) | Domains to manage |
| Allowlist | [Allowlist](/configuration/allowlist/) | Domain exceptions |
| Delays | [Unblock Delay](/configuration/unblock-delay/) | Friction-based protection |
| Timezone | [Timezone](/configuration/timezone/) | Schedule evaluation timezone |

## Managing Configuration

### View Current Config

```bash
nextdns-blocker config show
```

### Edit Configuration

```bash
nextdns-blocker config edit
```

### Validate Configuration

```bash
nextdns-blocker config validate
```

### Set Specific Values

```bash
nextdns-blocker config set timezone America/Los_Angeles
nextdns-blocker config set editor vim
```

## Configuration Best Practices

### Security

1. **Never commit `.env`** to version control
2. Keep API credentials private
3. Use environment variables in CI/CD

### Organization

1. Use descriptive `description` fields
2. Group related domains with similar schedules
3. Document protected domains clearly

### Testing

1. Use `config validate` before syncing
2. Use `sync --dry-run` to preview changes
3. Test schedule logic at boundary times

## Example Configurations

Ready-to-use templates in the `examples/` directory:

| Template | Use Case |
|----------|----------|
| `minimal.json` | Quick start |
| `work-focus.json` | Productivity |
| `gaming.json` | Gaming platforms |
| `social-media.json` | Social networks |
| `parental-control.json` | Protected blocking |
| `study-mode.json` | Student focus |

Copy a template:

```bash
cp examples/work-focus.json ~/.config/nextdns-blocker/config.json
nextdns-blocker config edit  # Customize
```

## Next Steps

- [Set up environment variables](/configuration/env-variables/)
- [Understand config.json structure](/configuration/config-json/)
- [Configure schedules](/configuration/schedules/)
