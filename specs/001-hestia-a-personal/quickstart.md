# Quickstart: Hestia - Personal On-Demand Service Gateway

## Prerequisites
- Docker and docker-compose installed
- Linux environment recommended
- `curl` for testing (optional)

## One-command startup

```bash
# From repo root
docker compose up -d
```

This starts:
- **hestia** (FastAPI app on port 8080)
- **semaphore** (Ansible Semaphore for automation)

## Configuration
- `hestia_config.yml` and `strategies/` are mounted as bind volumes for live development
- SQLite DB persisted to named volume `hestia_sqlite`
- Semaphore config persisted to named volume `semaphore_data`
- Structured logging with request IDs enabled by default

## Core API Endpoints

### Service Management
```bash
# Check service status
curl http://localhost:8080/v1/services/ollama/status

# Start a service proactively 
curl -X POST http://localhost:8080/v1/services/ollama/start

# Get service-specific metrics
curl http://localhost:8080/v1/services/ollama/metrics
```

### Transparent Proxy (Recommended)
**Use this URL pattern for unmodified clients:**
```bash
# Direct proxy to Ollama API
curl http://localhost:8080/services/ollama/api/tags

# List models through Hestia proxy
curl http://localhost:8080/services/ollama/api/tags

# Generate completion through proxy
curl -X POST http://localhost:8080/services/ollama/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama2", "prompt": "Hello world"}'
```

### Gateway Dispatcher
```bash
# Generic request dispatcher
curl -X POST http://localhost:8080/v1/requests \
  -H "Content-Type: application/json" \
  -d '{
    "serviceId": "ollama",
    "method": "GET", 
    "path": "/api/tags"
  }'
```

### Monitoring & Observability
```bash
# Global metrics (counters, timers, gauges)
curl http://localhost:8080/v1/metrics

# Service-specific metrics
curl http://localhost:8080/v1/services/ollama/metrics

# Health check (returns service status)
curl http://localhost:8080/v1/services/ollama/status
```

## Client Configuration

### Ollama
Set the base URL to use Hestia as a transparent proxy:
```bash
export OLLAMA_BASE_URL=http://localhost:8080/services/ollama
```

Then use Ollama normally:
```bash
ollama list                    # → GET /services/ollama/api/tags
ollama run llama2 "Hello"      # → POST /services/ollama/api/generate
```

### Other Services
For any service configured in `hestia_config.yml`:
```bash
# Replace service's base URL with:
http://localhost:8080/services/{serviceId}/

# Example for a custom service "myapi":
curl http://localhost:8080/services/myapi/health
curl http://localhost:8080/services/myapi/data
```

## API Authentication (Optional)
When authentication is enabled:

```bash
# API Key authentication
curl -H "X-API-Key: your-api-key" \
  http://localhost:8080/v1/services/ollama/status

# Or Bearer token
curl -H "Authorization: Bearer your-api-key" \
  http://localhost:8080/v1/services/ollama/status
```

Dashboard uses username/password when enabled (see configuration).

## Response Examples

### Service Status
```bash
curl http://localhost:8080/v1/services/ollama/status
```
```json
{
  "serviceId": "ollama",
  "state": "hot",
  "machineId": "local", 
  "readiness": "ready",
  "queuePending": 0
}
```

### Metrics
```bash
curl http://localhost:8080/v1/metrics
```
```json
{
  "counters": {
    "requests_total[method=GET,path=/v1/services/{serviceId}/status]": {
      "count": 5,
      "timestamp": "2025-09-09T05:30:00Z"
    }
  },
  "timers": {
    "request_duration_ms[method=GET]": {
      "count": 5,
      "avg_ms": 2.1,
      "min_ms": 1.2,
      "max_ms": 4.5
    }
  },
  "services": {
    "ollama": {
      "counters": {...},
      "timers": {...}
    }
  }
}
```

## Testing & Development

### Run Tests
```bash
# Full test suite
pytest -q

# Specific test categories
pytest tests/unit/ -v           # Unit tests
pytest tests/integration/ -v    # Integration tests
```

### Development Mode
```bash
# Start with live reloading
uvicorn hestia.app:app --reload --host 0.0.0.0 --port 8080

# Check logs (structured JSON format)
docker compose logs -f hestia
```

## Request Flow Examples

### Cold Service Startup
```bash
# 1. Service is cold initially
curl http://localhost:8080/v1/services/ollama/status
# {"state": "cold", "readiness": "not_ready", ...}

# 2. Make request → service starts automatically  
curl http://localhost:8080/services/ollama/api/tags
# Request queued while service starts, then proxied

# 3. Service is now hot
curl http://localhost:8080/v1/services/ollama/status  
# {"state": "hot", "readiness": "ready", ...}
```

### Proactive Warmup
```bash
# Start service before it's needed
curl -X POST http://localhost:8080/v1/services/ollama/start

# Subsequent requests are fast (no startup delay)
curl http://localhost:8080/services/ollama/api/tags
```

## Troubleshooting

### Common Issues
```bash
# Service not responding
curl http://localhost:8080/v1/services/ollama/status
# Check: state, readiness, queuePending

# View service logs  
docker compose logs -f hestia

# Check metrics for errors
curl http://localhost:8080/v1/metrics | jq '.counters | to_entries | map(select(.key | contains("error")))'
```

### Log Analysis
Hestia provides structured logs with request IDs:
```json
{
  "timestamp": "2025-09-09T05:30:00Z",
  "level": "INFO",
  "event_type": "service_start", 
  "service_id": "ollama",
  "request_id": "req_abc123",
  "message": "Starting service: ollama"
}
```

Track requests across the system using the `request_id` field.

## Configuration Files

- **`hestia_config.yml`** - Service definitions, timeouts, URLs
- **`strategies/`** - Custom startup strategies (see examples)
- **Docker Compose** - Container orchestration and networking

## Next Steps

1. **Configure your services** in `hestia_config.yml`
2. **Set client base URLs** to use Hestia proxy  
3. **Enable authentication** for production deployment

## Strategy-based Routing

Hestia supports strategy-based routing to distribute requests across multiple instances:

### Model-aware Routing
Configure different models to route to different instances:

```yaml
# hestia_config.yml
services:
  my-llm:
    base_url: "http://fallback-llm:11434"
    strategy: "model_router"
    instances:
      - { url: "http://llm-a:11434" }
      - { url: "http://llm-b:11434" }
    routing:
      model_key: "model"
      by_model:
        llama3: "http://llm-a:11434"
        mistral: "http://llm-b:11434"
```

Test model routing:
```bash
# Routes to llm-a
curl -X POST http://localhost:8080/services/my-llm/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3", "prompt": "Hello"}'

# Routes to llm-b  
curl -X POST http://localhost:8080/services/my-llm/api/generate \
  -H "Content-Type: application/json" \
  -d '{"model": "mistral", "prompt": "Hello"}'
```

### Load Balancer Strategy
Distribute requests across instances with health tracking:

```yaml
services:
  my-service:
    strategy: "load_balancer"
    instances:
      - { url: "http://service-a:8080", region: "us-east" }
      - { url: "http://service-b:8080", region: "us-west" }
```

### Strategy Inspection
View loaded strategies and configurations:
```bash
curl http://localhost:8080/v1/strategies | jq .
```

Returns:
```json
{
  "loaded_strategies": {
    "load_balancer": {
      "name": "load_balancer",
      "version": "1.0.0",
      "features": ["round_robin_selection", "health_tracking"]
    },
    "model_router": {
      "name": "model_router",
      "version": "1.0.0"
    }
  },
  "service_configurations": {
    "my-llm": {
      "strategy": "model_router",
      "instances": [...],
      "routing": {...}
    }
  }
}
```
4. **Monitor metrics** for performance optimization
5. **Customize strategies** for complex startup requirements

For authentication setup, see the Authentication Documentation (coming soon).
