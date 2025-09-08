# Research: Hestia - Personal On-Demand Service Gateway

## Decisions and Rationale

### Readiness Without Health Endpoint
- Decision: Support a per-service warm-up period when no health endpoint is available.
- Rationale: Simple, predictable fallback that avoids brittle probes.
- Alternatives: File/socket sentinel; active probe requests; rejected for added complexity at this stage.

### Request Queueing and Limits
- Decision: FIFO queue; queue while service is cold; forward when healthy; prevent duplicate startups.
- Limits: Configurable max wait timeout and max queue size per service.
- Rationale: Satisfies transparency while bounding resource usage.

### Authentication Storage
- Decision: Optional auth. API keys and dashboard credentials stored in config (hestia_config.yml) with environment variable overrides.
- Rationale: Simple, portable, aligns with containerized deployment.
- Alternatives: External secrets store; deferred for now.

### Semaphore Integration
- Decision: Use internal Docker DNS name `http://semaphore:3000/` and API token; communicate via httpx; mock in tests.
- Rationale: Works cleanly in docker-compose network; avoids hard-coded IPs.

### Strategy Plugin Discovery
- Decision: Load Python modules from `strategies/` directory via importlib; ensure safe, explicit registry of strategies.
- Rationale: Pluggable by design; hot-reload via bind-mount in dev.

### Docker Compose Volumes and Networks
- Decision: Named volumes for `hestia_sqlite` and `semaphore_data`; default network for inter-service comms.
- Rationale: Durability and simple networking.

## Open Questions Addressed
- Startup failure policy: retry → fallback → error (configurable)
- Logging scope: routing, start/stop, retries, readiness, idle shutdowns, auth decisions (no sensitive data)
- Protocol scope: HTTP APIs only (phase 1)

## References
- FastAPI + httpx best practices for async clients
- docker-compose service discovery and volumes
- pytest-asyncio patterns; respx for httpx mocking
