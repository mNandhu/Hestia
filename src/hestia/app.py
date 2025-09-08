import os
import time
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Response

app = FastAPI(title="Hestia API")


# In-memory minimal state for readiness/idle tracking (per-service)
_services: dict[str, dict] = {}


@app.post("/v1/requests")
def dispatch_request() -> Response:
    # Stub implementation to satisfy contract tests
    return Response(status_code=501)


@app.get("/v1/services/{serviceId}/status")
def get_status(serviceId: str):
    state = _services.get(serviceId, {"state": "cold", "readiness": "not_ready"})
    return _json(state)


@app.post("/v1/services/{serviceId}/start")
def start_service(serviceId: str):
    # Initialize service state
    now_ms = int(time.time() * 1000)
    svc = _services.setdefault(
        serviceId, {"state": "starting", "readiness": "not_ready", "last_used_ms": now_ms}
    )
    svc["state"] = "starting"
    svc["readiness"] = "not_ready"
    svc["last_used_ms"] = now_ms

    health_url = _get_service_health_url(serviceId)
    warmup_ms = _get_int_env("OLLAMA_WARMUP_MS", 0) if serviceId == "ollama" else 0

    # Background: poll health or wait warmup
    if health_url:
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(health_url)
                if resp.status_code == 200:
                    svc["readiness"] = "ready"
                    svc["state"] = "hot"
        except Exception:
            # keep not_ready
            pass
    else:
        if warmup_ms > 0:
            time.sleep(warmup_ms / 1000.0)
        svc["readiness"] = "ready"
        svc["state"] = "hot"

    return Response(status_code=202)


# Transparent proxy path supports multiple methods; stub all
@app.get("/services/{serviceId}/{proxyPath:path}")
def transparent_proxy_get(serviceId: str, proxyPath: str) -> Response:
    # Minimal behavior to satisfy integration test for ollama GET
    base = _resolve_service_base_url(serviceId)
    target = urljoin(base.rstrip("/") + "/", proxyPath)
    # Interpret retry count as TOTAL attempts on primary (including the first attempt)
    total_attempts = _get_int_env("OLLAMA_RETRY_COUNT", 1)
    if total_attempts < 1:
        total_attempts = 1
    retry_delay_ms = _get_int_env("OLLAMA_RETRY_DELAY_MS", 0)
    fallback = os.getenv("OLLAMA_FALLBACK_URL") if serviceId == "ollama" else None

    with httpx.Client(timeout=10.0) as client:
        for attempt in range(total_attempts):
            try:
                upstream = client.get(target)
                # mark activity
                _touch(serviceId)
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"),
                )
            except Exception:
                # if not last attempt, honor delay and retry
                if attempt < (total_attempts - 1):
                    if retry_delay_ms > 0:
                        time.sleep(retry_delay_ms / 1000.0)
                    continue
                # else exit loop to try fallback (if any)
                break

        # Try fallback once if available
        if fallback:
            try:
                fallback_target = urljoin(fallback.rstrip("/") + "/", proxyPath)
                upstream = client.get(fallback_target)
                _touch(serviceId)
                return Response(
                    content=upstream.content,
                    status_code=upstream.status_code,
                    media_type=upstream.headers.get("content-type"),
                )
            except Exception:
                pass

    return Response(status_code=503)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type"),
    )


def _resolve_service_base_url(service_id: str) -> str:
    if service_id == "ollama":
        return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    # Future: look up from config/database
    return os.getenv("Hestia_Default_Service_URL", "http://localhost:8081")


def _get_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except Exception:
        return default


def _get_service_health_url(service_id: str) -> str | None:
    if service_id == "ollama":
        return os.getenv("OLLAMA_HEALTH_URL")
    return None


def _json(payload: dict) -> Response:
    import json as _jsonlib

    return Response(
        content=_jsonlib.dumps(payload),
        media_type="application/json",
        status_code=200,
    )


def _touch(service_id: str) -> None:
    now_ms = int(time.time() * 1000)
    svc = _services.setdefault(
        service_id, {"state": "hot", "readiness": "ready", "last_used_ms": now_ms}
    )
    svc["last_used_ms"] = now_ms


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
