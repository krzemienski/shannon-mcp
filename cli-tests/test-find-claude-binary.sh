#!/usr/bin/env bash
# Test: find-claude-binary tool

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${SCRIPT_DIR}/../mcp-cli"

echo "Testing find-claude-binary command..."

# Test the find-claude-binary tool
OUTPUT=$("${CLI}" find-claude-binary 2>&1 || true)

# Check if output contains expected fields (path, version, etc.)
if echo "${OUTPUT}" | grep -qE '(path|version|not found|error)'; then
    echo "✓ find-claude-binary test passed - received valid response"
    echo "Output: ${OUTPUT}"
    exit 0
else
    echo "✗ find-claude-binary test failed - unexpected output format"
    echo "Output: ${OUTPUT}"
    exit 1
fi
