#!/usr/bin/env bash
# Shannon MCP CLI - Comprehensive Test Runner
# Runs all validation tests for the MCP CLI wrapper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test files
TESTS=(
    "test-help.sh"
    "test-list-tools.sh"
    "test-find-claude-binary.sh"
    "test-agents.sh"
    "test-resources.sh"
    "test-session-lifecycle.sh"
)

# Counters
PASSED=0
FAILED=0
WARNINGS=0

# Results tracking
declare -A RESULTS

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Shannon MCP CLI - Validation Test Suite${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if mcp-cli exists
if [[ ! -f "${SCRIPT_DIR}/../mcp-cli" ]]; then
    echo -e "${RED}✗ Error: mcp-cli script not found at ${SCRIPT_DIR}/../mcp-cli${NC}"
    exit 1
fi

# Check if mcp-cli is executable
if [[ ! -x "${SCRIPT_DIR}/../mcp-cli" ]]; then
    echo -e "${YELLOW}⚠ Warning: mcp-cli is not executable, attempting to fix...${NC}"
    chmod +x "${SCRIPT_DIR}/../mcp-cli"
fi

# Check dependencies
MISSING_DEPS=false

if ! command -v jq &> /dev/null; then
    echo -e "${RED}✗ Error: jq is required but not installed${NC}"
    MISSING_DEPS=true
fi

if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: poetry not found, MCP server may not run${NC}"
fi

if ${MISSING_DEPS}; then
    echo ""
    echo "Please install missing dependencies:"
    echo "  - jq: sudo apt-get install jq (or brew install jq on macOS)"
    exit 1
fi

echo ""

# Run each test
for test in "${TESTS[@]}"; do
    TEST_PATH="${SCRIPT_DIR}/${test}"

    if [[ ! -f "${TEST_PATH}" ]]; then
        echo -e "${RED}✗ Test file not found: ${test}${NC}"
        RESULTS[$test]="MISSING"
        ((FAILED++))
        continue
    fi

    # Make test executable if needed
    if [[ ! -x "${TEST_PATH}" ]]; then
        chmod +x "${TEST_PATH}"
    fi

    echo -e "${YELLOW}Running: ${test}${NC}"
    echo "----------------------------------------"

    # Run test and capture output
    if bash "${TEST_PATH}" 2>&1; then
        RESULTS[$test]="PASSED"
        ((PASSED++))
        echo ""
    else
        EXIT_CODE=$?
        if [[ ${EXIT_CODE} -eq 1 ]]; then
            RESULTS[$test]="FAILED"
            ((FAILED++))
        else
            RESULTS[$test]="WARNING"
            ((WARNINGS++))
        fi
        echo ""
    fi
done

# Print summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

for test in "${TESTS[@]}"; do
    result="${RESULTS[$test]:-UNKNOWN}"
    case "$result" in
        PASSED)
            echo -e "  ${GREEN}✓${NC} ${test}: ${GREEN}PASSED${NC}"
            ;;
        FAILED)
            echo -e "  ${RED}✗${NC} ${test}: ${RED}FAILED${NC}"
            ;;
        WARNING)
            echo -e "  ${YELLOW}⚠${NC} ${test}: ${YELLOW}WARNING${NC}"
            ;;
        MISSING)
            echo -e "  ${RED}✗${NC} ${test}: ${RED}MISSING${NC}"
            ;;
        *)
            echo -e "  ${YELLOW}?${NC} ${test}: ${YELLOW}UNKNOWN${NC}"
            ;;
    esac
done

echo ""
echo "----------------------------------------"
echo -e "${GREEN}Passed:  ${PASSED}${NC}"
echo -e "${YELLOW}Warnings: ${WARNINGS}${NC}"
echo -e "${RED}Failed:  ${FAILED}${NC}"
echo "Total:   $((PASSED + WARNINGS + FAILED))"
echo "----------------------------------------"

if [[ ${FAILED} -eq 0 ]]; then
    if [[ ${WARNINGS} -eq 0 ]]; then
        echo -e "${GREEN}All tests passed!${NC}"
        exit 0
    else
        echo -e "${YELLOW}All tests passed with warnings!${NC}"
        exit 0
    fi
else
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
fi
