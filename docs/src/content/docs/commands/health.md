---
title: health
description: Perform system health checks to verify NextDNS Blocker is working correctly
---

The `health` command runs diagnostic checks to verify that NextDNS Blocker is properly configured and can communicate with the NextDNS API.

## Usage

```bash
nextdns-blocker health [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--config-dir` | Config directory (default: auto-detect) |
| `--help` | Show help message |

## What It Checks

The health command performs four critical checks:

### 1. Configuration Loading

Verifies that:
- `.env` file exists and is readable
- Required environment variables are set (`NEXTDNS_API_KEY`, `NEXTDNS_PROFILE_ID`)
- Configuration values are valid

### 2. Domains Loading

Verifies that:
- `config.json` file exists and is valid JSON
- Domain entries are properly formatted
- Schedules are syntactically correct

### 3. API Connectivity

Verifies that:
- API key is valid
- Profile ID exists
- NextDNS API is reachable
- Current denylist can be fetched

### 4. Log Directory

Verifies that:
- Log directory exists or can be created
- Directory is writable
- Audit log can be accessed

## Examples

### Basic Health Check

```bash
nextdns-blocker health
```

Output (healthy system):
```
  Health Check
  ------------
  [✓] Configuration loaded
  [✓] Domains loaded (5 domains, 2 allowlist)
  [✓] API connectivity (12 items in denylist)
  [✓] Log directory: /Users/you/.local/share/nextdns-blocker/logs

  Result: 4/4 checks passed
  Status: HEALTHY
```

### Failing Health Check

```bash
nextdns-blocker health
```

Output (issues detected):
```
  Health Check
  ------------
  [✓] Configuration loaded
  [✓] Domains loaded (5 domains, 2 allowlist)
  [✗] API connectivity failed

  Result: 2/4 checks passed
  Status: DEGRADED
```

### Custom Config Directory

```bash
nextdns-blocker health --config-dir /path/to/config
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All checks passed (HEALTHY) |
| 1 | One or more checks failed (DEGRADED) |

## When to Use

Run `health` when:

- **After installation** - Verify setup is correct
- **After configuration changes** - Ensure changes are valid
- **When sync fails** - Diagnose connection issues
- **Before troubleshooting** - Quick system status overview
- **In automation** - Verify system is operational

## Troubleshooting

### Configuration failed

```
[✗] Configuration: Missing required environment variable: NEXTDNS_API_KEY
```

**Solution**: Run `nextdns-blocker init` to set up configuration.

### Domains failed

```
[✗] Domains: Invalid JSON in config.json
```

**Solution**:
1. Validate your config: `nextdns-blocker config validate`
2. Fix syntax errors in `config.json`

### API connectivity failed

```
[✗] API connectivity failed
```

**Solutions**:
1. Check internet connection
2. Verify API key is correct
3. Verify profile ID exists
4. Check NextDNS service status

### Log directory failed

```
[✗] Log directory: Permission denied
```

**Solution**: Check permissions on the data directory or run with appropriate user.

## Integration with Other Commands

Use `health` as part of a diagnostic workflow:

```bash
# Quick system check
nextdns-blocker health

# If healthy, run sync
nextdns-blocker sync

# If degraded, run fix
nextdns-blocker fix
```

## Scripting

Use in scripts to verify system before operations:

```bash
#!/bin/bash
if nextdns-blocker health > /dev/null 2>&1; then
    echo "System healthy, proceeding..."
    nextdns-blocker sync
else
    echo "System degraded, please check configuration"
    exit 1
fi
```
