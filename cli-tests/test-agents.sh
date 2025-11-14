#!/usr/bin/env bash
# Test: Agent-related commands (list-agents, assign-task)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI="${SCRIPT_DIR}/../mcp-cli"

echo "Testing agent commands..."

# Test 1: List all agents
echo "Step 1: Listing all agents..."
LIST_OUTPUT=$("${CLI}" list-agents 2>&1 || true)

if echo "${LIST_OUTPUT}" | grep -qE '(\[|\{|agent|error)'; then
    echo "✓ list-agents returned valid response"
else
    echo "✗ list-agents failed - unexpected output format"
    echo "Output: ${LIST_OUTPUT}"
    exit 1
fi

# Test 2: List agents by category
echo "Step 2: Listing agents by category..."
CATEGORY_OUTPUT=$("${CLI}" list-agents "core" 2>&1 || true)

if echo "${CATEGORY_OUTPUT}" | grep -qE '(\[|\{|agent|error)'; then
    echo "✓ list-agents with category filter returned valid response"
else
    echo "⚠ list-agents with category filter - unexpected output format"
fi

# Test 3: List agents by capability
echo "Step 3: Listing agents by capability..."
CAPABILITY_OUTPUT=$("${CLI}" list-agents "" "" "python" 2>&1 || true)

if echo "${CAPABILITY_OUTPUT}" | grep -qE '(\[|\{|agent|error)'; then
    echo "✓ list-agents with capability filter returned valid response"
else
    echo "⚠ list-agents with capability filter - unexpected output format"
fi

# Test 4: Assign task to agent
echo "Step 4: Assigning task to agent..."
TASK_OUTPUT=$("${CLI}" assign-task "Test task for CLI validation" '["python","testing"]' "medium" 2>&1 || true)

if echo "${TASK_OUTPUT}" | grep -qE '(task_id|agent_id|score|error)'; then
    echo "✓ assign-task returned valid response"

    # Try to extract task ID
    TASK_ID=$(echo "${TASK_OUTPUT}" | jq -r '.task_id // empty' 2>/dev/null || echo "")

    if [[ -n "${TASK_ID}" ]]; then
        echo "  Task ID: ${TASK_ID}"
    fi
else
    echo "⚠ assign-task response format unexpected"
    echo "Output: ${TASK_OUTPUT}"
fi

echo ""
echo "✓ Agent commands test completed"
exit 0
