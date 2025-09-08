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

T005. [Integration Tests] Define startup policy scenarios [P]
- `tests/integration/test_startup_policy.py`: retry up to N, then fallback to other machine, finally error → assert logs and response codes
- Dependencies: T002

T006. [Integration Tests] Define readiness/warm-up scenarios [P]
- `tests/integration/test_readiness.py`: health endpoint success vs warm-up delay fallback behavior
- Dependencies: T002

T007. [Integration Tests] Define activity/idle shutdown scenarios [P]
- `tests/integration/test_idle_shutdown.py`: after idle timeout, service transitions to cold and new request re-warms
- Dependencies: T002

T008. [Unit Tests] Config loader tests [P]
- `tests/unit/test_config_loader.py`: load `hestia_config.yml`, env overrides, validation errors
- Dependencies: T002

T009. [Unit Tests] Strategy loader tests [P]
- `tests/unit/test_strategy_loader.py`: discover/load from `strategies/`, prevent duplicate registrations
- Dependencies: T002

T010. [Unit Tests] Data model tests [P]
- `tests/unit/test_models.py`: SQLAlchemy models and constraints from `data-model.md`
- Dependencies: T002

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

T015. [Source] SQLAlchemy models per `data-model.md`
- Tables: Service, Machine, RoutingRule, Activity, AuthKey
- Dependencies: T010

T016. [Source] Persistence provider (SQLite) and initialization
- Create engine, session management, migrations bootstrap (if needed)
- Dependencies: T015

T017. [Source] Strategy plugin loader
- Load from `strategies/` via importlib; registry with thread-safe singleton
- Dependencies: T009

T018. [Source] Readiness checker
- Health endpoint polling; warm-up delay fallback per service
- Dependencies: T006

T019. [Source] Startup policy engine
- Retry with limit/delay; fallback machine selection; terminal error and event log
- Dependencies: T005, T016, T017, T018

T020. [Source] Request queue for cold services
- FIFO, bounded size, per-service timeouts; prevent duplicate startups
- Dependencies: T004, T019

T021. [Source] Transparent proxy implementation
- Implement proxy for `/services/{serviceId}/{proxyPath}` using httpx; preserve method, headers, body; stream response
- Dependencies: T003, T020

T022. [Source] Generic POST `/v1/requests` dispatcher
- Accept GatewayRequest, route to service, use queue/strategy engines
- Dependencies: T003, T020

T023. [Source] Service status and proactive start endpoints
- GET status, POST start; integrate with readiness and queue
- Dependencies: T003, T018, T019

T024. [Source] Optional auth middleware
- API key for API; dashboard username/password stub; warnings when disabled
- Dependencies: T004, T008

T025. [Source] Structured logging and basic metrics
- Log events per FR-013; add request IDs; counters/timers skeleton
- Dependencies: T004, T005

T026. [Integration] Semaphore API client and mocks
- httpx client; internal URL `http://semaphore:3000`; respx mocks in tests
- Dependencies: T003, T022

T027. [CI/CD] GitHub Actions: lint and format
- Ruff + Black on push to main
- Dependencies: T002

T028. [CI/CD] GitHub Actions: tests
- Install deps and run `pytest`
- Dependencies: T002, T003

T029. [Docs] Example `strategies/` and `hestia_config.yml`
- Provide placeholders and comments for customization
- Dependencies: T014, T017

T030. [Docs] Update quickstart with curl examples and stable URL
- Verify `/services/{serviceId}/...` usage and note `OLLAMA_BASE_URL=http://localhost:8080/services/ollama`
- Dependencies: T021

## Parallelization Guide
- [P] T003, T004, T005, T006, T007, T008, T009, T010 can run in parallel after T002
- [P] T027 and T028 can run in parallel after T002

## Suggested Task Agent Commands
- tasks run T003
- tasks run T004
- tasks run T005
- tasks run T006
- tasks run T007
- tasks run T008
- tasks run T009
- tasks run T010
