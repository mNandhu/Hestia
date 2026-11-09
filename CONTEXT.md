# Hestia glossary

Names used in code, docs and UI. Keep them in sync with the code: if a term is
renamed in code, rename it here in the same commit. Each term names the module
that owns it.

## Core

**Service** — one upstream Hestia fronts, identified by a lowercase **service id**
(`ollama`, `simple-fastapi`). Declared in the registry; immutable at runtime.
Owner: `services/registry.py` (`Service`).

**Registry** — the set of Services, loaded from the **registry file**
(`hestia.yml`, path from `HESTIA_CONFIG_FILE`). Never holds secrets.
Owner: `services/registry.py` (`Registry`).

**Upstream** — a Service's base URL. The proxy appends the path after
`/services/<id>` to it, keeping any base path (`http://h/base` + `/x` → `http://h/base/x`).

**Health path** — path on the upstream that answers 2xx when the Service is ready.
A **health probe** is one GET to it. Owner: `services/health_probe.py`.

**Proxy route** — `/services/<id>/<path>`. Transparent: method, path, query,
headers and body pass through; only hop-by-hop headers are stripped and
`X-Forwarded-*` added. Owner: `api/proxy.py` → `services/proxy_stream.py`.

**Streaming** — bodies are relayed chunk by chunk in both directions, never
buffered. Required for LLM tokens and SSE.

**In flight** — a proxied request from acceptance until its response stream is
closed (finished, failed, or client gone). Counted per Service.
Owner: `services/activity.py` (`ActivityTracker`).

**Activity** — per-Service `in_flight` count and `last_activity` time. **Idle
for** = seconds since the last request ended; always 0 while anything is in flight.

**Runtime** — everything one running process shares (settings, registry,
activity, upstream HTTP client), on `app.state.runtime`. No module singletons.
Owner: `services/runtime.py`.

**Settings** — process settings from env (`HESTIA_*`) / `.env`. Not the
registry. Owner: `core/config.py`.

## Upstream errors (`services/proxy_stream.py`)

| kind | HTTP | meaning |
|---|---|---|
| `unknown_service` | 404 | no Service with that id |
| `upstream_unreachable` | 502 | connect failed / transport error before the response |
| `upstream_timeout` | 504 | upstream accepted but went silent past `read_s` |

A failure *after* response bytes started aborts the client connection; it is
never turned into a clean (truncated) response.

## Coming in phase 2 (not in code yet)

**Driver** — how a Service is started/stopped: `none` (proxy only; Hestia never
starts or stops it — e.g. ollama), `semaphore` (Semaphore/Ansible task templates).
Only Services with a real driver can be woken or put to sleep.

**Lifecycle state** — `cold → starting → ready → stopping → cold`, plus `failed`.
One owner object per Service holds the state and lock.

**Wake** — starting a cold Service because a request arrived; requests wait
(bounded by **start timeout**) until a health probe passes.

**Idle timeout** — a Service with a driver is stopped once *idle for* exceeds it.
