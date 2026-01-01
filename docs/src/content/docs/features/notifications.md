---
title: Notifications
description: Real-time alerts for blocking events via multiple channels
---

Get instant notifications when domains are blocked, unblocked, or when special modes are activated. NextDNS Blocker supports multiple notification channels with batching and async delivery.

## Supported Channels

| Channel | Description |
|---------|-------------|
| **Discord** | Webhook notifications with rich embeds |
| **macOS** | Native system notifications via osascript |

## Configuration

Notifications are configured in `config.json` under the `notifications` section:

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/1234567890/abcdefghijklmnop"
      },
      "macos": {
        "enabled": true,
        "sound": true
      }
    }
  }
}
```

### Global Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | `true` | Master switch for all notifications |
| `channels` | object | `{}` | Channel-specific configurations |

### Discord Channel

```json
{
  "discord": {
    "enabled": true,
    "webhook_url": "https://discord.com/api/webhooks/..."
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `enabled` | boolean | Yes | Enable Discord notifications |
| `webhook_url` | string | Yes | Full Discord webhook URL |

**Creating a Discord Webhook:**

1. Open Discord server settings
2. Go to **Integrations** > **Webhooks**
3. Click **New Webhook**
4. Name it (e.g., "NextDNS Blocker")
5. Select the channel for notifications
6. Click **Copy Webhook URL**

### macOS Channel

```json
{
  "macos": {
    "enabled": true,
    "sound": true
  }
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | boolean | No | Enable macOS native notifications |
| `sound` | boolean | `true` | Play sound with notification |

**Note:** macOS notifications only work when running on macOS. The channel is automatically disabled on other platforms.

## Notification Types

### Sync Complete (Batched)

After each sync, a summary notification is sent:

**Discord Example:**
```
:bar_chart: NextDNS Blocker Sync Complete

:red_circle: Blocked (3): reddit.com, twitter.com, instagram.com
:green_circle: Unblocked (1): github.com
:shield: PC Activated (2): gambling, tiktok
:clock3: Scheduled (1): bumble.com

Profile: abc123 | Synced at 14:30
```

**macOS Example:**
```
NextDNS Blocker Sync
Blocked: 3 | Unblocked: 1 | Allowed: 0
```

### Event Types

| Event | Icon | Color | Description |
|-------|------|-------|-------------|
| Block | :red_circle: | Red | Domain added to denylist |
| Unblock | :green_circle: | Green | Domain removed from denylist |
| Allow | :white_check_mark: | Green | Domain added to allowlist |
| Disallow | :x: | Orange | Domain removed from allowlist |
| PC Activate | :shield: | Blue | Parental Control category/service activated |
| PC Deactivate | :unlock: | Blue | Parental Control category/service deactivated |
| Pending | :clock3: | Yellow | Unblock scheduled with delay |
| Panic | :rotating_light: | Dark Red | Panic mode activated |
| Error | :warning: | Red | Operation failed |

## Features

### Batching

Instead of sending individual notifications for each domain change, events are collected during a sync operation and sent as a single notification:

- Reduces notification spam
- Provides a summary view
- Groups events by type

### Async Delivery

Notifications are sent asynchronously in a background thread:

- Sync operations don't wait for notification delivery
- Notification failures don't affect sync success
- Multiple adapters can send in parallel

### Rate Limiting

Discord webhooks have rate limits. NextDNS Blocker handles this by:

- Batching events to reduce API calls
- Logging rate limit errors without retrying

## Testing

Verify your notification setup:

```bash
nextdns-blocker test-notifications
```

This sends a test message to all configured and enabled channels.

## Complete Configuration Example

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York"
  },
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/123456789/abcdef..."
      },
      "macos": {
        "enabled": true,
        "sound": true
      }
    }
  },
  "blocklist": [...]
}
```

## Disabling Notifications

### Disable All Notifications

```json
{
  "notifications": {
    "enabled": false
  }
}
```

### Disable Specific Channel

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": false,
        "webhook_url": "..."
      }
    }
  }
}
```

### Remove Configuration

Simply remove the `notifications` section from `config.json`.

## Troubleshooting

### Discord notifications not appearing

1. **Check webhook URL**:
   - Verify URL starts with `https://discord.com/api/webhooks/`
   - Copy fresh from Discord settings

2. **Check configuration**:
   ```bash
   nextdns-blocker config show
   ```
   Look for the `notifications` section.

3. **Test webhook manually**:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"content": "Test from NextDNS Blocker"}' \
     "YOUR_WEBHOOK_URL"
   ```

4. **Check logs**:
   ```bash
   tail -20 ~/.local/share/nextdns-blocker/logs/cron.log
   ```

### macOS notifications not appearing

1. **Check System Preferences**:
   - Go to System Preferences > Notifications
   - Ensure notifications are allowed for Terminal/iTerm

2. **Check platform**:
   - macOS notifications only work on macOS
   - The channel is auto-disabled on other platforms

### Webhook invalid or expired

1. Recreate webhook in Discord
2. Update `config.json` with new URL
3. Test with `nextdns-blocker test-notifications`

## Privacy Considerations

### What's Shared

Notifications include:
- Domain names being blocked/unblocked
- Category/service names (Parental Control)
- Timestamps
- Action types

### What's NOT Shared

Notifications don't include:
- Your IP address
- NextDNS credentials
- Full configuration details

### Recommendations

1. Use a private Discord server
2. Don't share webhook URLs
3. Consider a dedicated notification channel
4. Review channel access permissions

## Channel Ideas

### Separate Channels

Create different webhooks for different purposes:

1. **#nextdns-alerts** - All sync notifications
2. **#nextdns-panic** - Only panic mode (urgent)
3. **#accountability** - Share with accountability partner

### Private vs Shared

- **Private channel**: Personal monitoring
- **Shared channel**: Accountability with trusted person
