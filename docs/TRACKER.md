# Hestia tracker

Status of every piece of work in the redesign. Reasoning, decisions (D1–D8) and
the per-phase design live in `redesign-plan.md`; terms in `../CONTEXT.md`.

Legend: `[ ]` open, `[x]` done (commit hash), `[-]` dropped (reason). Phase 1 shipped
as the initial commit, so its items say that instead of a hash.
IDs: `H` housekeeping, `P<phase>.<n>` phase work, `X` deployment, `B` bugs found
later, `Q` open questions. **Update the line in the same commit as the work.** Don't make a separate commit
just to record a hash; fold tracker updates into the next substantive commit.
New items get the next free ID; never reuse one.

## Housekeeping

- [x] **H1** Move legacy repo to `../Hestia-legacy`; new repo at `~/Projects/Hestia`
- [x] **H2** First commit of phase 1; `hestia.yml` stays ignored (initial commit)
- [x] **H3** Legacy GitHub repo renamed `mNandhu/Hestia` → `mNandhu/Hestia-Legacy-v2` and made private (2026-11-09; 0 stars/forks lost). Local `../Hestia-legacy` remote updated. The name `Hestia-Legacy` was already taken by the older Jun–Aug 2025 generation (private, untouched)
- [x] **H6** New public `mNandhu/Hestia` created and pushed; AGPL-3.0-or-later (initial commit)
- [x] **H4** CI green on GitHub (initial commit)
- [ ] **H5** Pre-commit hook (ruff check + format on staged `.py`)

## Phase 1 — Registry + streaming proxy

- [x] **P1.1** `hestia.yml` registry: strict validation (`extra=forbid`, id pattern), no secrets (`services/registry.py`) (initial commit)
- [x] **P1.2** `/services/<id>/<path>` streaming proxy: no buffering either way, hop-by-hop stripping, `X-Forwarded-*`, repeated headers kept (`services/proxy_stream.py`) (initial commit)
- [x] **P1.3** Error mapping 404 `unknown_service` / 502 `upstream_unreachable` / 504 `upstream_timeout`; mid-stream failure aborts the connection (initial commit)
- [x] **P1.4** In-flight tracking, released on success, upstream error and client disconnect (`services/activity.py`) (initial commit)
- [x] **P1.5** `GET /api/v1/services`, `/{id}`, `/{id}/health`; root `/health` (initial commit)
- [x] **P1.6** `hestia serve | check` CLI, `justfile`, CI workflow, `CONTEXT.md`, `CLAUDE.md` (initial commit)
- [x] **P1.7** Tests (24): registry, proxy via ASGI, real-uvicorn streaming + disconnect, two real hops for request framing (initial commit)
- [x] **P1.8** Live check vs real Ollama: GET `/api/tags` 200, POST `/api/show` 200 (initial commit)
- [ ] **P1.9** Live check: streamed POST `/api/generate` through Hestia, tokens arrive incrementally (loads a model; do by hand)

## Phase 2 — Lifecycle, Semaphore driver, idle shutdown

- [ ] **P2.1** Registry fields: `driver` (`none` | `semaphore`), `idle_timeout_s`, `start_timeout_s`, `max_waiting`, driver options; reject driver options on `none`
- [ ] **P2.2** `ServiceLifecycle` per Service: states `cold → starting → ready → stopping → cold` + `failed`, one `asyncio.Lock`, waiters on an Event
- [ ] **P2.3** Single-flight wake: concurrent requests to a cold Service trigger exactly one start
- [ ] **P2.4** Ready only after a health probe passes within `start_timeout_s`; failure wakes every waiter → 503 `start_failed`
- [ ] **P2.5** Bounded wait per Service (`max_waiting`) → 503 `queue_full`
- [ ] **P2.6** Driver interface + `none` driver (probe only; Hestia never starts/stops it)
- [ ] **P2.7** `semaphore` driver: persistent session, configurable project id, start/stop template ids, task polling with timeout, credentials from env only
- [ ] **P2.8** Idle monitor: one asyncio task; stop when `idle_for() > idle_timeout_s` and `in_flight == 0`; driver services only
- [ ] **P2.9** Request arriving during `stopping` waits for stop, then wakes again
- [ ] **P2.10** Startup reconciliation: probe every Service on boot to set initial state
- [ ] **P2.11** Lifecycle state + last error in `/api/v1/services` views
- [ ] **P2.12** Fake Semaphore (httpx transport) + tests: success, task failure, timeout, concurrent wake, request during stop, idle stop skipped while streaming
- [ ] **P2.13** Live check: `simple-fastapi` on homelab via real Semaphore — cold start on request, stop after idle

## Phase 3 — Control API + auth

- [ ] **P3.1** `POST /api/v1/services/{id}/start | stop | restart` (driver services only; 409 for `none`)
- [ ] **P3.2** `HESTIA_API_KEY` required on control/config routes; proxy stays open on the tailnet (D3)
- [ ] **P3.3** `GET /api/v1/config` (no secrets in output)
- [ ] **P3.4** `PUT /api/v1/config`: validate → atomic write → hot-swap Registry; Services in flight keep working (D4, D5)
- [ ] **P3.5** Access log as pure ASGI middleware (never `BaseHTTPMiddleware`)
- [ ] **P3.6** Basic metrics: requests, errors by kind, wake count and duration per Service

## Phase 4 — Dashboard

- [ ] **P4.1** pnpm workspace; `packages/frontend` (React, react-router, TanStack Query, Tailwind); builds into the backend package; Vite proxies `/api` in dev
- [ ] **P4.2** Serve built UI from the backend on the same port (mounted last; must not shadow `/services` or `/api`)
- [ ] **P4.3** Services page: state, in-flight, idle time, health; start/stop/restart
- [ ] **P4.4** Config editor (validates server-side, shows errors per service)
- [ ] **P4.5** API key entry for the dashboard
- [ ] **P4.6** `packages/e2e`: Playwright against fake upstream + fake Semaphore servers; CI job

## Phase 5 — Websockets

- [ ] **P5.1** Websocket proxy on `/services/<id>/...`; open sockets count as in flight
- [ ] **P5.2** Route a ComfyUI client through Hestia; verify long cold start + header passthrough

## Deployment

- [ ] **X1** Dockerfile: frontend build stage → uv runtime; healthcheck on `/health`
- [ ] **X2** Compose with Tailscale sidecar (legacy `docker-compose-tailscale.yml` pattern), Semaphore alongside, `hestia.yml` mounted
- [ ] **X3** Replace the legacy deployment on the tailnet (`hestia:8080`); confirm clients using `/services/ollama` keep working

## Bugs found later

_(none yet)_

## Open questions

- [x] **Q1** Repo naming: legacy → `Hestia-Legacy-v2` (private); rebuild takes `Hestia` (see H3, H6)
- [ ] **Q2** Keep `/services/<id>` as the proxy prefix, or also accept bare `/<id>`? (Legacy README used `/services/ollama`; keeping it.)
- [ ] **Q3** Other drivers worth adding after Semaphore: `docker`, wake-on-LAN, shell command?
