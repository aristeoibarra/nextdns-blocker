# NextDNS Blocker

[![PyPI version](https://img.shields.io/pypi/v/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![PyPI downloads](https://img.shields.io/pypi/dm/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![Python versions](https://img.shields.io/pypi/pyversions/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![License](https://img.shields.io/github/license/aristeoibarra/nextdns-blocker)](LICENSE)
[![CI](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml/badge.svg)](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml)


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

### Option 1: Install from PyPI (Recommended)

```bash
pip install nextdns-blocker
```

Then run the setup wizard:

```bash
nextdns-blocker init
```

### Option 2: Install from Source

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
pip install -e .
nextdns-blocker init
```

### Windows Installation

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
- Timezone (auto-detected from system)
- Option to create sample domains.json

### 3. Configure Domains and Schedules

Edit `domains.json` in your config directory to configure your domains and their availability schedules.

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
cp domains.json.example domains.json
nano domains.json  # Configure your domains and schedules
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
| `DOMAINS_URL` | No | - | URL to fetch domains.json remotely |
| `TZ` | No | `America/Mexico_City` | Container timezone |

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

## Configuration

### Environment Variables (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXTDNS_API_KEY` | Yes | - | Your NextDNS API key |
| `NEXTDNS_PROFILE_ID` | Yes | - | Your NextDNS profile ID |
| `TIMEZONE` | No | Auto-detected | Timezone for schedule evaluation (auto-detected during init) |
| `API_TIMEOUT` | No | `10` | API request timeout in seconds |
| `API_RETRIES` | No | `3` | Number of retry attempts |
| `DOMAINS_URL` | No | - | URL to fetch domains.json from |
| `DISCORD_WEBHOOK_URL` | No | - | Discord webhook URL for notifications |
| `DISCORD_NOTIFICATIONS_ENABLED` | No | `false` | Enable Discord notifications (`true`/`false`) |

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

Edit `domains.json` to configure which domains to manage and their availability schedules:

```json
{
  "domains": [
    {
      "domain": "reddit.com",
      "description": "Social media",
      "protected": false,
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
      "protected": true,
      "schedule": null
    }
  ]
}
```

#### Domain Configuration Options

| Field | Required | Description |
|-------|----------|-------------|
| `domain` | Yes | Domain name to manage |
| `description` | No | Human-readable description |
| `protected` | No | If `true`, domain cannot be manually unblocked |
| `schedule` | No | Availability schedule (null = always blocked) |

Changes take effect on next sync (every 2 minutes).

See [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) for complete documentation and examples.

### Allowlist (Exceptions)

Use the `allowlist` to keep specific subdomains accessible even when their parent domain is blocked:

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
      "domain": "developer.amazon.com",
      "description": "Amazon Developer - always accessible"
    }
  ]
}
```

#### Allowlist Behavior

- Allowlist entries are **always active 24/7** (no schedule support)
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

### Timezone

The timezone is auto-detected during `init` based on your system settings:
- **macOS/Linux**: Reads `/etc/localtime` symlink
- **Windows**: Uses `tzutil /g` command
- **Fallback**: `TZ` environment variable or `UTC`

To override, edit `.env`:

```bash
TIMEZONE=America/New_York
```

See [list of timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Troubleshooting

**Sync not working?**
- Check cron: `crontab -l` (should see sync job running every 2 minutes)
- Check logs: `tail -f ~/.local/share/nextdns-blocker/logs/app.log`
- Test manually: `nextdns-blocker sync`
- Validate JSON: `python3 -m json.tool domains.json`

**Domains.json errors?**
- Ensure valid JSON syntax (use [jsonlint.com](https://jsonlint.com))
- Check time format is HH:MM (24-hour)
- Check day names are lowercase (monday, tuesday, etc.)
- Domain names must be valid (no spaces, special characters)
- See `domains.json.example` for reference

**Wrong timezone?**
- Re-run `nextdns-blocker init` (timezone is auto-detected)
- Or manually update `TIMEZONE` in `.env`
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
- [domains.json.example](domains.json.example) - Example configuration file
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
