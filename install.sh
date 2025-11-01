#!/bin/bash
# NextDNS Blocker - Installation Script for EC2

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="$HOME/nextdns-blocker"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  NextDNS Blocker - Installation${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python 3
echo -e "${YELLOW}[1/7]${NC} Checking Python 3..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found${NC}"
    echo "Installing Python 3..."
    sudo yum install -y python3 || sudo apt-get install -y python3
fi

PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓${NC} $PYTHON_VERSION installed"
echo ""

# Check pip
echo -e "${YELLOW}[2/7]${NC} Checking pip..."
if ! command -v pip3 &> /dev/null; then
    echo "Installing pip..."
    sudo yum install -y python3-pip || sudo apt-get install -y python3-pip
fi
echo -e "${GREEN}✓${NC} pip installed"
echo ""

# Verify directory
echo -e "${YELLOW}[3/7]${NC} Setting up installation directory..."
cd "$HOME"
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "${RED}❌ Directory $INSTALL_DIR not found${NC}"
    echo "Please upload files to $INSTALL_DIR first"
    exit 1
fi
cd "$INSTALL_DIR"
echo -e "${GREEN}✓${NC} Directory configured: $INSTALL_DIR"
echo ""

# Install dependencies
echo -e "${YELLOW}[4/7]${NC} Installing Python dependencies..."
pip3 install -r requirements.txt --user
echo -e "${GREEN}✓${NC} Dependencies installed"
echo ""

# Set permissions
echo -e "${YELLOW}[5/7]${NC} Setting permissions..."
chmod +x nextdns_blocker.py
echo -e "${GREEN}✓${NC} Permissions set"
echo ""

# Verify .env file
echo -e "${YELLOW}[6/7]${NC} Verifying configuration..."
if [ ! -f "$INSTALL_DIR/.env" ]; then
    echo -e "${RED}❌ .env file not found${NC}"
    echo ""
    echo "Please create .env file:"
    echo "  1. Copy template: cp .env.example .env"
    echo "  2. Edit file: nano .env"
    echo "  3. Add your NEXTDNS_API_KEY and NEXTDNS_PROFILE_ID"
    echo "  4. Run this script again"
    exit 1
fi

if grep -q "tu_api_key_aqui\|your_api_key_here" .env; then
    echo -e "${RED}❌ .env not configured correctly${NC}"
    echo "Please edit .env and add your real API key"
    exit 1
fi

echo -e "${GREEN}✓${NC} Configuration valid"
echo ""

# Setup cron jobs
echo -e "${YELLOW}[7/7]${NC} Setting up cron jobs..."

source .env
UNLOCK_HOUR=${UNLOCK_HOUR:-18}
LOCK_HOUR=${LOCK_HOUR:-22}

CRON_UNLOCK="0 $UNLOCK_HOUR * * * cd $INSTALL_DIR && /usr/bin/python3 nextdns_blocker.py unblock >> $INSTALL_DIR/logs/cron.log 2>&1"
CRON_LOCK="0 $LOCK_HOUR * * * cd $INSTALL_DIR && /usr/bin/python3 nextdns_blocker.py block >> $INSTALL_DIR/logs/cron.log 2>&1"

# Remove old cron jobs
crontab -l 2>/dev/null | grep -v "nextdns_blocker.py" | crontab - 2>/dev/null || true

# Add new cron jobs
(crontab -l 2>/dev/null; echo "$CRON_UNLOCK"; echo "$CRON_LOCK") | crontab -

echo -e "${GREEN}✓${NC} Cron jobs configured:"
echo "   - Unblock: ${UNLOCK_HOUR}:00"
echo "   - Block:   ${LOCK_HOUR}:00"
echo ""

# Verify installation
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Installation completed${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Checking current status..."
python3 nextdns_blocker.py status
echo ""

echo -e "${BLUE}Info:${NC}"
echo "  📁 Directory: $INSTALL_DIR"
echo "  📝 Logs: $INSTALL_DIR/logs/"
echo "  ⏰ Schedule: ${UNLOCK_HOUR}:00 - ${LOCK_HOUR}:00 (unblocked)"
echo ""
echo -e "${BLUE}Commands:${NC}"
echo "  Check status:  python3 $INSTALL_DIR/nextdns_blocker.py status"
echo "  Block now:     python3 $INSTALL_DIR/nextdns_blocker.py block"
echo "  View logs:     tail -f $INSTALL_DIR/logs/nextdns_blocker.log"
echo "  View cron:     crontab -l"
echo ""
echo -e "${GREEN}Done! System is configured and running.${NC}"
