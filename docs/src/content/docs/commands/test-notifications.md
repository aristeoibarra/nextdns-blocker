---
title: test-notifications
description: Send a test notification to verify Discord integration
---

The `test-notifications` command sends a test message to your configured Discord webhook to verify the integration is working correctly.

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

Before using this command, you need:

1. **Discord webhook URL** - Create one in your Discord server settings
2. **Configured in `.env`** - Add `DISCORD_WEBHOOK_URL=your_url`

## Setting Up Discord Notifications

### 1. Create a Discord Webhook

1. Open Discord and go to your server
2. Click on the channel where you want notifications
3. Click the gear icon (Edit Channel)
4. Go to **Integrations** > **Webhooks**
5. Click **New Webhook**
6. Copy the webhook URL

### 2. Configure NextDNS Blocker

Add to your `.env` file:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/123456789/abcdef...
```

Or edit existing configuration:

```bash
nextdns-blocker config edit
# Add the webhook URL to your .env file
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
  Notification sent! Check your Discord channel.
```

You should see a message in your Discord channel confirming the connection.

### Missing Configuration

```bash
nextdns-blocker test-notifications
```

Output:
```
  Error: DISCORD_WEBHOOK_URL is not set in configuration.
      Please add it to your .env file.
```

## What Notifications Are Sent

When enabled, NextDNS Blocker sends Discord notifications for:

| Event | Description |
|-------|-------------|
| Sync complete | Summary of blocked/unblocked domains |
| Panic mode activated | Alert when emergency mode starts |
| Panic mode ended | Alert when emergency mode expires |
| Unblock request | When a pending unblock is created |
| Unblock executed | When a pending unblock completes |

## Notification Format

Test notifications appear in Discord like:

```
🧪 NextDNS Blocker Test
Test Connection
Connection successful!
```

Regular notifications include:
- Event type icon
- Domain or action details
- Timestamp

## Troubleshooting

### Webhook URL not set

```
Error: DISCORD_WEBHOOK_URL is not set in configuration.
```

**Solution**: Add the webhook URL to your `.env` file:

```bash
echo 'DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...' >> ~/.config/nextdns-blocker/.env
```

### Invalid webhook URL

If the notification fails silently:

1. Verify the webhook URL is correct
2. Check the webhook hasn't been deleted in Discord
3. Ensure the channel still exists
4. Try creating a new webhook

### Notification not appearing

1. Check the correct Discord channel
2. Verify webhook permissions in Discord
3. Check if notifications are muted for that channel
4. Try the webhook URL in a browser/curl to test directly

### Rate limiting

Discord webhooks have rate limits. If sending many notifications:
- Wait a few minutes before testing again
- Consider reducing notification frequency

## Disabling Notifications

To disable Discord notifications:

1. Remove or comment out `DISCORD_WEBHOOK_URL` in `.env`:

```bash
# DISCORD_WEBHOOK_URL=https://...
```

2. Or set it to empty:

```bash
DISCORD_WEBHOOK_URL=
```

## Security Notes

- Keep your webhook URL private
- Don't share your `.env` file
- Webhook URLs can be used by anyone to post to your channel
- Regenerate the webhook if compromised

## Related

- [Notifications Feature](/features/notifications/) - Complete notification setup guide
- [Configuration](/configuration/env-variables/) - Environment variable reference
