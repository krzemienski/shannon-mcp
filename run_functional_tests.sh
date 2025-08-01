#!/bin/bash
#
# Shannon MCP Functional Test Runner
#
# This script runs the functional test client against the Shannon MCP server
# and provides a clear summary of the results.

set -e

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Shannon MCP Functional Test Runner${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $python_version"

# Check if we're in the right directory
if [ ! -f "functional_test_client.py" ]; then
    echo -e "${RED}Error: functional_test_client.py not found${NC}"
    echo "Please run this script from the Shannon MCP project root"
    exit 1
fi

# Check if server exists
if [ ! -f "src/shannon_mcp/stdio_wrapper.py" ]; then
    echo -e "${RED}Error: Shannon MCP server not found${NC}"
    echo "Please ensure the server is properly installed"
    exit 1
fi

# Create logs directory
mkdir -p logs

# Run the functional tests
echo ""
echo -e "${YELLOW}Starting functional tests...${NC}"
echo "Log file: logs/functional_test_$(date +%Y%m%d_%H%M%S).log"
echo ""

# Run tests and capture output
log_file="logs/functional_test_$(date +%Y%m%d_%H%M%S).log"
python3 functional_test_client.py 2>&1 | tee "$log_file"

# Check exit code
exit_code=${PIPESTATUS[0]}

echo ""
echo -e "${BLUE}========================================${NC}"

if [ $exit_code -eq 0 ]; then
    echo -e "${GREEN}✅ ALL TESTS PASSED!${NC}"
else
    echo -e "${RED}❌ SOME TESTS FAILED${NC}"
    echo ""
    echo "Check the log file for details: $log_file"
fi

echo -e "${BLUE}========================================${NC}"

# Show results file if it exists
if [ -f "functional_test_results.json" ]; then
    echo ""
    echo "Detailed results saved to: functional_test_results.json"
    echo ""
    echo "Summary:"
    python3 -c "
import json
with open('functional_test_results.json') as f:
    data = json.load(f)
    summary = data.get('summary', {})
    print(f\"  Total Tests: {summary.get('total', 0)}\")
    print(f\"  Passed: {summary.get('passed', 0)}\")
    print(f\"  Failed: {summary.get('failed', 0)}\")
    print(f\"  Success Rate: {summary.get('success_rate', 0) * 100:.1f}%\")
"
fi

exit $exit_code