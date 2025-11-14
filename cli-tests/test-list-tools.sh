#!/usr/bin/env bash
# Test: list-tools utility

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${SCRIPT_DIR}/../mcp-cli"

echo "Testing list-tools command..."

# Test the list-tools utility
OUTPUT=$("${CLI}" list-tools 2>&1 || true)

# Check if output contains expected tool names
EXPECTED_TOOLS=(
    "find_claude_binary"
    "create_session"
    "send_message"
    "cancel_session"
    "list_sessions"
    "list_agents"
    "assign_task"
)

ALL_FOUND=true
for tool in "${EXPECTED_TOOLS[@]}"; do
    if ! echo "${OUTPUT}" | grep -q "${tool}"; then
        echo "✗ Missing tool: ${tool}"
        ALL_FOUND=false
    fi
done

if ${ALL_FOUND}; then
    echo "✓ list-tools test passed - all expected tools found"
    exit 0
else
    echo "✗ list-tools test failed - some tools missing"
    echo "Output: ${OUTPUT}"
    exit 1
fi
