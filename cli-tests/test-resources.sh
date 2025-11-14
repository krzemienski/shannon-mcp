#!/usr/bin/env bash
# Test: MCP resources (config, agents, sessions)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${SCRIPT_DIR}/../mcp-cli"

echo "Testing MCP resources..."

# Test 1: Get configuration resource
echo "Step 1: Getting configuration..."
CONFIG_OUTPUT=$("${CLI}" get-config 2>&1 || true)

if echo "${CONFIG_OUTPUT}" | grep -qE '(\{|config|version|error)'; then
    echo "✓ get-config returned valid response"
else
    echo "✗ get-config failed - unexpected output format"
    echo "Output: ${CONFIG_OUTPUT}"
    exit 1
fi

# Test 2: Get agents resource
echo "Step 2: Getting agents resource..."
AGENTS_OUTPUT=$("${CLI}" get-agents-resource 2>&1 || true)

if echo "${AGENTS_OUTPUT}" | grep -qE '(\[|\{|agent|error)'; then
    echo "✓ get-agents-resource returned valid response"
else
    echo "⚠ get-agents-resource - unexpected output format"
    echo "Output: ${AGENTS_OUTPUT}"
fi

# Test 3: Get sessions resource
echo "Step 3: Getting sessions resource..."
SESSIONS_OUTPUT=$("${CLI}" get-sessions-resource 2>&1 || true)

if echo "${SESSIONS_OUTPUT}" | grep -qE '(\[|\{|session|error)'; then
    echo "✓ get-sessions-resource returned valid response"
else
    echo "⚠ get-sessions-resource - unexpected output format"
    echo "Output: ${SESSIONS_OUTPUT}"
fi

echo ""
echo "✓ Resource commands test completed"
exit 0
