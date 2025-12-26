---
title: Discord Notifications
description: Real-time alerts for blocking events
---

Get instant notifications on Discord when domains are blocked, unblocked, or when special modes are activated.

## Setup

### 1. Create Discord Webhook

1. Open Discord server settings
2. Go to **Integrations** → **Webhooks**
3. Click **New Webhook**
4. Name it (e.g., "NextDNS Blocker")
5. Select the channel for notifications
6. Click **Copy Webhook URL**

### 2. Configure NextDNS Blocker

Add to your `.env` file:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/1234567890/abcdefghijklmnop
DISCORD_NOTIFICATIONS_ENABLED=true
```

### 3. Verify Setup

Run a sync to test:

```bash
nextdns-blocker sync --verbose
```

Check Discord for notification.

## Notification Types

### Block Event

When a domain is blocked:

```
🔴 Domain Blocked

Domain: reddit.com
Time: 2024-01-15 09:00:00
Reason: Outside available hours

Next available: 12:00
```

**Color**: Red

### Unblock Event

When a domain is unblocked:

```
🟢 Domain Unblocked

Domain: reddit.com
Time: 2024-01-15 12:00:00
Reason: Within schedule

Blocks at: 13:00
```

**Color**: Green

### Pending Action Created

When an unblock is queued:

```
🟡 Pending Unblock

Domain: bumble.com
Delay: 24h
Executes: 2024-01-16 14:30:00
ID: pnd_20240115_143000_a1b2c3
```

**Color**: Yellow

### Pending Action Cancelled

When you cancel a pending unblock:

```
⚪ Pending Cancelled

Domain: bumble.com
Was scheduled for: 2024-01-16 14:30:00
Cancelled at: 2024-01-15 15:00:00
```

**Color**: Gray

### Panic Mode Activated

When panic mode starts:

```
🚨 PANIC MODE ACTIVATED

Duration: 60 minutes
Expires: 2024-01-15 15:30:00
All domains now blocked
```

**Color**: Red (urgent)

### Allow/Disallow Events

When allowlist changes:

```
✅ Domain Allowed

Domain: aws.amazon.com
Added to allowlist
```

```
❌ Domain Disallowed

Domain: aws.amazon.com
Removed from allowlist
```

## Configuration Options

### DISCORD_WEBHOOK_URL

The full webhook URL from Discord.

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

**Format validation**:
- Must start with `https://discord.com/api/webhooks/`
- Must include webhook ID and token

### DISCORD_NOTIFICATIONS_ENABLED

Enable or disable notifications.

```bash
DISCORD_NOTIFICATIONS_ENABLED=true   # Enabled
DISCORD_NOTIFICATIONS_ENABLED=false  # Disabled
```

Default: `false`

## Rate Limiting

Notifications are rate-limited to prevent spam:

- **Minimum interval**: 3 seconds between notifications
- **Batch similar events**: Multiple blocks/unblocks grouped
- **Non-blocking**: Notification failures don't affect sync

## Notification Channel Ideas

### Separate Channels

Create different webhooks for different purposes:

1. **#nextdns-alerts** - All notifications
2. **#nextdns-panic** - Only panic mode (urgent)
3. **#accountability** - Share with accountability partner

### Private vs Shared

- **Private channel**: Personal monitoring
- **Shared channel**: Accountability with trusted person

## Disabling Notifications

### Temporarily

Comment out or change in `.env`:

```bash
DISCORD_NOTIFICATIONS_ENABLED=false
```

### Permanently

Remove from `.env`:

```bash
# DISCORD_WEBHOOK_URL=...
# DISCORD_NOTIFICATIONS_ENABLED=...
```

## Troubleshooting

### Notifications not appearing

1. **Check webhook URL**:
   - Copy fresh from Discord
   - Ensure no extra spaces

2. **Check enabled flag**:
   ```bash
   grep DISCORD ~/.config/nextdns-blocker/.env
   ```

3. **Test webhook manually**:
   ```bash
   curl -X POST \
     -H "Content-Type: application/json" \
     -d '{"content": "Test from NextDNS Blocker"}' \
     "YOUR_WEBHOOK_URL"
   ```

4. **Check sync logs**:
   ```bash
   tail -20 ~/.local/share/nextdns-blocker/logs/cron.log
   ```

### Webhook invalid

Discord webhook deleted or expired:

1. Create new webhook in Discord
2. Update `.env` with new URL
3. Test with sync

### Duplicate notifications

Might be from:
- Multiple sync runs
- Watchdog restart

Rate limiting should prevent most duplicates.

### Notifications delayed

Discord webhook delivery can be delayed by:
- Discord server load
- Network issues
- Rate limiting

Usually resolves within seconds.

## Privacy Considerations

### What's Shared

Notifications include:
- Domain names being blocked/unblocked
- Timestamps
- Action types

### What's NOT Shared

Notifications don't include:
- Your IP address
- NextDNS credentials
- Full configuration

### Recommendations

1. Use a private Discord server
2. Don't share webhook URL
3. Consider separate notification channel
4. Review who has access to the channel

## Alternative Notification Methods

Currently, only Discord is supported. Future possibilities:
- Slack
- Email
- Telegram
- Webhook (generic)

Feature requests welcome on GitHub.
