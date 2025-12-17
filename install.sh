#!/bin/bash
# NextDNS Blocker - Cross-platform Install Script
# Supports: macOS (Homebrew + launchd) and Linux (apt/yum + cron)

set -e

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        *)          echo "unknown" ;;
    esac
}

OS=$(detect_os)

# Set paths based on OS
if [ "$OS" = "macos" ]; then
    CONFIG_DIR="$HOME/Library/Application Support/nextdns-blocker"
    LOG_DIR="$HOME/Library/Application Support/nextdns-blocker/logs"
    LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
else
    CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/nextdns-blocker"
    LOG_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/nextdns-blocker/logs"
fi

echo ""
echo "  nextdns-blocker install"
echo "  -----------------------"
echo "  OS: $OS"
echo ""

# Check for unsupported OS
if [ "$OS" = "unknown" ]; then
    echo "  error: unsupported operating system"
    exit 1
fi

# Step 1: Install Python 3
echo "  [1/7] python3"
if ! command -v python3 &> /dev/null; then
    if [ "$OS" = "macos" ]; then
        if command -v brew &> /dev/null; then
            brew install python3
        else
            echo "  error: Homebrew not found. Install from https://brew.sh"
            exit 1
        fi
    else
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y python3
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3
        else
            echo "  error: no package manager found"
            exit 1
        fi
    fi
fi
echo "         $(python3 --version)"

# Step 2: Install pip
echo "  [2/7] pip"
if ! command -v pip3 &> /dev/null; then
    if [ "$OS" = "macos" ]; then
        if command -v brew &> /dev/null; then
            brew install python3  # pip3 comes with python3 in Homebrew
        fi
    else
        if command -v apt-get &> /dev/null; then
            sudo apt-get install -y python3-pip
        elif command -v yum &> /dev/null; then
            sudo yum install -y python3-pip
        elif command -v dnf &> /dev/null; then
            sudo dnf install -y python3-pip
        fi
    fi
fi

# Step 3: Create directories
echo "  [3/7] directories"
mkdir -p "$CONFIG_DIR"
mkdir -p "$LOG_DIR"
echo "         config: $CONFIG_DIR"
echo "         logs:   $LOG_DIR"

# Step 4: Install package
echo "  [4/7] installing nextdns-blocker"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f "pyproject.toml" ]; then
    pip3 install . --user --quiet
elif [ -f "requirements.txt" ]; then
    pip3 install -r requirements.txt --user --quiet
fi

# Verify installation
if ! command -v nextdns-blocker &> /dev/null; then
    echo "  warning: nextdns-blocker not in PATH"
    echo "           you may need to add ~/.local/bin to your PATH"
fi

# Step 5: Check/create config
echo "  [5/7] config"

# Check if already initialized
if [ -f "$CONFIG_DIR/.env" ]; then
    echo "         using existing: $CONFIG_DIR/.env"
    # shellcheck source=/dev/null
    source "$CONFIG_DIR/.env"
elif [ -f "$SCRIPT_DIR/.env" ]; then
    echo "         copying: $SCRIPT_DIR/.env -> $CONFIG_DIR/.env"
    cp "$SCRIPT_DIR/.env" "$CONFIG_DIR/.env"
    # shellcheck source=/dev/null
    source "$CONFIG_DIR/.env"
else
    echo ""
    echo "  .env not found. Run 'nextdns-blocker init' to create configuration."
    echo ""
    exit 0
fi

# Check for config.json
if [ -f "$CONFIG_DIR/config.json" ]; then
    echo "         using local: $CONFIG_DIR/config.json"
elif [ -f "$SCRIPT_DIR/config.json" ]; then
    echo "         copying: $SCRIPT_DIR/config.json -> $CONFIG_DIR/config.json"
    cp "$SCRIPT_DIR/config.json" "$CONFIG_DIR/config.json"
else
    echo "  warning: no config.json found"
    echo "           run 'nextdns-blocker init' to create one"
fi

# Step 6: Validate API
echo "  [6/7] validating API"
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

# Step 7: Setup scheduling (OS-specific)
echo "  [7/7] scheduling"

if [ "$OS" = "macos" ]; then
    # macOS: Use launchd
    echo "         setting up launchd..."

    # Find nextdns-blocker executable
    BLOCKER_PATH=$(command -v nextdns-blocker 2>/dev/null || echo "$HOME/.local/bin/nextdns-blocker")

    # Create sync LaunchAgent
    SYNC_PLIST="$LAUNCH_AGENTS_DIR/com.nextdns-blocker.sync.plist"
    cat > "$SYNC_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nextdns-blocker.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BLOCKER_PATH</string>
        <string>sync</string>
    </array>
    <key>StartInterval</key>
    <integer>120</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/sync.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/sync.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.local/bin</string>
    </dict>
</dict>
</plist>
EOF

    # Create watchdog LaunchAgent
    WD_PLIST="$LAUNCH_AGENTS_DIR/com.nextdns-blocker.watchdog.plist"
    cat > "$WD_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nextdns-blocker.watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>$BLOCKER_PATH</string>
        <string>watchdog</string>
        <string>check</string>
    </array>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>$LOG_DIR/watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>$LOG_DIR/watchdog.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$HOME/.local/bin</string>
    </dict>
</dict>
</plist>
EOF

    # Load LaunchAgents
    launchctl unload "$SYNC_PLIST" 2>/dev/null || true
    launchctl unload "$WD_PLIST" 2>/dev/null || true
    launchctl load "$SYNC_PLIST"
    launchctl load "$WD_PLIST"

    echo "         launchd jobs loaded"
else
    # Linux: Use cron
    echo "         setting up cron..."

    BLOCKER_PATH=$(command -v nextdns-blocker 2>/dev/null || echo "$HOME/.local/bin/nextdns-blocker")

    CRON_SYNC="*/2 * * * * $BLOCKER_PATH sync >> $LOG_DIR/sync.log 2>&1"
    CRON_WD="* * * * * $BLOCKER_PATH watchdog check >> $LOG_DIR/watchdog.log 2>&1"

    # Remove old entries and add new ones
    (crontab -l 2>/dev/null | grep -v "nextdns-blocker" || true; echo "$CRON_SYNC"; echo "$CRON_WD") | crontab -

    echo "         cron jobs installed"
fi

# Run initial sync
echo ""
echo "  syncing..."
if command -v nextdns-blocker &> /dev/null; then
    nextdns-blocker sync || true
else
    python3 -m nextdns_blocker sync || true
fi

# Done
echo ""
echo "  done"
echo ""
echo "  paths"
echo "    config:  $CONFIG_DIR"
echo "    logs:    $LOG_DIR"
echo ""
echo "  schedule"
echo "    sync:      every 2 min"
echo "    watchdog:  every 1 min"
echo ""
echo "  commands"
echo "    nextdns-blocker status"
echo "    nextdns-blocker sync"
echo "    nextdns-blocker watchdog status"
echo ""
if [ "$OS" = "macos" ]; then
echo "  launchd"
echo "    launchctl list | grep nextdns"
echo "    launchctl unload ~/Library/LaunchAgents/com.nextdns-blocker.sync.plist"
echo ""
else
echo "  cron"
echo "    crontab -l | grep nextdns"
echo ""
fi
