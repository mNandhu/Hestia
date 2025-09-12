#!/bin/bash

# Hestia Development Helper Script
# Combines common development tasks for easier workflow

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}🚀 Hestia Development Helper${NC}"
    echo -e "${BLUE}================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Function to run full development setup
dev_setup() {
    print_header
    echo "Setting up complete development environment..."
    
    # Start dependencies
    echo "📦 Starting dependencies..."
    ./scripts/dev-env.sh start
    
    print_success "Development environment ready!"
    echo ""
    echo "🌐 Service URLs:"
    echo "  Hestia API: http://localhost:8080 (run locally)"
    echo "  Semaphore UI: http://localhost:3000 (admin/admin)"
    echo ""
    echo "💻 Next steps:"
    echo "  1. Run Hestia: ./scripts/dev.sh run"
    echo "  2. Run tests: ./scripts/dev.sh test"
    echo "  3. Monitor logs: ./scripts/dev.sh logs"
}

# Function to run Hestia locally
run_hestia() {
    print_header
    echo "🔄 Starting Hestia with hot reload..."
    echo "📡 API will be available at: http://localhost:8080"
    echo "🛑 Press Ctrl+C to stop"
    echo ""
    
    # Check if dependencies are running
    if ! docker-compose -f docker-compose.dev.yml ps --services --filter "status=running" | grep -q semaphore; then
        print_warning "Dependencies not running. Starting them first..."
        ./scripts/dev-env.sh start
    fi
    
    uv run uvicorn hestia.app:app --port 8080 --reload
}

# Function to run tests
run_tests() {
    print_header
    echo "🧪 Running tests..."
    
    case "${2:-all}" in
        contract)
            echo "📋 Running contract tests..."
            uv run pytest tests/contract/ -v
            ;;
        integration)
            echo "🔗 Running integration tests..."
            uv run pytest tests/integration/ -v
            ;;
        unit)
            echo "🔬 Running unit tests..."
            uv run pytest tests/unit/ -v
            ;;
        semaphore)
            echo "🤖 Running Semaphore-specific tests..."
            uv run pytest tests/contract/test_contract_semaphore.py tests/integration/test_semaphore_startup.py tests/integration/test_semaphore_shutdown.py -v
            ;;
        coverage)
            echo "📊 Running tests with coverage..."
            uv run pytest --cov=src/hestia --cov-report=html --cov-report=term
            print_success "Coverage report generated in htmlcov/"
            ;;
        all)
            echo "🔍 Running all tests..."
            uv run pytest -v
            ;;
        *)
            echo "❓ Running specific test: $2"
            uv run pytest "$2" -v
            ;;
    esac
}

# Function to show logs
show_logs() {
    print_header
    echo "📋 Showing dependency logs..."
    ./scripts/dev-env.sh logs
}

# Function to reset environment
reset_env() {
    print_header
    echo "🧹 Resetting development environment..."
    ./scripts/dev-env.sh reset
    print_success "Environment reset complete!"
}

# Function to check status
check_status() {
    print_header
    ./scripts/dev-env.sh status
    
    echo ""
    echo "🔍 Quick health checks:"
    
    # Check if Hestia port is available
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        print_success "Hestia is running on port 8080"
    else
        print_warning "Hestia is not running on port 8080"
    fi
    
    # Check if Semaphore is accessible
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        print_success "Semaphore is accessible on port 3000"
    else
        print_warning "Semaphore is not accessible on port 3000"
    fi
}

# Function to stop everything
stop_all() {
    print_header
    echo "🛑 Stopping all services..."
    
    # Stop any local Hestia process
    pkill -f "uvicorn hestia.app:app" 2>/dev/null || true
    
    # Stop dependencies
    ./scripts/dev-env.sh stop
    
    print_success "All services stopped"
}

# Function to show quick API tests
api_test() {
    print_header
    echo "🌐 Running quick API tests..."
    
    echo "Testing Hestia health endpoint..."
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        print_success "Hestia health check passed"
    else
        print_error "Hestia is not responding"
        return 1
    fi
    
    echo "Testing Semaphore ping..."
    if curl -s http://localhost:3000/api/ping > /dev/null 2>&1; then
        print_success "Semaphore ping successful"
    else
        print_warning "Semaphore ping failed (may not be fully ready)"
    fi
    
    echo "Testing service status endpoint..."
    curl -s http://localhost:8080/v1/services/ollama/status | head -c 200
    echo ""
}

# Main command handling
case "${1:-setup}" in
    setup)
        dev_setup
        ;;
    run)
        run_hestia
        ;;
    test)
        run_tests "$@"
        ;;
    logs)
        show_logs
        ;;
    status)
        check_status
        ;;
    reset)
        reset_env
        ;;
    stop)
        stop_all
        ;;
    api)
        api_test
        ;;
    help|--help|-h)
        print_header
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  setup              Set up complete development environment (default)"
        echo "  run                Run Hestia locally with hot reload"
        echo "  test [type]        Run tests (all|contract|integration|unit|semaphore|coverage|<path>)"
        echo "  logs               Show dependency logs"
        echo "  status             Show environment status and health checks"
        echo "  reset              Reset environment (deletes data)"
        echo "  stop               Stop all services (Hestia + dependencies)"
        echo "  api                Run quick API tests"
        echo "  help               Show this help"
        echo ""
        echo "Examples:"
        echo "  $0 setup                          # Full environment setup"
        echo "  $0 run                           # Run Hestia with hot reload"
        echo "  $0 test semaphore                # Run Semaphore tests"
        echo "  $0 test coverage                 # Run tests with coverage"
        echo "  $0 test tests/unit/test_config.py  # Run specific test"
        echo "  $0 api                           # Quick API health check"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Run '$0 help' for usage information."
        exit 1
        ;;
esac