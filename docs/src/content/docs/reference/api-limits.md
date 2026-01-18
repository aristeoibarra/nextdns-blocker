---
title: API & Rate Limiting
description: NextDNS API usage, caching, and rate limiting in NextDNS Blocker
---

NextDNS Blocker interacts with the NextDNS API to manage your denylist and allowlist. This page covers API usage, caching, and rate limiting.

## NextDNS API

### Endpoints Used

| Endpoint | Purpose | Method |
|----------|---------|--------|
| `/profiles/{id}/denylist` | Get denylist | GET |
| `/profiles/{id}/denylist` | Add to denylist | POST |
| `/profiles/{id}/denylist/{domain}` | Remove from denylist | DELETE |
| `/profiles/{id}/allowlist` | Get allowlist | GET |
| `/profiles/{id}/allowlist` | Add to allowlist | POST |
| `/profiles/{id}/allowlist/{domain}` | Remove from allowlist | DELETE |
| `/profiles/{id}/parentalControl` | Get Parental Control settings | GET |
| `/profiles/{id}/parentalControl` | Update Parental Control settings | PATCH |
| `/profiles/{id}/parentalControl/categories/{id}` | Update category | PATCH |
| `/profiles/{id}/parentalControl/services` | Add service | POST |
| `/profiles/{id}/parentalControl/services/{id}` | Update service | PATCH |
| `/profiles/{id}/parentalControl/services/{id}` | Remove service | DELETE |

### Authentication

All requests include the API key header:

```
X-Api-Key: your_api_key
```

### Base URL

```
https://api.nextdns.io
```

## Rate Limiting

### Built-in Rate Limiter

NextDNS Blocker includes a sliding window rate limiter to prevent API abuse.

### Configuration

Set in `.env`:

```bash
RATE_LIMIT_REQUESTS=30   # Max requests per window
RATE_LIMIT_WINDOW=60     # Window in seconds
```

### Default Settings

| Setting | Default | Description |
|---------|---------|-------------|
| `RATE_LIMIT_REQUESTS` | 30 | Max requests per 60 seconds |
| `RATE_LIMIT_WINDOW` | 60 | Window duration in seconds |

### Behavior

When limit is reached:
1. Request is queued
2. Thread waits for window to slide
3. Request proceeds when under limit
4. No error is raised

### Algorithm

Uses sliding window with `time.monotonic()`:
- Unaffected by system clock changes
- Thread-safe using Condition variables
- O(1) time complexity

## Caching

### Denylist Cache

To reduce API calls, the current denylist is cached.

### Configuration

```bash
CACHE_TTL=60  # Cache duration in seconds
```

### Default Settings

| Setting | Default | Range |
|---------|---------|-------|
| `CACHE_TTL` | 60 | 1-3600 seconds |

### Behavior

1. First sync: Fetch denylist from API
2. Cache result with timestamp
3. Subsequent syncs: Use cache if valid
4. Cache expires: Fetch fresh data

### Cache Invalidation

Cache is automatically invalidated:
- After TTL expires
- When domain is added/removed
- On explicit sync with verbose mode

## Request Handling

### Timeout

```bash
API_TIMEOUT=10  # Seconds
```

| Setting | Default | Recommended |
|---------|---------|-------------|
| `API_TIMEOUT` | 10 | 10-30 seconds |

### Retries

```bash
API_RETRIES=3
```

| Setting | Default | Max |
|---------|---------|-----|
| `API_RETRIES` | 3 | 5 |

### Exponential Backoff

Failed requests use exponential backoff:

| Attempt | Wait Time |
|---------|-----------|
| 1 | 1 second |
| 2 | 2 seconds |
| 3 | 4 seconds |
| 4 | 8 seconds |
| 5 | 16 seconds |

With random jitter (0-1 second) to prevent thundering herd.

### Maximum Backoff

Capped at 30 seconds per attempt.

## API Usage Patterns

### Normal Sync

```
1. GET /denylist (cached or fresh)
2. For each domain needing block:
   PUT /denylist/{domain}
3. For each domain needing unblock:
   DELETE /denylist/{domain}
4. Similar for allowlist
```

### Typical API Calls

| Scenario | API Calls |
|----------|-----------|
| No changes needed | 1 (GET denylist, cached) |
| 1 domain block | 2 (GET + PUT) |
| 5 domain changes | 6 (GET + 5 PUT/DELETE) |

### Watchdog Impact

With 2-minute sync interval:
- 30 syncs per hour
- ~720 syncs per day
- Most use cached GET (1 call)

## Error Handling

### API Errors

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 200 | Success | Continue |
| 401 | Unauthorized | Check API key |
| 404 | Not found | Check profile ID |
| 429 | Rate limited | Wait and retry |
| 500+ | Server error | Retry with backoff |

### Handling Rate Limit (429)

If NextDNS returns 429:
1. Wait for `Retry-After` header
2. Or wait 60 seconds
3. Retry request
4. Increment retry counter

### Connection Errors

| Error | Handling |
|-------|----------|
| Timeout | Retry with backoff |
| DNS failure | Retry with backoff |
| Connection refused | Retry with backoff |
| SSL error | Fail (security issue) |

## Monitoring API Usage

### Verbose Mode

```bash
nextdns-blocker config push --verbose
```

Shows:
```
API call: GET /profiles/abc123/denylist
Response: 200 OK (3 domains)
Cache: MISS (fetching fresh data)
```

### Log Analysis

```bash
# Count API calls today
grep "API call" ~/.local/share/nextdns-blocker/logs/app.log | \
  grep "$(date +%Y-%m-%d)" | wc -l
```

## Optimizing API Usage

### Reduce API Calls

1. **Increase cache TTL** for stable configs:
   ```bash
   CACHE_TTL=300  # 5 minutes
   ```

2. **Fewer domains** = fewer potential changes

3. **Stable schedules** = fewer transitions

### Reduce Errors

1. **Validate config** before sync:
   ```bash
   nextdns-blocker config validate
   ```

2. **Test with dry run**:
   ```bash
   nextdns-blocker config push --dry-run
   ```

3. **Check credentials**:
   ```bash
   nextdns-blocker init
   ```

## NextDNS API Limits

### Official Limits

Check NextDNS documentation for current limits. As of 2024:
- Reasonable use expected
- No published hard limits
- Abuse may result in throttling

### Best Practices

1. Don't sync more than every 2 minutes
2. Batch operations when possible
3. Use caching
4. Handle rate limits gracefully

## Troubleshooting

### "Rate limit exceeded"

Internal rate limiting triggered:
- Wait 60 seconds
- Reduce sync frequency
- Increase `RATE_LIMIT_WINDOW`

### "API timeout"

```bash
# Increase timeout
API_TIMEOUT=30
```

### "Connection refused"

1. Check internet connection
2. Check if NextDNS is accessible
3. Try manual curl:
   ```bash
   curl -I https://api.nextdns.io
   ```

### "Authentication failed"

1. Verify API key
2. Check for extra whitespace
3. Regenerate API key if needed
