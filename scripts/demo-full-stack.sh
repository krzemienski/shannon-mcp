#!/bin/bash

# Shannon MCP Full Stack Demo Script
# This script demonstrates the complete Shannon MCP system with both backend and frontend

set -e

echo "🚀 Shannon MCP Full Stack Demo"
echo "=============================="

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the Shannon MCP root directory"
    exit 1
fi

# Check dependencies
echo "🔍 Checking dependencies..."

# Check Python and uv
if ! command -v uv &> /dev/null; then
    echo "❌ Error: uv is not installed. Please install uv first:"
    echo "   curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed. Please install Node.js 18+ first."
    exit 1
fi

echo "✅ Dependencies found"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
uv sync

# Setup frontend if not already done
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Setting up frontend..."
    ./scripts/setup-frontend.sh
else
    echo "✅ Frontend already set up"
fi

# Create demo token file
echo "🔑 Generating demo authentication token..."
cat > .demo-token << EOL
# Demo JWT Token for Shannon MCP
# This token is for demonstration purposes only
# In production, use proper authentication

DEMO_TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiZGVtb191c2VyIiwiaWF0IjoxNzM4NDU1MjE2LCJleHAiOjE3Mzg1NDE2MTYsInNlc3Npb25fc2NvcGUiOiJkZW1vIiwicGVybWlzc2lvbnMiOlsic2Vzc2lvbnM6Y3JlYXRlIiwic2Vzc2lvbnM6bWFuYWdlIl19.dummy"
SECRET_KEY="demo-secret-key-change-in-production"
EOL

echo ""
echo "🎯 Demo Instructions:"
echo "====================="
echo ""
echo "1. Terminal 1 - Start Backend WebSocket Server:"
echo "   python examples/websocket_demo.py"
echo ""
echo "2. Terminal 2 - Start Frontend Development Server:"
echo "   cd frontend && npm run dev"
echo ""
echo "3. Browser - Open the Application:"
echo "   http://localhost:3000"
echo ""
echo "4. Test the Integration:"
echo "   • Click 'New Session' or go to /session"
echo "   • Enter a prompt like 'Hello, Claude! Can you help me?'"
echo "   • Watch real-time streaming responses"
echo "   • Try different Claude Code commands"
echo ""
echo "🔧 Advanced Testing:"
echo "==================="
echo ""
echo "Test WebSocket directly with Socket.IO client:"
echo ""
cat << 'EOL'
const io = require('socket.io-client');
const socket = io('http://localhost:8080', {
  auth: { token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...' }
});

socket.on('connect', () => {
  console.log('Connected!');
  
  // Start a session
  socket.emit('claude_start', {
    prompt: 'Hello Claude!',
    model: 'claude-3-sonnet'
  }, (response) => {
    console.log('Session:', response);
  });
});
EOL
echo ""
echo "📊 Features to Test:"
echo "==================="
echo "• Real-time message streaming"
echo "• Session management (start/stop)"
echo "• WebSocket connection status"
echo "• Message history and virtual scrolling"
echo "• Responsive design"
echo "• Error handling and reconnection"
echo ""
echo "🚨 Troubleshooting:"
echo "=================="
echo "• Backend not starting? Check Claude Code binary is available"
echo "• Frontend errors? Check browser console and network tab"
echo "• WebSocket issues? Verify port 8080 is not in use"
echo "• Authentication errors? Use the demo token from .demo-token"
echo ""
echo "Ready to start? Run the commands above in separate terminals!"
echo ""