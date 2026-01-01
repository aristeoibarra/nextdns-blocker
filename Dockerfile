# NextDNS Blocker - Docker Image
# Lightweight Python Alpine image for minimal footprint

FROM python:3.14-alpine

# Labels
LABEL maintainer="aristeoibarra"
LABEL description="NextDNS Domain Blocker with scheduling support"
LABEL version="6.5.1"

# Set working directory
WORKDIR /app

# Copy package files for installation
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install package
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN adduser -D -u 1000 blocker && \
    mkdir -p /home/blocker/.config/nextdns-blocker \
             /home/blocker/.local/share/nextdns-blocker/logs && \
    chown -R blocker:blocker /app /home/blocker

# Switch to non-root user
USER blocker

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check using installed CLI
HEALTHCHECK --interval=5m --timeout=30s --start-period=30s --retries=3 \
    CMD nextdns-blocker health || exit 1

# Default command: run sync with verbose output
CMD ["nextdns-blocker", "sync", "-v"]
