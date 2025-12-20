[English](README.md) | [Español](README.es.md)
# NextDNS Blocker

[![PyPI version](https://img.shields.io/pypi/v/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![PyPI downloads](https://img.shields.io/pypi/dm/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![Python versions](https://img.shields.io/pypi/pyversions/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![License](https://img.shields.io/github/license/aristeoibarra/nextdns-blocker)](LICENSE)
[![CI](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml/badge.svg)](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml)
[![Homebrew](https://img.shields.io/badge/homebrew-tap-blue)](https://github.com/aristeoibarra/homebrew-tap)


Automated system to control domain access with per-domain schedule configuration using the NextDNS API.

## Features

- **Cross-platform**: Native support for macOS (launchd), Linux (cron), and Windows (Task Scheduler)
- **Per-domain scheduling**: Configure unique availability hours for each domain
- **Flexible time ranges**: Multiple time windows per day, different schedules per weekday
- **Protected domains**: Mark domains as protected to prevent accidental unblocking
- **Pause/Resume**: Temporarily disable blocking without changing configuration
- **Automatic synchronization**: Runs every 2 minutes with watchdog protection
- **Discord notifications**: Real-time alerts for block/unblock events
- **Timezone-aware**: Respects configured timezone for schedule evaluation
- **Secure**: File permissions, input validation, and audit logging
- **NextDNS API integration**: Works via NextDNS denylist
- **Dry-run mode**: Preview changes without applying them
- **Smart caching**: Reduces API calls with intelligent denylist caching
- **Rate limiting**: Built-in protection against API rate limits
- **Exponential backoff**: Automatic retries with increasing delays on failures
- **Self-update**: Built-in command to check and install updates

## Requirements

- Python 3.9+
- NextDNS account with API key
- Linux/macOS/Windows

## Installation

### Option 1: Homebrew (macOS/Linux)

```bash
brew tap aristeoibarra/tap
brew install nextdns-blocker
```

Then run the setup wizard:

```bash
nextdns-blocker init
```

### Option 2: Install from PyPI

```bash
pip install nextdns-blocker
```

Then run the setup wizard:

```bash
nextdns-blocker init
```

### Option 3: Install from Source

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
pip install -e .
nextdns-blocker init
```

### Option 4: Windows Installation

On Windows, you can also use the PowerShell installer:

```powershell
# Download and run the installer
irm https://raw.githubusercontent.com/aristeoibarra/nextdns-blocker/main/install.ps1 | iex

# Or run locally after cloning
.\install.ps1
```

The installer will:
- Check for Python installation
- Install the package via pip
- Run the interactive setup wizard
- Configure Windows Task Scheduler for automatic sync

## Quick Setup

### 1. Get NextDNS Credentials

- **API Key**: https://my.nextdns.io/account
- **Profile ID**: From URL (e.g., `https://my.nextdns.io/abc123` -> `abc123`)

### 2. Run Setup Wizard

```bash
nextdns-blocker init
```

The wizard will prompt for:
- API Key
- Profile ID

Timezone is automatically detected from your system and saved to `config.json`.

### 3. Configure Domains and Schedules

Edit `config.json` in your config directory to configure your domains and their availability schedules:

```bash
nextdns-blocker config edit
```

See [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) for detailed schedule configuration examples.

### 4. Install Watchdog (Optional)

For automatic syncing every 2 minutes:

```bash
nextdns-blocker watchdog install
```

This installs platform-specific scheduled jobs:
- **macOS**: launchd jobs (`~/Library/LaunchAgents/`)
- **Linux**: cron jobs (`crontab -l`)
- **Windows**: Task Scheduler tasks (view with `taskschd.msc`)

Done! The system will now automatically sync based on your configured schedules.

## Docker Setup

Alternatively, run NextDNS Blocker using Docker:

### 1. Configure Environment

```bash
cp .env.example .env
nano .env  # Add your API key, profile ID, and timezone
```

### 2. Configure Domains

```bash
cp config.json.example config.json
nano config.json  # Configure your domains and schedules
```

### 3. Run with Docker Compose

```bash
docker compose up -d
```

### Docker Commands

```bash
# View logs
docker compose logs -f

# Stop the container
docker compose down

# Rebuild after changes
docker compose up -d --build

# Check status
docker compose ps

# Run a one-time sync
docker compose exec nextdns-blocker python nextdns_blocker.py sync -v

# Check blocking status
docker compose exec nextdns-blocker python nextdns_blocker.py status
```

### Environment Variables for Docker

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXTDNS_API_KEY` | Yes | - | Your NextDNS API key |
| `NEXTDNS_PROFILE_ID` | Yes | - | Your NextDNS profile ID |
| `TZ` | No | `UTC` | Container timezone |

## Commands

### Main Blocker Commands

```bash
# Sync based on schedules (runs automatically every 2 min)
nextdns-blocker sync

# Preview what sync would do without making changes
nextdns-blocker sync --dry-run

# Sync with verbose output showing all actions
nextdns-blocker sync --verbose
nextdns-blocker sync -v

# Check current blocking status
nextdns-blocker status

# Manually unblock a domain (won't work on protected domains)
nextdns-blocker unblock example.com

# Pause all blocking for 30 minutes (default)
nextdns-blocker pause

# Pause for custom duration (e.g., 60 minutes)
nextdns-blocker pause 60

# Resume blocking immediately
nextdns-blocker resume

# Check for updates and upgrade
nextdns-blocker update

# Update without confirmation prompt
nextdns-blocker update -y
```

### Pending Actions Commands

```bash
# List all pending unblock actions
nextdns-blocker pending list

# Show details of a specific pending action
nextdns-blocker pending show <action-id>

# Cancel a pending unblock action
nextdns-blocker pending cancel <action-id>

# Cancel without confirmation
nextdns-blocker pending cancel <action-id> -y
```

### Config Commands

```bash
# Show current configuration
nextdns-blocker config show

# Edit config in your editor ($EDITOR)
nextdns-blocker config edit

# Set a configuration value
nextdns-blocker config set timezone America/New_York
nextdns-blocker config set editor vim

# Validate configuration syntax and structure
nextdns-blocker config validate

# Sync domains (same as root sync, but preferred)
nextdns-blocker config sync
```

### Watchdog Commands

```bash
# Check cron status
nextdns-blocker watchdog status

# Disable watchdog for 30 minutes
nextdns-blocker watchdog disable 30

# Disable watchdog permanently
nextdns-blocker watchdog disable

# Re-enable watchdog
nextdns-blocker watchdog enable

# Manually install cron jobs
nextdns-blocker watchdog install

# Remove cron jobs
nextdns-blocker watchdog uninstall
```

### Panic Mode Commands

Emergency lockdown mode that temporarily blocks all domains and hides dangerous commands.

```bash
# Activate panic mode for 1 hour
nextdns-blocker panic 60

# Check panic mode status
nextdns-blocker panic status

# Extend panic mode by 30 minutes
nextdns-blocker panic extend 30
```

During panic mode:
- All domains are immediately blocked
- Commands like `unblock`, `pause`, `resume`, `allow`, `disallow` are hidden
- Sync skips unblocks and allowlist operations
- Pending actions are paused
- Minimum duration is 15 minutes

### Logs

```bash
# View application logs
tail -f ~/.local/share/nextdns-blocker/logs/app.log

# View audit log (all blocking/unblocking actions)
cat ~/.local/share/nextdns-blocker/logs/audit.log

# View cron execution logs
tail -f ~/.local/share/nextdns-blocker/logs/cron.log

# View watchdog logs
tail -f ~/.local/share/nextdns-blocker/logs/wd.log

# View cron jobs
crontab -l
```

### Shell Completion

Enable tab completion for commands, subcommands, and domain names.

**Bash** - add to `~/.bashrc`:

```bash
eval "$(nextdns-blocker completion bash)"
```

**Zsh** - add to `~/.zshrc`:

```bash
eval "$(nextdns-blocker completion zsh)"
```

**Fish** - save to completions directory:

```bash
nextdns-blocker completion fish > ~/.config/fish/completions/nextdns-blocker.fish
```

After adding the completion script, restart your shell or source the config file.

**What completes:**

| Context | Completions |
|---------|-------------|
| `nextdns-blocker <TAB>` | All commands |
| `nextdns-blocker config <TAB>` | Subcommands: edit, show, sync, etc. |
| `nextdns-blocker unblock <TAB>` | Domain names from your blocklist |
| `nextdns-blocker disallow <TAB>` | Domain names from your allowlist |
| `nextdns-blocker pending cancel <TAB>` | Pending action IDs |
| `nextdns-blocker --<TAB>` | Flags: --help, --version, --no-color |

## Configuration

### Environment Variables (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXTDNS_API_KEY` | Yes | - | Your NextDNS API key |
| `NEXTDNS_PROFILE_ID` | Yes | - | Your NextDNS profile ID |
| `API_TIMEOUT` | No | `10` | API request timeout in seconds |
| `API_RETRIES` | No | `3` | Number of retry attempts |
| `DISCORD_WEBHOOK_URL` | No | - | Discord webhook URL for notifications |
| `DISCORD_NOTIFICATIONS_ENABLED` | No | `false` | Enable Discord notifications (`true`/`false`) |

> **Note:** Timezone is now configured in `config.json` under `settings.timezone` and is auto-detected during setup.

### Discord Notifications

Get real-time alerts when domains are blocked or unblocked:

1. Create a Discord webhook in your server (Server Settings → Integrations → Webhooks)
2. Add to your `.env`:

```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
DISCORD_NOTIFICATIONS_ENABLED=true
```

Notifications show:
- Domain name
- Action (blocked/unblocked)
- Timestamp
- Color-coded embeds (red=block, green=unblock)

### Domain Schedules

Edit `config.json` to configure which domains to manage and their availability schedules:

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
      "unblock_delay": "0",
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
              {"start": "10:00", "end": "22:00"}
            ]
          }
        ]
      }
    },
    {
      "domain": "gambling-site.com",
      "description": "Always blocked",
      "unblock_delay": "never",
      "schedule": null
    }
  ],
  "allowlist": []
}
```

#### Domain Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `domain` | Yes | Domain name to manage |
| `description` | No | Human-readable description |
| `unblock_delay` | No | Cooldown before unblock executes (see below) |
| `schedule` | No | Availability schedule (null = always blocked) |

#### Unblock Delay Options

The `unblock_delay` field creates friction against impulsive unblocking:

| Value | Behavior |
|-------|----------|
| `"0"` | Instant unblock (no protection) |
| `"30m"` | Unblock queued, executes in 30 minutes |
| `"4h"` | Unblock queued, executes in 4 hours |
| `"24h"` | Unblock queued, executes in 24 hours |
| `"never"` | Cannot unblock (fully protected) |

When a delay is set, attempting to unblock creates a **pending action**:

```bash
$ nextdns-blocker unblock bumble.com

Unblock scheduled for 'bumble.com'
Delay: 24h
Execute at: 2025-12-16T03:45:00
ID: pnd_20251215_034500_a1b2c3

Use 'pending list' to view or 'pending cancel' to abort
```

You can cancel the pending action before it executes:

```bash
$ nextdns-blocker pending cancel a1b2c3
Cancelled pending unblock for bumble.com
```

This is based on research showing that cravings typically fade within 20-30 minutes. The delay creates space for better decisions.

Changes take effect on next sync (every 2 minutes).

See [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) for complete documentation and examples.

### Allowlist (Exceptions)

Use the `allowlist` to keep specific subdomains accessible even when their parent domain is blocked. Allowlist entries also support **schedules** for time-based access:

```json
{
  "domains": [
    {
      "domain": "amazon.com",
      "description": "E-commerce - blocked with schedule",
      "schedule": { ... }
    }
  ],
  "allowlist": [
    {
      "domain": "aws.amazon.com",
      "description": "AWS Console - always accessible"
    },
    {
      "domain": "youtube.com",
      "description": "Streaming - blocked by NextDNS category, allow evenings",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
            "time_ranges": [{ "start": "20:00", "end": "22:30" }]
          }
        ]
      }
    }
  ]
}
```

#### Allowlist Behavior

| Schedule | Behavior |
|----------|----------|
| `null` or missing | Always in allowlist (24/7) |
| defined | Only in allowlist during scheduled hours |

- **Scheduled allowlist** is useful for domains blocked by NextDNS categories or services
- Outside schedule hours, the domain is removed from the allowlist (category/service blocks it)
- During schedule hours, the domain is added to the allowlist (unblocked)
- A domain cannot be in both `domains` (denylist) and `allowlist`
- Use for subdomain exceptions: block `amazon.com` but allow `aws.amazon.com`
- Changes sync automatically every 2 minutes

#### Allowlist Commands

```bash
# Add domain to allowlist (always accessible)
nextdns-blocker allow aws.amazon.com

# Remove domain from allowlist
nextdns-blocker disallow aws.amazon.com

# View current status including allowlist
nextdns-blocker status
```

#### Blocklist and Allowlist Interaction

NextDNS processes these lists with specific priority rules:

1. **Allowlist has highest priority** - If a domain is in both lists, NextDNS will ALLOW it
2. **Subdomain inheritance** - Blocking `amazon.com` blocks all subdomains (`*.amazon.com`)
3. **Subdomain exceptions** - You can allow `aws.amazon.com` while blocking `amazon.com`

Example configuration:

```json
{
  "blocklist": [
    {"domain": "amazon.com", "schedule": null}
  ],
  "allowlist": [
    {"domain": "aws.amazon.com"}
  ]
}
```

Result in NextDNS:
- `amazon.com` → Blocked
- `www.amazon.com` → Blocked (inherits from parent)
- `aws.amazon.com` → **Allowed** (allowlist overrides)
- `console.aws.amazon.com` → **Allowed** (inherits from allowlist entry)

> **Note:** This tool validates that the exact same domain doesn't appear in both lists.
> Subdomain relationships are allowed and will generate an informational warning during config load.

#### Panic Mode and Allowlist

During [panic mode](#panic-mode-commands), **all allowlist operations are blocked**:
- The `allow` command is hidden
- The `disallow` command is hidden
- Scheduled allowlist sync is completely skipped

This prevents scheduled allowlist entries from creating security holes during emergency lockdown.
The allowlist has highest priority in NextDNS and would bypass all blocks if allowed to sync.

### Timezone

The timezone is auto-detected during `init` based on your system settings:
- **macOS/Linux**: Reads `/etc/localtime` symlink
- **Windows**: Uses `tzutil /g` command
- **Fallback**: `TZ` environment variable or `UTC`

Timezone is stored in `config.json` under `settings.timezone`. To change it:

```bash
nextdns-blocker config set timezone America/New_York
```

See [list of timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Troubleshooting

**Sync not working?**
- Check cron: `crontab -l` (should see sync job running every 2 minutes)
- Check logs: `tail -f ~/.local/share/nextdns-blocker/logs/app.log`
- Test manually: `nextdns-blocker sync`
- Validate JSON: `python3 -m json.tool config.json`

**Config.json errors?**
- Ensure valid JSON syntax (use [jsonlint.com](https://jsonlint.com))
- Check time format is HH:MM (24-hour)
- Check day names are lowercase (monday, tuesday, etc.)
- Domain names must be valid (no spaces, special characters)
- Validate with: `nextdns-blocker config validate`
- See `config.json.example` for reference

**Wrong timezone?**
- Change with: `nextdns-blocker config set timezone America/New_York`
- Or re-run `nextdns-blocker init` (timezone is auto-detected)
- Check logs to verify timezone is being used

**API timeouts?**
- Increase `API_TIMEOUT` in `.env` (default: 10 seconds)
- Increase `API_RETRIES` in `.env` (default: 3 attempts)

**Cron not running?**
```bash
# Check cron service status
sudo service cron status || sudo service crond status

# Check watchdog status
nextdns-blocker watchdog status
```

### Windows Troubleshooting

**Task Scheduler not running?**
```powershell
# Check Task Scheduler status
nextdns-blocker watchdog status

# View tasks in Task Scheduler GUI
taskschd.msc

# List tasks via command line
schtasks /query /tn "NextDNS-Blocker-Sync"
schtasks /query /tn "NextDNS-Blocker-Watchdog"

# Manually run sync task
schtasks /run /tn "NextDNS-Blocker-Sync"
```

**Paths with spaces causing issues?**
- The application handles paths with spaces automatically
- If you see errors, check that your username doesn't contain special characters like `<`, `>`, `|`, `&`
- Log files are stored in: `%LOCALAPPDATA%\nextdns-blocker\logs\`

**PowerShell script won't run?**
```powershell
# Check execution policy
Get-ExecutionPolicy

# Allow scripts for current user (if needed)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Run installer
.\install.ps1
```

**View Windows logs**
```powershell
# Application log
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\app.log" -Tail 50

# Sync log
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\sync.log" -Tail 50

# Audit log
Get-Content "$env:LOCALAPPDATA\nextdns-blocker\logs\audit.log" -Tail 50
```

**File permissions on Windows**
- Windows uses ACLs instead of Unix file permissions (0o600)
- Files are created with default user permissions
- Configuration files in `%APPDATA%\nextdns-blocker\` are only accessible by the current user in typical configurations

## Uninstall

```bash
# Remove cron jobs
nextdns-blocker watchdog uninstall

# Remove files
rm -rf ~/nextdns-blocker

# Remove logs (optional)
rm -rf ~/.local/share/nextdns-blocker
```

## Log Rotation

To prevent log files from growing indefinitely, set up log rotation:

```bash
chmod +x setup-logrotate.sh
./setup-logrotate.sh
```

This configures automatic rotation with:
- `app.log`: daily, 7 days retention
- `audit.log`: weekly, 12 weeks retention
- `cron.log`: daily, 7 days retention
- `wd.log`: daily, 7 days retention

## Development

### Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Test Coverage

```bash
pytest tests/ --cov=nextdns_blocker --cov-report=html
```

Current coverage: **94%** with **1154 tests**.

### Code Quality

The codebase follows these practices:
- Type hints on all functions
- Docstrings with Args/Returns documentation
- Custom exceptions for error handling
- Secure file permissions (0o600)
- Input validation before API calls

## Documentation

- [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) - Complete schedule configuration guide with examples
- [examples/](examples/) - Ready-to-use configuration templates:
  - `minimal.json` - Quick-start templates
  - `work-focus.json` - Productivity-focused rules
  - `gaming.json` - Gaming platforms scheduling
  - `social-media.json` - Social networks management
  - `parental-control.json` - Protected content blocking
  - `study-mode.json` - Student-focused scheduling for distraction-free studying
- [config.json.example](config.json.example) - Example configuration file
- [CONTRIBUTING.md](CONTRIBUTING.md) - Contribution guidelines

## Security

- Never share your `.env` file (contains API key)
- `.gitignore` is configured to ignore sensitive files
- All API requests use HTTPS
- Sensitive files created with `0o600` permissions
- Domain names validated before API calls
- Audit log tracks all blocking/unblocking actions

## License

MIT

## ❓ Frequently Asked Questions

###  What is the difference between this tool and the NextDNS dashboard?
While the NextDNS dashboard allows you to manually toggle blocklists or set basic parental controls, **nextdns-blocker** is an automation agent. It allows for:
- **Dynamic Scheduling:** Automatically blocking and unblocking specific domains at precise times (e.g., blocking gaming sites only during study hours).
- **State Enforcement:** The "Watchdog" feature actively monitors your configuration to ensure restrictions haven't been manually disabled or bypassed.

###  How do I get my NextDNS API Key and Profile ID?
- **Profile ID:** This is the 6-character code found in the URL of your NextDNS dashboard (e.g., `https://my.nextdns.io/abcdef` -> `abcdef`).
- **API Key:** Go to your [NextDNS Account page](https://my.nextdns.io/account), scroll to the "API Key" section, and click to reveal/copy your key.

###  Does this tool block ads automatically?
**No.** This tool is designed to manage **access policies** (blocking specific websites/apps) rather than maintaining ad-block lists. For ad blocking, please enable the *NextDNS Ads & Trackers Blocklist* directly in your profile settings.

###  How does the "Watchdog" feature work?
The Watchdog runs in the background to prevent unauthorized changes. If a blocked domain is manually unblocked via the dashboard (or by another user), the Watchdog detects the discrepancy and immediately re-applies the block rule to maintain the security policy.

###  Where can I see what changes the blocker has made?
The tool includes an **Audit Log** feature. Check the generated log files (default location typically in the installation directory) to view a history of all block/unblock actions and watchdog enforcement events.

###  Can I run this on a Raspberry Pi?
**Yes.** Since `nextdns-blocker` is a Python package, it is lightweight and compatible with any system that supports Python 3, including Raspberry Pi, Linux servers, macOS, and Windows.
