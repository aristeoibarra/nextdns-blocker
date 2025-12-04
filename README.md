# NextDNS Blocker

Automated system to control domain access with per-domain schedule configuration using the NextDNS API.

## Features

- **Per-domain scheduling**: Configure unique availability hours for each domain
- **Flexible time ranges**: Multiple time windows per day, different schedules per weekday
- **Protected domains**: Mark domains as protected to prevent accidental unblocking
- **Pause/Resume**: Temporarily disable blocking without changing configuration
- **Automatic synchronization**: Runs every 2 minutes via cron with watchdog protection
- **Timezone-aware**: Respects configured timezone for schedule evaluation
- **Secure**: File permissions, input validation, and audit logging
- **NextDNS API integration**: Works via NextDNS denylist
- **Dry-run mode**: Preview changes without applying them
- **Smart caching**: Reduces API calls with intelligent denylist caching
- **Rate limiting**: Built-in protection against API rate limits
- **Exponential backoff**: Automatic retries with increasing delays on failures

## Requirements

- Python 3.8+
- NextDNS account with API key
- Linux/macOS server
- Dependencies: `requests`, `tzdata` (auto-installed)

## Quick Setup

### 1. Get NextDNS Credentials

- **API Key**: https://my.nextdns.io/account
- **Profile ID**: From URL (e.g., `https://my.nextdns.io/abc123` -> `abc123`)

### 2. Clone Repository

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
```

### 3. Configure Environment

```bash
cp .env.example .env
nano .env  # Add your API key, profile ID, and timezone
```

### 4. Configure Domains and Schedules

```bash
cp domains.json.example domains.json
nano domains.json  # Configure your domains and their availability schedules
```

See [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) for detailed schedule configuration examples.

### 5. Install

```bash
chmod +x install.sh
./install.sh
```

Done! The system will now automatically sync every 2 minutes based on your configured schedules.

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
./blocker sync

# Preview what sync would do without making changes
./blocker sync --dry-run

# Sync with verbose output showing all actions
./blocker sync --verbose
./blocker sync -v

# Check current blocking status
./blocker status

# Manually unblock a domain (won't work on protected domains)
./blocker unblock example.com

# Pause all blocking for 30 minutes (default)
./blocker pause

# Pause for custom duration (e.g., 60 minutes)
./blocker pause 60

# Resume blocking immediately
./blocker resume
```

### Watchdog Commands

```bash
# Check cron status
./watchdog status

# Disable watchdog for 30 minutes
./watchdog disable 30

# Disable watchdog permanently
./watchdog disable

# Re-enable watchdog
./watchdog enable

# Manually install cron jobs
./watchdog install

# Remove cron jobs
./watchdog uninstall
```

### Logs

```bash
# View application logs
tail -f ~/.local/share/nextdns-audit/logs/app.log

# View audit log (all blocking/unblocking actions)
cat ~/.local/share/nextdns-audit/logs/audit.log

# View cron execution logs
tail -f ~/.local/share/nextdns-audit/logs/cron.log

# View watchdog logs
tail -f ~/.local/share/nextdns-audit/logs/wd.log

# View cron jobs
crontab -l
```

## Configuration

### Environment Variables (.env)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXTDNS_API_KEY` | Yes | - | Your NextDNS API key |
| `NEXTDNS_PROFILE_ID` | Yes | - | Your NextDNS profile ID |
| `TIMEZONE` | No | `UTC` | Timezone for schedule evaluation |
| `API_TIMEOUT` | No | `10` | API request timeout in seconds |
| `API_RETRIES` | No | `3` | Number of retry attempts |
| `DOMAINS_URL` | No | - | URL to fetch domains.json from |

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
./blocker allow aws.amazon.com

# Remove domain from allowlist
./blocker disallow aws.amazon.com

# View current status including allowlist
./blocker status
```

### Timezone

Edit `.env` to change timezone:

```bash
TIMEZONE=America/New_York
```

See [list of timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones).

## Troubleshooting

**Sync not working?**
- Check cron: `crontab -l` (should see sync job running every 2 minutes)
- Check logs: `tail -f ~/.local/share/nextdns-audit/logs/app.log`
- Test manually: `./blocker sync`
- Validate JSON: `python3 -m json.tool domains.json`

**Domains.json errors?**
- Ensure valid JSON syntax (use [jsonlint.com](https://jsonlint.com))
- Check time format is HH:MM (24-hour)
- Check day names are lowercase (monday, tuesday, etc.)
- Domain names must be valid (no spaces, special characters)
- See `domains.json.example` for reference

**Wrong timezone?**
- Update `TIMEZONE` in `.env`
- Re-run `./install.sh`
- Check logs to verify timezone is being used

**API timeouts?**
- Increase `API_TIMEOUT` in `.env` (default: 10 seconds)
- Increase `API_RETRIES` in `.env` (default: 3 attempts)

**Cron not running?**
```bash
# Check cron service status
sudo service cron status || sudo service crond status

# Check watchdog status
./watchdog status
```

## Uninstall

```bash
# Remove cron jobs
./watchdog uninstall

# Remove files
rm -rf ~/nextdns-blocker

# Remove logs (optional)
rm -rf ~/.local/share/nextdns-audit
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
pip3 install -r requirements-dev.txt
pytest tests/ -v
```

### Test Coverage

```bash
pytest tests/ --cov=nextdns_blocker --cov-report=html
```

Current coverage: **92%** with **287 tests**.

### Code Quality

The codebase follows these practices:
- Type hints on all functions
- Docstrings with Args/Returns documentation
- Custom exceptions for error handling
- Secure file permissions (0o600)
- Input validation before API calls

## Documentation

- [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) - Complete schedule configuration guide with examples
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
