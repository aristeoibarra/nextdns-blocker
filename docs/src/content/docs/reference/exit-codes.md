---
title: Exit Codes
description: CLI exit codes for scripting and automation
---

NextDNS Blocker uses standard exit codes to indicate success or failure, enabling scripting and automation.

## Exit Code Summary

| Code | Name | Description |
|------|------|-------------|
| 0 | Success | Command completed successfully |
| 1 | General Error | Unspecified error |
| 2 | Configuration Error | Invalid or missing configuration |
| 3 | API Error | NextDNS API communication failed |
| 4 | Validation Error | Input validation failed |
| 5 | Permission Error | Insufficient permissions |
| 130 | Interrupted | User interrupted (Ctrl+C) |

## Detailed Descriptions

### 0 - Success

Command completed without errors.

```bash
nextdns-blocker sync
echo $?  # Returns: 0
```

### 1 - General Error

An unspecified error occurred.

Common causes:
- Unexpected exception
- Unknown command
- Missing required argument

```bash
nextdns-blocker unknown-command
echo $?  # Returns: 1
```

### 2 - Configuration Error

Configuration file is invalid or missing.

Common causes:
- `config.json` syntax error
- Missing required fields
- `.env` file not found
- Missing API credentials

```bash
# With invalid config
nextdns-blocker sync
echo $?  # Returns: 2
```

### 3 - API Error

Communication with NextDNS API failed.

Common causes:
- Invalid API key
- Invalid profile ID
- Network timeout
- Rate limit exceeded
- NextDNS service unavailable

```bash
# With wrong API key
nextdns-blocker sync
echo $?  # Returns: 3
```

### 4 - Validation Error

Input validation failed.

Common causes:
- Invalid domain format
- Invalid time format
- Unknown day name
- Invalid duration format

```bash
# With invalid domain
nextdns-blocker unblock "not a domain"
echo $?  # Returns: 4
```

### 5 - Permission Error

Insufficient file permissions.

Common causes:
- Cannot read configuration
- Cannot write state files
- Cannot access log directory

```bash
# With read-only config
chmod 000 ~/.config/nextdns-blocker/config.json
nextdns-blocker sync
echo $?  # Returns: 5
```

### 130 - Interrupted

User pressed Ctrl+C during execution.

```bash
nextdns-blocker sync  # Press Ctrl+C
echo $?  # Returns: 130
```

## Using Exit Codes

### In Shell Scripts

```bash
#!/bin/bash

nextdns-blocker sync
exit_code=$?

case $exit_code in
    0)
        echo "Sync successful"
        ;;
    2)
        echo "Configuration error - check config.json"
        exit 1
        ;;
    3)
        echo "API error - check credentials"
        exit 1
        ;;
    *)
        echo "Unknown error: $exit_code"
        exit 1
        ;;
esac
```

### Conditional Execution

```bash
# Only proceed if sync succeeds
nextdns-blocker sync && echo "Sync complete"

# Handle failure
nextdns-blocker sync || echo "Sync failed"
```

### In CI/CD

```yaml
# GitHub Actions example
- name: Sync domains
  run: nextdns-blocker sync
  continue-on-error: false  # Fail job on non-zero exit
```

### In Cron

```bash
# Log exit code
*/2 * * * * nextdns-blocker sync; echo "Exit: $?" >> /tmp/sync.log
```

## Command-Specific Behavior

### sync

| Scenario | Exit Code |
|----------|-----------|
| All domains synced | 0 |
| Configuration invalid | 2 |
| API connection failed | 3 |
| Partial success (some domains) | 0 |

### config validate

| Scenario | Exit Code |
|----------|-----------|
| Configuration valid | 0 |
| JSON syntax error | 2 |
| Invalid field values | 2 |
| File not found | 2 |

### unblock

| Scenario | Exit Code |
|----------|-----------|
| Unblock successful | 0 |
| Pending action created | 0 |
| Domain not in blocklist | 1 |
| Protected domain | 1 |
| Panic mode active | 1 |

### panic

| Scenario | Exit Code |
|----------|-----------|
| Panic activated | 0 |
| Duration too short | 4 |
| Already in panic | 1 |

### watchdog install

| Scenario | Exit Code |
|----------|-----------|
| Jobs installed | 0 |
| Permission denied | 5 |
| Already installed | 0 |

## Scripting Examples

### Health Check

```bash
#!/bin/bash
# health-check.sh

if nextdns-blocker status > /dev/null 2>&1; then
    echo "OK"
    exit 0
else
    echo "FAIL"
    exit 1
fi
```

### Retry on Failure

```bash
#!/bin/bash
# sync-with-retry.sh

max_attempts=3
attempt=1

while [ $attempt -le $max_attempts ]; do
    nextdns-blocker sync
    if [ $? -eq 0 ]; then
        exit 0
    fi
    echo "Attempt $attempt failed, retrying..."
    attempt=$((attempt + 1))
    sleep 10
done

echo "All attempts failed"
exit 1
```

### Notification on Error

```bash
#!/bin/bash
# sync-notify.sh

nextdns-blocker sync
exit_code=$?

if [ $exit_code -ne 0 ]; then
    # Send notification (example with curl to webhook)
    curl -X POST -H "Content-Type: application/json" \
        -d "{\"text\": \"NextDNS Blocker sync failed with code $exit_code\"}" \
        "$NOTIFICATION_WEBHOOK"
fi

exit $exit_code
```
