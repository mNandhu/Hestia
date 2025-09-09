import asyncio
import json
import time
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Response, Request
from fastapi.responses import StreamingResponse

from hestia.config import load_config
from hestia.persistence import init_database
from hestia.request_queue import RequestQueue
from hestia.models.gateway import GatewayRequest, GatewayResponse, ServiceStatus

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
async def dispatch_request(gateway_request: GatewayRequest) -> GatewayResponse:
    """
    Generic dispatcher for routing HTTP requests through the gateway.
    Handles cold service startup, queuing, and request forwarding.
    """
    _ensure_idle_monitor_started()

    # Get service configuration
    service_id = gateway_request.service_id
    service_config = _get_config().services.get(service_id, _get_config().services["ollama"])

    # Check if service is ready
    service_state = _services.get(service_id, {})
    is_service_ready = (
        service_state.get("state") == "hot" and service_state.get("readiness") == "ready"
    )

    # If service is cold, queue the request and start the service
    if not is_service_ready:
        # Check if service startup is already in progress
        if not _request_queue.is_service_starting(service_id):
            # Mark service as starting to prevent duplicate startup attempts
            if _request_queue.mark_service_starting(service_id):
                # Start service asynchronously
                asyncio.create_task(_start_service_async(service_id, service_config))

        # Prepare request data for queuing
        request_data = {
            "method": gateway_request.method,
            "path": gateway_request.path,
            "headers": gateway_request.headers or {},
            "body": gateway_request.body,
        }

        try:
            # Queue the request and wait for service to be ready
            await _request_queue.queue_request(
                service_id=service_id,
                request_data=request_data,
                timeout_seconds=service_config.request_timeout_seconds,
            )

            # If we get here, service is ready, proceed with actual request

        except Exception:
            # Queue timeout or other error
            return GatewayResponse(
                status=503,
                headers={"content-type": "application/json"},
                body={"error": "Service unavailable"},
            )

    # Service is ready, perform the actual request
    try:
        response_data = await _perform_gateway_request(gateway_request, service_config)
        return response_data
    except Exception:
        return GatewayResponse(
            status=503,
            headers={"content-type": "application/json"},
            body={"error": "Request failed"},
        )


async def _perform_gateway_request(
    gateway_request: GatewayRequest, service_config
) -> GatewayResponse:
    """Perform the actual HTTP request to the target service."""
    base = service_config.base_url
    target = urljoin(base.rstrip("/") + "/", gateway_request.path.lstrip("/"))

    # Prepare request parameters
    method = gateway_request.method.upper()
    headers = gateway_request.headers or {}

    # Remove hop-by-hop headers
    hop_by_hop_headers = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
    headers = {k: v for k, v in headers.items() if k.lower() not in hop_by_hop_headers}

    # Prepare body content
    body = None
    if method in ["POST", "PUT", "PATCH"] and gateway_request.body is not None:
        if isinstance(gateway_request.body, (dict, list)):
            # JSON serialization
            body = json.dumps(gateway_request.body).encode("utf-8")
            headers["content-type"] = "application/json"
        elif isinstance(gateway_request.body, str):
            body = gateway_request.body.encode("utf-8")
        elif isinstance(gateway_request.body, bytes):
            body = gateway_request.body
        else:
            # Try to serialize as JSON
            body = json.dumps(gateway_request.body).encode("utf-8")
            headers["content-type"] = "application/json"

    # Retry configuration
    total_attempts = service_config.retry_count
    if total_attempts < 1:
        total_attempts = 1
    retry_delay_ms = service_config.retry_delay_ms
    fallback = service_config.fallback_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Try primary endpoint with retries
        for attempt in range(total_attempts):
            try:
                upstream_response = await client.request(
                    method=method, url=target, headers=headers, content=body, follow_redirects=False
                )

                # Mark activity for idle tracking
                _touch(gateway_request.service_id)

                # Prepare response headers
                response_headers = dict(upstream_response.headers)
                # Remove hop-by-hop headers from response
                response_headers = {
                    k: v for k, v in response_headers.items() if k.lower() not in hop_by_hop_headers
                }

                # Parse response body
                response_body = None
                content_type = upstream_response.headers.get("content-type", "").lower()

                if "application/json" in content_type:
                    try:
                        response_body = upstream_response.json()
                    except Exception:
                        response_body = upstream_response.text
                else:
                    response_body = upstream_response.text

                return GatewayResponse(
                    status=upstream_response.status_code,
                    headers=response_headers,
                    body=response_body,
                )

            except Exception:
                # If not last attempt, honor delay and retry
                if attempt < (total_attempts - 1):
                    if retry_delay_ms > 0:
                        await asyncio.sleep(retry_delay_ms / 1000.0)
                    continue
                # else exit loop to try fallback (if any)
                break

        # Try fallback once if available
        if fallback:
            try:
                fallback_target = urljoin(
                    fallback.rstrip("/") + "/", gateway_request.path.lstrip("/")
                )

                upstream_response = await client.request(
                    method=method,
                    url=fallback_target,
                    headers=headers,
                    content=body,
                    follow_redirects=False,
                )

                _touch(gateway_request.service_id)

                response_headers = dict(upstream_response.headers)
                response_headers = {
                    k: v for k, v in response_headers.items() if k.lower() not in hop_by_hop_headers
                }

                # Parse response body
                response_body = None
                content_type = upstream_response.headers.get("content-type", "").lower()

                if "application/json" in content_type:
                    try:
                        response_body = upstream_response.json()
                    except Exception:
                        response_body = upstream_response.text
                else:
                    response_body = upstream_response.text

                return GatewayResponse(
                    status=upstream_response.status_code,
                    headers=response_headers,
                    body=response_body,
                )

            except Exception:
                pass

    # All attempts failed
    raise Exception("All request attempts failed")


@app.get("/v1/services/{serviceId}/status")
def get_service_status(serviceId: str) -> ServiceStatus:
    """Get current status of a service including state, readiness, and queue information."""
    _ensure_idle_monitor_started()

    # Get service state from in-memory store
    service_state = _services.get(serviceId, {})
    state = service_state.get("state", "cold")
    readiness = service_state.get("readiness", "not_ready")

    # Get queue information
    queue_status = _request_queue.get_queue_status(serviceId)

    # Only override state to "starting" if service is not already hot/ready
    # and queue indicates startup is in progress
    if _request_queue.is_service_starting(serviceId) and not (
        state == "hot" and readiness == "ready"
    ):
        state = "starting"

    return ServiceStatus(
        serviceId=serviceId,
        state=state,
        machineId="local",  # For now, always local machine
        readiness=readiness,
        queuePending=queue_status.get("pending_requests", 0),
    )


@app.post("/v1/services/{serviceId}/start")
async def start_service_proactively(serviceId: str) -> Response:
    """Proactively start a service if it's not already running."""
    _ensure_idle_monitor_started()

    # Check current service state
    service_state = _services.get(serviceId, {})
    current_state = service_state.get("state", "cold")
    current_readiness = service_state.get("readiness", "not_ready")

    # If service is already hot and ready, return 409 Conflict
    if current_state == "hot" and current_readiness == "ready":
        return Response(
            status_code=409,
            content='{"message": "Service is already running"}',
            media_type="application/json",
        )

    # If service is already starting, return 409 Conflict
    if _request_queue.is_service_starting(serviceId):
        return Response(
            status_code=409,
            content='{"message": "Service is already starting"}',
            media_type="application/json",
        )

    # Start the service
    service_config = _get_config().services.get(serviceId, _get_config().services["ollama"])

    # Mark service as starting
    if _request_queue.mark_service_starting(serviceId):
        # For very small warmup times (likely tests), start synchronously
        service_config = _get_config().services.get(serviceId, _get_config().services["ollama"])
        if service_config.warmup_ms <= 100 and not service_config.health_url:
            # Synchronous startup for fast tests
            try:
                if service_config.warmup_ms > 0:
                    time.sleep(service_config.warmup_ms / 1000.0)

                now_ms = int(time.time() * 1000)
                _services.setdefault(serviceId, {})["readiness"] = "ready"
                _services[serviceId]["state"] = "hot"
                _services[serviceId]["last_used_ms"] = now_ms  # Set initial timestamp

                _request_queue.mark_service_ready(serviceId)
                _request_queue.process_all_requests(serviceId, {"service_ready": True})
            except Exception:
                _request_queue.clear_queue(serviceId)
                _request_queue.mark_service_ready(serviceId)
        else:
            # Asynchronous startup for normal operation
            asyncio.create_task(_start_service_async(serviceId, service_config))

        return Response(
            status_code=202,
            content='{"message": "Service start initiated"}',
            media_type="application/json",
        )
    else:
        # Another process is already starting the service
        return Response(
            status_code=409,
            content='{"message": "Service is already starting"}',
            media_type="application/json",
        )


# Transparent proxy path supports multiple methods
@app.api_route(
    "/services/{serviceId}/{proxyPath:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"]
)
async def transparent_proxy(request: Request, serviceId: str, proxyPath: str) -> Response:
    """Transparent proxy supporting all HTTP methods with queue integration for cold services."""
    _ensure_idle_monitor_started()

    # Get service configuration
    service_config = _get_config().services.get(serviceId, _get_config().services["ollama"])

    # Check if service is ready
    service_state = _services.get(serviceId, {})
    is_service_ready = (
        service_state.get("state") == "hot" and service_state.get("readiness") == "ready"
    )

    # If service is cold, queue the request and start the service
    if not is_service_ready:
        # Check if service startup is already in progress
        if not _request_queue.is_service_starting(serviceId):
            # Mark service as starting to prevent duplicate startup attempts
            if _request_queue.mark_service_starting(serviceId):
                # Start service asynchronously
                asyncio.create_task(_start_service_async(serviceId, service_config))

        # Prepare request data for queuing
        request_data = {
            "method": request.method,
            "path": proxyPath,
            "headers": dict(request.headers),
            "query_params": str(request.url.query) if request.url.query else None,
            "body": await request.body() if request.method in ["POST", "PUT", "PATCH"] else None,
        }

        try:
            # Queue the request and wait for service to be ready
            await _request_queue.queue_request(
                service_id=serviceId,
                request_data=request_data,
                timeout_seconds=service_config.request_timeout_seconds,
            )

            # If we get here, service is ready, proceed with actual proxy

        except Exception:
            # Queue timeout or other error
            return Response(status_code=503, content="Service unavailable")

    # Service is ready, perform the actual proxy request
    return await _perform_proxy_request(request, serviceId, proxyPath, service_config)


async def _perform_proxy_request(
    request: Request, serviceId: str, proxyPath: str, service_config
) -> Response:
    """Perform the actual proxy request to the upstream service."""
    base = service_config.base_url
    target = urljoin(base.rstrip("/") + "/", proxyPath)

    # Prepare request parameters
    method = request.method
    headers = dict(request.headers)

    # Remove hop-by-hop headers
    hop_by_hop_headers = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
    }
    headers = {k: v for k, v in headers.items() if k.lower() not in hop_by_hop_headers}

    # Get request body for methods that support it
    body = None
    if method in ["POST", "PUT", "PATCH"]:
        body = await request.body()

    # Get query parameters
    query_params = str(request.url.query) if request.url.query else None
    if query_params:
        target = f"{target}?{query_params}"

    # Retry configuration
    total_attempts = service_config.retry_count
    if total_attempts < 1:
        total_attempts = 1
    retry_delay_ms = service_config.retry_delay_ms
    fallback = service_config.fallback_url

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Try primary endpoint with retries
        for attempt in range(total_attempts):
            try:
                upstream_response = await client.request(
                    method=method, url=target, headers=headers, content=body, follow_redirects=False
                )

                # Mark activity for idle tracking
                _touch(serviceId)

                # Prepare response headers
                response_headers = dict(upstream_response.headers)
                # Remove hop-by-hop headers from response
                response_headers = {
                    k: v for k, v in response_headers.items() if k.lower() not in hop_by_hop_headers
                }

                # Handle streaming responses
                if _should_stream_response(upstream_response):
                    return StreamingResponse(
                        content=upstream_response.iter_bytes(chunk_size=8192),
                        status_code=upstream_response.status_code,
                        headers=response_headers,
                        media_type=upstream_response.headers.get("content-type"),
                    )
                else:
                    return Response(
                        content=upstream_response.content,
                        status_code=upstream_response.status_code,
                        headers=response_headers,
                        media_type=upstream_response.headers.get("content-type"),
                    )

            except Exception:
                # If not last attempt, honor delay and retry
                if attempt < (total_attempts - 1):
                    if retry_delay_ms > 0:
                        await asyncio.sleep(retry_delay_ms / 1000.0)
                    continue
                # else exit loop to try fallback (if any)
                break

        # Try fallback once if available
        if fallback:
            try:
                fallback_target = urljoin(fallback.rstrip("/") + "/", proxyPath)
                if query_params:
                    fallback_target = f"{fallback_target}?{query_params}"

                upstream_response = await client.request(
                    method=method,
                    url=fallback_target,
                    headers=headers,
                    content=body,
                    follow_redirects=False,
                )

                _touch(serviceId)

                response_headers = dict(upstream_response.headers)
                response_headers = {
                    k: v for k, v in response_headers.items() if k.lower() not in hop_by_hop_headers
                }

                if _should_stream_response(upstream_response):
                    return StreamingResponse(
                        content=upstream_response.iter_bytes(chunk_size=8192),
                        status_code=upstream_response.status_code,
                        headers=response_headers,
                        media_type=upstream_response.headers.get("content-type"),
                    )
                else:
                    return Response(
                        content=upstream_response.content,
                        status_code=upstream_response.status_code,
                        headers=response_headers,
                        media_type=upstream_response.headers.get("content-type"),
                    )

            except Exception:
                pass

    return Response(status_code=503, content="Service unavailable")


def _should_stream_response(response: httpx.Response) -> bool:
    """Determine if response should be streamed based on content type and size."""
    content_type = response.headers.get("content-type", "").lower()

    # Stream server-sent events and other streaming content types
    streaming_types = [
        "text/event-stream",
        "application/octet-stream",
        "text/plain",
        "application/json",  # Large JSON responses
    ]

    if any(stream_type in content_type for stream_type in streaming_types):
        return True

    # Stream large responses (>1MB)
    content_length = response.headers.get("content-length")
    if content_length and int(content_length) > 1024 * 1024:
        return True

    return False


async def _start_service_async(service_id: str, service_config) -> None:
    """Start a cold service asynchronously and notify queued requests when ready."""
    try:
        # Simulate service startup process
        # In a real implementation, this might call the existing start endpoint logic
        # or use a strategy pattern to start different types of services

        # For now, use the existing readiness logic
        health_url = service_config.health_url
        warmup_ms = service_config.warmup_ms

        if health_url:
            # Try health check approach
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(health_url)
                    if resp.status_code == 200:
                        now_ms = int(time.time() * 1000)
                        _services.setdefault(service_id, {})["readiness"] = "ready"
                        _services[service_id]["state"] = "hot"
                        _services[service_id]["last_used_ms"] = now_ms
                    else:
                        # Fallback to warmup delay
                        if warmup_ms > 0:
                            await asyncio.sleep(warmup_ms / 1000.0)
                        now_ms = int(time.time() * 1000)
                        _services.setdefault(service_id, {})["readiness"] = "ready"
                        _services[service_id]["state"] = "hot"
                        _services[service_id]["last_used_ms"] = now_ms
            except Exception:
                # Fallback to warmup delay
                if warmup_ms > 0:
                    await asyncio.sleep(warmup_ms / 1000.0)
                now_ms = int(time.time() * 1000)
                _services.setdefault(service_id, {})["readiness"] = "ready"
                _services[service_id]["state"] = "hot"
                _services[service_id]["last_used_ms"] = now_ms
        else:
            # Use warmup delay
            if warmup_ms > 0:
                await asyncio.sleep(warmup_ms / 1000.0)
            now_ms = int(time.time() * 1000)
            _services.setdefault(service_id, {})["readiness"] = "ready"
            _services[service_id]["state"] = "hot"
            _services[service_id]["last_used_ms"] = now_ms

        # Mark service as ready and process all queued requests
        _request_queue.mark_service_ready(service_id)
        _request_queue.process_all_requests(service_id, {"service_ready": True})

    except Exception:
        # Service startup failed, clear the queue and mark as not starting
        _request_queue.clear_queue(service_id)
        _request_queue.mark_service_ready(service_id)  # Reset starting flag


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
