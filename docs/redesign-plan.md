# Hestia redesign plan

- **Date started:** 2026-11-09
- **Status:** Phase 1 done (initial commit); Phase 2 next
- **Glossary:** `CONTEXT.md`
- **Tracker:** `docs/TRACKER.md` — item-level status lives there, not here

## Why

The legacy Hestia (`../Hestia-legacy`, 50 commits, last 2026-07) grew from a
Spec-Kit task list into a 1,450-line `app.py`, and its core behaviors were broken:

- Requests to a cold service were never actually held — the queue Future was
  created but never awaited (`app.py:219`, `:811`).
- "Start" marked a service ready even when its health probe failed (`app.py:1184-1229`).
- "Streaming" buffered whole responses before sending.
- Idle shutdown ran in a thread that re-read the YAML every 25 ms and mutated
  shared state without a lock; a failed Semaphore start left a service "starting" forever.
- The HEAD of `feat/frontend` (86b828b) committed stash-conflict markers; the app didn't import.

## Real use (what the design serves)

1. A stable tailnet endpoint for Ollama (`hestia:8080/services/ollama`). Hestia
   only proxies and health-checks it; it never starts/stops it.
2. Wake a home-lab service via Semaphore/Ansible on first request; stop after idle
   (tested in legacy with `simple-fastapi`).
3. Later: a ComfyUI client routed through Hestia — needs websockets,
   long cold starts, header passthrough.

## Decisions

| # | Decision | Why |
|---|---|---|
| D1 | Rebuild in a new repo; legacy kept as archive | Little worth keeping; structure was the problem |
| D2 | Monorepo: `packages/backend` (FastAPI, uv), later `packages/frontend`, `packages/e2e` | Frontend and e2e slot in without restructuring |
| D3 | Proxy open on the tailnet; control/config API needs an API key | Tailnet is the perimeter; protect mutations |
| D4 | `hestia.yml` is the source of truth; the dashboard edits it atomically | Git-friendly, readable |
| D5 | Secrets only from env; never written to YAML | Legacy PUT /config leaked env secrets into YAML |
| D6 | Websocket proxy deferred to phase 5 | Not needed for current use |
| D7 | Per-service **driver** (`none`, `semaphore`) | Start/stop is meaningless for proxy-only services |
| D8 | Idle = no requests **in flight** for `idle_timeout_s` | Never stop a service mid-stream |

### Dropped from legacy (don't port)

SQLAlchemy models + `hestia.db` (never read or written), strategy plugin loader
and load balancer/model router, `/api/v1/requests` JSON envelope dispatcher,
the 724-line custom logger, `BaseHTTPMiddleware` request logging, the implicit
`ollama` default and unknown-id→ollama fallback, the `<SVC>_<FIELD>` env-suffix
config parser, retries/fallback URL (can't replay a streamed body; revisit only
with a real need).

## Phases

### Phase 1 — Registry + streaming proxy ✅
Done; items P1.1–P1.9 in the tracker (P1.9, a live streamed generate, still open).

### Phase 2 — Lifecycle, Semaphore driver, idle shutdown
- `ServiceLifecycle` owner per Service: state machine + `asyncio.Lock`; waiters
  block on an Event; ready only after a health probe passes within `start_timeout_s`;
  failure wakes every waiter with an error (→ 503 `start_failed`).
- Single-flight wake: concurrent requests to a cold Service trigger one start.
- Bounded wait queue per Service (`max_waiting`) → 503 `queue_full`.
- Drivers: `none` (always considered running; probe only), `semaphore`
  (persistent session, configurable project id, start/stop template ids,
  task polling with timeout; credentials from env).
- Idle monitor: one asyncio task, checks `activity.idle_for()` against
  `idle_timeout_s`; never stops while in flight; a request arriving during
  `stopping` waits, then wakes again.
- Startup reconciliation: on boot, probe each Service to set initial state.
- Tests: fake Semaphore (`httpx` transport) covering success, task failure,
  timeout, concurrent wake, request during stop.

### Phase 3 — Control API + auth
- `POST /api/v1/services/{id}/start|stop|restart` (driver services only).
- `GET/PUT /api/v1/config`: validate → atomic write → hot-swap Registry.
- API key (`HESTIA_API_KEY`) required on control/config routes; proxy stays open.
- Structured access log as pure ASGI middleware; basic metrics.

### Phase 4 — Dashboard
- `packages/frontend`: React + react-router + TanStack Query + Tailwind; builds
  into the backend package, served on the same port; Vite proxies `/api` in dev.
- Service list with state, in-flight, idle time; start/stop; config editor.
- `packages/e2e`: Playwright against fake upstream + fake Semaphore servers.

### Phase 5 — Websockets
- Websocket proxy on the same route; open sockets count as in flight.
- Route a ComfyUI client through Hestia; verify long cold start tolerance.

### Deployment (alongside phase 2/3)
- Single Dockerfile (frontend build stage → uv runtime), compose with
  Tailscale sidecar (legacy `docker-compose-tailscale.yml` pattern), healthcheck on `/health`.

## Status log

- **2026-11-09** — Legacy moved to `../Hestia-legacy`. Phase 1 implemented:
  24 tests green, ruff clean; real Ollama GET + POST through the proxy verified.
  Upstream request framing checked over real sockets (fixed body → Content-Length
  only; streamed body → chunked only). Published as public
  `mNandhu/Hestia` (AGPL-3.0-or-later); legacy renamed `Hestia-Legacy-v2` (private). CI green.
