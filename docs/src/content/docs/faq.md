---
title: FAQ
description: Frequently asked questions about NextDNS Blocker
---

Answers to common questions about NextDNS Blocker.

## General

### What is NextDNS Blocker?

NextDNS Blocker is a command-line tool that automates domain blocking using the NextDNS API. It provides:
- Per-domain scheduling (block during work, allow during breaks)
- Unblock delays (friction against impulsive access)
- Automatic synchronization

### How is this different from the NextDNS dashboard?

The NextDNS dashboard allows manual blocking, but NextDNS Blocker adds:
- **Automated scheduling**: Domains block/unblock based on time
- **Watchdog enforcement**: Automatically re-applies rules
- **Unblock delays**: Creates friction for manual unblocking

### Is this an official NextDNS product?

No, NextDNS Blocker is a community project that uses the official NextDNS API.

### Is it free?

Yes, NextDNS Blocker is free and open source (MIT license). You need a NextDNS account, which has free and paid tiers.

## Setup

### How do I get my API key?

1. Go to [my.nextdns.io/account](https://my.nextdns.io/account)
2. Scroll to the "API" section
3. Click to reveal and copy your key

### How do I find my Profile ID?

Your Profile ID is the 6-character code in your NextDNS URL:
- URL: `https://my.nextdns.io/abc123/setup`
- Profile ID: `abc123`

### Can I use multiple profiles?

Yes, but each installation of NextDNS Blocker manages one profile. For multiple profiles:
- Run separate instances with different `.env` files
- Or use Docker with multiple containers

### Does this work on my phone?

NextDNS Blocker runs on computers (macOS, Linux, Windows). For phone blocking:
- Use NextDNS directly on your phone
- Or let NextDNS Blocker manage your router's DNS

## Blocking

### What exactly gets blocked?

When a domain is blocked:
1. NextDNS Blocker adds it to your NextDNS denylist
2. NextDNS returns NXDOMAIN for DNS queries
3. Your browser/app can't resolve the domain

### Does it block subdomains too?

Yes, blocking `reddit.com` blocks:
- `reddit.com`
- `www.reddit.com`
- `old.reddit.com`
- All `*.reddit.com`

### Can I allow a subdomain while blocking the parent?

Yes, use the allowlist:

```json
{
  "blocklist": [{"domain": "amazon.com"}],
  "allowlist": [{"domain": "aws.amazon.com"}]
}
```

### Does this block ads?

No, NextDNS Blocker manages **access policies** (which websites you can visit). For ad blocking, enable NextDNS's built-in ad blocking in the dashboard.

## Schedules

### How does scheduling work?

You define `available_hours` - when a domain is accessible. Outside those hours, it's blocked.

```json
{
  "schedule": {
    "available_hours": [
      {
        "days": ["monday", "friday"],
        "time_ranges": [{"start": "18:00", "end": "22:00"}]
      }
    ]
  }
}
```

### What timezone is used?

The timezone from your `config.json`:

```json
{
  "settings": {
    "timezone": "America/New_York"
  }
}
```

Auto-detected during `init`, or set with:
```bash
nextdns-blocker config set timezone America/Los_Angeles
```

### Can I have overnight schedules?

Yes, use time ranges that cross midnight:

```json
{"start": "22:00", "end": "02:00"}
```

This allows access from 10 PM to 2 AM.

## Unblock Delays

### What are unblock delays?

Delays that create friction between requesting access and receiving it:

| Delay | What happens |
|-------|--------------|
| `"0"` | Instant unblock |
| `"30m"` | Wait 30 minutes |
| `"24h"` | Wait 24 hours |
| `"never"` | Cannot unblock |

### Why use delays?

Research shows cravings fade after 20-30 minutes. The delay:
- Interrupts autopilot behavior
- Creates time for reflection
- Allows cancellation if urge passes

### Can I cancel a pending unblock?

Yes:
```bash
nextdns-blocker pending list     # See pending actions
nextdns-blocker pending cancel ID  # Cancel specific action
```

## Watchdog

### What is the watchdog?

The watchdog:
- Runs sync every 2 minutes
- Restores itself if deleted
- Ensures consistent enforcement

### Why does it restore itself?

To prevent circumvention. If you or something else deletes the sync job, the watchdog recreates it.

### Can I disable it?

Temporarily:
```bash
nextdns-blocker watchdog disable 4  # Disable for 4 hours
```

Permanently:
```bash
nextdns-blocker watchdog uninstall
```

## Troubleshooting

### Domains not blocking

1. Check schedule: Is it outside available hours?
2. Check timezone: Is it correct?
3. Check watchdog: Is it running?
4. Force sync: `nextdns-blocker config push`
5. Flush DNS cache

### "API authentication failed"

Your API key is invalid. Re-run setup:
```bash
nextdns-blocker init
```

### Sites still accessible after blocking

1. Flush DNS cache
2. Clear browser cache
3. Try incognito mode
4. Verify device uses NextDNS

## Privacy & Security

### What data is sent to NextDNS?

Only domain names to add/remove from denylist. No browsing history is sent.

### What data is logged locally?

- Domain blocking events
- Timestamps
- Panic mode usage
- No API credentials

### Is my API key secure?

Yes, if you:
- Keep `.env` file private (0600 permissions)
- Don't commit it to git
- Don't share your configuration

## Compatibility

### Which platforms are supported?

- macOS (Apple Silicon and Intel)
- Linux (all major distributions)
- Windows 10/11
- Docker
- WSL

### Which Python versions work?

Python 3.9 or newer. Recommended: Python 3.11+.

### Does it work with VPNs?

If your VPN routes DNS through NextDNS, yes. If not, blocking may not work when VPN is active.

## Contributing

### How can I contribute?

See [CONTRIBUTING.md](https://github.com/aristeoibarra/nextdns-blocker/blob/main/CONTRIBUTING.md):
- Bug reports and fixes
- Feature suggestions
- Documentation improvements
- Translations

### Where do I report bugs?

[GitHub Issues](https://github.com/aristeoibarra/nextdns-blocker/issues)

Include:
- NextDNS Blocker version
- Platform
- Steps to reproduce
- Relevant logs
