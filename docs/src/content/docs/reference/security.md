---
title: Security
description: Security features and best practices for NextDNS Blocker
---

NextDNS Blocker is designed with security in mind, protecting your credentials and ensuring safe operation.

## Credential Security

### API Key Storage

API credentials are stored in `.env` with restricted permissions:

```bash
# File permissions (Unix)
chmod 600 ~/.config/nextdns-blocker/.env
# Result: -rw------- (owner read/write only)
```

### Never Commit Credentials

`.gitignore` patterns prevent accidental commits:

```gitignore
.env
*.env
.env.*
```

### Environment Variable Override

Credentials can be provided via environment for CI/CD:

```bash
export NEXTDNS_API_KEY=your_key
export NEXTDNS_PROFILE_ID=your_id
nextdns-blocker config sync
```

## File Permissions

### Unix (macOS/Linux)

| File | Permissions | Description |
|------|-------------|-------------|
| `.env` | `0600` | Owner read/write |
| `config.json` | `0600` | Owner read/write |
| `pending.json` | `0600` | Owner read/write |
| `*.log` | `0644` | Owner write, world read |

### Secure File Creation

Files are created with restrictive permissions by default using `write_secure_file()`:

```python
# Internal implementation
os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
```

### Windows

Windows uses ACLs. Files are created with user-only access by default.

## Input Validation

### Domain Validation

Before API calls, domains are validated:

- No empty strings
- Valid domain format (alphanumeric, hyphens, dots)
- Maximum length check
- No path components

```python
# Valid
"reddit.com"
"api.example.co.uk"

# Invalid (rejected)
"https://reddit.com"  # No protocol
""                     # Empty
"../etc/passwd"        # Path traversal attempt
```

### Credential Validation

API credentials are validated against patterns:

| Credential | Pattern | Minimum Length |
|------------|---------|----------------|
| API Key | Alphanumeric | 8 characters |
| Profile ID | Alphanumeric | 4 characters |
| Webhook URL | Strict URL format | - |

### Schedule Validation

Schedule entries are validated:

- Days: Lowercase weekday names only
- Times: `HH:MM` format (00:00-23:59)
- Required fields: Both `start` and `end`

## API Security

### HTTPS Only

All API communication uses HTTPS:

```
https://api.nextdns.io/...
```

No HTTP fallback is allowed.

### Request Authentication

API key is sent via header, not query string:

```
X-Api-Key: your_api_key
```

This prevents key leakage in logs.

### Rate Limiting

Built-in rate limiting prevents API abuse:

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_REQUESTS` | 30 | Max requests per window |
| `RATE_LIMIT_WINDOW` | 60s | Time window |

Uses sliding window algorithm for accurate limiting.

## Audit Logging

### What's Logged

All security-relevant actions:

| Event | Logged |
|-------|--------|
| Domain blocked | Yes |
| Domain unblocked | Yes |
| Panic mode start/end | Yes |
| Pending action created | Yes |
| Pending action cancelled | Yes |
| Configuration changes | Yes |

### Log Format

```
2024-01-15 14:30:00 BLOCK reddit.com reason="outside schedule"
2024-01-15 20:00:00 PANIC_START duration=60
```

### Log Protection

Audit logs use append-only writes with file locking to prevent tampering during concurrent access.

## PIN Protection

NextDNS Blocker includes optional PIN protection for sensitive commands, adding an authentication layer against impulsive behavior.

### Protected Commands

When PIN is enabled, these commands require verification:
- `unblock` - Remove domain from denylist
- `pause` - Pause all blocking
- `allow` - Add domain to allowlist
- `config edit` - Edit configuration
- `config pull` - Pull remote config

### PIN Features

| Feature | Default | Description |
|---------|---------|-------------|
| Minimum length | 4 characters | PIN must be 4+ characters |
| Maximum length | 32 characters | Upper limit for PIN |
| Session duration | 30 minutes | Valid session after verification |
| Max attempts | 3 | Attempts before lockout |
| Lockout duration | 15 minutes | Cooldown after max attempts |
| Removal delay | 24 hours | Waiting period to remove PIN |

### PIN Commands

```bash
# Enable PIN
nextdns-blocker protection pin set

# Check PIN status
nextdns-blocker protection pin status

# Verify PIN and start session
nextdns-blocker protection pin verify

# Remove PIN (creates pending action with 24h delay)
nextdns-blocker protection pin remove
```

### Security Properties

1. **PBKDF2-SHA256**: PIN is hashed with 600,000 iterations (OWASP recommendation)
2. **Random salt**: Unique salt per installation prevents rainbow table attacks
3. **Secure storage**: Hash stored with `0600` permissions
4. **Brute force protection**: Lockout after failed attempts
5. **Session-based**: One verification covers multiple commands for 30 minutes
6. **Delayed removal**: 24-hour delay prevents impulsive disabling

### Configuration

PIN data is stored separately from config:

| File | Contents |
|------|----------|
| `.pin_hash` | Salt and hash (never contains plaintext) |
| `.pin_session` | Session expiration timestamp |
| `.pin_attempts` | Failed attempt timestamps |

## Panic Mode Security

### Cannot Be Cancelled

Panic mode intentionally cannot be disabled early:
- Prevents bypass during weak moments
- Timer must expire

### Hidden Commands

During panic:
- `unblock` is hidden
- `pause` is hidden
- `allow` is hidden
- Commands cannot be run directly

### PIN During Panic

When both panic mode and PIN are active:
- Panic mode takes priority
- Commands are completely hidden (not just PIN-protected)
- No authentication prompt is shown

### Allowlist Sync Disabled

Scheduled allowlist sync is completely skipped during panic to prevent security bypasses.

## File Locking

### Concurrent Access Protection

State files use file locking:

| Platform | Mechanism |
|----------|-----------|
| Unix | `fcntl.flock()` |
| Windows | `msvcrt.locking()` |

Prevents corruption from:
- Multiple sync processes
- Watchdog and manual operations
- Race conditions

### Atomic Writes

Configuration changes use atomic write pattern:
1. Write to temporary file
2. Sync to disk
3. Rename to target

## Best Practices

### Credential Management

1. Never share `.env` file
2. Use unique API key for this tool
3. Rotate API key if compromised
4. Don't commit credentials to version control

### Configuration Security

1. Review config changes before applying
2. Use `config validate` before sync
3. Keep backups of working configuration

### System Security

1. Keep Python updated
2. Keep nextdns-blocker updated
3. Monitor audit logs regularly
4. Use panic mode when needed

### Network Security

1. Ensure DNS goes through NextDNS
2. Block VPN/proxy if needed (in NextDNS)
3. Verify HTTPS in all API calls

## Threat Model

### Protected Against

| Threat | Protection |
|--------|------------|
| Credential theft | File permissions, no logging of keys |
| API abuse | Rate limiting |
| Config tampering | File permissions |
| Panic bypass | Command hiding, no cancellation |
| Race conditions | File locking |

### Not Protected Against

| Threat | Reason |
|--------|--------|
| Root/admin access | Can read any file |
| Physical access | Can modify files offline |
| Keylogger | External to application |
| Browser cache | External to DNS blocking |

## Reporting Vulnerabilities

If you discover a security issue:

1. **Do not** open a public issue
2. Email security concerns privately
3. Include reproduction steps
4. Allow time for fix before disclosure

See [SECURITY.md](https://github.com/aristeoibarra/nextdns-blocker/blob/main/SECURITY.md) for details.
