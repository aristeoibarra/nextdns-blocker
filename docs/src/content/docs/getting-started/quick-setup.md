---
title: Quick Setup
description: Configure NextDNS Blocker with your credentials and first domains
---

After installation, run the interactive setup wizard to configure your NextDNS credentials.

## Get Your NextDNS Credentials

Before running the wizard, you'll need:

### API Key

1. Go to [my.nextdns.io/account](https://my.nextdns.io/account)
2. Scroll to the "API" section
3. Click to reveal and copy your API key

### Profile ID

1. Go to [my.nextdns.io](https://my.nextdns.io)
2. Select your profile
3. Copy the ID from the URL: `https://my.nextdns.io/abc123/setup` → **abc123**

## Run the Setup Wizard

```bash
nextdns-blocker init
```

:::tip
See the [`init` command reference](/commands/init/) for all options including non-interactive mode for CI/CD.
:::

The wizard will prompt for:

```
NextDNS Blocker Setup
━━━━━━━━━━━━━━━━━━━━━

Enter your NextDNS API Key: ********
Enter your NextDNS Profile ID: abc123

Validating credentials... ✓

Detecting timezone... America/New_York ✓

Configuration saved to:
  ~/.config/nextdns-blocker/.env
  ~/.config/nextdns-blocker/config.json

Run 'nextdns-blocker config edit' to configure domains.
```

### What Gets Created

| File | Purpose |
|------|---------|
| `.env` | API credentials (API key, profile ID) |
| `config.json` | Domain schedules and settings |

Both files are created in your platform's config directory:
- **macOS/Linux**: `~/.config/nextdns-blocker/`
- **Windows**: `%APPDATA%\nextdns-blocker\`

## Configure Your First Domain

Open the configuration editor:

```bash
nextdns-blocker config edit
```

This opens `config.json` in your default editor. Add your first domain:

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York",
    "editor": null
  },
  "blocklist": [
    {
      "domain": "reddit.com",
      "description": "Social media",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "22:00"}
            ]
          },
          {
            "days": ["saturday", "sunday"],
            "time_ranges": [
              {"start": "10:00", "end": "23:00"}
            ]
          }
        ]
      }
    }
  ],
  "allowlist": []
}
```

Save and exit the editor.

## Validate Configuration

Check that your configuration is valid:

```bash
nextdns-blocker config validate
```

Expected output:

```
Configuration valid ✓
  Blocklist: 1 domain
  Allowlist: 0 domains
  Timezone: America/New_York
```

## Install the Watchdog

For automatic syncing every 2 minutes:

```bash
nextdns-blocker watchdog install
```

This creates platform-specific scheduled tasks:
- **macOS**: launchd job
- **Linux**: cron entry
- **Windows**: Task Scheduler task

Verify it's running:

```bash
nextdns-blocker watchdog status
```

## Test Your Configuration

Run a manual sync to verify everything works:

```bash
nextdns-blocker config push --verbose
```

You should see output like:

```
Syncing domains...
  reddit.com: BLOCKED (outside available hours)
Sync complete: 1 blocked, 0 unblocked
```

## Configuration Examples

Ready-to-use templates are available in the `examples/` directory:

| Template | Description |
|----------|-------------|
| `minimal.json` | Quick-start with one domain |
| `work-focus.json` | Productivity-focused rules |
| `gaming.json` | Gaming platforms scheduling |
| `social-media.json` | Social networks management |
| `parental-control.json` | Protected content blocking |
| `study-mode.json` | Student-focused scheduling |

Copy a template:

```bash
cp examples/work-focus.json ~/.config/nextdns-blocker/config.json
nextdns-blocker config edit  # Customize as needed
```

## Timezone Configuration

Timezone is auto-detected during setup. To change it:

```bash
nextdns-blocker config set timezone America/Los_Angeles
```

See the [Timezone guide](/configuration/timezone/) for more details.

## Next Steps

- [Perform your first sync](/getting-started/first-sync/)
- [Learn about schedules](/configuration/schedules/)
- [Explore all commands](/commands/)
