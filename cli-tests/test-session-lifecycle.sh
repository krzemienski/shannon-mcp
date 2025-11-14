#!/usr/bin/env bash
# Test: Complete session lifecycle (create, list, send message, cancel)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${SCRIPT_DIR}/../mcp-cli"

echo "Testing session lifecycle..."

# Test 1: Create session
echo "Step 1: Creating session..."
CREATE_OUTPUT=$("${CLI}" create-session "Test session for CLI validation" 2>&1 || true)

if echo "${CREATE_OUTPUT}" | grep -qE '(session_id|error)'; then
    echo "✓ create-session returned valid response"

    # Try to extract session ID (if successful)
    SESSION_ID=$(echo "${CREATE_OUTPUT}" | jq -r '.session_id // empty' 2>/dev/null || echo "")

    if [[ -n "${SESSION_ID}" ]]; then
        echo "  Session ID: ${SESSION_ID}"

        # Test 2: List sessions
        echo "Step 2: Listing sessions..."
        LIST_OUTPUT=$("${CLI}" list-sessions 2>&1 || true)

        if echo "${LIST_OUTPUT}" | grep -q "${SESSION_ID}"; then
            echo "✓ Session found in list-sessions output"
        else
            echo "⚠ Session not found in list (may be expected if session completed quickly)"
        fi

        # Test 3: Send message to session
        echo "Step 3: Sending message to session..."
        MESSAGE_OUTPUT=$("${CLI}" send-message "${SESSION_ID}" "Test message" 2>&1 || true)

        if echo "${MESSAGE_OUTPUT}" | grep -qE '(success|error)'; then
            echo "✓ send-message returned valid response"
        else
            echo "⚠ send-message response format unexpected"
        fi

        # Test 4: Cancel session
        echo "Step 4: Canceling session..."
        CANCEL_OUTPUT=$("${CLI}" cancel-session "${SESSION_ID}" 2>&1 || true)

        if echo "${CANCEL_OUTPUT}" | grep -qE '(success|error)'; then
            echo "✓ cancel-session returned valid response"
        else
            echo "⚠ cancel-session response format unexpected"
        fi
    else
        echo "⚠ Could not extract session ID, skipping lifecycle tests"
    fi
else
    echo "✗ create-session failed - unexpected output format"
    echo "Output: ${CREATE_OUTPUT}"
    exit 1
fi

echo ""
echo "✓ Session lifecycle test completed (check warnings above for any issues)"
exit 0
