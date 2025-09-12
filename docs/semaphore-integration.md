# Semaphore Integration Guide

This guide covers how to integrate Hestia with Semaphore for remote service orchestration, including setup, configuration, and real-world usage patterns.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Setup](#setup)
- [Configuration](#configuration)
- [Usage Patterns](#usage-patterns)
- [Semaphore Templates](#semaphore-templates)
- [Best Practices](#best-practices)
- [Troubleshooting](#troubleshooting)

## Overview

Hestia's Semaphore integration enables **remote service orchestration** through Ansible automation. This powerful combination allows you to:

- **Automatically provision** cloud VMs when services are accessed
- **Start/stop services** on remote machines based on demand
- **Manage GPU resources** efficiently with automated scheduling
- **Implement cost optimization** through intelligent startup/shutdown
- **Scale services dynamically** across multiple machines/regions

### How It Works

1. **Cold Service Request**: User accesses a Semaphore-enabled service
2. **Automation Trigger**: Hestia calls Semaphore API to start the service
3. **Remote Execution**: Semaphore runs Ansible playbooks on target machines
4. **Status Polling**: Hestia monitors task completion
5. **Service Ready**: Requests are forwarded to the now-running service
6. **Auto Shutdown**: After idle timeout, Hestia triggers shutdown automation

## Quick Start

### 1. Enable Semaphore Globally

```bash
# Set Semaphore server URL
export SEMAPHORE_BASE_URL="http://semaphore:3000"

# Start Hestia
uv run uvicorn hestia.app:app --port 8080
```

### 2. Configure a Service with Semaphore

```bash
# Enable Semaphore for a service via environment variables
export MYSERVICE_BASE_URL="http://target.local:8080"
export MYSERVICE_SEMAPHORE_ENABLED=true
export MYSERVICE_SEMAPHORE_MACHINE_ID="my-server"
export MYSERVICE_IDLE_TIMEOUT_MS=300000  # 5 minutes
```

### 3. Access the Service

```bash
# This will trigger Semaphore automation to start the service
curl http://localhost:8080/services/myservice/api/status
```

Hestia will:
1. Detect the service is cold
2. Call Semaphore to run the start template on `my-server`
3. Wait for the task to complete
4. Forward your request to the running service

## Setup

### Prerequisites

- **Semaphore Server**: Running and accessible from Hestia
- **Target Machines**: Configured in Semaphore with SSH access
- **Ansible Playbooks**: Templates for starting/stopping services
- **Network Access**: Hestia can reach both Semaphore and target services

### 1. Semaphore Server Setup

```bash
# Using Docker Compose (recommended)
docker run -d \
  --name semaphore \
  -p 3000:3000 \
  -e SEMAPHORE_ADMIN=admin \
  -e SEMAPHORE_ADMIN_PASSWORD=admin \
  -e SEMAPHORE_ADMIN_NAME=Administrator \
  -e SEMAPHORE_ADMIN_EMAIL=admin@example.com \
  semaphoreui/semaphore:latest
```

### 2. Configure Semaphore Projects

1. **Access Semaphore UI**: http://localhost:3000 (admin/admin)
2. **Create Project**: Name it "hestia-services"
3. **Add Key Store**: SSH keys for target machines
4. **Add Inventory**: Define your target machines
5. **Create Templates**: Ansible playbooks for service operations

### 3. Test Semaphore API

```bash
# Verify Semaphore is accessible
curl http://localhost:3000/api/ping

# Test task creation (requires auth)
curl -X POST http://localhost:3000/api/project/1/tasks \
  -H "Content-Type: application/json" \
  -d '{"template_id": 1}'
```

## Configuration

### Service Configuration

Services can be configured via `hestia_config.yml` or environment variables:

#### YAML Configuration

```yaml
services:
  my-cloud-service:
    # Standard service settings
    base_url: "http://cloud-vm.example.com:8080"
    retry_count: 2
    idle_timeout_ms: 1800000  # 30 minutes
    
    # Semaphore automation settings
    semaphore_enabled: true
    semaphore_machine_id: "cloud-vm-01"
    semaphore_start_template_id: 1
    semaphore_stop_template_id: 2
    semaphore_task_timeout: 300
    semaphore_poll_interval: 2.0
```

#### Environment Variables

```bash
# Service configuration
export MYSERVICE_BASE_URL="http://target.local:8080"
export MYSERVICE_SEMAPHORE_ENABLED=true
export MYSERVICE_SEMAPHORE_MACHINE_ID="target-server"

# Optional: Custom template IDs
export MYSERVICE_SEMAPHORE_START_TEMPLATE_ID=5
export MYSERVICE_SEMAPHORE_STOP_TEMPLATE_ID=6

# Optional: Timing configuration  
export MYSERVICE_SEMAPHORE_TASK_TIMEOUT=600      # 10 minutes
export MYSERVICE_SEMAPHORE_POLL_INTERVAL=5.0     # 5 seconds

# Global Semaphore URL
export SEMAPHORE_BASE_URL="http://semaphore:3000"
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `semaphore_enabled` | bool | false | Enable Semaphore automation |
| `semaphore_machine_id` | string | required | Target machine ID in Semaphore |
| `semaphore_start_template_id` | int | 1 | Template for service startup |
| `semaphore_stop_template_id` | int | 2 | Template for service shutdown |
| `semaphore_task_timeout` | int | 300 | Max time to wait for tasks (seconds) |
| `semaphore_poll_interval` | float | 2.0 | Status polling interval (seconds) |

### Global Configuration

```yaml
# Global Semaphore settings
semaphore_base_url: "http://semaphore:3000"
semaphore_timeout: 30  # HTTP timeout for API calls
```

## Usage Patterns

### 1. Cloud Cost Optimization

**Scenario**: Automatically provision cloud VMs only when needed

```yaml
cloud-ml-service:
  base_url: "http://gpu-vm.aws.com:8080"
  idle_timeout_ms: 600000  # 10 minutes
  
  semaphore_enabled: true
  semaphore_machine_id: "aws-gpu-instance"
  semaphore_start_template_id: 10  # VM provision + service start
  semaphore_stop_template_id: 11   # Service stop + VM terminate
  semaphore_task_timeout: 600      # 10 minutes for VM startup
```

**Benefits**:
- Pay only for compute time actually used
- Automatic VM provisioning and termination
- No manual intervention required

### 2. GPU Resource Management

**Scenario**: Share expensive GPU servers across multiple services

```yaml
stable-diffusion:
  base_url: "http://gpu-server:7860"
  idle_timeout_ms: 900000  # 15 minutes
  
  semaphore_enabled: true
  semaphore_machine_id: "gpu-server-01"
  semaphore_start_template_id: 20  # Load model + start service
  semaphore_stop_template_id: 21   # Stop service + unload model
  
comfyui:
  base_url: "http://gpu-server:8188"
  idle_timeout_ms: 900000
  
  semaphore_enabled: true
  semaphore_machine_id: "gpu-server-01"  # Same server!
  semaphore_start_template_id: 22
  semaphore_stop_template_id: 23
```

**Benefits**:
- Efficient GPU utilization
- Automatic model loading/unloading
- Resource conflict prevention

### 3. Development Environment Automation

**Scenario**: Spin up development environments on demand

```yaml
dev-workspace:
  base_url: "http://dev-vm.local:8080"
  idle_timeout_ms: 300000  # 5 minutes (aggressive for dev)
  
  semaphore_enabled: true
  semaphore_machine_id: "dev-vm-pool"
  semaphore_start_template_id: 30  # VM clone + setup
  semaphore_stop_template_id: 31   # Cleanup + destroy
  semaphore_task_timeout: 180      # 3 minutes
```

**Benefits**:
- Fast environment provisioning
- Automatic cleanup
- Resource conservation

### 4. Multi-Region Deployment

**Scenario**: Deploy services to the optimal region based on demand

```yaml
global-api:
  base_url: "http://api.us-east.example.com:8080"
  
  semaphore_enabled: true
  semaphore_machine_id: "global-lb"
  semaphore_start_template_id: 40  # Region selection + deployment
  semaphore_stop_template_id: 41   # Graceful shutdown + cleanup
```

**Benefits**:
- Latency optimization
- Geographic load distribution
- Automatic failover

## Semaphore Templates

### Template Types

Hestia works with various Semaphore template patterns:

#### 1. Basic Service Management

```yaml
# Template 1: Generic Service Start
- name: Start service
  systemd:
    name: "{{ service_name }}"
    state: started
    enabled: yes

# Template 2: Generic Service Stop  
- name: Stop service
  systemd:
    name: "{{ service_name }}"
    state: stopped
```

#### 2. Docker Container Management

```yaml
# Template 3: Docker Container Start
- name: Start container
  docker_container:
    name: "{{ container_name }}"
    image: "{{ image_name }}"
    state: started
    ports:
      - "{{ service_port }}:{{ container_port }}"

# Template 4: Docker Container Stop
- name: Stop container
  docker_container:
    name: "{{ container_name }}"
    state: stopped
```

#### 3. Cloud VM Management

```yaml
# Template 10: AWS Instance Provision
- name: Launch EC2 instance
  amazon.aws.ec2:
    key_name: "{{ key_pair }}"
    instance_type: "{{ instance_type }}"
    image: "{{ ami_id }}"
    wait: yes
    state: present
    tags:
      Name: "{{ service_id }}-instance"

# Template 11: AWS Instance Terminate
- name: Terminate EC2 instance
  amazon.aws.ec2:
    filters:
      "tag:Name": "{{ service_id }}-instance"
    state: absent
```

#### 4. GPU Model Management

```yaml
# Template 20: Load ML Model
- name: Download model
  get_url:
    url: "{{ model_url }}"
    dest: "/models/{{ model_name }}"
    
- name: Start GPU service
  docker_container:
    name: "{{ service_name }}"
    image: "{{ gpu_image }}"
    runtime: nvidia
    state: started

# Template 21: Unload ML Model
- name: Stop GPU service
  docker_container:
    name: "{{ service_name }}"
    state: stopped
    
- name: Cleanup model files
  file:
    path: "/models/{{ model_name }}"
    state: absent
```

### Template Variables

Hestia automatically provides these variables to Semaphore templates:

```yaml
# Automatic variables
service_id: "my-service"        # Service identifier
machine_id: "target-server"     # Target machine ID
action: "start"                 # "start" or "stop"

# Custom variables (via environment)
extra_vars:
  service_port: 8080
  container_name: "my-app"
  model_name: "llama-7b"
```

## Best Practices

### 1. Timeout Configuration

```yaml
# Light services (web apps)
semaphore_task_timeout: 60      # 1 minute
semaphore_poll_interval: 1.0    # 1 second

# Heavy services (ML models)  
semaphore_task_timeout: 600     # 10 minutes
semaphore_poll_interval: 5.0    # 5 seconds

# Cloud provisioning
semaphore_task_timeout: 900     # 15 minutes
semaphore_poll_interval: 10.0   # 10 seconds
```

### 2. Error Handling

```yaml
# Always set fallback behavior
services:
  my-service:
    semaphore_enabled: true
    # If Semaphore fails, use traditional startup
    warmup_ms: 5000  # Fallback timing
    health_url: "http://target:8080/health"
```

### 3. Resource Management

```yaml
# Group related services by machine
gpu-services:
  stable-diffusion:
    semaphore_machine_id: "gpu-01"
    semaphore_start_template_id: 100
    
  comfyui:
    semaphore_machine_id: "gpu-01"  # Same machine
    semaphore_start_template_id: 101  # Different template
```

### 4. Cost Optimization

```yaml
# Aggressive timeouts for cost-sensitive services
cloud-service:
  idle_timeout_ms: 300000        # 5 minutes
  semaphore_task_timeout: 120    # 2 minutes (fast provision)
  
# Conservative timeouts for production
prod-service:
  idle_timeout_ms: 3600000       # 1 hour
  semaphore_task_timeout: 300    # 5 minutes (reliable)
```

### 5. Development vs Production

```yaml
# Development: Fast iteration
dev-service:
  idle_timeout_ms: 60000         # 1 minute
  semaphore_poll_interval: 1.0   # Fast feedback
  
# Production: Stability
prod-service:
  idle_timeout_ms: 0             # Never auto-shutdown
  semaphore_poll_interval: 5.0   # Less aggressive polling
```

## Troubleshooting

### Common Issues

#### 1. Semaphore Connection Failed

**Symptoms**: `Semaphore client not available` errors

**Solutions**:
```bash
# Check Semaphore server status
curl http://semaphore:3000/api/ping

# Verify environment variable
echo $SEMAPHORE_BASE_URL

# Check network connectivity
ping semaphore
```

#### 2. Task Timeout

**Symptoms**: `Semaphore task failed: timeout` errors

**Solutions**:
```yaml
# Increase timeout for slow operations
semaphore_task_timeout: 900  # 15 minutes

# Check Semaphore UI for task details
# http://semaphore:3000/project/1/history
```

#### 3. Template Not Found

**Symptoms**: `Template not found` or `404` errors

**Solutions**:
```bash
# Verify template ID exists in Semaphore
curl http://semaphore:3000/api/project/1/templates

# Check template configuration
semaphore_start_template_id: 1  # Use correct ID
```

#### 4. SSH Connection Issues

**Symptoms**: Tasks fail with SSH errors

**Solutions**:
- Verify SSH keys are configured in Semaphore
- Check target machine accessibility
- Validate inventory configuration
- Test manual SSH connection

#### 5. Permission Denied

**Symptoms**: Ansible tasks fail with permission errors

**Solutions**:
```yaml
# Use sudo in Ansible tasks
- name: Start service
  systemd:
    name: "{{ service_name }}"
    state: started
  become: yes

# Or configure sudoers on target machines
```

### Debugging Tools

#### 1. Enable Debug Logging

```bash
# Set debug level for detailed logs
export HESTIA_LOG_LEVEL=DEBUG

# Check Hestia logs for Semaphore operations
docker logs hestia | grep semaphore
```

#### 2. Monitor Semaphore Tasks

```bash
# Check task status via API
curl http://semaphore:3000/api/project/1/tasks/TASK_ID

# Monitor Semaphore UI
open http://semaphore:3000/project/1/history
```

#### 3. Test Configuration

```bash
# Test service configuration
./scripts/dev.sh test semaphore

# Verify environment variables
env | grep SEMAPHORE
env | grep MYSERVICE
```

### Performance Optimization

#### 1. Polling Intervals

```yaml
# Fast services: aggressive polling
web-service:
  semaphore_poll_interval: 1.0

# Slow services: conservative polling  
ml-service:
  semaphore_poll_interval: 10.0
```

#### 2. Concurrent Operations

```yaml
# Services on different machines can start in parallel
service-a:
  semaphore_machine_id: "server-01"
  
service-b:
  semaphore_machine_id: "server-02"  # Different machine = parallel
```

#### 3. Template Optimization

```yaml
# Use lightweight templates for faster execution
- name: Quick health check
  uri:
    url: "http://{{ service_host }}:{{ service_port }}/health"
    method: GET
  register: health_result
```

## Advanced Patterns

### 1. Conditional Automation

```yaml
# Only use Semaphore in production
services:
  my-service:
    semaphore_enabled: "{{ 'true' if env == 'prod' else 'false' }}"
```

### 2. Dynamic Machine Selection

```yaml
# Use environment variable for machine ID
export MYSERVICE_SEMAPHORE_MACHINE_ID="server-${REGION}-01"
```

### 3. Custom Template Variables

```bash
# Pass additional context to templates
export MYSERVICE_CUSTOM_VAR="value"
```

### 4. Integration with CI/CD

```yaml
# Deploy service via Semaphore when code changes
deploy-service:
  semaphore_machine_id: "deploy-server"
  semaphore_start_template_id: 50  # Deploy latest code
```

## Conclusion

Semaphore integration transforms Hestia from a simple gateway into a powerful service orchestration platform. By combining Hestia's intelligent routing and queue management with Semaphore's automation capabilities, you can build cost-effective, scalable, and highly automated service infrastructures.

Key benefits:
- **Cost Optimization**: Pay only for resources when needed
- **Operational Efficiency**: Fully automated service lifecycle management  
- **Scalability**: Dynamic provisioning based on demand
- **Flexibility**: Works with any infrastructure (cloud, on-premise, hybrid)

For more examples and advanced patterns, see the [Configuration Reference](configuration-reference.md) and [Best Practices Guide](best-practices.md).