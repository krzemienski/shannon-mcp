#!/bin/bash

# Shannon MCP Frontend Setup Script
# This script sets up the frontend development environment

set -e

echo "🚀 Setting up Shannon MCP Frontend..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the Shannon MCP root directory"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed. Please install Node.js 18+ first."
    echo "   Visit: https://nodejs.org/"
    exit 1
fi

# Check Node.js version
NODE_VERSION=$(node -v | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Error: Node.js version 18+ is required. Current version: $(node -v)"
    exit 1
fi

echo "✅ Node.js version: $(node -v)"

# Change to frontend directory
cd frontend

# Install dependencies
echo "📦 Installing frontend dependencies..."
npm install

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file..."
    cat > .env << EOL
# Shannon MCP Frontend Configuration
VITE_API_URL=http://localhost:8000
VITE_WS_URL=http://localhost:8080
VITE_APP_TITLE=Shannon MCP
EOL
fi

echo "✅ Frontend setup complete!"
echo ""
echo "🎯 Next steps:"
echo "   1. Start the backend server: cd .. && python examples/websocket_demo.py"
echo "   2. Start the frontend: npm run dev"
echo "   3. Open http://localhost:3000 in your browser"
echo ""
echo "📚 Available commands:"
echo "   npm run dev      - Start development server"
echo "   npm run build    - Build for production"
echo "   npm run preview  - Preview production build"
echo "   npm run lint     - Run linting"
echo "   npm run type-check - Type checking"