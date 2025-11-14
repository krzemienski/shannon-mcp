#!/usr/bin/env bash
# Test: Help command

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${SCRIPT_DIR}/../mcp-cli"

echo "Testing help command..."

# Test help command
HELP_OUTPUT=$("${CLI}" help 2>&1 || true)

# Check if help output contains expected sections
EXPECTED_SECTIONS=(
    "USAGE"
    "TOOLS"
    "RESOURCES"
    "EXAMPLES"
    "find-claude-binary"
    "create-session"
    "list-agents"
)

ALL_FOUND=true
for section in "${EXPECTED_SECTIONS[@]}"; do
    if ! echo "${HELP_OUTPUT}" | grep -q "${section}"; then
        echo "✗ Missing section/command in help: ${section}"
        ALL_FOUND=false
    fi
done

if ${ALL_FOUND}; then
    echo "✓ help command test passed - all expected sections found"
    exit 0
else
    echo "✗ help command test failed - some sections missing"
    echo "Output: ${HELP_OUTPUT}"
    exit 1
fi
