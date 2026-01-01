---
title: test-notifications
description: Send a test notification to verify notification channels
---

The `test-notifications` command sends a test message to all configured notification channels to verify the integration is working correctly.

## Usage

```bash
nextdns-blocker test-notifications [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--config-dir` | Config directory (default: auto-detect) |
| `--help` | Show help message |

## Prerequisites

Before using this command, configure notifications in your `config.json`:

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/..."
      },
      "macos": {
        "enabled": true,
        "sound": true
      }
    }
  }
}
```

## Setting Up Notifications

### 1. Create a Discord Webhook

1. Open Discord and go to your server
2. Click on the channel where you want notifications
3. Click the gear icon (Edit Channel)
4. Go to **Integrations** > **Webhooks**
5. Click **New Webhook**
6. Copy the webhook URL

### 2. Configure in config.json

Edit your configuration:

```bash
nextdns-blocker config edit
```

Add the notifications section:

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/123456789/abcdef..."
      }
    }
  }
}
```

### 3. Test the Integration

```bash
nextdns-blocker test-notifications
```

## Example

### Successful Test

```bash
nextdns-blocker test-notifications
```

Output:
```
  Sending test notification...
  Discord: Sent successfully
  macOS: Sent successfully
  All notifications sent!
```

### Missing Configuration

```bash
nextdns-blocker test-notifications
```

Output:
```
  No notification channels configured.
  Add a 'notifications' section to your config.json
```

### Partial Success

```bash
nextdns-blocker test-notifications
```

Output:
```
  Sending test notification...
  Discord: Sent successfully
  macOS: Not available (not on macOS)
```

## What Notifications Are Sent

When enabled, NextDNS Blocker sends notifications for:

| Event | Description |
|-------|-------------|
| Sync complete | Summary of blocked/unblocked domains |
| Panic mode activated | Alert when emergency mode starts |
| Panic mode ended | Alert when emergency mode expires |
| Unblock request | When a pending unblock is created |
| Unblock executed | When a pending unblock completes |
| Parental Control changes | Category/service activations |

## Notification Format

Test notifications appear as:

**Discord:**
```
:test_tube: NextDNS Blocker Test
Test Connection
Connection successful!
```

**macOS:**
```
NextDNS Blocker Test
Connection successful!
```

## Troubleshooting

### No channels configured

```
No notification channels configured.
```

**Solution**: Add the `notifications` section to your `config.json`:

```json
{
  "notifications": {
    "enabled": true,
    "channels": {
      "discord": {
        "enabled": true,
        "webhook_url": "https://discord.com/api/webhooks/..."
      }
    }
  }
}
```

### Discord webhook failed

If Discord notification fails silently:

1. Verify the webhook URL is correct and complete
2. Check the webhook hasn't been deleted in Discord
3. Ensure the channel still exists
4. Try creating a new webhook

### macOS notifications not available

```
macOS: Not available (not on macOS)
```

This is expected when running on Linux or Windows. macOS notifications only work on macOS.

### Notification not appearing in Discord

1. Check the correct Discord channel
2. Verify webhook permissions in Discord
3. Check if notifications are muted for that channel
4. Test the webhook URL directly:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"content": "Test"}' \
  "YOUR_WEBHOOK_URL"
```

### Rate limiting

Discord webhooks have rate limits. If sending many notifications:
- Wait a few minutes before testing again
- NextDNS Blocker batches notifications to reduce API calls

## Supported Channels

| Channel | Platform | Description |
|---------|----------|-------------|
| Discord | All | Webhook notifications with rich embeds |
| macOS | macOS only | Native system notifications |

## Security Notes

- Keep your webhook URL private
- Webhook URLs allow anyone to post to your channel
- Regenerate the webhook if compromised
- Consider using a private Discord server

## Related

- [Notifications Feature](/features/notifications/) - Complete notification setup guide
- [config.json Structure](/configuration/config-json/) - Configuration file reference
