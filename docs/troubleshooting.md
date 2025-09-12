# Troubleshooting Guide

Comprehensive troubleshooting guide for Hestia Gateway and Semaphore integration issues.

## Table of Contents

- [General Troubleshooting](#general-troubleshooting)
- [Service Issues](#service-issues)
- [Semaphore Integration](#semaphore-integration)
- [Configuration Problems](#configuration-problems)
- [Performance Issues](#performance-issues)
- [Network & Connectivity](#network--connectivity)
- [Logging & Debugging](#logging--debugging)
- [Common Error Messages](#common-error-messages)

## General Troubleshooting

### Enable Debug Logging

```bash
# Set debug logging level
export HESTIA_LOG_LEVEL=DEBUG

# Start Hestia with verbose output
uv run uvicorn hestia.app:app --port 8080 --log-level debug

# Or with Docker
docker compose logs -f hestia
```

### Check Service Status

```bash
# Global gateway status
curl http://localhost:8080/v1/metrics

# Specific service status
curl http://localhost:8080/v1/services/ollama/status

# Service health probe
curl http://localhost:8080/v1/services/ollama/start
```

### Verify Configuration

```bash
# Check environment variables
env | grep -E "(HESTIA|SEMAPHORE|OLLAMA|MYSERVICE)"

# Validate YAML syntax
python -c "import yaml; print(yaml.safe_load(open('hestia_config.yml')))"

# Test configuration loading
uv run python -c "from src.hestia.config import load_config; print(load_config().services.keys())"
```

## Service Issues

### Service Won't Start

**Symptoms**: Service remains in "cold" state, requests timeout

**Diagnosis**:
```bash
# Check service configuration
curl http://localhost:8080/v1/services/myservice/status

# Check logs for startup errors
docker logs hestia | grep "myservice"

# Test direct connectivity to service
curl http://target-service:8080/health
```

**Solutions**:

1. **Verify base_url**:
```bash
export MYSERVICE_BASE_URL="http://correct-host:8080"
```

2. **Check health_url**:
```bash
# Test health endpoint directly
curl http://target-service:8080/health

# Or remove health check and use warmup delay
export MYSERVICE_HEALTH_URL=""
export MYSERVICE_WARMUP_MS=5000
```

3. **Increase timeouts**:
```bash
export MYSERVICE_REQUEST_TIMEOUT_SECONDS=120
export MYSERVICE_WARMUP_MS=10000
```

### Service Starts But Immediately Dies

**Symptoms**: Service state flickers between "starting" and "cold"

**Diagnosis**:
```bash
# Monitor service state changes
watch -n 1 "curl -s http://localhost:8080/v1/services/myservice/status | jq '.state'"

# Check for error patterns in logs
docker logs hestia | grep -E "(error|failed|exception)" | grep myservice
```

**Solutions**:

1. **Fix health check URL**:
```bash
# Health check returns wrong status code
export MYSERVICE_HEALTH_URL="http://target:8080/actuator/health"
```

2. **Adjust warmup timing**:
```bash
# Service needs more time to start
export MYSERVICE_WARMUP_MS=15000
```

3. **Check target service logs**:
```bash
# Service may be crashing
docker logs target-service
```

### Requests Are Queued But Never Processed

**Symptoms**: Queue count increases but never decreases

**Diagnosis**:
```bash
# Check queue status
curl http://localhost:8080/v1/services/myservice/status | jq '.queuePending'

# Check if service ever becomes ready
curl http://localhost:8080/v1/services/myservice/status | jq '.readiness'
```

**Solutions**:

1. **Clear stuck queues**:
```bash
# Restart Hestia to clear queues
docker compose restart hestia
```

2. **Fix service startup**:
```bash
# Check why service isn't becoming ready
export MYSERVICE_WARMUP_MS=30000
export MYSERVICE_REQUEST_TIMEOUT_SECONDS=180
```

3. **Check for startup deadlock**:
```bash
# Service may depend on itself
export MYSERVICE_HEALTH_URL=""  # Remove circular dependency
```

## Semaphore Integration

### Semaphore Connection Failed

**Symptoms**: `Semaphore client not available` errors

**Diagnosis**:
```bash
# Test Semaphore connectivity
curl http://semaphore:3000/api/ping

# Check Semaphore container
docker ps | grep semaphore
docker logs semaphore
```

**Solutions**:

1. **Verify Semaphore URL**:
```bash
export SEMAPHORE_BASE_URL="http://localhost:3000"

# Or for Docker networking
export SEMAPHORE_BASE_URL="http://semaphore:3000"
```

2. **Check network connectivity**:
```bash
# From Hestia container
docker exec hestia ping semaphore
docker exec hestia curl http://semaphore:3000/api/ping
```

3. **Restart Semaphore**:
```bash
docker compose restart semaphore
```

### Semaphore Tasks Timeout

**Symptoms**: `Semaphore task failed: timeout` errors

**Diagnosis**:
```bash
# Check task status in Semaphore UI
open http://localhost:3000/project/1/history

# Check Semaphore task logs
curl http://semaphore:3000/api/project/1/tasks/TASK_ID
```

**Solutions**:

1. **Increase task timeout**:
```bash
export MYSERVICE_SEMAPHORE_TASK_TIMEOUT=900  # 15 minutes
```

2. **Check Ansible playbook**:
```yaml
# Ensure playbook doesn't hang
- name: Start service
  service:
    name: myservice
    state: started
  register: result
  retries: 3
  delay: 10
```

3. **Adjust polling interval**:
```bash
export MYSERVICE_SEMAPHORE_POLL_INTERVAL=10.0  # Slower polling
```

### Semaphore Tasks Fail

**Symptoms**: `Semaphore task failed: error` messages

**Diagnosis**:
```bash
# Check Semaphore UI for task details
open http://localhost:3000/project/1/history

# Get task output
curl http://semaphore:3000/api/project/1/tasks/TASK_ID/output
```

**Solutions**:

1. **Fix Ansible playbook errors**:
```yaml
# Common fixes
- name: Ensure service user exists
  user:
    name: myservice
    state: present
  become: yes

- name: Start service with retry
  service:
    name: myservice
    state: started
  become: yes
  retries: 3
  delay: 5
```

2. **Check SSH connectivity**:
```bash
# Test SSH from Semaphore to target
ssh -i /path/to/key user@target-machine

# Verify SSH keys in Semaphore
# Go to Key Store in Semaphore UI
```

3. **Verify template configuration**:
```bash
# Check template ID exists
curl http://semaphore:3000/api/project/1/templates

# Update template ID
export MYSERVICE_SEMAPHORE_START_TEMPLATE_ID=5
```

### Semaphore Service Never Becomes Ready

**Symptoms**: Semaphore task succeeds but service stays "not_ready"

**Diagnosis**:
```bash
# Check if service actually started on target
ssh target-machine "systemctl status myservice"

# Test service connectivity
curl http://target-machine:8080/health

# Check Hestia health probe
export MYSERVICE_HEALTH_URL="http://target-machine:8080/health"
curl $MYSERVICE_HEALTH_URL
```

**Solutions**:

1. **Fix service startup in Ansible**:
```yaml
- name: Wait for service to be ready
  uri:
    url: "http://localhost:8080/health"
    method: GET
  register: result
  until: result.status == 200
  retries: 30
  delay: 2
```

2. **Adjust health check URL**:
```bash
export MYSERVICE_HEALTH_URL="http://target:8080/api/health"
```

3. **Use warmup delay instead**:
```bash
export MYSERVICE_HEALTH_URL=""
export MYSERVICE_WARMUP_MS=10000
```

## Configuration Problems

### Environment Variables Not Working

**Symptoms**: Configuration changes ignored

**Diagnosis**:
```bash
# Check if variables are set
env | grep MYSERVICE

# Test configuration loading
uv run python -c "
from src.hestia.config import load_config
config = load_config()
service = config.services.get('myservice') or config.services.get('my-service')
print(f'Found service: {service}')
if service:
    print(f'Base URL: {service.base_url}')
    print(f'Semaphore enabled: {service.semaphore_enabled}')
"
```

**Solutions**:

1. **Check service ID transformation**:
```bash
# Service "my-service" needs "MY_SERVICE_*" variables
export MY_SERVICE_BASE_URL="http://target:8080"
export MY_SERVICE_SEMAPHORE_ENABLED=true
```

2. **Restart after changes**:
```bash
# Restart Hestia to pick up new environment
docker compose restart hestia
```

3. **Use YAML configuration**:
```yaml
# hestia_config.yml
services:
  my-service:
    base_url: "http://target:8080"
    semaphore_enabled: true
```

### YAML Configuration Not Loaded

**Symptoms**: YAML changes have no effect

**Diagnosis**:
```bash
# Check file location and syntax
ls -la hestia_config.yml
python -c "import yaml; yaml.safe_load(open('hestia_config.yml'))"

# Check if file is mounted in Docker
docker exec hestia ls -la /app/hestia_config.yml
```

**Solutions**:

1. **Fix file path**:
```bash
# Ensure file is in correct location
export HESTIA_CONFIG_PATH="/app/hestia_config.yml"
```

2. **Fix YAML syntax**:
```yaml
# Common YAML issues
services:
  my-service:  # Use quotes if service ID has special chars
    base_url: "http://target:8080"  # Always quote URLs
    retry_count: 3  # Numbers don't need quotes
    semaphore_enabled: true  # Booleans don't need quotes
```

3. **Check Docker mount**:
```yaml
# docker-compose.yml
services:
  hestia:
    volumes:
      - ./hestia_config.yml:/app/hestia_config.yml
```

## Performance Issues

### Slow Response Times

**Symptoms**: Requests take much longer than expected

**Diagnosis**:
```bash
# Test direct service response time
time curl http://target-service:8080/api

# Test through Hestia
time curl http://localhost:8080/services/myservice/api

# Check metrics for timing data
curl http://localhost:8080/v1/metrics | jq '.timers'
```

**Solutions**:

1. **Optimize health checks**:
```bash
# Use faster health endpoint
export MYSERVICE_HEALTH_URL="http://target:8080/ping"

# Or remove health check
export MYSERVICE_HEALTH_URL=""
export MYSERVICE_WARMUP_MS=2000
```

2. **Reduce timeouts**:
```bash
export MYSERVICE_REQUEST_TIMEOUT_SECONDS=30
export MYSERVICE_RETRY_DELAY_MS=500
```

3. **Tune Semaphore polling**:
```bash
export MYSERVICE_SEMAPHORE_POLL_INTERVAL=1.0  # Faster polling
```

### High Memory Usage

**Symptoms**: Hestia container uses excessive memory

**Diagnosis**:
```bash
# Check container memory usage
docker stats hestia

# Check queue sizes
curl http://localhost:8080/v1/metrics | jq '.services'
```

**Solutions**:

1. **Reduce queue sizes**:
```bash
export MYSERVICE_QUEUE_SIZE=50  # Smaller queues
```

2. **Optimize idle timeouts**:
```bash
export MYSERVICE_IDLE_TIMEOUT_MS=300000  # 5 minutes
```

3. **Restart periodically**:
```bash
# Add to crontab for long-running deployments
0 3 * * * docker compose restart hestia
```

## Network & Connectivity

### Service Connection Refused

**Symptoms**: `Connection refused` errors

**Diagnosis**:
```bash
# Test connectivity
ping target-service
telnet target-service 8080

# Check service status on target
ssh target-service "systemctl status myservice"
```

**Solutions**:

1. **Fix service URL**:
```bash
export MYSERVICE_BASE_URL="http://correct-host:8080"
```

2. **Check firewall**:
```bash
# Open ports on target machine
sudo ufw allow 8080
```

3. **Verify service binding**:
```bash
# Service should bind to 0.0.0.0, not 127.0.0.1
netstat -tlnp | grep 8080
```

### DNS Resolution Issues

**Symptoms**: `Name resolution failed` errors

**Diagnosis**:
```bash
# Test DNS from Hestia container
docker exec hestia nslookup target-service
docker exec hestia ping target-service
```

**Solutions**:

1. **Use IP addresses**:
```bash
export MYSERVICE_BASE_URL="http://192.168.1.100:8080"
```

2. **Fix Docker networking**:
```yaml
# docker-compose.yml
services:
  hestia:
    networks:
      - app-network
  target-service:
    networks:
      - app-network
networks:
  app-network:
```

3. **Add DNS entries**:
```yaml
# docker-compose.yml
services:
  hestia:
    extra_hosts:
      - "target-service:192.168.1.100"
```

## Logging & Debugging

### Enable Detailed Logging

```bash
# Maximum verbosity
export HESTIA_LOG_LEVEL=DEBUG
export PYTHONPATH=/app/src

# Start with detailed output
uv run uvicorn hestia.app:app --port 8080 --log-level debug

# Filter specific components
docker logs hestia | grep semaphore
docker logs hestia | grep myservice
docker logs hestia | grep ERROR
```

### Structured Log Analysis

```bash
# Parse JSON logs
docker logs hestia | jq 'select(.service_id == "myservice")'
docker logs hestia | jq 'select(.event_type == "semaphore_error")'

# Track request flows
docker logs hestia | jq 'select(.request_id == "req_123")'

# Monitor service state changes
docker logs hestia | jq 'select(.event_type == "service_state_change")'
```

### Debug Network Issues

```bash
# Test from Hestia container
docker exec -it hestia bash

# Install debugging tools
apt update && apt install -y curl telnet dnsutils

# Test connectivity
curl -v http://target-service:8080/health
telnet target-service 8080
nslookup target-service
```

## Common Error Messages

### "Service not found in configuration"

**Cause**: Service ID doesn't match configuration

**Solution**:
```bash
# Check available services
curl http://localhost:8080/v1/metrics | jq '.services | keys'

# Add service configuration
export MYSERVICE_BASE_URL="http://target:8080"
```

### "Request timeout waiting for service startup"

**Cause**: Service takes longer to start than timeout

**Solution**:
```bash
export MYSERVICE_REQUEST_TIMEOUT_SECONDS=300  # 5 minutes
export MYSERVICE_WARMUP_MS=60000  # 1 minute
```

### "Queue full, request rejected"

**Cause**: Too many requests queued during startup

**Solution**:
```bash
export MYSERVICE_QUEUE_SIZE=200  # Larger queue
export MYSERVICE_WARMUP_MS=5000  # Faster startup
```

### "Semaphore client not available"

**Cause**: Semaphore URL not configured or unreachable

**Solution**:
```bash
export SEMAPHORE_BASE_URL="http://semaphore:3000"

# Test connectivity
curl http://semaphore:3000/api/ping
```

### "Template not found"

**Cause**: Semaphore template ID doesn't exist

**Solution**:
```bash
# List available templates
curl http://semaphore:3000/api/project/1/templates

# Use correct template ID
export MYSERVICE_SEMAPHORE_START_TEMPLATE_ID=5
```

### "SSH connection failed"

**Cause**: Semaphore can't connect to target machine

**Solution**:
1. Check SSH keys in Semaphore Key Store
2. Verify target machine SSH access
3. Update inventory configuration

### "Health check failed"

**Cause**: Health endpoint returns wrong status or doesn't exist

**Solution**:
```bash
# Test health endpoint directly
curl http://target:8080/health

# Use different endpoint
export MYSERVICE_HEALTH_URL="http://target:8080/api/ping"

# Or disable health check
export MYSERVICE_HEALTH_URL=""
export MYSERVICE_WARMUP_MS=5000
```

## Emergency Recovery

### Complete Reset

```bash
# Stop everything
docker compose down

# Clear volumes (loses data!)
docker volume rm hestia_hestia_sqlite hestia_semaphore_data

# Reset configuration
git checkout hestia_config.yml

# Restart fresh
docker compose up -d
```

### Service-Specific Reset

```bash
# Clear single service state
curl -X POST http://localhost:8080/v1/services/myservice/stop

# Or restart Hestia to clear all service state
docker compose restart hestia
```

### Configuration Backup

```bash
# Backup working configuration
cp hestia_config.yml hestia_config.yml.backup

# Backup environment variables
env | grep -E "(SEMAPHORE|MYSERVICE)" > env_backup.txt
```

## Getting Help

### Collect Debug Information

```bash
#!/bin/bash
# debug_info.sh - Collect troubleshooting information

echo "=== System Information ==="
uname -a
docker --version
docker compose version

echo "=== Hestia Status ==="
docker ps | grep hestia
curl -s http://localhost:8080/v1/metrics | jq '.'

echo "=== Configuration ==="
env | grep -E "(HESTIA|SEMAPHORE|MYSERVICE)"
cat hestia_config.yml

echo "=== Recent Logs ==="
docker logs --tail 50 hestia

echo "=== Semaphore Status ==="
curl -s http://localhost:3000/api/ping || echo "Semaphore not reachable"
```

### Support Channels

- **GitHub Issues**: https://github.com/mNandhu/Hestia-SSD/issues
- **Documentation**: See [docs/](.) directory
- **Configuration Reference**: [configuration-reference.md](configuration-reference.md)
- **Semaphore Integration**: [semaphore-integration.md](semaphore-integration.md)

### Before Reporting Issues

1. **Run debug script** (above) and include output
2. **Test with minimal configuration** (single service)
3. **Check existing issues** on GitHub
4. **Include version information** (Hestia, Docker, OS)
5. **Provide reproduction steps** if possible

Remember: Most issues are configuration-related. Start with the simplest possible setup and gradually add complexity!