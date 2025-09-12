# Hestia - Personal On-Demand Service Gateway

🏠 **Personal service orchestration with transparent proxying and intelligent queue management.**

## Quick Start

```bash
# Clone and start
cd Hestia
docker compose up -d

# Test the gateway
curl http://localhost:8080/v1/services/ollama/status
```

**That's it!** Hestia is now running and ready to manage your services.

## What is Hestia?

Hestia is a **personal service gateway** that:
- 🔄 **Transparently proxies** requests to backend services  
- ⚡ **Automatically starts** cold services on-demand
- 🤖 **Orchestrates remote services** via Semaphore automation (cloud VMs, GPU servers)
- 📊 **Provides observability** with metrics and structured logging
- 🔒 **Secures access** with optional authentication
- 🎯 **Queues requests** during service startup for zero downtime

Perfect for **personal development environments**, **home labs**, **cloud cost optimization**, and **small deployments** where you want professional-grade service management without complexity.

## 🤖 Semaphore Automation (New!)

Hestia now integrates with **Semaphore** for powerful remote service orchestration:

```bash
# Enable automation for any service
export MYSERVICE_SEMAPHORE_ENABLED=true
export MYSERVICE_SEMAPHORE_MACHINE_ID="aws-gpu-instance"
export SEMAPHORE_BASE_URL="http://semaphore:3000"

# This request will automatically provision cloud VMs and start services
curl http://localhost:8080/services/myservice/api/status
```

**Use Cases:**
- 💰 **Cloud Cost Optimization**: Auto-provision VMs only when needed
- 🖥️ **GPU Resource Management**: Share expensive GPU servers efficiently  
- 🔄 **Development Environments**: Spin up dev environments on demand
- 🌍 **Multi-Region Deployment**: Deploy services to optimal regions automatically

See [Semaphore Integration Guide](docs/semaphore-integration.md) for full setup instructions.

## Key Features

### 🔄 Transparent Proxy
```bash
# Instead of: http://localhost:11434/api/tags
curl http://localhost:8080/services/ollama/api/tags

# Works with any client:
export OLLAMA_BASE_URL=http://localhost:8080/services/ollama
ollama list  # Just works!
```

### ⚡ Smart Service Management
- **Cold Start**: Services start automatically when first accessed
- **Hot Standby**: Keep frequently used services warm
- **Idle Shutdown**: Automatic cleanup to save resources
- **Queue Management**: Requests wait gracefully during startup

### 📊 Built-in Observability  
```bash
# Service status
curl http://localhost:8080/v1/services/ollama/status

# System metrics  
curl http://localhost:8080/v1/metrics

# Structured logs with request tracing
docker compose logs -f hestia
```

### 🎯 Zero Configuration
Works out of the box with sensible defaults. Customize with `hestia_config.yml` when needed.

## Documentation

### 🚀 Getting Started
- **[📚 Quickstart Guide](specs/001-hestia-a-personal/quickstart.md)** - Complete setup and usage examples
- **[⚙️ Configuration Reference](docs/configuration-reference.md)** - All configuration options with examples

### 🤖 Advanced Features  
- **[🎯 Semaphore Integration](docs/semaphore-integration.md)** - Remote service orchestration setup
- **[🔧 Troubleshooting Guide](docs/troubleshooting.md)** - Common issues and solutions
- **[📋 Strategy Development](strategies/README.md)** - Custom routing and load balancing

### 📖 Reference
- **[🌐 API Documentation](specs/001-hestia-a-personal/contracts/openapi.yaml)** - OpenAPI specification
- **[🏗️ Architecture](specs/001-hestia-a-personal/spec.md)** - System design and patterns
- **[🔒 Security](specs/001-hestia-a-personal/)** - Authentication and best practices

## Development

### Quick Development Setup

```bash
# One command setup - starts dependencies and shows next steps
./scripts/dev.sh setup

# Run Hestia locally with hot reload  
./scripts/dev.sh run

# Run tests (contract/integration/unit/semaphore/coverage)
./scripts/dev.sh test semaphore

# Check status and health
./scripts/dev.sh status

# Stop everything
./scripts/dev.sh stop
```

See **[DEV_ENVIRONMENT.md](DEV_ENVIRONMENT.md)** for complete development guide.

### Development URLs

- **Hestia**: http://localhost:8080 (run locally)
- **Semaphore UI**: http://localhost:3000 (admin/admin)

## Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Client    │───▶│   Hestia    │───▶│  Services   │
│             │    │   Gateway   │    │ (Ollama,    │
│ (Unchanged) │    │             │    │  Custom)    │
└─────────────┘    └─────────────┘    └─────────────┘
                          │
                          ▼
                   ┌─────────────┐
                   │  Semaphore  │
                   │ (Automation)│
                   └─────────────┘
```

**Hestia sits between your clients and services**, providing intelligent routing, lifecycle management, and observability without requiring changes to existing applications.

## Use Cases

- **🏠 Home Lab**: Manage multiple self-hosted services efficiently
- **💻 Development**: Hot-reload services in development environments  
- **🔬 Experimentation**: Quick testing with automatic service orchestration
- **📱 Personal AI**: Gateway for local AI services (Ollama, etc.)
- **🔧 Prototyping**: Rapid service composition and testing

## Technology Stack

- **FastAPI** - High-performance async web framework
- **SQLite** - Embedded database for state persistence  
- **Docker** - Containerized deployment
- **Semaphore** - Ansible automation engine
- **Structured Logging** - JSON logs with request tracing
- **Metrics Collection** - Built-in performance monitoring

## Status

✅ **Production Ready** for personal use  
🔧 **Active Development** - New features regularly added  
📖 **Well Documented** - Comprehensive guides and examples  
🧪 **Thoroughly Tested** - Extensive test coverage

## License

[License details here]

## Contributing

Contributions welcome! See our [development guide](tests/) and [task list](specs/001-hestia-a-personal/tasks.md).

---

**Get started in 30 seconds**: `docker compose up -d` → `curl http://localhost:8080/v1/services/ollama/status` ✨