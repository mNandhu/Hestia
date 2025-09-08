# Quickstart: Hestia - Personal On-Demand Service Gateway

## Prerequisites
- Docker and docker-compose installed
- Linux environment recommended

## One-command startup

```sh
# from repo root
docker compose up -d
```

This starts:
- hestia (FastAPI app)
- semaphore (Ansible Semaphore)

## Configuration
- `hestia_config.yml` and `strategies/` are mounted as bind volumes for live development.
- SQLite DB persisted to named volume `hestia_sqlite`.
- Semaphore config persisted to named volume `semaphore_data`.

## API Authentication (optional)
- Set `X-API-Key` header for API calls when auth is enabled.
- Dashboard uses username/password when enabled.

## Core Endpoints
- POST `http://localhost:8080/v1/requests` – transparent gateway (see contracts/openapi.yaml)
- GET `http://localhost:8080/v1/services/{serviceId}/status` – service status
- POST `http://localhost:8080/v1/services/{serviceId}/start` – proactive warm-up

## Testing
```sh
# run tests
pytest -q
```
- Async tests use pytest-asyncio.
- External calls (Semaphore) mocked via respx/httpx.MockTransport.

## Logs
- Structured logs with configurable levels; see FR-013 for event types captured.
