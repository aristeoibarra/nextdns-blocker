---
title: validate
description: Validate configuration files before deployment
sidebar:
  order: 2
---

:::caution[Command Moved]
The root `validate` command has been removed. Use `nextdns-blocker config validate` instead.
:::

The `config validate` command checks your configuration files for errors before deployment.

## Usage

```bash
nextdns-blocker config validate [OPTIONS]
```

## Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--config-dir PATH` | Config directory (default: auto-detect) |

## What Gets Validated

| Check | Description |
|-------|-------------|
| JSON syntax | Valid JSON format |
| Required fields | Domain field present |
| Domain format | Valid domain names |
| Schedule format | Valid days and times |
| Time format | HH:MM (24-hour format) |
| Day names | Lowercase weekday names |
| Unblock delay | Valid delay values (0, 30m, 1h, never, etc.) |
| No conflicts | Domain not in both blocklist and allowlist |

## Example Output

### Successful Validation

```bash
$ nextdns-blocker config validate

  ✓ config.json: valid JSON syntax
  ✓ domains configured: 5 domains
  ✓ allowlist entries: 2 entries
  ✓ protected domains: 1 protected
  ✓ domain formats: all valid
  ✓ schedules: 3 schedule(s) valid
  ✓ no conflicts: no denylist/allowlist conflicts

  ✅ Configuration OK
```

### Validation Errors

```bash
$ nextdns-blocker config validate

  ✓ config.json: valid JSON syntax
  ✓ domains configured: 5 domains
  ✗ domain formats: 2 error(s)
  ✗ no conflicts: 1 conflict(s)

  ❌ Configuration has 3 error(s)
    • blocklist[2]: Invalid domain format 'not a domain'
    • blocklist[3]: Invalid time format '25:00' (expected HH:MM)
    • Domain 'example.com' appears in both blocklist and allowlist
```

## JSON Output

For scripting and CI/CD pipelines, use `--json` for machine-readable output:

```bash
nextdns-blocker config validate --json
```

### JSON Response Structure

```json
{
  "valid": true,
  "checks": [
    {"name": "config.json", "passed": true, "detail": "valid JSON syntax"},
    {"name": "domains configured", "passed": true, "detail": "5 domains"},
    {"name": "domain formats", "passed": true, "detail": "all valid"},
    {"name": "no conflicts", "passed": true, "detail": "no denylist/allowlist conflicts"}
  ],
  "errors": [],
  "warnings": [],
  "summary": {
    "domains_count": 5,
    "allowlist_count": 2,
    "protected_count": 1,
    "schedules_count": 3
  }
}
```

### Failed Validation JSON

```json
{
  "valid": false,
  "checks": [
    {"name": "config.json", "passed": true, "detail": "valid JSON syntax"},
    {"name": "domain formats", "passed": false, "detail": "2 error(s)"}
  ],
  "errors": [
    "blocklist[2]: Invalid domain format 'not a domain'",
    "blocklist[3]: Invalid time format '25:00'"
  ],
  "warnings": [],
  "summary": {
    "domains_count": 5,
    "allowlist_count": 0,
    "protected_count": 0,
    "schedules_count": 2
  }
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Configuration is valid |
| 1 | Configuration has errors |

## Common Validation Errors

### Invalid Domain Format

```
blocklist[0]: Invalid domain format 'http://example.com'
```

**Fix:** Remove protocol prefix. Use `example.com` instead of `http://example.com`.

### Invalid Time Format

```
blocklist[1].schedule.monday: Invalid time format '9:00'
```

**Fix:** Use 24-hour format with leading zeros: `09:00` instead of `9:00`.

### Invalid Day Name

```
blocklist[2].schedule: Unknown day name 'Mon'
```

**Fix:** Use full lowercase day names: `monday` instead of `Mon`.

### Denylist/Allowlist Conflict

```
Domain 'example.com' appears in both blocklist and allowlist
```

**Fix:** Remove the domain from one of the lists. A domain cannot be in both.

### Invalid Unblock Delay

```
blocklist[3]: Invalid unblock_delay 'invalid'
```

**Fix:** Use valid formats: `0`, `30m`, `1h`, `4h`, `24h`, `1d`, or `never`.

## CI/CD Integration

### GitHub Actions Example

```yaml
- name: Validate config
  run: |
    nextdns-blocker config validate --json > validation.json
    if [ $? -ne 0 ]; then
      echo "Configuration validation failed"
      cat validation.json
      exit 1
    fi
```

### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

if [ -f "config.json" ]; then
  nextdns-blocker config validate --config-dir . || exit 1
fi
```

## Use Cases

### Before Deployment

Always validate before deploying configuration changes:

```bash
# Edit config
nextdns-blocker config edit

# Validate before sync
nextdns-blocker config validate && nextdns-blocker config push
```

### Automated Testing

```bash
# Run in CI pipeline
nextdns-blocker config validate --json | jq '.valid'
```

### Debugging Issues

When sync isn't working as expected:

```bash
# Check config first
nextdns-blocker config validate

# Then check health
nextdns-blocker health
```

## Related

- [config](/commands/config/) - Parent command group
- [config.json Reference](/configuration/config-json/) - Configuration file format
- [Schedules](/configuration/schedules/) - Schedule format documentation
