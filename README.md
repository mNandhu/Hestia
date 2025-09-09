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
- 📊 **Provides observability** with metrics and structured logging
- 🔒 **Secures access** with optional authentication
- 🎯 **Queues requests** during service startup for zero downtime

Perfect for **personal development environments**, **home labs**, and **small deployments** where you want professional-grade service management without complexity.

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

- **[📚 Quickstart Guide](specs/001-hestia-a-personal/quickstart.md)** - Complete setup and usage examples
- **[⚙️ Configuration](examples/)** - Service definitions and strategies  
- **[🔒 Security](specs/001-hestia-a-personal/)** - Authentication and best practices (coming soon)
- **[🧪 Development](tests/)** - Testing and contributing

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