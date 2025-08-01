#!/bin/bash
#
# Run Fast MCP Integration Tests
# This script tests Shannon MCP from an external client perspective
#

set -e

echo "=============================================="
echo "Shannon MCP - Fast MCP Integration Test Suite"
echo "=============================================="
echo

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Step 1: Install dependencies
echo -e "${YELLOW}[1/4] Installing dependencies...${NC}"
poetry install

# Step 2: Test Fast MCP import
echo -e "\n${YELLOW}[2/4] Testing Fast MCP import...${NC}"
poetry run python -c "
try:
    from fastmcp import FastMCP, Client
    print('✓ Fast MCP imported successfully')
    print(f'  Version: {FastMCP.__module__}')
except ImportError as e:
    print('✗ Fast MCP import failed:', e)
    exit(1)
"

# Step 3: Run syntax check on Fast MCP server
echo -e "\n${YELLOW}[3/4] Checking Fast MCP server syntax...${NC}"
poetry run python -m py_compile src/shannon_mcp/server_fastmcp.py
echo "✓ Server syntax is valid"

# Step 4: Run external client tests
echo -e "\n${YELLOW}[4/4] Running external client tests...${NC}"
echo "This simulates how Claude Desktop or other MCP clients would interact with the server."
echo

# Run the external test client
poetry run python test_external_client.py src/shannon_mcp/server_fastmcp.py

# Summary
echo -e "\n${GREEN}=============================================="
echo "Test suite completed!"
echo "=============================================="
echo -e "${NC}"
echo "Next steps:"
echo "1. Run the Fast MCP server: poetry run shannon-mcp-fastmcp"
echo "2. Configure Claude Desktop to use the server"
echo "3. Test with real Claude Code binary"
echo
echo "Configuration for Claude Desktop:"
echo '{'
echo '  "shannon-mcp": {'
echo '    "command": "poetry",'
echo '    "args": ["run", "shannon-mcp-fastmcp"],'
echo '    "cwd": "'$(pwd)'"'
echo '  }'
echo '}'