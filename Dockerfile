# NextDNS Blocker - Docker Image
# Lightweight Python Alpine image for minimal footprint

FROM python:3.11-alpine

# Labels
LABEL maintainer="aristeoibarra"
LABEL description="NextDNS Domain Blocker with scheduling support"
LABEL version="5.0.0"

# Set working directory
WORKDIR /app

# Copy package files for installation
COPY pyproject.toml .
COPY README.md .
COPY nextdns_blocker.py .
COPY common.py .
COPY watchdog.py .

# Install package (uses pyproject.toml)
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN adduser -D -u 1000 blocker && \
    mkdir -p /home/blocker/.local/share/nextdns-audit/logs && \
    chown -R blocker:blocker /app /home/blocker

# Switch to non-root user
USER blocker

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=5m --timeout=10s --start-period=30s --retries=3 \
    CMD python nextdns_blocker.py health || exit 1

# Default command: run sync with verbose output
CMD ["python", "nextdns_blocker.py", "sync", "-v"]
