# NextDNS Blocker

Automated system to control domain access with per-domain schedule configuration using the NextDNS API.

## Features

- **Per-domain scheduling**: Configure unique availability hours for each domain
- **Flexible time ranges**: Multiple time windows per day, different schedules per weekday
- **Automatic synchronization**: Runs every 10 minutes via cron
- **Timezone-aware**: Respects configured timezone for schedule evaluation
- **NextDNS API integration**: Works via NextDNS denylist
- **Easy configuration**: JSON-based configuration with examples

## Requirements

- Python 3.6+
- NextDNS account with API key
- Linux server (tested on Ubuntu/Amazon Linux)
- Dependencies: `requests`, `pytz` (auto-installed)

## Quick Setup

### 1. Get NextDNS Credentials

- **API Key**: https://my.nextdns.io/account
- **Profile ID**: From URL (e.g., `https://my.nextdns.io/abc123` → `abc123`)

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

## Commands

```bash
# Sync based on schedules (runs automatically every 2 min)
./blocker.bin sync

# Check current status
./blocker.bin status

# View logs
tail -f ~/.local/share/nextdns-audit/logs/app.log

# View audit log
cat ~/.local/share/nextdns-audit/logs/audit.log

# View cron jobs
crontab -l
```

## Configuration

### Domain Schedules

Edit `domains.json` to configure which domains to manage and their availability schedules:

```bash
nano ~/nextdns-blocker/domains.json
```

Example configuration:

```json
{
  "domains": [
    {
      "domain": "reddit.com",
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
    }
  ]
}
```

Changes take effect on next sync (every 2 minutes).

See [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) for complete documentation and examples.

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
- Test manually: `./blocker.bin sync`
- Validate JSON: `python3 -m json.tool domains.json`

**Domains.json errors?**
- Ensure valid JSON syntax (use [jsonlint.com](https://jsonlint.com))
- Check time format is HH:MM (24-hour)
- Check day names are lowercase (monday, tuesday, etc.)
- See `domains.json.example` for reference

**Wrong timezone?**
- Update `TIMEZONE` in `.env`
- Re-run `./install.sh`
- Check logs to verify timezone is being used

**Cron not running?**
```bash
# Check cron service status
sudo service cron status || sudo service crond status
```

## Uninstall

```bash
# Remove cron jobs
crontab -l | grep -v "blocker" | grep -v "watchdog" | crontab -

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

## Documentation

- [SCHEDULE_GUIDE.md](SCHEDULE_GUIDE.md) - Complete schedule configuration guide with examples
- [domains.json.example](domains.json.example) - Example configuration file

## Security

- Never share your `.env` file (contains API key)
- `.gitignore` is configured to ignore sensitive files
- All API requests use HTTPS

## License

MIT
