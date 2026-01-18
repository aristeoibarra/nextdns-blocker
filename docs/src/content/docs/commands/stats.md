---
title: stats
description: Show usage statistics and patterns from the audit log
---

The `stats` command group provides comprehensive analytics by parsing the audit log, showing blocking patterns, effectiveness scores, and domain-level statistics.

## Usage

```bash
nextdns-blocker stats [OPTIONS]
nextdns-blocker stats SUBCOMMAND [ARGS]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days N` | 7 | Number of days to analyze |
| `--domain NAME` | - | Filter statistics by domain |

## Subcommands

| Subcommand | Description |
|------------|-------------|
| (none) | Show summary statistics |
| `domains` | Show top blocked domains with details |
| `hours` | Show detailed hourly activity patterns |
| `actions` | Show breakdown of all action types |
| `export` | Export statistics to CSV file |

## Summary View (Default)

```bash
nextdns-blocker stats
```

Output:
```
NextDNS Blocker Statistics (last 7 days)

  Summary
    Total entries: 2178
    Unique domains: 45
    Date range: 2024-01-08 to 2024-01-15

  Actions
    Blocks: 245
    Unblocks: 42
    Allows: 18
    Disallows: 5
    Pauses: 12
    Resumes: 12
    Panic activations: 3

  Effectiveness Score: 83%
    (blocks maintained / total blocks)

  Top Blocked Domains
    1. reddit.com            ████████████ 89
    2. twitter.com           ████████     52
    3. youtube.com           ██████       38
    4. instagram.com         █████        31
    5. tiktok.com            ████         25

  Activity by Hour
    00-06: ████     (low)
    06-12: ██████   (medium)
    12-18: ████████ (high)
    18-24: ██████████ (peak)
```

### With Date Filter

```bash
nextdns-blocker stats --days 30
```

### With Domain Filter

```bash
nextdns-blocker stats --domain reddit.com
```

Output:
```
Statistics for reddit.com (last 7 days)

  Activity
    Blocks: 89
    Unblocks: 12
    Allows: 0
    Disallows: 0

  Pending Actions
    Created: 5
    Cancelled: 3
    Executed: 2

  Last blocked: 2024-01-15 10:30
  Last unblocked: 2024-01-14 19:45

  Effectiveness Score: 87%
```

## stats domains

Show top blocked domains with detailed statistics.

```bash
nextdns-blocker stats domains [--limit N]
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--limit N` | 10 | Number of domains to show |

### Example

```bash
nextdns-blocker stats domains --limit 20
```

Output:
```
Top 20 Blocked Domains (last 7 days)

#   Domain               Blocks  Unblocks  Effectiveness
────────────────────────────────────────────────────────
1   reddit.com           89      12        87%
2   twitter.com          52      8         85%
3   youtube.com          38      15        61%
4   instagram.com        31      2         94%
5   tiktok.com           25      0         100%
...
```

## stats hours

Show detailed hourly activity patterns.

```bash
nextdns-blocker stats hours
```

Output:
```
Hourly Activity (last 7 days)

00:00 ██                        B:2 U:0
01:00 █                         B:1 U:0
02:00                           B:0 U:0
...
09:00 ████████                  B:15 U:3
10:00 ██████████████            B:28 U:5
...
22:00 ████████████████████████  B:45 U:8
23:00 ██████████████            B:25 U:2
```

## stats actions

Show breakdown of all action types.

```bash
nextdns-blocker stats actions
```

Output:
```
Action Breakdown (last 7 days)

Action              Count
────────────────────────────────
BLOCK               245   ████████████████████
SYNC                1847  ██████████████████████████████
UNBLOCK             42    ████
ALLOW               18    ██
PANIC_ACTIVATE      3
PENDING_CREATE      8     █
PENDING_CANCEL      3
PENDING_EXECUTE     5

Total entries: 2195
```

## stats export

Export statistics to CSV format for external analysis.

```bash
nextdns-blocker stats export -o FILE
```

### Options

| Option | Required | Description |
|--------|----------|-------------|
| `-o, --output FILE` | Yes | Output CSV file path |

### Example

```bash
nextdns-blocker stats export -o ~/stats.csv
nextdns-blocker stats --days 30 export -o monthly.csv
```

CSV format:
```csv
timestamp,action,domain,prefix
2024-01-15T10:30:00,BLOCK,reddit.com,
2024-01-15T10:35:00,WD,RESTORE,
2024-01-15T11:00:00,UNBLOCK,reddit.com,
```

## Effectiveness Score

The effectiveness score measures how well blocking is maintained:

```
Score = (blocks - unblocks) / blocks * 100
```

| Score | Interpretation |
|-------|----------------|
| 90-100% | Excellent - Very few bypasses |
| 70-89% | Good - Some bypasses but mostly effective |
| 50-69% | Fair - Consider adjusting schedules |
| <50% | Poor - Blocking may be too restrictive |

## Action Types

| Action | Description |
|--------|-------------|
| `BLOCK` | Domain was added to denylist |
| `UNBLOCK` | Domain was removed from denylist |
| `ALLOW` | Domain was added to allowlist |
| `DISALLOW` | Domain was removed from allowlist |
| `PANIC_ACTIVATE` | Panic mode was activated |
| `PENDING_CREATE` | Pending action was created |
| `PENDING_CANCEL` | Pending action was cancelled |
| `PENDING_EXECUTE` | Pending action was executed |
| `PC_ACTIVATE` | Parental Control category/service activated |

## Audit Log Location

Statistics are derived from the audit log at:

- **macOS/Linux**: `~/.local/share/nextdns-blocker/logs/audit.log`
- **Windows**: `%LOCALAPPDATA%\nextdns-blocker\logs\audit.log`

## Audit Log Format

Each line in the audit log follows this format:

```
2024-01-15T14:30:00 | ACTION | details
```

For watchdog entries:

```
2024-01-15T14:30:00 | WD | ACTION | details
```

## No Audit Log

If no audit log exists:

```bash
nextdns-blocker stats
```

Output:
```
  No activity recorded in the last 7 days
```

This happens when:
- Fresh installation (no actions yet)
- Audit log was deleted
- Data directory doesn't exist

## Privacy

The audit log contains:
- Timestamps of actions
- Action types
- Domain names (for block/unblock)

It does NOT contain:
- Browsing history
- DNS queries
- Personal information

## Clearing Statistics

To reset statistics, delete the audit log:

```bash
rm ~/.local/share/nextdns-blocker/logs/audit.log
```

Or uninstall and reinstall:

```bash
nextdns-blocker uninstall
nextdns-blocker init
```

## Scripting

Use JSON output for automation:

```bash
# Export to CSV and process
nextdns-blocker stats export -o /tmp/stats.csv
cat /tmp/stats.csv | wc -l
```

## Related

- [Log Files Reference](/reference/log-files/) - Audit log details
- [health](/commands/health/) - System health checks
