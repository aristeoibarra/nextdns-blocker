# NextDNS Blocker

[![PyPI version](https://img.shields.io/pypi/v/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![PyPI downloads](https://img.shields.io/pypi/dm/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![Python versions](https://img.shields.io/pypi/pyversions/nextdns-blocker)](https://pypi.org/project/nextdns-blocker/)
[![License](https://img.shields.io/github/license/aristeoibarra/nextdns-blocker)](LICENSE)
[![CI](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml/badge.svg)](https://github.com/aristeoibarra/nextdns-blocker/actions/workflows/ci.yml)
[![Homebrew](https://img.shields.io/badge/homebrew-tap-blue)](https://github.com/aristeoibarra/homebrew-tap)

Automated domain blocking with per-domain scheduling via the NextDNS API. Build healthier digital habits through intelligent scheduling and friction-based protection.

## Features

- **Per-domain scheduling** - Configure unique availability hours for each domain
- **Domain categories** - Group domains together with shared schedules
- **NextDNS Parental Control** - Enable/disable native NextDNS categories and services
- **Unblock delays** - Add friction against impulsive unblocking (30m, 4h, 24h, or never)
- **Panic mode** - Emergency lockdown that blocks all domains
- **Cross-platform** - Native support for macOS, Linux, and Windows
- **Automatic sync** - Watchdog runs every 2 minutes to enforce schedules
- **Discord notifications** - Real-time alerts for block/unblock events
- **Allowlist with schedules** - Time-based exceptions for specific domains

## Quick Install

### Homebrew (macOS/Linux)

```bash
brew tap aristeoibarra/tap
brew install nextdns-blocker
nextdns-blocker init
```

### pip

```bash
pip install nextdns-blocker
nextdns-blocker init
```

### Docker

```bash
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker
cp .env.example .env && cp config.json.example config.json
docker compose up -d
```

## Quick Start

1. Get your [NextDNS API Key](https://my.nextdns.io/account) and Profile ID
2. Run `nextdns-blocker init` to configure
3. Edit your domains: `nextdns-blocker config edit`
4. Install watchdog: `nextdns-blocker watchdog install`

## Documentation

For complete documentation, visit: **[nextdns-blocker.pages.dev](https://nextdns-blocker.pages.dev)**

- [Getting Started](https://nextdns-blocker.pages.dev/getting-started/)
- [Commands Reference](https://nextdns-blocker.pages.dev/commands/)
- [Configuration Guide](https://nextdns-blocker.pages.dev/configuration/)

## Basic Commands

```bash
nextdns-blocker sync              # Sync based on schedules
nextdns-blocker status            # Check current blocking status
nextdns-blocker pause [minutes]   # Pause blocking temporarily
nextdns-blocker resume            # Resume blocking
nextdns-blocker unblock <domain>  # Manually unblock a domain
nextdns-blocker panic <minutes>   # Activate emergency lockdown
```

## Example Configuration

```json
{
  "blocklist": [
    {
      "domain": "reddit.com",
      "unblock_delay": "30m",
      "schedule": {
        "available_hours": [
          {
            "days": ["monday", "tuesday", "wednesday", "thursday", "friday"],
            "time_ranges": [
              {"start": "12:00", "end": "13:00"},
              {"start": "18:00", "end": "22:00"}
            ]
          }
        ]
      }
    }
  ]
}
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT
