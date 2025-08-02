#!/bin/bash
# Local test runner for Shannon MCP development

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TEST_TYPE="all"
VERBOSE=""
PARALLEL=""
WATCH_MODE=""
COVERAGE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -t|--type)
            TEST_TYPE="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE="--verbose"
            shift
            ;;
        -p|--parallel)
            PARALLEL="--parallel"
            shift
            ;;
        -w|--watch)
            WATCH_MODE="1"
            shift
            ;;
        -c|--coverage)
            COVERAGE="1"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -t, --type TYPE     Test type: all, real, claude, full, edge, unit (default: all)"
            echo "  -v, --verbose       Verbose output"
            echo "  -p, --parallel      Run tests in parallel"
            echo "  -w, --watch         Watch mode - rerun on file changes"
            echo "  -c, --coverage      Generate coverage report"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Function to print colored output
print_color() {
    local color=$1
    shift
    echo -e "${color}$@${NC}"
}

# Function to check dependencies
check_dependencies() {
    print_color $BLUE "Checking dependencies..."
    
    local missing=()
    
    # Check Python version
    if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
        missing+=("Python 3.11+")
    fi
    
    # Check for uv
    if ! command -v uv &> /dev/null; then
        missing+=("uv (pip install uv)")
    fi
    
    # Check for pytest
    if ! python3 -c "import pytest" 2>/dev/null; then
        missing+=("pytest")
    fi
    
    if [ ${#missing[@]} -ne 0 ]; then
        print_color $RED "Missing dependencies:"
        for dep in "${missing[@]}"; do
            echo "  - $dep"
        done
        exit 1
    fi
    
    print_color $GREEN "✓ All dependencies satisfied"
}

# Function to setup test environment
setup_test_env() {
    print_color $BLUE "Setting up test environment..."
    
    # Create test directories
    mkdir -p test_output
    mkdir -p .coverage
    
    # Set environment variables
    export SHANNON_TEST_MODE="local"
    export PYTHONDONTWRITEBYTECODE=1
    export PYTEST_CURRENT_TEST=1
    
    if [ -n "$COVERAGE" ]; then
        export WITH_COVERAGE=1
    fi
    
    print_color $GREEN "✓ Test environment ready"
}

# Function to run tests
run_tests() {
    local test_cmd="python run_e2e_tests.py --type $TEST_TYPE $VERBOSE $PARALLEL"
    
    print_color $BLUE "Running $TEST_TYPE tests..."
    print_color $YELLOW "Command: $test_cmd"
    echo ""
    
    if $test_cmd; then
        print_color $GREEN "✓ Tests passed!"
        return 0
    else
        print_color $RED "✗ Tests failed!"
        return 1
    fi
}

# Function to run tests in watch mode
run_watch_mode() {
    print_color $BLUE "Starting watch mode..."
    print_color $YELLOW "Watching for changes in src/ and tests/"
    print_color $YELLOW "Press Ctrl+C to exit"
    echo ""
    
    # Use inotifywait if available, otherwise fall back to polling
    if command -v inotifywait &> /dev/null; then
        while true; do
            run_tests
            echo ""
            print_color $BLUE "Waiting for file changes..."
            inotifywait -r -e modify,create,delete,move src/ tests/ 2>/dev/null
            echo ""
            print_color $YELLOW "Changes detected, rerunning tests..."
            sleep 1
        done
    else
        # Fallback to simple polling
        local last_modified=$(find src/ tests/ -type f -name "*.py" -exec stat -c %Y {} \; | sort -n | tail -1)
        
        while true; do
            run_tests
            echo ""
            print_color $BLUE "Waiting for file changes (polling mode)..."
            
            while true; do
                sleep 2
                local current_modified=$(find src/ tests/ -type f -name "*.py" -exec stat -c %Y {} \; | sort -n | tail -1)
                if [ "$current_modified" != "$last_modified" ]; then
                    last_modified=$current_modified
                    echo ""
                    print_color $YELLOW "Changes detected, rerunning tests..."
                    sleep 1
                    break
                fi
            done
        done
    fi
}

# Function to show test report
show_report() {
    local latest_dir=$(ls -td test_output/run_* 2>/dev/null | head -1)
    
    if [ -z "$latest_dir" ]; then
        return
    fi
    
    echo ""
    print_color $BLUE "Test Reports:"
    
    if [ -f "$latest_dir/report.html" ]; then
        echo "  HTML Report: file://$PWD/$latest_dir/report.html"
    fi
    
    if [ -f "$latest_dir/coverage/index.html" ]; then
        echo "  Coverage Report: file://$PWD/$latest_dir/coverage/index.html"
    fi
    
    if [ -f "$latest_dir/test_results.json" ]; then
        echo "  JSON Results: $latest_dir/test_results.json"
    fi
}

# Main execution
main() {
    print_color $BLUE "Shannon MCP Local Test Runner"
    echo "=============================="
    echo ""
    
    # Check dependencies
    check_dependencies
    
    # Setup environment
    setup_test_env
    
    # Run tests
    if [ -n "$WATCH_MODE" ]; then
        run_watch_mode
    else
        if run_tests; then
            show_report
            exit 0
        else
            show_report
            exit 1
        fi
    fi
}

# Run main function
main