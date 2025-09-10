# Tasks: Hestia - Personal On-Demand Service Gateway

Feature Dir: `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal`
Contracts: `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal/contracts/openapi.yaml`
Plan: `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal/plan.md`
Data Model: `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal/data-model.md`
Quickstart: `/home/mnand/Projects/Hestia/specs/001-hestia-a-personal/quickstart.md`

Constitution Imperatives:
- Test-First (NON-NEGOTIABLE): Write failing tests before implementation
- Integration-First: Contract and integration tests precede unit tests

## Parallel Groups Legend
[P] = Tasks can run in parallel (different files). No [P] for tasks touching same file/area.

## Tasks

T001. [Setup] Create repository structure (no code yet)
- Create directories: `src/models`, `src/services`, `src/cli`, `src/lib`, `tests/contract`, `tests/integration`, `tests/unit`
- Add `.gitkeep` in empty dirs
- Dependencies: none
 - Status: DONE

T002. [Setup] Initialize `pyproject.toml` and dependencies
- Python 3.12; runtime deps: fastapi, uvicorn, pydantic, sqlalchemy, httpx
- Dev deps: pytest, pytest-asyncio, respx, black, ruff
- Dependencies: T001
 - Status: DONE

T003. [Contract Tests] Generate failing contract tests from OpenAPI [P]
- For each endpoint in `contracts/openapi.yaml`, create `tests/contract/test_contract_<name>.py`
- Validate: route exists, methods allowed, required fields enforced, security when enabled
- Endpoints: `/services/{serviceId}/{proxyPath}`, `/v1/requests`, `/v1/services/{id}/start`, `/v1/services/{id}/status`
- Dependencies: T002
 - Status: DONE (tests import app and expect 501 for stubs)

T004. [Integration Tests] Define gateway transparency scenarios [P]
- `tests/integration/test_transparent_proxy.py`: calling `GET /services/ollama/v1/models` returns 200 with mocked downstream
- Include cold-start path: first call queues until ready
- Include auth enabled/disabled variants
- Dependencies: T002
 - Status: DONE (GET implemented via httpx; other methods pending in T021)

T005. [Integration Tests] Define startup policy scenarios [P]
- `tests/integration/test_startup_policy.py`: retry up to N, then fallback to other machine, finally error → assert logs and response codes
- Dependencies: T002
 - Status: DONE (retry count interpreted as total primary attempts; one fallback attempt; returns 503 on failure)

T006. [Integration Tests] Define readiness/warm-up scenarios [P]
- `tests/integration/test_readiness.py`: health endpoint success vs warm-up delay fallback behavior
- Dependencies: T002
 - Status: DONE (in-memory readiness on start; health URL or warmup ms flips to ready)

T007. [Integration Tests] Define activity/idle shutdown scenarios [P]
- `tests/integration/test_idle_shutdown.py`: after idle timeout, service transitions to cold and new request re-warms
- Dependencies: T002
 - Status: DONE (idle monitor thread implemented; state flips to cold after OLLAMA_IDLE_TIMEOUT_MS)

T008. [Unit Tests] Config loader tests [P]
- `tests/unit/test_config_loader.py`: load `hestia_config.yml`, env overrides, validation errors
- Dependencies: T002
 - Status: DONE (Pydantic models with YAML load, env overrides, validation)

T009. [Unit Tests] Strategy loader tests [P]
- `tests/unit/test_strategy_loader.py`: discover/load from `strategies/`, prevent duplicate registrations
- Dependencies: T002
 - Status: DONE (thread-safe singleton registry with importlib-based discovery)

T010. [Unit Tests] Data model tests [P]
- `tests/unit/test_models.py`: SQLAlchemy models and constraints from `data-model.md`
- Dependencies: T002
 - Status: DONE (comprehensive tests for all models: Service, Machine, RoutingRule, Activity, AuthKey)

T011. [Infra] Dockerfile (multi-stage) and docker-compose (hestia + semaphore)
- Compose: port 8080, named volumes `hestia_sqlite`, `semaphore_data`, bind-mount `strategies/` and `hestia_config.yml`
- Dependencies: T001
 - Status: DONE

T012. [Source] Minimal FastAPI app skeleton to load and serve contracts (no business logic)
 - `src/hestia/app.py` with FastAPI instance and health route `/__health`
- Wire uvicorn entry in `pyproject.toml`
- Dependencies: T003 (tests should fail until endpoints exist)
 - Status: DONE (implemented at `src/hestia/app.py`)

T013. [Source] Contract routing stubs to make contract tests discover endpoints
- Implement routes: transparent proxy `/services/{serviceId}/{proxyPath}` (methods GET/POST/PUT/PATCH/DELETE), `/v1/requests`, `/v1/services/{id}/start`, `/v1/services/{id}/status` returning 501
- Dependencies: T012; Target: make routing exist but tests still fail on behavior
 - Status: DONE (all endpoints return 501 as stubs)

T014. [Source] Config loader implementation
- Pydantic models; supports env overrides; load at startup
- Dependencies: T008
 - Status: DONE (implemented with YAML support and dynamic env override pickup)

T015. [Source] SQLAlchemy models per `data-model.md`
- Tables: Service, Machine, RoutingRule, Activity, AuthKey
- Dependencies: T010
 - Status: DONE (all models implemented with proper relationships, enums, JSON fields)

T016. [Source] Persistence provider (SQLite) and initialization
- Create engine, session management, migrations bootstrap (if needed)
- Dependencies: T015
 - Status: DONE (SQLite with session management, context managers, testing support, auto-initialization)

T017. [Source] Strategy plugin loader
- Load from `strategies/` via importlib; registry with thread-safe singleton
- Dependencies: T009
 - Status: DONE (thread-safe singleton registry with importlib discovery and graceful error handling)

T018. [Source] Readiness checker
- Health endpoint polling; warm-up delay fallback per service
- Dependencies: T006
 - Status: DONE (health URL 200 flips to ready/hot; otherwise warm-up ms then ready/hot)

T019. [Source] Startup policy engine
- Retry with limit/delay; fallback machine selection; terminal error and event log
- Dependencies: T005, T016, T017, T018
 - Status: DONE (comprehensive startup policy with retry/delay, fallback selection, terminal error handling, and complete event logging for observability)

T020. [Source] Request queue for cold services
- FIFO, bounded size, per-service timeouts; prevent duplicate startups
- Dependencies: T004, T019
 - Status: DONE (FIFO queue with bounded size, timeouts, duplicate startup prevention, config integration)

T021. [Source] Transparent proxy implementation
- Implement proxy for `/services/{serviceId}/{proxyPath}` using httpx; preserve method, headers, body; stream response
- Dependencies: T003, T020
 - Status: DONE (all HTTP methods supported, queue integration for cold services, streaming responses, comprehensive testing)

T022. [Source] Generic POST `/v1/requests` dispatcher
- Accept GatewayRequest, route to service, use queue/strategy engines
- Dependencies: T003, T020
 - Status: DONE (full dispatcher implementation with queue integration, service startup, comprehensive testing)

T023. [Source] Service status and proactive start endpoints
- GET status, POST start; integrate with readiness and queue
- Dependencies: T003, T018, T019
 - Status: DONE (comprehensive service management API with status reporting, proactive startup, queue integration)

T024. [Source] Optional auth middleware
- API key for API; dashboard username/password stub; warnings when disabled
- Dependencies: T004, T008

T025. [Source] Structured logging and basic metrics
- Log events per FR-013; add request IDs; counters/timers skeleton
- Dependencies: T004, T005
 - Status: DONE (comprehensive structured logging system with request IDs, event tracking, metrics collection, middleware integration, service lifecycle logging, and 30 passing tests)

T026. [Integration] Semaphore API client and mocks
- httpx client; internal URL `http://semaphore:3000`; respx mocks in tests
- Dependencies: T003, T022

T027. [CI/CD] GitHub Actions: lint and format
- Ruff on push to main
- Dependencies: T002
- Status: Done (lint.yml with ruff lint and format checks)

T028. [CI/CD] GitHub Actions: tests
- Install deps and run `pytest`
- Dependencies: T002, T003
- Status: Done (test.yml with full test suite run on push to main)

T029. [Docs] Example `strategies/` and `hestia_config.yml`
- Provide placeholders and comments for customization
- Dependencies: T014, T017
 - Status: DONE (comprehensive examples with 11 services, 4 strategies, detailed documentation)

T030. [Docs] Update quickstart with curl examples and stable URL
- Verify `/services/{serviceId}/...` usage and note `OLLAMA_BASE_URL=http://localhost:8080/services/ollama`
- Dependencies: T021
 - Status: DONE (comprehensive quickstart guide with curl examples, response formats, troubleshooting, configuration examples, and verified test coverage)

T031. [Docs] Authentication documentation
- Document API key configuration, security best practices, and auth endpoints
- Include examples for different auth methods and troubleshooting guide
- Dependencies: T024

---

## Strategy-based Routing (Service-agnostic)

Context: Hestia supports plugin strategies discovered from `strategies/` (see T017). Routing must remain service-agnostic: Hestia is not specific to Ollama. Each service can opt into its own strategy and rules (e.g., model-aware routing for LLMs, region-aware for others). Strategies select an upstream base URL per-request via a `request_context` derived from the incoming request.

T032. [Spec/Design] Strategy routing requirements and config schema
- Define service-agnostic config keys in `hestia_config.yml`:
	- `services.<id>.instances: [ { url, weight?, region? } ]`
	- `services.<id>.strategy: <name>` (optional, default none)
	- `services.<id>.routing.by_model: { <key>: <instance_url> }` (example strategy-specific mapping)
- Document how `request_context` is constructed (path, headers, body fields like `model`, query params).
- Dependencies: T017, T014
 - Status: DONE (config schema added to ServiceConfig; request_context defined and used; examples documented)

T033. [Tests] Integration tests for strategy-based routing [P]
- Add `tests/integration/test_strategy_routing.py`:
	- Given instances A/B and `routing.by_model` mapping, requests with model=X route to A, model=Y to B.
	- When no mapping matches, fallback to load balancer selection.
	- Use `respx` to assert correct upstream URLs are called (no hardcoded Ollama assumptions; use generic `serviceId`).
- Dependencies: T032
 - Status: DONE (tests/integration/test_strategy_routing.py implemented and passing)

T034. [Source] Load strategies on startup and wire into request path
- In `src/hestia/app.py`, load strategies at startup (`load_strategies("strategies")`) and keep a registry reference.
- In dispatcher (`POST /v1/requests`) and transparent proxy, before constructing target URL:
	- Build `request_context` (e.g., parsed JSON body fields including `model`, headers, query params, path).
	- Resolve upstream base URL via configured strategy:
		- If `routing.by_model` exists, prefer exact match.
		- Else call `load_balancer.get_next_instance(service_id, request_context)`.
		- Fallback to `service_config.base_url` if none.
- Dependencies: T017, T032
 - Status: DONE (strategies loaded at startup; request_context built; resolution via strategy/LB/fallback wired)

T035. [Source] Provide a minimal model-aware router strategy (example)
- Add `strategies/model_router.py` with `register_strategy(registry)`:
	- `route_request(service_id, request_context, config)` returns instance URL based on arbitrary mapping (e.g., `by_model`).
	- Delegates to load balancer when no direct hit.
- Keep generic; do not assume Ollama-specific shapes beyond a configurable key name (default `model`).
- Dependencies: T017, T032
 - Status: DONE (strategies/model_router.py implemented and registered)

T036. [Config/Docs] Extend examples for strategies and routing
- Update example `hestia_config.yml` to include `instances` and `routing` blocks.
- Document service-agnostic patterns in `strategies/README.md` with a short example.
- Dependencies: T032, T035
 - Status: DONE (hestia_config.yml example extended; strategies/README.md updated)

T037. [Tests] Health/fallback and LB integration [P]
- Integration tests:
	- When chosen instance is down (respx 503/timeout), mark unhealthy and next request selects alternative.
	- Ensure instance recovery toggles health back to healthy on 200.
- Dependencies: T033, T034
 - Status: DONE (comprehensive health tracking integration tests passing; failover and recovery working correctly)

T038. [Source] Observability for routing
- Add structured logs and metrics for routing decisions:
	- Which strategy selected, selected instance URL, reason (mapping hit / LB / fallback).
	- Counters per strategy and per service.
- Dependencies: T025, T034
 - Status: DONE (routing decision logs and metrics integrated; resolution_reason tracking added)

T039. [Docs] Quickstart and spec updates
- Update `specs/001-hestia-a-personal/quickstart.md` with routing examples.
- Update `contracts` or notes if we expose any strategy inspection endpoints (optional).
- Dependencies: T033, T034
 - Status: DONE (comprehensive strategy routing examples added to quickstart; strategy inspection endpoint documented)

T040. [Optional] Strategy inspection endpoint [P]
- Add `/v1/strategies` listing loaded strategies and per-service strategy configuration (read-only).
- Dependencies: T017
 - Status: DONE (endpoint implemented; returns loaded strategies info and per-service configuration)

# Semaphore Integration: Remote Service Management

T041. [Contract Tests] Semaphore API contract [P]
- Create contract tests for Hestia <-> Semaphore API: service start/stop requests, error handling, status polling
- Endpoints: `/v1/semaphore/start`, `/v1/semaphore/stop`, `/v1/semaphore/status`
- Dependencies: T003
 - Status: DONE (comprehensive contract tests created with 12 test cases covering all endpoints, validation, and error handling)

T042. [Integration Tests] Remote service startup/shutdown [P]
- `tests/integration/test_semaphore_startup.py`: When a service is cold, Hestia requests Semaphore to start it, queues requests, and forwards when ready
- `tests/integration/test_semaphore_shutdown.py`: After idle timeout, Hestia requests Semaphore to stop the service
- Dependencies: T041
 - Status: TODO

T043. [Source] Semaphore API client and orchestration logic
- Implement Semaphore client in Hestia; wire into cold start and idle shutdown flows
- Support config-driven orchestration: per-service/host startup/shutdown policies
- Dependencies: T042
 - Status: TODO

T044. [Config/Docs] Extend config and docs for Semaphore
- Update `hestia_config.yml` to support remote orchestration policies
- Document Semaphore integration, config options, and example flows
- Dependencies: T043
 - Status: TODO

## Parallelization Guide
- [P] T003, T004, T005, T006, T007, T008, T009, T010 can run in parallel after T002
- [P] T027 and T028 can run in parallel after T002
- [P] T033, T037, T040 can run in parallel with source work after T032
- [P] T041, T042, T043, T044 can run in parallel with other TODO tasks

## Suggested Task Agent Commands
- tasks run T003
- tasks run T004
- tasks run T005
- tasks run T006
- tasks run T007
- tasks run T008
- tasks run T009
- tasks run T010
