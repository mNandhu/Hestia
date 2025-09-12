# Configuration Reference

Complete reference for all Hestia configuration options, including traditional service management and Semaphore automation.

## Table of Contents

- [Configuration Sources](#configuration-sources)
- [Global Configuration](#global-configuration)
- [Service Configuration](#service-configuration)
- [Environment Variables](#environment-variables)
- [Semaphore Integration](#semaphore-integration)
- [Examples](#examples)
- [Validation Rules](#validation-rules)

## Configuration Sources

Hestia loads configuration from multiple sources in order of precedence:

1. **Environment Variables** (highest priority)
2. **YAML Configuration File** (`hestia_config.yml`)
3. **Default Values** (lowest priority)

### Configuration File Location

```bash
# Default location
./hestia_config.yml

# Custom location via environment
export HESTIA_CONFIG_PATH="/path/to/config.yml"
```

## Global Configuration

### Top-Level Settings

```yaml
# Global Semaphore automation settings
semaphore_base_url: "http://semaphore:3000"  # Semaphore server URL
semaphore_timeout: 30                        # HTTP timeout (seconds)

# Service definitions
services:
  # Individual service configurations
```

### Environment Variable Overrides

```bash
# Global Semaphore settings
export SEMAPHORE_BASE_URL="http://semaphore.local:3000"
export SEMAPHORE_TIMEOUT=60
```

## Service Configuration

Each service supports the following configuration options:

### Basic Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_url` | string | `"http://localhost:11434"` | Target service URL |
| `retry_count` | int | `1` | Number of retry attempts |
| `retry_delay_ms` | int | `0` | Delay between retries (milliseconds) |
| `fallback_url` | string | `null` | Backup service URL |

### Health & Startup

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `health_url` | string | `null` | Health check endpoint |
| `warmup_ms` | int | `0` | Startup delay if no health check |
| `idle_timeout_ms` | int | `0` | Auto-shutdown after inactivity (0=disabled) |

### Request Handling

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `queue_size` | int | `100` | Maximum queued requests |
| `request_timeout_seconds` | int | `60` | Request timeout |

### Strategy-Based Routing

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `strategy` | string | `null` | Routing strategy name |
| `instances` | array | `[]` | Upstream instances |
| `routing` | object | `{}` | Strategy-specific configuration |

### Semaphore Automation

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `semaphore_enabled` | bool | `false` | Enable Semaphore automation |
| `semaphore_machine_id` | string | `null` | Target machine identifier |
| `semaphore_start_template_id` | int | `1` | Start automation template |
| `semaphore_stop_template_id` | int | `2` | Stop automation template |
| `semaphore_task_timeout` | int | `300` | Task completion timeout (seconds) |
| `semaphore_poll_interval` | float | `2.0` | Status polling interval (seconds) |

## Environment Variables

### Service Configuration Pattern

Environment variables follow the pattern: `<SERVICE_ID>_<FIELD_NAME>`

```bash
# Examples
export OLLAMA_BASE_URL="http://remote:11434"
export OLLAMA_RETRY_COUNT=3
export OLLAMA_IDLE_TIMEOUT_MS=600000

export MYSERVICE_SEMAPHORE_ENABLED=true
export MYSERVICE_SEMAPHORE_MACHINE_ID="server-01"
```

### Service ID Transformation

- Service IDs are converted to uppercase
- Hyphens become underscores
- Example: `my-service` → `MY_SERVICE_*`

```bash
# Service: my-cloud-service
export MY_CLOUD_SERVICE_BASE_URL="http://cloud.local"
export MY_CLOUD_SERVICE_SEMAPHORE_ENABLED=true
```

### Field Type Conversion

| Type | Environment Value | Parsed Value |
|------|-------------------|--------------|
| `bool` | `"true"`, `"1"`, `"yes"`, `"on"` | `true` |
| `bool` | `"false"`, `"0"`, `"no"`, `"off"` | `false` |
| `int` | `"123"` | `123` |
| `float` | `"2.5"` | `2.5` |
| `string` | `"value"` | `"value"` |

## Semaphore Integration

### Required Settings

To enable Semaphore automation, you must set:

```bash
# Global Semaphore server
export SEMAPHORE_BASE_URL="http://semaphore:3000"

# Per-service settings
export MYSERVICE_SEMAPHORE_ENABLED=true
export MYSERVICE_SEMAPHORE_MACHINE_ID="target-machine"
```

### Template Configuration

```bash
# Optional: Custom template IDs
export MYSERVICE_SEMAPHORE_START_TEMPLATE_ID=10
export MYSERVICE_SEMAPHORE_STOP_TEMPLATE_ID=11

# Optional: Timing configuration
export MYSERVICE_SEMAPHORE_TASK_TIMEOUT=600      # 10 minutes
export MYSERVICE_SEMAPHORE_POLL_INTERVAL=5.0     # 5 seconds
```

### Template Variables

Hestia automatically provides these variables to Semaphore templates:

```yaml
# Standard variables
SERVICE_ID: "my-service"
MACHINE_ID: "target-server"
ACTION: "start"  # or "stop"

# Extra variables (from extra_vars in template)
extra_vars:
  service_id: "my-service"
  machine_id: "target-server"
```

## Examples

### 1. Simple Local Service

```yaml
# YAML Configuration
services:
  ollama:
    base_url: "http://localhost:11434"
    health_url: "http://localhost:11434/api/tags"
    retry_count: 2
    idle_timeout_ms: 300000
```

```bash
# Environment Configuration
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_HEALTH_URL="http://localhost:11434/api/tags"
export OLLAMA_RETRY_COUNT=2
export OLLAMA_IDLE_TIMEOUT_MS=300000
```

### 2. High-Availability Service

```yaml
services:
  api:
    base_url: "http://primary:8080"
    health_url: "http://primary:8080/health"
    retry_count: 3
    retry_delay_ms: 1000
    fallback_url: "http://secondary:8080"
    idle_timeout_ms: 0  # Never shutdown
    queue_size: 500
```

### 3. Cloud Service with Automation

```yaml
services:
  cloud-ml:
    base_url: "http://gpu-vm.aws.com:8080"
    retry_count: 2
    idle_timeout_ms: 1800000  # 30 minutes
    request_timeout_seconds: 180
    
    # Semaphore automation
    semaphore_enabled: true
    semaphore_machine_id: "aws-gpu-instance"
    semaphore_start_template_id: 10  # VM provision + start
    semaphore_stop_template_id: 11   # Stop + terminate
    semaphore_task_timeout: 600      # 10 minutes
    semaphore_poll_interval: 5.0
```

### 4. GPU Resource Management

```yaml
services:
  stable-diffusion:
    base_url: "http://gpu-server:7860"
    idle_timeout_ms: 900000  # 15 minutes
    
    semaphore_enabled: true
    semaphore_machine_id: "gpu-server-01"
    semaphore_start_template_id: 20  # Model load + start
    semaphore_stop_template_id: 21   # Stop + unload
    
  comfyui:
    base_url: "http://gpu-server:8188"
    idle_timeout_ms: 900000
    
    semaphore_enabled: true
    semaphore_machine_id: "gpu-server-01"  # Same server
    semaphore_start_template_id: 22
    semaphore_stop_template_id: 23
```

### 5. Development Environment

```bash
# Quick dev setup via environment
export DEV_ENV_BASE_URL="http://dev.local:8080"
export DEV_ENV_SEMAPHORE_ENABLED=true
export DEV_ENV_SEMAPHORE_MACHINE_ID="dev-vm-pool"
export DEV_ENV_IDLE_TIMEOUT_MS=300000           # 5 minutes
export DEV_ENV_SEMAPHORE_TASK_TIMEOUT=120       # 2 minutes
export DEV_ENV_SEMAPHORE_START_TEMPLATE_ID=30   # VM provision
export DEV_ENV_SEMAPHORE_STOP_TEMPLATE_ID=31    # VM destroy
```

### 6. Strategy-Based Routing

```yaml
services:
  load-balanced-api:
    strategy: "load_balancer"
    instances:
      - url: "http://api-1:8080"
        weight: 1
      - url: "http://api-2:8080"
        weight: 2
    routing:
      algorithm: "round_robin"
      
  model-router:
    strategy: "model_router"
    base_url: "http://default:11434"  # Fallback
    instances:
      - url: "http://gpu-1:11434"
        models: ["llama2", "codellama"]
      - url: "http://gpu-2:11434"
        models: ["mistral", "vicuna"]
    routing:
      model_key: "model"
      by_model:
        llama2: "http://gpu-1:11434"
        mistral: "http://gpu-2:11434"
```

## Validation Rules

### Required Fields

- `base_url`: Must be a valid HTTP/HTTPS URL
- `semaphore_machine_id`: Required if `semaphore_enabled=true`

### Constraints

```yaml
# Numeric constraints
retry_count: >= 0
retry_delay_ms: >= 0
warmup_ms: >= 0
idle_timeout_ms: >= 0
queue_size: >= 1
request_timeout_seconds: >= 1
semaphore_task_timeout: >= 1
semaphore_poll_interval: > 0.0

# Boolean fields
semaphore_enabled: true/false

# String fields
base_url: "http://" or "https://"
health_url: "http://" or "https://" or null
fallback_url: "http://" or "https://" or null
```

### Default Service

The `ollama` service is always present with defaults:

```yaml
ollama:
  base_url: "http://localhost:11434"
  retry_count: 1
  retry_delay_ms: 0
  health_url: null
  warmup_ms: 0
  idle_timeout_ms: 0
  fallback_url: null
  queue_size: 100
  request_timeout_seconds: 60
  semaphore_enabled: false
```

## Configuration Debugging

### Check Loaded Configuration

```bash
# Start Hestia with debug logging
export HESTIA_LOG_LEVEL=DEBUG
uv run uvicorn hestia.app:app --port 8080

# Look for configuration logs
grep "configuration" logs/hestia.log
```

### Test Service Configuration

```bash
# Check service status (shows loaded config)
curl http://localhost:8080/v1/services/myservice/status

# Verify environment variables
env | grep MYSERVICE
env | grep SEMAPHORE
```

### Validate YAML Syntax

```bash
# Check YAML syntax
python -c "import yaml; yaml.safe_load(open('hestia_config.yml'))"

# Or use yq
yq eval . hestia_config.yml
```

## Best Practices

### 1. Environment Organization

```bash
# Group related settings
# Service: cloud-ml-service
export CLOUD_ML_SERVICE_BASE_URL="http://gpu.cloud.com:8080"
export CLOUD_ML_SERVICE_SEMAPHORE_ENABLED=true
export CLOUD_ML_SERVICE_SEMAPHORE_MACHINE_ID="gpu-cloud-01"
export CLOUD_ML_SERVICE_IDLE_TIMEOUT_MS=1800000
```

### 2. Configuration Layering

```yaml
# Base configuration in YAML
services:
  api:
    base_url: "http://localhost:8080"
    retry_count: 2
    queue_size: 100
```

```bash
# Environment overrides for deployment
export API_BASE_URL="http://prod-api:8080"
export API_RETRY_COUNT=5
export API_FALLBACK_URL="http://backup-api:8080"
```

### 3. Semaphore Template IDs

```bash
# Use meaningful template ID patterns
export SERVICE_SEMAPHORE_START_TEMPLATE_ID=100  # Basic start
export SERVICE_SEMAPHORE_STOP_TEMPLATE_ID=101   # Basic stop

export GPU_SERVICE_SEMAPHORE_START_TEMPLATE_ID=200  # GPU start
export GPU_SERVICE_SEMAPHORE_STOP_TEMPLATE_ID=201   # GPU stop

export CLOUD_SERVICE_SEMAPHORE_START_TEMPLATE_ID=300  # VM provision
export CLOUD_SERVICE_SEMAPHORE_STOP_TEMPLATE_ID=301   # VM destroy
```

### 4. Timeout Guidelines

```yaml
# Service type-based timeouts
web-service:
  idle_timeout_ms: 300000           # 5 minutes
  semaphore_task_timeout: 60        # 1 minute
  semaphore_poll_interval: 1.0      # 1 second

ml-service:
  idle_timeout_ms: 1800000          # 30 minutes
  semaphore_task_timeout: 600       # 10 minutes
  semaphore_poll_interval: 5.0      # 5 seconds

cloud-service:
  idle_timeout_ms: 900000           # 15 minutes
  semaphore_task_timeout: 900       # 15 minutes
  semaphore_poll_interval: 10.0     # 10 seconds
```

### 5. Development vs Production

```bash
# Development: Fast iteration
export DEV_SERVICE_IDLE_TIMEOUT_MS=60000        # 1 minute
export DEV_SERVICE_SEMAPHORE_TASK_TIMEOUT=60    # 1 minute
export DEV_SERVICE_SEMAPHORE_POLL_INTERVAL=1.0  # 1 second

# Production: Stability
export PROD_SERVICE_IDLE_TIMEOUT_MS=0           # Never shutdown
export PROD_SERVICE_SEMAPHORE_TASK_TIMEOUT=300  # 5 minutes
export PROD_SERVICE_SEMAPHORE_POLL_INTERVAL=5.0 # 5 seconds
```

## Migration Guide

### From Simple to Semaphore

1. **Start with basic configuration**:
```yaml
my-service:
  base_url: "http://target:8080"
  idle_timeout_ms: 600000
```

2. **Add Semaphore settings**:
```yaml
my-service:
  base_url: "http://target:8080"
  idle_timeout_ms: 600000
  
  # Add Semaphore automation
  semaphore_enabled: true
  semaphore_machine_id: "target-server"
```

3. **Test and tune**:
```bash
# Monitor logs for Semaphore operations
docker logs hestia | grep semaphore

# Adjust timeouts based on actual performance
export MY_SERVICE_SEMAPHORE_TASK_TIMEOUT=180
```

### Environment Variable Migration

```bash
# Old: Ollama-specific
export OLLAMA_BASE_URL="http://remote:11434"

# New: Any service
export OLLAMA_BASE_URL="http://remote:11434"
export MYSERVICE_BASE_URL="http://other:8080"
export MYSERVICE_SEMAPHORE_ENABLED=true
```

For more examples and patterns, see:
- [Semaphore Integration Guide](semaphore-integration.md)
- [Quickstart Guide](../specs/001-hestia-a-personal/quickstart.md)
- [Example configurations](../hestia_config.yml)