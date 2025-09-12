# Development Environment Guide

This guide shows how to use the new development environment setup for Hestia development.

## Quick Start

```bash
# Start dependencies (Semaphore) in Docker
./scripts/dev-env.sh start

# Run Hestia locally with hot reload
uv run uvicorn hestia.app:app --port 8080 --reload

# In another terminal, run tests
uv run pytest tests/integration/test_semaphore_startup.py -v
```

## Development Workflow

### 1. Start Development Environment
```bash
./scripts/dev-env.sh start
```
This starts:
- **Semaphore**: http://localhost:3000 (admin/admin)
- Creates Docker network and volumes
- Sets up health checks

### 2. Run Hestia Locally
```bash
# Terminal 1: Run Hestia with hot reload
uv run uvicorn hestia.app:app --port 8080 --reload

# Terminal 2: Run tests as you develop
uv run pytest tests/integration/test_semaphore_startup.py -v

# Terminal 3: Monitor dependency logs
./scripts/dev-env.sh logs
```

### 3. Access Services
- **Hestia API**: http://localhost:8080
- **Semaphore UI**: http://localhost:3000 (admin/admin)

## Development Commands

### Environment Management
```bash
./scripts/dev-env.sh start          # Start dependencies
./scripts/dev-env.sh stop           # Stop dependencies
./scripts/dev-env.sh restart        # Restart dependencies
./scripts/dev-env.sh status         # Show status and URLs
./scripts/dev-env.sh logs           # Follow dependency logs
./scripts/dev-env.sh reset          # Reset environment (deletes data)
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test suites
uv run pytest tests/contract/          # Contract tests
uv run pytest tests/integration/       # Integration tests
uv run pytest tests/unit/              # Unit tests

# Run Semaphore-specific tests
uv run pytest tests/contract/test_contract_semaphore.py -v
uv run pytest tests/integration/test_semaphore_startup.py -v
uv run pytest tests/integration/test_semaphore_shutdown.py -v

# Run with coverage
uv run pytest --cov=src/hestia
```

### API Testing
```bash
# Test Hestia endpoints
curl http://localhost:8080/v1/services/ollama/status

# Test Semaphore API (for T043 development)
curl http://localhost:3000/api/ping

# Test transparent proxy
curl http://localhost:8080/services/ollama/api/tags
```

## Benefits of This Setup

1. **Fast Development Cycle**: Only Hestia runs locally with hot reload
2. **Isolated Dependencies**: Semaphore runs in Docker with persistent data
3. **Easy Testing**: Integration tests work immediately with real Semaphore instance
4. **Clean State Management**: Easy to reset/restart dependencies
5. **Consistent Environment**: Same setup across all developers

## Troubleshooting

### Dependencies Won't Start
```bash
# Check Docker is running
docker ps

# View dependency logs
./scripts/dev-env.sh logs

# Reset environment
./scripts/dev-env.sh reset
```

### Semaphore Setup Issues
```bash
# Access Semaphore container directly
docker-compose -f docker-compose.dev.yml exec semaphore /bin/sh

# Check Semaphore logs
docker-compose -f docker-compose.dev.yml logs semaphore

# Reset Semaphore data
./scripts/dev-env.sh reset
```

### Port Conflicts
If ports 3000 or 8080 are in use:
- Stop conflicting services
- Or modify ports in `docker-compose.dev.yml`
- Update the script URLs accordingly