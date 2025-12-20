---
title: Environment Variables
description: Configure API credentials and system settings via .env
---

The `.env` file stores sensitive credentials and system-level settings.

## File Location

| Platform | Path |
|----------|------|
| macOS/Linux | `~/.config/nextdns-blocker/.env` |
| Windows | `%APPDATA%\nextdns-blocker\.env` |

## Required Variables

### NEXTDNS_API_KEY

Your NextDNS API key for authentication.

```bash
NEXTDNS_API_KEY=abcdef1234567890
```

**How to get it:**
1. Go to [my.nextdns.io/account](https://my.nextdns.io/account)
2. Scroll to "API" section
3. Click to reveal and copy

**Requirements:**
- Minimum 8 characters
- Alphanumeric

### NEXTDNS_PROFILE_ID

Your NextDNS profile identifier.

```bash
NEXTDNS_PROFILE_ID=abc123
```

**How to get it:**
1. Go to [my.nextdns.io](https://my.nextdns.io)
2. Select your profile
3. Copy from URL: `https://my.nextdns.io/abc123/setup`

**Requirements:**
- 4-30 characters
- Alphanumeric

## Optional Variables

### API_TIMEOUT

Request timeout in seconds.

```bash
API_TIMEOUT=10
```

| Value | Default | Description |
|-------|---------|-------------|
| `5` | - | Fast timeout, may fail on slow connections |
| `10` | ✓ | Balanced default |
| `30` | - | For slow/unreliable connections |

### API_RETRIES

Number of retry attempts on failure.

```bash
API_RETRIES=3
```

| Value | Default | Description |
|-------|---------|-------------|
| `1` | - | Fail fast |
| `3` | ✓ | Balanced default |
| `5` | - | Maximum retry effort |

Retries use exponential backoff (1s, 2s, 4s, etc.).

### DISCORD_WEBHOOK_URL

Discord webhook for notifications.

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1234567890/abcdefg
```

**How to create:**
1. Open Discord server settings
2. Go to Integrations → Webhooks
3. Create webhook, copy URL

**Format validation:**
- Must start with `https://discord.com/api/webhooks/`
- Must include webhook ID and token

### DISCORD_NOTIFICATIONS_ENABLED

Enable/disable Discord notifications.

```bash
DISCORD_NOTIFICATIONS_ENABLED=true
```

| Value | Description |
|-------|-------------|
| `true` | Send notifications |
| `false` | Disable notifications (default) |

Requires `DISCORD_WEBHOOK_URL` to be set.

## Advanced Variables

### RATE_LIMIT_REQUESTS

Maximum API requests per time window.

```bash
RATE_LIMIT_REQUESTS=30
```

| Value | Default | Description |
|-------|---------|-------------|
| `10` | - | Conservative |
| `30` | ✓ | Balanced |
| `60` | - | High-frequency sync |

### RATE_LIMIT_WINDOW

Time window for rate limiting in seconds.

```bash
RATE_LIMIT_WINDOW=60
```

| Value | Default | Description |
|-------|---------|-------------|
| `30` | - | Stricter limiting |
| `60` | ✓ | Standard window |
| `120` | - | More permissive |

### CACHE_TTL

How long to cache denylist data in seconds.

```bash
CACHE_TTL=60
```

| Value | Default | Description |
|-------|---------|-------------|
| `30` | - | Fresher data, more API calls |
| `60` | ✓ | Balanced |
| `300` | - | Fewer API calls |

## Complete Example

```bash
# Required - NextDNS Credentials
NEXTDNS_API_KEY=your_api_key_here
NEXTDNS_PROFILE_ID=abc123

# Optional - API Settings
API_TIMEOUT=10
API_RETRIES=3

# Optional - Discord Notifications
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456/abcdef
DISCORD_NOTIFICATIONS_ENABLED=true

# Advanced - Rate Limiting (usually not needed)
# RATE_LIMIT_REQUESTS=30
# RATE_LIMIT_WINDOW=60
# CACHE_TTL=60
```

## Security

### File Permissions

The `.env` file is created with restricted permissions (0600):

```bash
# Check permissions
ls -la ~/.config/nextdns-blocker/.env
# Should show: -rw------- (owner read/write only)

# Fix permissions if needed
chmod 600 ~/.config/nextdns-blocker/.env
```

### Git Ignore

Never commit `.env` to version control. It's included in `.gitignore`:

```gitignore
.env
*.env
```

### Environment Variable Override

Variables can also be set in your shell environment:

```bash
export NEXTDNS_API_KEY=your_key
nextdns-blocker sync
```

Priority order:
1. Shell environment variables
2. `.env` file in config directory
3. Default values

## Validation

### Check Credentials

```bash
nextdns-blocker init
```

The setup wizard validates credentials against the NextDNS API.

### Manual Validation

```bash
# Test API key
curl -H "X-Api-Key: YOUR_API_KEY" https://api.nextdns.io/profiles

# Should return your profiles, not an error
```

## Troubleshooting

### "API key invalid"

1. Check for extra whitespace in `.env`
2. Regenerate API key at [my.nextdns.io/account](https://my.nextdns.io/account)
3. Verify key is correct (copy/paste carefully)

### "Profile not found"

1. Check profile ID matches URL exactly
2. Verify profile exists at [my.nextdns.io](https://my.nextdns.io)
3. Check API key has access to profile

### "Connection timeout"

1. Increase `API_TIMEOUT`:
   ```bash
   API_TIMEOUT=30
   ```
2. Check internet connection
3. Check NextDNS service status

### Discord notifications not working

1. Verify webhook URL is complete
2. Check `DISCORD_NOTIFICATIONS_ENABLED=true`
3. Test webhook manually:
   ```bash
   curl -X POST -H "Content-Type: application/json" \
     -d '{"content": "Test"}' \
     "YOUR_WEBHOOK_URL"
   ```
