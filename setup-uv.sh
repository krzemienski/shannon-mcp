#!/bin/bash
# Shannon MCP - UV Environment Setup Script
# This script sets up a complete development environment using uv

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
PYTHON_VERSION="3.11"
PROJECT_NAME="Shannon MCP"

# Helper functions
print_header() {
    echo ""
    echo -e "${PURPLE}========================================${NC}"
    echo -e "${PURPLE}$1${NC}"
    echo -e "${PURPLE}========================================${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check system requirements
check_system() {
    print_header "Checking System Requirements"
    
    # Check OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
        OS="Windows"
    else
        OS="Unknown"
    fi
    print_info "Operating System: $OS"
    
    # Check if git is installed
    if command -v git &> /dev/null; then
        print_success "Git is installed: $(git --version)"
    else
        print_error "Git is not installed. Please install git first."
        exit 1
    fi
    
    # Check if curl is installed
    if command -v curl &> /dev/null; then
        print_success "Curl is installed"
    else
        print_error "Curl is not installed. Please install curl first."
        exit 1
    fi
}

# Install uv if not already installed
install_uv() {
    print_header "Installing UV"
    
    if command -v uv &> /dev/null; then
        print_success "UV is already installed: $(uv --version)"
        
        # Ask if user wants to update
        read -p "Do you want to update UV to the latest version? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Updating UV..."
            uv self update
            print_success "UV updated to: $(uv --version)"
        fi
    else
        print_info "Installing UV..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        
        # Add to PATH if needed
        export PATH="$HOME/.local/bin:$PATH"
        
        # Add to shell profile
        if [[ "$SHELL" == *"bash"* ]]; then
            PROFILE="$HOME/.bashrc"
        elif [[ "$SHELL" == *"zsh"* ]]; then
            PROFILE="$HOME/.zshrc"
        else
            PROFILE="$HOME/.profile"
        fi
        
        if ! grep -q '.local/bin' "$PROFILE"; then
            echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$PROFILE"
            print_info "Added UV to PATH in $PROFILE"
            print_warning "Please run: source $PROFILE"
        fi
        
        print_success "UV installed successfully!"
    fi
}

# Setup Python environment
setup_python() {
    print_header "Setting Up Python Environment"
    
    # Check if Python version is available
    print_info "Checking Python $PYTHON_VERSION availability..."
    if uv python list | grep -q "$PYTHON_VERSION"; then
        print_success "Python $PYTHON_VERSION is available"
    else
        print_info "Installing Python $PYTHON_VERSION..."
        uv python install $PYTHON_VERSION
    fi
    
    # Create virtual environment with specific Python version
    if [ -d ".venv" ]; then
        print_warning "Virtual environment already exists"
        read -p "Do you want to recreate it? (y/N) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing virtual environment..."
            rm -rf .venv
            print_info "Creating new virtual environment..."
            uv venv --python $PYTHON_VERSION
        fi
    else
        print_info "Creating virtual environment..."
        uv venv --python $PYTHON_VERSION
    fi
    
    print_success "Python environment ready!"
}

# Install dependencies
install_dependencies() {
    print_header "Installing Dependencies"
    
    print_info "Syncing project dependencies..."
    uv sync --dev
    
    print_success "All dependencies installed!"
}

# Setup pre-commit hooks
setup_precommit() {
    print_header "Setting Up Pre-commit Hooks"
    
    print_info "Installing pre-commit hooks..."
    uv run pre-commit install
    
    print_success "Pre-commit hooks installed!"
}

# Verify installation
verify_installation() {
    print_header "Verifying Installation"
    
    # Check if shannon-mcp is installed
    print_info "Checking shannon-mcp installation..."
    if uv run shannon-mcp --help &> /dev/null; then
        print_success "shannon-mcp is installed correctly"
    else
        print_error "shannon-mcp installation failed"
        exit 1
    fi
    
    # Run a simple test
    print_info "Running basic tests..."
    if uv run pytest --version &> /dev/null; then
        print_success "Test framework is working"
    else
        print_warning "Test framework not fully configured"
    fi
}

# Show next steps
show_next_steps() {
    print_header "Setup Complete! 🎉"
    
    echo "Your Shannon MCP development environment is ready!"
    echo ""
    echo "Next steps:"
    echo "1. Activate the virtual environment:"
    echo "   ${GREEN}source .venv/bin/activate${NC}"
    echo ""
    echo "2. Or use the dev script for common tasks:"
    echo "   ${GREEN}./dev.sh help${NC}"
    echo ""
    echo "3. Run the server:"
    echo "   ${GREEN}./dev.sh dev${NC}"
    echo ""
    echo "4. Run tests:"
    echo "   ${GREEN}./dev.sh test${NC}"
    echo ""
    echo "Happy coding! 🚀"
}

# Main setup flow
main() {
    print_header "Shannon MCP Development Setup"
    
    # Check if we're in the right directory
    if [ ! -f "pyproject.toml" ]; then
        print_error "This script must be run from the Shannon MCP project root"
        print_error "Current directory: $(pwd)"
        exit 1
    fi
    
    # Run setup steps
    check_system
    install_uv
    setup_python
    install_dependencies
    setup_precommit
    verify_installation
    show_next_steps
}

# Handle command line arguments
case "$1" in
    --help|-h)
        echo "Shannon MCP UV Setup Script"
        echo ""
        echo "Usage: ./setup-uv.sh [options]"
        echo ""
        echo "Options:"
        echo "  --help, -h     Show this help message"
        echo "  --clean        Clean install (removes existing .venv)"
        echo "  --no-precommit Skip pre-commit hook setup"
        echo ""
        ;;
    --clean)
        print_warning "Performing clean installation..."
        rm -rf .venv uv.lock
        main
        ;;
    --no-precommit)
        check_system
        install_uv
        setup_python
        install_dependencies
        verify_installation
        show_next_steps
        ;;
    *)
        main
        ;;
esac