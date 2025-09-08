import time
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Response

from hestia.config import load_config
from hestia.persistence import init_database
from hestia.request_queue import RequestQueue

app = FastAPI(title="Hestia API")

# Initialize database on startup
init_database()

# Initialize request queue
_request_queue = RequestQueue()

# In-memory minimal state for readiness/idle tracking (per-service)
_services: dict[str, dict] = {}
_IDLE_THREAD_STARTED = False


def _get_config():
    """Get current config (reloads to pick up env changes in tests)"""
    return load_config()


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
    _ensure_idle_monitor_started()
    # Initialize service state
    now_ms = int(time.time() * 1000)
    svc = _services.setdefault(
        serviceId, {"state": "starting", "readiness": "not_ready", "last_used_ms": now_ms}
    )
    svc["state"] = "starting"
    svc["readiness"] = "not_ready"
    svc["last_used_ms"] = now_ms

    health_url = _get_config().services.get(serviceId, _get_config().services["ollama"]).health_url
    warmup_ms = _get_config().services.get(serviceId, _get_config().services["ollama"]).warmup_ms

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
    _ensure_idle_monitor_started()
    # Minimal behavior to satisfy integration test for ollama GET
    service_config = _get_config().services.get(serviceId, _get_config().services["ollama"])
    base = service_config.base_url
    target = urljoin(base.rstrip("/") + "/", proxyPath)
    # Interpret retry count as TOTAL attempts on primary (including the first attempt)
    total_attempts = service_config.retry_count
    if total_attempts < 1:
        total_attempts = 1
    retry_delay_ms = service_config.retry_delay_ms
    fallback = service_config.fallback_url

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


def _get_idle_timeout_ms(service_id: str) -> int:
    service_config = _get_config().services.get(service_id, _get_config().services["ollama"])
    return service_config.idle_timeout_ms


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


def _idle_monitor_loop():
    check_interval_ms = 25
    while True:
        now_ms = int(time.time() * 1000)
        for sid, svc in list(_services.items()):
            idle_ms = _get_idle_timeout_ms(sid)
            if idle_ms <= 0:
                continue
            last = svc.get("last_used_ms", now_ms)
            # Only flip hot services that have exceeded idle timeout
            if svc.get("state") == "hot" and (now_ms - last) >= idle_ms:
                svc["state"] = "cold"
                svc["readiness"] = "not_ready"
        time.sleep(check_interval_ms / 1000.0)


def _ensure_idle_monitor_started() -> None:
    global _IDLE_THREAD_STARTED
    if _IDLE_THREAD_STARTED:
        return
    import threading

    t = threading.Thread(target=_idle_monitor_loop, name="hestia-idle-monitor", daemon=True)
    t.start()
    _IDLE_THREAD_STARTED = True


def run() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
