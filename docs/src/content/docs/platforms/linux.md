---
title: Linux
description: NextDNS Blocker setup and usage on Linux
---

NextDNS Blocker works on all major Linux distributions using systemd timers (preferred) or cron for scheduling.

## Installation

### pip (Recommended)

```bash
pip3 install nextdns-blocker
```

### pipx (Isolated)

```bash
pipx install nextdns-blocker
```

### From Source

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
pip3 install -e .
```

## Setup

```bash
# Initialize configuration
nextdns-blocker init

# Configure domains
nextdns-blocker config edit

# Install watchdog
nextdns-blocker watchdog install
```

## Scheduler Integration

NextDNS Blocker automatically detects and uses the best scheduler for your system:

| System | Scheduler | Detection |
|--------|-----------|-----------|
| Modern Linux with systemd | systemd timers | `/run/systemd/system` exists |
| Older Linux / minimal installs | cron | systemd not detected |
| WSL (Windows Subsystem for Linux) | cron | WSL detected in kernel |

### Check Your Scheduler

```bash
nextdns-blocker watchdog status
```

Output shows which scheduler is in use:
```
Scheduler: systemd
Status: active
```

## systemd Timer Integration (Recommended)

On modern Linux distributions with systemd, NextDNS Blocker uses user-level systemd timers.

### How It Works

When you run `watchdog install`, it creates:

1. **Service unit**: `~/.config/systemd/user/nextdns-blocker-sync.service`
2. **Timer unit**: `~/.config/systemd/user/nextdns-blocker-sync.timer`
3. **Watchdog service**: `~/.config/systemd/user/nextdns-blocker-wd.service`
4. **Watchdog timer**: `~/.config/systemd/user/nextdns-blocker-wd.timer`

### View Timer Status

```bash
# Check timer status
systemctl --user status nextdns-blocker-sync.timer

# List all timers
systemctl --user list-timers

# View timer details
systemctl --user cat nextdns-blocker-sync.timer
```

### Timer Schedule

| Timer | Interval | Purpose |
|-------|----------|---------|
| `nextdns-blocker-sync.timer` | Every 2 minutes | Domain sync based on schedules |
| `nextdns-blocker-wd.timer` | Every 5 minutes | Health check and recovery |

### Manual Control

```bash
# Stop timers temporarily
systemctl --user stop nextdns-blocker-sync.timer

# Start timers
systemctl --user start nextdns-blocker-sync.timer

# Disable timers (persist across reboots)
systemctl --user disable nextdns-blocker-sync.timer

# Enable timers
systemctl --user enable nextdns-blocker-sync.timer

# Run sync manually
systemctl --user start nextdns-blocker-sync.service
```

### View Logs

```bash
# View service logs
journalctl --user -u nextdns-blocker-sync.service -f

# View recent logs
journalctl --user -u nextdns-blocker-sync.service --since "1 hour ago"
```

### Lingering (Run Without Login)

By default, user services only run while you're logged in. To run even when logged out:

```bash
# Enable lingering for your user
sudo loginctl enable-linger $USER

# Verify
loginctl show-user $USER | grep Linger
# Output: Linger=yes
```

## cron Integration (Fallback)

On systems without systemd or on WSL, NextDNS Blocker uses cron.

### How It Works

NextDNS Blocker adds entries to your user's crontab:

```bash
# View crontab
crontab -l
```

Expected entries:
```
*/2 * * * * /home/user/.local/bin/nextdns-blocker config sync >> /home/user/.local/share/nextdns-blocker/logs/cron.log 2>&1
*/5 * * * * /home/user/.local/bin/nextdns-blocker watchdog check >> /home/user/.local/share/nextdns-blocker/logs/wd.log 2>&1
```

### Managing cron

```bash
# Check watchdog status
nextdns-blocker watchdog status

# View crontab
crontab -l

# Edit crontab manually (if needed)
crontab -e
```

### Cron Service

Ensure cron is running:

```bash
# systemd-based distros
sudo systemctl status cron
# or
sudo systemctl status crond

# Start if not running
sudo systemctl start cron
sudo systemctl enable cron
```

## File Locations

| Component | Path |
|-----------|------|
| Config | `~/.config/nextdns-blocker/config.json` |
| Environment | `~/.config/nextdns-blocker/.env` |
| Logs | `~/.local/share/nextdns-blocker/logs/` |
| State | `~/.local/share/nextdns-blocker/` |
| Binary | `~/.local/bin/nextdns-blocker` |

## Timezone Detection

Linux timezone is detected from:

```bash
# System timezone link
readlink /etc/localtime
# Returns: /usr/share/zoneinfo/America/New_York

# Or from timedatectl
timedatectl | grep "Time zone"
```

## Distribution-Specific Notes

### Ubuntu/Debian

```bash
# Install dependencies
sudo apt update
sudo apt install python3 python3-pip

# Install nextdns-blocker
pip3 install nextdns-blocker

# Add to PATH if needed
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Fedora/RHEL/CentOS

```bash
# Install dependencies
sudo dnf install python3 python3-pip

# Install nextdns-blocker
pip3 install nextdns-blocker
```

### Arch Linux

```bash
# Install dependencies
sudo pacman -S python python-pip

# Install nextdns-blocker
pip install nextdns-blocker
```

### Alpine Linux

```bash
# Install dependencies
apk add python3 py3-pip

# Install nextdns-blocker
pip3 install nextdns-blocker
```

## WSL (Windows Subsystem for Linux)

### Detection

NextDNS Blocker detects WSL via `/proc/version`:

```bash
cat /proc/version
# Contains "Microsoft" or "WSL"
```

### Setup in WSL

```bash
# Standard installation
pip3 install nextdns-blocker
nextdns-blocker init
nextdns-blocker watchdog install
```

### WSL Cron

Ensure cron runs in WSL:

```bash
# Start cron manually
sudo service cron start

# Add to .bashrc for auto-start (WSL1)
echo 'sudo service cron start' >> ~/.bashrc
```

For WSL2 with systemd:
```bash
# Enable systemd in /etc/wsl.conf
[boot]
systemd=true
```

## Headless/Server Setup

### Running Without Desktop

NextDNS Blocker works fully in CLI:

```bash
# All operations via terminal
nextdns-blocker init
nextdns-blocker config edit  # Uses $EDITOR
nextdns-blocker watchdog install
```

### Unattended Setup

```bash
# Create .env manually
cat > ~/.config/nextdns-blocker/.env << EOF
NEXTDNS_API_KEY=your_key
NEXTDNS_PROFILE_ID=your_id
EOF

# Create config.json
cp config.json.example ~/.config/nextdns-blocker/config.json

# Install watchdog
nextdns-blocker watchdog install
```

## DNS Cache

Flush DNS cache:

```bash
# systemd-resolved
sudo systemctl restart systemd-resolved

# nscd (if used)
sudo service nscd restart

# dnsmasq (if used)
sudo service dnsmasq restart
```

## Troubleshooting

### Command Not Found

```bash
# Check PATH
echo $PATH

# Add ~/.local/bin to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Verify
which nextdns-blocker
```

### Cron Not Running Jobs

```bash
# Check cron service
systemctl status cron

# Check cron logs
grep CRON /var/log/syslog

# Check crontab
crontab -l

# Test manual execution
nextdns-blocker config sync --verbose
```

### Permission Denied

```bash
# Fix config permissions
chmod 600 ~/.config/nextdns-blocker/.env
chmod 600 ~/.config/nextdns-blocker/config.json

# Fix executable permissions
chmod +x ~/.local/bin/nextdns-blocker
```

### Python Version Issues

```bash
# Check Python version
python3 --version

# Needs Python 3.9+
# Install newer Python if needed (Ubuntu example)
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.11
```

## Troubleshooting systemd

### Timer Not Starting

```bash
# Check for errors
systemctl --user status nextdns-blocker-sync.timer

# Reload daemon
systemctl --user daemon-reload

# Re-enable timer
systemctl --user enable --now nextdns-blocker-sync.timer
```

### Service Fails to Run

```bash
# Check service status
systemctl --user status nextdns-blocker-sync.service

# View detailed logs
journalctl --user -u nextdns-blocker-sync.service -n 50

# Test manually
~/.local/bin/nextdns-blocker config sync --verbose
```

### User Services Not Running After Reboot

Enable lingering:
```bash
sudo loginctl enable-linger $USER
```

### Switching Between Schedulers

If you need to switch from cron to systemd (or vice versa):

```bash
# Uninstall current scheduler
nextdns-blocker watchdog uninstall

# The next install will auto-detect the preferred scheduler
nextdns-blocker watchdog install
```

To force a specific scheduler (advanced):

```bash
# Force cron even on systemd systems
# (Not recommended - for debugging only)
NEXTDNS_FORCE_CRON=1 nextdns-blocker watchdog install
```

## Uninstalling

```bash
# Remove watchdog
nextdns-blocker watchdog uninstall

# Remove package
pip3 uninstall nextdns-blocker

# Remove configuration (optional)
rm -rf ~/.config/nextdns-blocker

# Remove data (optional)
rm -rf ~/.local/share/nextdns-blocker
```
