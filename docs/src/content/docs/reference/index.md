---
title: Reference Overview
description: Technical reference documentation for NextDNS Blocker
---

This section provides technical reference information for advanced users and developers.

## Reference Topics

### [File Locations](/reference/file-locations/)
Where NextDNS Blocker stores configuration, data, and logs across platforms.

### [Log Files](/reference/log-files/)
Understanding log files, their contents, and rotation.

### [Exit Codes](/reference/exit-codes/)
CLI exit codes for scripting and automation.

### [Security](/reference/security/)
Security features, file permissions, and best practices.

### [API & Rate Limiting](/reference/api-limits/)
NextDNS API usage, caching, and rate limiting.

## Quick Reference

### Version

```bash
nextdns-blocker --version
```

### Help

```bash
nextdns-blocker --help
nextdns-blocker <command> --help
```

### Configuration Paths

| Platform | Config | Data |
|----------|--------|------|
| macOS/Linux | `~/.config/nextdns-blocker/` | `~/.local/share/nextdns-blocker/` |
| Windows | `%APPDATA%\nextdns-blocker\` | `%LOCALAPPDATA%\nextdns-blocker\` |

### Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `NEXTDNS_API_KEY` | Yes | - |
| `NEXTDNS_PROFILE_ID` | Yes | - |
| `API_TIMEOUT` | No | 10 |
| `API_RETRIES` | No | 3 |
| `CACHE_TTL` | No | 60 |
| `RATE_LIMIT_REQUESTS` | No | 30 |
| `RATE_LIMIT_WINDOW` | No | 60 |

### Command Quick Reference

| Command | Description |
|---------|-------------|
| `config push` | Synchronize domain states |
| `status` | Show current status |
| `unblock DOMAIN` | Request unblock |
| `allow DOMAIN` | Add to allowlist |
| `disallow DOMAIN` | Remove from allowlist |
| `config show` | Show configuration |
| `config edit` | Edit configuration |
| `config validate` | Validate configuration |
| `config set KEY VAL` | Set config value |
| `watchdog status` | Check watchdog |
| `watchdog install` | Install watchdog |
| `watchdog uninstall` | Remove watchdog |
| `panic DURATION` | Activate panic mode |
| `panic status` | Check panic mode |
| `pending list` | List pending actions |
| `pending cancel ID` | Cancel pending action |
| `update` | Check for updates |
| `completion SHELL` | Generate completions |
