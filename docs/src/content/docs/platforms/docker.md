---
title: Docker
description: Run NextDNS Blocker in a Docker container
---

Docker provides an isolated, portable way to run NextDNS Blocker without installing Python.

## Quick Start

```bash
# Clone repository
git clone https://github.com/aristeoibarra/nextdns-blocker.git
cd nextdns-blocker

# Copy configuration templates
cp .env.example .env
cp config.json.example config.json

# Edit configuration
nano .env        # Add API credentials
nano config.json # Configure domains

# Start container
docker compose up -d
```

## Configuration

### .env File

```bash
# Required
NEXTDNS_API_KEY=your_api_key_here
NEXTDNS_PROFILE_ID=your_profile_id

# Optional
API_TIMEOUT=10
API_RETRIES=3
```

:::note
Timezone is configured in `config.json` via `settings.timezone`, not via environment variables.
:::

### config.json

Same format as native installation:

```json
{
  "version": "1.0",
  "settings": {
    "timezone": "America/New_York"
  },
  "blocklist": [...],
  "allowlist": [...]
}
```

## docker-compose.yml

```yaml
version: '3.8'

services:
  nextdns-blocker:
    build: .
    container_name: nextdns-blocker
    restart: unless-stopped
    env_file:
      - .env
    volumes:
      - ./config.json:/app/config.json:ro
      - nextdns-data:/app/data

volumes:
  nextdns-data:
```

## Container Operations

### Start

```bash
docker compose up -d
```

### Stop

```bash
docker compose down
```

### View Logs

```bash
# All logs
docker compose logs -f

# Recent logs
docker compose logs --tail 100
```

### Rebuild After Changes

```bash
docker compose up -d --build
```

### Check Status

```bash
docker compose ps
```

## Running Commands

### Via docker compose exec

```bash
# Check status
docker compose exec nextdns-blocker nextdns-blocker status

# Manual sync
docker compose exec nextdns-blocker nextdns-blocker config push -v

# View config
docker compose exec nextdns-blocker nextdns-blocker config show
```

### Via docker run

```bash
docker run --rm \
  --env-file .env \
  -v $(pwd)/config.json:/app/config.json:ro \
  nextdns-blocker nextdns-blocker status
```

## Dockerfile

The provided Dockerfile:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY src/ ./src/
COPY pyproject.toml .

# Install application
RUN pip install --no-cache-dir .

# Create data directory
RUN mkdir -p /app/data

# Set up cron
RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

# Add cron job
RUN echo "*/2 * * * * nextdns-blocker config push >> /app/data/cron.log 2>&1" | crontab -

# Start cron in foreground
CMD ["cron", "-f"]
```

## Data Persistence

### Volumes

The `nextdns-data` volume persists:
- Logs (`/app/data/logs/`)
- Pending actions (`pending.json`)

### Config as Read-Only

Configuration is mounted read-only for safety:

```yaml
volumes:
  - ./config.json:/app/config.json:ro
```

To modify config:
1. Edit locally: `nano config.json`
2. Restart container: `docker compose restart`

## Timezone

Timezone is configured in `config.json`, not via environment variables:

```json
{
  "settings": {
    "timezone": "America/New_York"
  }
}
```

:::caution
The `TZ` and `TIMEZONE` environment variables are no longer supported. Always configure timezone in `config.json` via `settings.timezone`.
:::

## Networking

### DNS Resolution

The container resolves DNS normally. Ensure your Docker network allows external DNS:

```yaml
services:
  nextdns-blocker:
    dns:
      - 1.1.1.1
      - 8.8.8.8
```

### No Port Exposure Needed

NextDNS Blocker only makes outbound API calls. No ports need to be exposed.

## Health Check

Add a health check to docker-compose.yml:

```yaml
services:
  nextdns-blocker:
    healthcheck:
      test: ["CMD", "nextdns-blocker", "status"]
      interval: 5m
      timeout: 10s
      retries: 3
```

## Multiple Profiles

Run multiple instances for different NextDNS profiles:

```yaml
version: '3.8'

services:
  nextdns-work:
    build: .
    env_file: .env.work
    volumes:
      - ./config-work.json:/app/config.json:ro
      - work-data:/app/data

  nextdns-home:
    build: .
    env_file: .env.home
    volumes:
      - ./config-home.json:/app/config.json:ro
      - home-data:/app/data

volumes:
  work-data:
  home-data:
```

## Updating

### Pull Latest

```bash
git pull
docker compose up -d --build
```

### From Registry (if published)

```bash
docker compose pull
docker compose up -d
```

## Troubleshooting

### Container Keeps Restarting

Check logs:
```bash
docker compose logs --tail 50
```

Common causes:
- Invalid credentials
- Malformed config.json
- Missing environment variables

### Sync Not Running

```bash
# Check cron is running
docker compose exec nextdns-blocker ps aux | grep cron

# Check cron log
docker compose exec nextdns-blocker cat /app/data/cron.log

# Run sync manually
docker compose exec nextdns-blocker nextdns-blocker config push -v
```

### Config Changes Not Applied

```bash
# Restart container
docker compose restart

# Or recreate
docker compose up -d --force-recreate
```

### Permission Issues

```bash
# Check file permissions in container
docker compose exec nextdns-blocker ls -la /app/

# Fix volume permissions
docker compose down
sudo chown -R $USER:$USER ./
docker compose up -d
```

## Resource Limits

Add resource limits for production:

```yaml
services:
  nextdns-blocker:
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 128M
        reservations:
          memory: 64M
```

## Logging Configuration

Configure logging driver:

```yaml
services:
  nextdns-blocker:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

## Uninstalling

```bash
# Stop and remove container
docker compose down

# Remove volume (loses data)
docker compose down -v

# Remove image
docker rmi nextdns-blocker

# Remove files
rm -rf config.json .env
```
