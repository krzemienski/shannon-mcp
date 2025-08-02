#!/bin/bash
# Shannon MCP Development Script using UV/UVX
# This script provides convenient shortcuts for common development tasks

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if uv is installed
check_uv() {
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Please install it first:"
        echo "curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
}

# Main function
main() {
    check_uv
    
    case "$1" in
        # Setup commands
        setup)
            print_info "Setting up Shannon MCP development environment..."
            uv sync --dev
            uv run pre-commit install
            print_success "Development environment setup complete!"
            ;;
        
        # Testing commands
        test)
            shift
            print_info "Running tests..."
            uv run pytest "$@"
            ;;
        
        test-cov)
            shift
            print_info "Running tests with coverage..."
            uv run pytest --cov=shannon_mcp --cov-report=term-missing --cov-report=html "$@"
            ;;
        
        test-integration)
            shift
            print_info "Running integration tests..."
            uv run pytest tests/integration/ -v "$@"
            ;;
        
        test-functional)
            shift
            print_info "Running functional tests..."
            uv run pytest tests/functional/ -v "$@"
            ;;
        
        test-benchmark)
            shift
            print_info "Running benchmark tests..."
            uv run pytest tests/benchmarks/ -v --benchmark-only "$@"
            ;;
        
        # Code quality commands
        format)
            print_info "Formatting code..."
            uv run black .
            uv run isort .
            print_success "Code formatted!"
            ;;
        
        lint)
            print_info "Running linters..."
            uv run flake8 src tests
            ;;
        
        typecheck)
            print_info "Running type checker..."
            uv run mypy src
            ;;
        
        check)
            print_info "Running all checks..."
            uv run black . --check
            uv run isort . --check
            uv run flake8 src tests
            uv run mypy src
            print_success "All checks passed!"
            ;;
        
        # Development commands
        dev)
            print_info "Starting Shannon MCP server..."
            uv run shannon-mcp
            ;;
        
        shell)
            print_info "Starting Python shell with project context..."
            uv run python
            ;;
        
        run)
            shift
            uv run "$@"
            ;;
        
        # Build commands
        build)
            print_info "Building package..."
            uv run python -m build
            print_success "Build complete!"
            ;;
        
        clean)
            print_info "Cleaning build artifacts..."
            rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov .mypy_cache
            find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
            print_success "Clean complete!"
            ;;
        
        # Documentation commands
        docs)
            print_info "Building documentation..."
            cd docs && uv run make html
            print_success "Documentation built!"
            ;;
        
        docs-serve)
            print_info "Serving documentation on http://localhost:8080..."
            cd docs && uv run python -m http.server -d build/html 8080
            ;;
        
        # Dependency management
        add)
            shift
            print_info "Adding dependency: $1"
            uv add "$@"
            ;;
        
        add-dev)
            shift
            print_info "Adding dev dependency: $1"
            uv add --dev "$@"
            ;;
        
        remove)
            shift
            print_info "Removing dependency: $1"
            uv remove "$@"
            ;;
        
        update)
            print_info "Updating all dependencies..."
            uv lock --upgrade-all
            uv sync
            print_success "Dependencies updated!"
            ;;
        
        show)
            print_info "Showing installed packages..."
            uv pip list
            ;;
        
        tree)
            print_info "Showing dependency tree..."
            uv pip tree
            ;;
        
        # Help
        help|*)
            echo "Shannon MCP Development Script"
            echo ""
            echo "Usage: ./dev.sh [command] [options]"
            echo ""
            echo "Setup Commands:"
            echo "  setup              - Set up development environment"
            echo ""
            echo "Testing Commands:"
            echo "  test [args]        - Run all tests"
            echo "  test-cov [args]    - Run tests with coverage"
            echo "  test-integration   - Run integration tests"
            echo "  test-functional    - Run functional tests"
            echo "  test-benchmark     - Run benchmark tests"
            echo ""
            echo "Code Quality Commands:"
            echo "  format             - Format code with black and isort"
            echo "  lint               - Run flake8 linter"
            echo "  typecheck          - Run mypy type checker"
            echo "  check              - Run all checks (format, lint, typecheck)"
            echo ""
            echo "Development Commands:"
            echo "  dev                - Start Shannon MCP server"
            echo "  shell              - Start Python shell"
            echo "  run [cmd]          - Run any command in the uv environment"
            echo ""
            echo "Build Commands:"
            echo "  build              - Build the package"
            echo "  clean              - Clean build artifacts"
            echo ""
            echo "Documentation Commands:"
            echo "  docs               - Build documentation"
            echo "  docs-serve         - Serve documentation locally"
            echo ""
            echo "Dependency Management:"
            echo "  add [pkg]          - Add a dependency"
            echo "  add-dev [pkg]      - Add a dev dependency"
            echo "  remove [pkg]       - Remove a dependency"
            echo "  update             - Update all dependencies"
            echo "  show               - Show installed packages"
            echo "  tree               - Show dependency tree"
            echo ""
            echo "Examples:"
            echo "  ./dev.sh setup"
            echo "  ./dev.sh test"
            echo "  ./dev.sh format"
            echo "  ./dev.sh add httpx"
            echo "  ./dev.sh run python -c 'import shannon_mcp; print(shannon_mcp.__version__)'"
            ;;
    esac
}

# Run main function with all arguments
main "$@"