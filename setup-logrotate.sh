#!/bin/bash
# Setup log rotation for nextdns-blocker

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="$HOME/.local/share/nextdns-audit/logs"
LOGROTATE_CONF="/etc/logrotate.d/nextdns-blocker"

echo ""
echo "  nextdns-blocker log rotation setup"
echo "  -----------------------------------"
echo ""

# Check if logrotate is installed
if ! command -v logrotate &> /dev/null; then
    echo "  [!] logrotate not found, installing..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y logrotate
    elif command -v yum &> /dev/null; then
        sudo yum install -y logrotate
    elif command -v brew &> /dev/null; then
        brew install logrotate
    else
        echo "  error: could not install logrotate"
        exit 1
    fi
fi

# Expand ~ in the config file for the current user
EXPANDED_CONF=$(mktemp)
sed "s|~|$HOME|g" "$SCRIPT_DIR/logrotate.conf" > "$EXPANDED_CONF"

# Install logrotate config
echo "  [1/2] installing logrotate config"
sudo cp "$EXPANDED_CONF" "$LOGROTATE_CONF"
sudo chmod 644 "$LOGROTATE_CONF"
rm "$EXPANDED_CONF"

# Test the configuration
echo "  [2/2] testing configuration"
if sudo logrotate -d "$LOGROTATE_CONF" 2>&1 | grep -q "error"; then
    echo "  error: logrotate configuration has errors"
    exit 1
fi

echo ""
echo "  done"
echo ""
echo "  config: $LOGROTATE_CONF"
echo "  logs:   $LOG_DIR"
echo ""
echo "  rotation schedule:"
echo "    app.log    daily,  7 days retention"
echo "    audit.log  weekly, 12 weeks retention"
echo "    cron.log   daily,  7 days retention"
echo "    wd.log     daily,  7 days retention"
echo ""
echo "  test with: sudo logrotate -d $LOGROTATE_CONF"
echo "  force run: sudo logrotate -f $LOGROTATE_CONF"
echo ""
