---
title: init
description: Initialize NextDNS Blocker configuration
sidebar:
  order: 1
---

The `init` command runs an interactive wizard to configure NextDNS Blocker for the first time.

## Usage

```bash
nextdns-blocker init [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--config-dir PATH` | Config directory (default: XDG config dir) |
| `--non-interactive` | Use environment variables instead of prompts |

## Interactive Mode

By default, `init` runs an interactive wizard that guides you through the configuration process.

### What it does

1. Prompts for your NextDNS API key
2. Prompts for your NextDNS Profile ID
3. Validates credentials by testing API connectivity
4. Creates the configuration files

### Example Session

```bash
$ nextdns-blocker init

NextDNS Blocker Setup
━━━━━━━━━━━━━━━━━━━━━

Enter your NextDNS API key: ********
Enter your NextDNS Profile ID: abc123

Validating credentials...
  ✓ API connection successful

Creating configuration files...
  ✓ Created ~/.config/nextdns-blocker/.env
  ✓ Created ~/.config/nextdns-blocker/config.json

Setup complete!

Next steps:
  1. Edit your blocklist: nextdns-blocker config edit
  2. Install the scheduler: nextdns-blocker watchdog install
  3. Check status: nextdns-blocker status
```

## Non-Interactive Mode

For CI/CD pipelines or automated deployments, use `--non-interactive` mode with environment variables.

### Required Environment Variables

| Variable | Description |
|----------|-------------|
| `NEXTDNS_API_KEY` | Your NextDNS API key |
| `NEXTDNS_PROFILE_ID` | Your NextDNS Profile ID |

### Example

```bash
export NEXTDNS_API_KEY="your-api-key"
export NEXTDNS_PROFILE_ID="abc123"
nextdns-blocker init --non-interactive
```

### Docker Example

```dockerfile
ENV NEXTDNS_API_KEY=your-api-key
ENV NEXTDNS_PROFILE_ID=abc123
RUN nextdns-blocker init --non-interactive
```

## Custom Config Directory

You can specify a custom configuration directory:

```bash
nextdns-blocker init --config-dir /path/to/config
```

This is useful for:
- Testing configurations
- Running multiple instances
- Non-standard deployments

## Files Created

The `init` command creates the following files:

| File | Description |
|------|-------------|
| `.env` | API credentials (secured with 600 permissions) |
| `config.json` | Domain blocklist and settings |

### File Locations

| Platform | Default Path |
|----------|--------------|
| macOS/Linux | `~/.config/nextdns-blocker/` |
| Windows | `%APPDATA%\nextdns-blocker\` |

## Re-running Init

If you run `init` when configuration already exists:

```bash
$ nextdns-blocker init

Configuration already exists at ~/.config/nextdns-blocker

Overwrite existing configuration? [y/N]: n
Cancelled.
```

To force reconfiguration:

```bash
$ nextdns-blocker init

Overwrite existing configuration? [y/N]: y
# Proceeds with setup wizard...
```

## Getting Your API Key

1. Go to [my.nextdns.io](https://my.nextdns.io)
2. Navigate to **Account** → **API**
3. Click **Create API key**
4. Copy the key (it's only shown once)

## Getting Your Profile ID

1. Go to [my.nextdns.io](https://my.nextdns.io)
2. Select your configuration profile
3. The Profile ID is shown in the URL: `my.nextdns.io/abc123/...`
4. It's also displayed in the **Setup** tab

## Troubleshooting

### "Invalid API key"

Ensure your API key is correct and hasn't been revoked. Create a new API key at [my.nextdns.io](https://my.nextdns.io).

### "Invalid Profile ID"

The Profile ID should be a short alphanumeric string (e.g., `abc123`). Check your NextDNS dashboard.

### "Permission denied"

The config directory might have incorrect permissions:

```bash
chmod 700 ~/.config/nextdns-blocker
```

### "Connection failed"

Check your internet connection and ensure you can reach `api.nextdns.io`.

## What's Next

After running `init`:

1. **Edit your blocklist:**
   ```bash
   nextdns-blocker config edit
   ```

2. **Install the scheduler:**
   ```bash
   nextdns-blocker watchdog install
   ```

3. **Verify everything works:**
   ```bash
   nextdns-blocker status
   nextdns-blocker health
   ```

## Related

- [Configuration Reference](/configuration/config-json/) - Full config.json documentation
- [Environment Variables](/configuration/env-variables/) - .env file reference
- [Watchdog](/commands/watchdog/) - Automatic synchronization
