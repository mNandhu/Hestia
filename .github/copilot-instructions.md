# Copilot Instructions for Hestia-SSD

Purpose: Equip AI coding agents to be productive immediately in this repo. Keep responses concise, concrete, and follow the repo’s patterns.

## Big picture
- Hestia is a FastAPI gateway that transparently proxies to per-service upstreams and manages lifecycle (cold start, warm/warmup, idle shutdown), metrics, and structured logs.
- Core pieces:
  - `src/hestia/app.py`: FastAPI app; endpoints: dispatcher (`POST /v1/requests`), service status/metrics/start, transparent proxy (`/services/{serviceId}/{path}`); readiness/idle state in `_services`.
  - `src/hestia/config.py`: YAML + env var config (`hestia_config.yml`), with defaults for `ollama`. Keys include `base_url`, `health_url`, `warmup_ms`, `idle_timeout_ms`, queue sizes, timeouts.
  - `src/hestia/request_queue.py`: Queues requests for cold services; controls startup flag and readiness signalling.
  - `src/hestia/middleware.py`: Structured request logging + metrics.
  - `src/hestia/logging.py`: JSON logs with `SafeStreamHandler`; use `logger.log_*` helpers.
  - `src/hestia/metrics.py`: In-memory counters/timers/histograms.
  - `src/hestia/persistence.py` + `src/hestia/models/*`: SQLite models for activity and services.
  - `src/hestia/strategy_loader.py` and `strategies/`: Optional plugin strategies (LB, health, routing); auto-discovered via `register_strategy()`.

## Development workflows
- Run: `uv run uvicorn hestia.app:app --port 8080`. Uses uv to start the server.
- Run (docker): `docker compose up -d` (gateway on 8080). Image uses `ghcr.io/astral-sh/uv:python3.12-alpine` base; dependencies from `pyproject.toml`/`uv.lock` via `uv sync`.
- Tests: `pytest -q`. Unit + integration. Use `respx` to mock upstreams. The test client is strict asyncio mode.
- Lint/format: `ruff check --fix` (configured in `pyproject.toml`).
- Quick smoke (no Docker): Use `fastapi.testclient` in small scripts or tests.

## Key behaviors and patterns
- Transparent proxy: `/services/{serviceId}/{path}` forwards to `base_url` joined with `path`. Large/streaming responses are streamed.
- Cold start flow: If service not hot/ready, dispatcher or proxy marks service “starting”, queues requests, and kicks `_start_service_async` which uses `health_url` or `warmup_ms` to flip to hot/ready.
- Status probe: `GET /v1/services/{serviceId}/status` performs a quick health probe when state is cold and `health_url` is set, so pre-running upstreams report hot without needing a proxy request.
- Idle shutdown: Background thread sets hot services to cold after `idle_timeout_ms` of inactivity.
- Config precedence: `hestia_config.yml` then env vars like `OLLAMA_BASE_URL`, `OLLAMA_HEALTH_URL`, etc. If `services.ollama` missing, defaults are injected.
- Logging: Use `get_logger(...)` and methods like `log_service_start`, `log_service_ready`, `log_proxy_*`. Avoid writing to `print`; logs are JSON. The handler tolerates pytest shutdown.
- Metrics: Use `get_metrics()` and record counters/timers/histograms. Normalize paths via middleware when labeling.

## Conventions
- Service IDs: arbitrary strings; `ollama` exists by default. Many endpoints accept any `{serviceId}` and fall back to `ollama` config if missing.
- Prefer small, synchronous checks in endpoints; do async work in background tasks (e.g., `_start_service_async`).
- Tests use deterministic service IDs to avoid state leakage: prefer unique IDs per test.
- Use `respx` for upstream HTTP stubs and `monkeypatch.setenv` for config overrides.

## Useful files to reference
- `src/hestia/app.py` — endpoints, hot/cold logic, proxy behavior
- `src/hestia/config.py` — config loading and env var mapping
- `src/hestia/request_queue.py` — queue/start/ready signalling
- `src/hestia/middleware.py` — logging + metrics wiring
- `src/hestia/logging.py` — event helpers and SafeStreamHandler
- `tests/integration/test_service_management.py` — service lifecycle tests
- `specs/001-hestia-a-personal/quickstart.md` — curl examples and client setup

## Spec-driven development
- Specs live in `specs/`; start from `specs/001-hestia-a-personal/` and keep docs/tests in sync.
- When adding features:
  1) Draft/update spec in `specs/...`
  2) Add/adjust tests (happy path + edge cases)
  3) Implement minimal changes keeping public behavior stable
  4) Update docs and examples

## Examples
- Probe status when upstream is running:
  - Set `OLLAMA_BASE_URL=http://upstream.local` and `OLLAMA_HEALTH_URL=http://upstream.local/api/tags`
  - `GET /v1/services/ollama/status` → returns `hot`/`ready` without prior proxy calls (see tests).
- Transparent proxy usage:
  - `GET /services/ollama/api/tags` forwards to `base_url/api/tags` with retries/timeout per config.

## Gotchas
- Don’t block in request path; long work belongs in `_start_service_async`.
- The in-memory `_services` and queue flags are process-local; tests should use unique IDs to avoid cross-test state.
- For streaming responses, avoid reading the whole body; use `StreamingResponse`.
- Use `uv` project management commands (`uv sync`, `uv run`, etc.) to ensure dependency consistency.

Keep instructions short and code changes scoped. Prefer using existing helpers over rolling new patterns.
