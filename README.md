# Hestia

Personal on-demand service gateway. One stable address on the tailnet in front of
home-lab services: Hestia proxies requests to them, wakes them when a request
arrives, and puts them back to sleep when idle.

```
client ──► hestia:8080/services/ollama/api/chat ──► http://<ollama-host>:11434/api/chat
```

> This is a rebuild. The previous implementation lives in `../Hestia-legacy`
> (archive only). See `docs/redesign-plan.md` for why and what changes.

## Status

Phase 1: service registry and streaming reverse proxy. Wake/sleep lifecycle,
the control API and the dashboard come next (see the plan).

## Quick start

```bash
cp hestia.example.yml hestia.yml   # edit services
just dev                           # backend on :8080 with reload
curl localhost:8080/api/v1/services
curl localhost:8080/services/ollama/api/tags
```

Point clients at `http://<hestia>:8080/services/<id>` instead of the service's own
address, e.g. `OLLAMA_BASE_URL=http://hestia:8080/services/ollama`.

## Layout

```
packages/backend/   FastAPI app (Python, uv)
docs/               plans and decisions
CONTEXT.md          glossary — the names used in code
CLAUDE.md           commands, invariants, gotchas
```

## Commands

`just` lists recipes: `dev`, `serve`, `test`, `lint`, `fmt`.
