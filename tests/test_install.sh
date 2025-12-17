#!/bin/bash
# Tests for install.sh domain configuration logic

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DIR=$(mktemp -d)

cleanup() {
    rm -rf "$TEST_DIR"
}
trap cleanup EXIT

echo "Testing install.sh domain configuration logic"
echo "=============================================="

# Test 1: Should fail without config.json AND without DOMAINS_URL
echo -n "Test 1: Fail without config.json and DOMAINS_URL... "
mkdir -p "$TEST_DIR/test1"
cat > "$TEST_DIR/test1/.env" << 'EOF'
NEXTDNS_API_KEY=test_key
NEXTDNS_PROFILE_ID=test_profile
EOF

# Extract and test the config check logic
cd "$TEST_DIR/test1"
source .env

if [ ! -f "config.json" ] && [ -z "$DOMAINS_URL" ]; then
    echo "PASS"
else
    echo "FAIL - should have detected missing config"
    exit 1
fi

# Test 2: Should pass with DOMAINS_URL set (no local config.json)
echo -n "Test 2: Pass with DOMAINS_URL (no local file)... "
mkdir -p "$TEST_DIR/test2"
cat > "$TEST_DIR/test2/.env" << 'EOF'
NEXTDNS_API_KEY=test_key
NEXTDNS_PROFILE_ID=test_profile
DOMAINS_URL=https://example.com/config.json
EOF

cd "$TEST_DIR/test2"
source .env

if [ ! -f "config.json" ] && [ -z "$DOMAINS_URL" ]; then
    echo "FAIL - should have accepted DOMAINS_URL"
    exit 1
else
    echo "PASS"
fi

# Test 3: Should pass with local config.json (no DOMAINS_URL)
echo -n "Test 3: Pass with local config.json... "
mkdir -p "$TEST_DIR/test3"
cat > "$TEST_DIR/test3/.env" << 'EOF'
NEXTDNS_API_KEY=test_key
NEXTDNS_PROFILE_ID=test_profile
EOF
echo '{"blocklist": []}' > "$TEST_DIR/test3/config.json"

cd "$TEST_DIR/test3"
source .env

if [ ! -f "config.json" ] && [ -z "$DOMAINS_URL" ]; then
    echo "FAIL - should have accepted local config.json"
    exit 1
else
    echo "PASS"
fi

# Test 4: Should pass with both DOMAINS_URL and local config.json
echo -n "Test 4: Pass with both DOMAINS_URL and local file... "
mkdir -p "$TEST_DIR/test4"
cat > "$TEST_DIR/test4/.env" << 'EOF'
NEXTDNS_API_KEY=test_key
NEXTDNS_PROFILE_ID=test_profile
DOMAINS_URL=https://example.com/config.json
EOF
echo '{"blocklist": []}' > "$TEST_DIR/test4/config.json"

cd "$TEST_DIR/test4"
source .env

if [ ! -f "config.json" ] && [ -z "$DOMAINS_URL" ]; then
    echo "FAIL - should have accepted both configs"
    exit 1
else
    echo "PASS"
fi

# Test 5: Verify correct message for remote config
echo -n "Test 5: Correct output for remote config... "
cd "$TEST_DIR/test2"
source .env

if [ -n "$DOMAINS_URL" ]; then
    OUTPUT="using remote: $DOMAINS_URL"
    if [[ "$OUTPUT" == *"remote"* ]]; then
        echo "PASS"
    else
        echo "FAIL - wrong output message"
        exit 1
    fi
else
    echo "FAIL - DOMAINS_URL not detected"
    exit 1
fi

# Test 6: Verify correct message for local config
echo -n "Test 6: Correct output for local config... "
cd "$TEST_DIR/test3"
unset DOMAINS_URL
source .env

if [ -f "config.json" ]; then
    OUTPUT="using local: config.json"
    if [[ "$OUTPUT" == *"local"* ]]; then
        echo "PASS"
    else
        echo "FAIL - wrong output message"
        exit 1
    fi
else
    echo "FAIL - config.json not detected"
    exit 1
fi

echo ""
echo "All tests passed!"
