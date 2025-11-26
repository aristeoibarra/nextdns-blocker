#!/bin/bash
# NextDNS Blocker - Install

set -e

AUDIT_DIR="$HOME/.local/share/nextdns-audit/logs"

echo ""
echo "  nextdns-blocker install"
echo "  -----------------------"
echo ""

# Ask for install directory
DEFAULT_DIR="$(cd "$(dirname "$0")" && pwd)"
read -p "  install path [$DEFAULT_DIR]: " INSTALL_DIR
INSTALL_DIR="${INSTALL_DIR:-$DEFAULT_DIR}"
echo ""

# Check Python 3
echo "  [1/9] python3"
if ! command -v python3 &> /dev/null; then
    sudo yum install -y python3 || sudo apt-get install -y python3
fi

# Check pip
echo "  [2/9] pip"
if ! command -v pip3 &> /dev/null; then
    sudo yum install -y python3-pip || sudo apt-get install -y python3-pip
fi

# Verify directory
echo "  [3/9] directory"
if [ ! -d "$INSTALL_DIR" ]; then
    echo "  error: $INSTALL_DIR not found"
    exit 1
fi
cd "$INSTALL_DIR"

# Install dependencies
echo "  [4/9] dependencies"
pip3 install -r requirements.txt --user --quiet
pip3 install nuitka --user --quiet

# Install gcc if needed
echo "  [5/9] compiler"
if ! command -v gcc &> /dev/null; then
    sudo yum install -y gcc || sudo apt-get install -y gcc
fi

# Verify config files
echo "  [6/10] config"
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo "  error: .env not found"
    exit 1
fi
if [ ! -f "$INSTALL_DIR/domains.json" ]; then
    echo "  error: domains.json not found"
    exit 1
fi

# Validate API credentials
echo "  [7/10] validating API"
source "$INSTALL_DIR/.env"
if [ -z "$NEXTDNS_API_KEY" ] || [ -z "$NEXTDNS_PROFILE_ID" ]; then
    echo "  error: NEXTDNS_API_KEY or NEXTDNS_PROFILE_ID not set in .env"
    exit 1
fi

API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "X-Api-Key: $NEXTDNS_API_KEY" \
    "https://api.nextdns.io/profiles/$NEXTDNS_PROFILE_ID")

if [ "$API_RESPONSE" != "200" ]; then
    echo "  error: API validation failed (HTTP $API_RESPONSE)"
    echo "         Check your API key and profile ID"
    exit 1
fi
echo "         credentials valid"

# Create audit directory
echo "  [8/10] directories"
mkdir -p "$AUDIT_DIR"

# Compile to binary
echo "  [9/10] compiling"
echo "         blocker..."
python3 -m nuitka --onefile --quiet --output-filename=blocker.bin nextdns_blocker.py 2>/dev/null || \
python3 -m nuitka --onefile --output-filename=blocker.bin nextdns_blocker.py

echo "         watchdog..."
python3 -m nuitka --onefile --quiet --output-filename=watchdog.bin watchdog.py 2>/dev/null || \
python3 -m nuitka --onefile --output-filename=watchdog.bin watchdog.py

chmod +x blocker.bin watchdog.bin

# Remove source files
rm -f nextdns_blocker.py watchdog.py
rm -rf nextdns_blocker.build nextdns_blocker.dist nextdns_blocker.onefile-build
rm -rf watchdog.build watchdog.dist watchdog.onefile-build
rm -f *.spec 2>/dev/null || true

# Setup cron jobs
echo "  [10/10] cron"

CRON_SYNC="*/2 * * * * cd $INSTALL_DIR && ./blocker.bin sync >> $AUDIT_DIR/cron.log 2>&1"
CRON_WD="* * * * * cd $INSTALL_DIR && ./watchdog.bin check >> $AUDIT_DIR/wd.log 2>&1"

crontab -l 2>/dev/null | grep -v "blocker" | grep -v "watchdog" | grep -v "nextdns" | crontab - 2>/dev/null || true
(crontab -l 2>/dev/null; echo "$CRON_SYNC"; echo "$CRON_WD") | crontab -

# Run initial sync
echo ""
echo "  syncing..."
./blocker.bin sync || true

# Done
echo ""
echo "  done"
echo ""
echo "  files"
echo "    blocker.bin    main binary"
echo "    watchdog.bin   cron protector"
echo "    domains.json   schedule config"
echo "    .env           credentials"
echo ""
echo "  schedule"
echo "    sync           every 2 min"
echo "    watchdog       every 1 min"
echo ""
echo "  commands"
echo "    ./blocker.bin status"
echo "    ./blocker.bin sync"
echo "    ./watchdog.bin status"
echo ""
