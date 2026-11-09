# Hestia

Personal on-demand service gateway: proxies `/services/<id>/...` to home-lab
services on the tailnet; phase 2 adds wake-on-request and sleep-when-idle.
Glossary: `CONTEXT.md`. Plan: `docs/redesign-plan.md`. Work items:
`docs/TRACKER.md` — tick the item (with commit hash) in the same commit as the work.
Previous implementation: `../Hestia-legacy` (archive — don't port code from it
without checking the plan's "dropped" list).

## Commands

`just` lists them. Common: `just dev` (reload on :8080), `just test [-k x]`,
`just lint`, `just fmt`, `just check` (validate `hestia.yml`).
Backend venv lives in `packages/backend/.venv`; run Python via
`uv run --project packages/backend ...` or from inside `packages/backend`.

## Layout (`packages/backend/src/hestia/`)

- `api/` — thin routers. Map domain errors to HTTP; no logic.
- `services/` — logic, flat `<area>_<thing>.py` files.
- `core/` — settings, logging.
- `main.py` — `create_app(settings, registry, transport)`; the last two are test injection points.
- Tests in `packages/backend/tests/`: `test_<module>.py` unit,
  `test_<x>_integration.py` through the ASGI app, `test_streaming_live.py` through real uvicorn.

## Invariants

- **Never buffer proxied bodies** (`services/proxy_stream.py`). No
  `BaseHTTPMiddleware` anywhere — it breaks streaming. Write pure ASGI middleware if needed.
- **Every accepted proxy request must reach `activity.end()` exactly once**,
  however it ends (success, upstream error, client disconnect). Idle shutdown trusts this.
- **Close upstream responses inside a shielded cancel scope** — on client
  disconnect the relay runs in a cancelled scope.
- **No secrets in `hestia.yml`** or anything the API writes to it; secrets come from env.
- **No module-level singletons** — state hangs off `Runtime` on `app.state`.
- The upstream `httpx.AsyncClient` uses `trust_env=False` (don't route through env proxies).

## Commits

- No AI attribution: no `Co-Authored-By`, `Claude-Session` or similar trailers.
- Few, substantial commits: one per coherent piece of work (a phase, a feature).
  No follow-up commits for small fixes, tracker hashes or typos — fold them into
  the next real commit, or amend before pushing.
- Imperative subject, body lists what changed.

## Gotchas

- `httpx.MockTransport` and `httpx.Response(text=/json=)` pre-read bodies, so
  streaming can't be tested with them; use `tests/fake_upstream.py` (`FakeUpstream`, `Stream`).
- `httpx.ASGITransport` buffers the full response — streaming/disconnect behavior
  is only tested for real in `test_streaming_live.py`.
- httpx adds its own `Connection: keep-alive` on the upstream hop; that's expected.
- Node in non-interactive shells: nvm lazy-loader breaks; use
  `~/.nvm/versions/node/v24.15.0/bin` on PATH (frontend, phase 4).
