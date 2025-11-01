# NextDNS Blocker

Automated system to block access to NextDNS configuration (`my.nextdns.io`) during specific hours using the NextDNS API.

## Features

- Auto-blocks `my.nextdns.io` outside allowed hours
- Default schedule: 🔓 18:00-22:00 (unblocked) / 🔒 22:00-18:00 (blocked)
- Works via NextDNS API denylist
- Automated via cron jobs
- Support for multiple domains

## Requirements

- Python 3.6+
- NextDNS account with API key
- Linux server (tested on Ubuntu/Amazon Linux)

## Quick Setup

### 1. Get NextDNS Credentials

- **API Key**: https://my.nextdns.io/account
- **Profile ID**: From URL (e.g., `https://my.nextdns.io/abc123` → `abc123`)

### 2. Clone Repository

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
```

### 3. Configure

```bash
cp .env.example .env
nano .env  # Add your API key and profile ID
```

### 4. Install

```bash
chmod +x install.sh
./install.sh
```

Done! The system will now block/unblock automatically.

## Manual Commands

```bash
# Check status
python3 ~/nextdns-blocker/nextdns_blocker.py status

# Block manually
python3 ~/nextdns-blocker/nextdns_blocker.py block

# Unblock manually
python3 ~/nextdns-blocker/nextdns_blocker.py unblock

# View logs
tail -f ~/nextdns-blocker/logs/nextdns_blocker.log

# View cron jobs
crontab -l
```

## Customization

### Change Schedule

Edit `.env` to change hours:

```bash
UNLOCK_HOUR=20  # Change to 8pm
LOCK_HOUR=23    # Change to 11pm
```

Then run `./install.sh` again.

### Add More Domains

Edit `domains.txt` to block additional sites:

```bash
nano ~/nextdns-blocker/domains.txt
```

Add one domain per line:

```
my.nextdns.io
reddit.com
twitter.com
facebook.com
```

No need to reinstall, changes take effect immediately on next cron run.

## Troubleshooting

**Blocking not working?**
- Check cron: `crontab -l`
- Check logs: `tail -f ~/nextdns-blocker/logs/nextdns_blocker.log`
- Test manually: `python3 ~/nextdns-blocker/nextdns_blocker.py block`

**Cron not running?**
```bash
# Check cron service status
sudo service cron status || sudo service crond status
```

## Uninstall

```bash
# Remove cron jobs
crontab -l | grep -v "nextdns_blocker.py" | crontab -

# Unblock before removing
python3 ~/nextdns-blocker/nextdns_blocker.py unblock

# Remove files
rm -rf ~/nextdns-blocker
```

## Security

- Never share your `.env` file (contains API key)
- `.gitignore` is configured to ignore sensitive files
- All API requests use HTTPS

## License

MIT
