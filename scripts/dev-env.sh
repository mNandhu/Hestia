#!/bin/bash

# Development environment setup script for Hestia
# This script starts only the dependencies in Docker while allowing Hestia to run locally

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "🚀 Starting Hestia development environment..."

# Function to check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        echo "❌ Error: Docker is not running. Please start Docker first."
        exit 1
    fi
}

# Function to start dependencies
start_deps() {
    echo "📦 Starting dependencies (Semaphore)..."
    docker-compose -f docker-compose.dev.yml up -d
    
    echo "⏳ Waiting for Semaphore to be ready..."
    timeout 90 bash -c 'until curl -s http://localhost:3000 > /dev/null 2>&1; do sleep 3; done' || {
        echo "❌ Semaphore failed to start within 90 seconds"
        echo "📋 Checking logs..."
        docker-compose -f docker-compose.dev.yml logs --tail 50 semaphore
        exit 1
    }
    
    echo "✅ Dependencies are ready!"
}

# Function to stop dependencies
stop_deps() {
    echo "🛑 Stopping dependencies..."
    docker-compose -f docker-compose.dev.yml down
}

# Function to show status
show_status() {
    echo "📊 Development environment status:"
    docker-compose -f docker-compose.dev.yml ps
    echo ""
    echo "🌐 Service URLs:"
    echo "  Semaphore UI: http://localhost:3000"
    echo "    Username: admin"
    echo "    Password: admin"
    echo ""
    echo "💻 To run Hestia locally:"
    echo "  uv run uvicorn hestia.app:app --port 8080 --reload"
}

# Function to show logs
show_logs() {
    docker-compose -f docker-compose.dev.yml logs -f
}

# Function to reset environment (clean volumes)
reset_env() {
    echo "⚠️  This will delete all Semaphore data. Continue? (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        echo "🧹 Resetting development environment..."
        docker-compose -f docker-compose.dev.yml down -v
        docker-compose -f docker-compose.dev.yml up -d
        echo "✅ Environment reset complete!"
    else
        echo "❌ Reset cancelled."
    fi
}

# Main command handling
case "${1:-start}" in
    start)
        check_docker
        start_deps
        show_status
        ;;
    stop)
        stop_deps
        ;;
    restart)
        check_docker
        stop_deps
        start_deps
        show_status
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    reset)
        check_docker
        reset_env
        ;;
    help|--help|-h)
        echo "Hestia Development Environment"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start    Start dependencies (default)"
        echo "  stop     Stop dependencies"
        echo "  restart  Restart dependencies"
        echo "  status   Show status and URLs"
        echo "  logs     Show dependency logs"
        echo "  reset    Reset environment (deletes data)"
        echo "  help     Show this help"
        echo ""
        echo "Examples:"
        echo "  $0                    # Start dependencies"
        echo "  $0 status             # Check what's running"
        echo "  $0 logs               # Follow logs"
        echo "  $0 stop               # Stop everything"
        ;;
    *)
        echo "❌ Unknown command: $1"
        echo "Run '$0 help' for usage information."
        exit 1
        ;;
esac