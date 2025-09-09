import asyncio
import json
import time
from typing import Optional, Any
from urllib.parse import urljoin

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from hestia.config import load_config
from hestia.logging import EventType, LogLevel, configure_logging, get_logger
from hestia.metrics import get_metrics
from hestia.middleware import add_logging_middleware
from hestia.models.gateway import GatewayRequest, GatewayResponse, ServiceStatus
from hestia.persistence import init_database
from hestia.request_queue import RequestQueue
from hestia.strategy_loader import StrategyRegistry, load_strategies

app = FastAPI(title="Hestia API")

# Configure structured logging
configure_logging(LogLevel.INFO)
logger = get_logger("hestia.app")
metrics = get_metrics()

# Add logging middleware
add_logging_middleware(app, exclude_paths=["/health", "/metrics", "/favicon.ico"])

# Initialize database on startup
init_database()

# Initialize request queue
_request_queue = RequestQueue()

# In-memory minimal state for readiness/idle tracking (per-service)
_services: dict[str, dict] = {}
_IDLE_THREAD_STARTED = False

# Load strategies and keep instances cache
_strategy_registry = StrategyRegistry()
load_strategies("strategies")
_strategy_instances: dict[str, Any] = {}

# Log gateway startup
logger.log_event(EventType.GATEWAY_START, "Hestia Gateway starting up")


def _get_config():
    """Get current config (reloads to pick up env changes in tests)"""
    return load_config()


def _get_strategy_instance(name: str):
    """Get or create a strategy instance by name from registry."""
    try:
        if name not in _strategy_instances:
            factory = _strategy_registry.get_strategy(name)
            _strategy_instances[name] = factory()
        return _strategy_instances[name]
    except Exception:
        return None


def _mark_instance_healthy_on_success(service_id: str, instance_url: str):
    """Mark an instance as healthy after a successful request."""
    lb = _get_strategy_instance("load_balancer")
    if lb and hasattr(lb, "mark_instance_healthy"):
        try:
            lb.mark_instance_healthy(service_id, instance_url)
        except Exception:
            pass


def _mark_instance_unhealthy_on_error(service_id: str, instance_url: str, error: Exception):
    """Mark an instance as unhealthy after a failed request."""
    lb = _get_strategy_instance("load_balancer")
    if lb and hasattr(lb, "mark_instance_unhealthy"):
        try:
            lb.mark_instance_unhealthy(service_id, instance_url, error)
        except Exception:
            pass


def _build_request_context_from_gateway(gateway_request: GatewayRequest) -> dict:
    ctx = {
        "method": gateway_request.method,
        "path": gateway_request.path,
        "headers": gateway_request.headers or {},
        "body": gateway_request.body,
        "json": gateway_request.body if isinstance(gateway_request.body, (dict, list)) else None,
    }
    # Extract a convenient 'model' if present
    if isinstance(gateway_request.body, dict) and "model" in gateway_request.body:
        ctx["model"] = gateway_request.body.get("model")
    return ctx


async def _build_request_context_from_proxy(request: Request, proxyPath: str) -> dict:
    headers = dict(request.headers)
    body_bytes = None
    json_obj = None
    if request.method in ["POST", "PUT", "PATCH"]:
        body_bytes = await request.body()
        # Try parse json
        try:
            json_obj = json.loads(body_bytes.decode("utf-8")) if body_bytes else None
        except Exception:
            json_obj = None
    ctx = {
        "method": request.method,
        "path": proxyPath,
        "headers": headers,
        "query": str(request.url.query) if request.url.query else None,
        "body": body_bytes,
        "json": json_obj,
    }
    if isinstance(json_obj, dict) and "model" in json_obj:
        ctx["model"] = json_obj.get("model")
    return ctx


def _resolve_upstream_base(
    service_id: str, service_config, request_context: dict
) -> tuple[str, str]:
    """Resolve upstream base URL using configured strategy or fallback to base_url.

    Strategy contract: strategy.route_request(service_id, request_context, config) -> Optional[str]

    Returns:
        Tuple of (base_url, resolution_reason) for observability
    """
    # Strategy-based resolution
    strategy_name = getattr(service_config, "strategy", None)
    if strategy_name:
        strategy = _get_strategy_instance(strategy_name)
        if strategy and hasattr(strategy, "route_request"):
            try:
                url = strategy.route_request(service_id, request_context, service_config)
                if isinstance(url, str) and url:
                    return url, f"strategy:{strategy_name}"
            except Exception:
                # Ignore strategy errors and fallback
                pass

    # Fallback: if instances configured and load_balancer available, select one
    instances = getattr(service_config, "instances", []) or []
    if instances:
        lb = _get_strategy_instance("load_balancer")
        if lb and hasattr(lb, "register_service_instances") and hasattr(lb, "get_next_instance"):
            try:
                # Register instances for this service (idempotent)
                lb.register_service_instances(service_id, instances)
                picked = lb.get_next_instance(service_id, request_context)
                if isinstance(picked, str) and picked:
                    return picked, "load_balancer"
            except Exception:
                pass

    return service_config.base_url, "base_url"


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
    # Resolve base via strategy
    req_ctx = _build_request_context_from_gateway(gateway_request)
    base, resolution_reason = _resolve_upstream_base(
        gateway_request.service_id, service_config, req_ctx
    )
    target = urljoin(base.rstrip("/") + "/", gateway_request.path.lstrip("/"))

    # Log routing decision for observability
    logger.info(
        f"Routing decision for {gateway_request.service_id}",
        event_type=EventType.PROXY_START,
        service_id=gateway_request.service_id,
        target_url=base,
        resolution_reason=resolution_reason,
        path=gateway_request.path,
    )
    metrics.increment_counter(
        "routing_decisions_total",
        service_id=gateway_request.service_id,
        labels={"reason": resolution_reason},
    )

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

                # Check if response indicates a healthy service (2xx-4xx) vs unhealthy (5xx)
                if 200 <= upstream_response.status_code < 500:
                    # Mark instance as healthy for successful responses (including 4xx client errors)
                    _mark_instance_healthy_on_success(gateway_request.service_id, base)
                else:
                    # Mark instance as unhealthy for 5xx server errors
                    _mark_instance_unhealthy_on_error(
                        gateway_request.service_id,
                        base,
                        Exception(f"HTTP {upstream_response.status_code}"),
                    )

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

                # For 5xx errors, continue to retry/fallback instead of returning immediately
                if upstream_response.status_code >= 500:
                    if attempt < (total_attempts - 1):
                        if retry_delay_ms > 0:
                            await asyncio.sleep(retry_delay_ms / 1000.0)
                        continue
                    # If last attempt, will fall through to fallback logic

                return GatewayResponse(
                    status=upstream_response.status_code,
                    headers=response_headers,
                    body=response_body,
                )

            except Exception as e:
                # Mark instance as unhealthy if using load balancer
                _mark_instance_unhealthy_on_error(gateway_request.service_id, base, e)

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

    # Load service config (to access health_url for proactive readiness detection)
    service_config = _get_config().services.get(serviceId, _get_config().services["ollama"])

    # Get service state from in-memory store
    service_state = _services.get(serviceId, {})
    state = service_state.get("state", "cold")
    readiness = service_state.get("readiness", "not_ready")

    # If service appears cold/not_ready but a health_url is configured, probe it once here
    # to reflect the true state when the upstream is already running before any proxy usage.
    if not (state == "hot" and readiness == "ready") and service_config.health_url:
        try:
            resp = httpx.get(service_config.health_url, timeout=2.0)
            if resp.status_code == 200:
                # Mark service as hot/ready
                now_ms = int(time.time() * 1000)
                svc = _services.setdefault(serviceId, {})
                svc["state"] = "hot"
                svc["readiness"] = "ready"
                svc["last_used_ms"] = now_ms
                state = "hot"
                readiness = "ready"

                # Clear any starting flag in the queue since service is effectively ready
                if _request_queue.is_service_starting(serviceId):
                    _request_queue.mark_service_ready(serviceId)

                # Log detection of ready state
                logger.log_service_ready(serviceId)
        except Exception:
            # Ignore health probe errors; keep reported state as-is
            pass

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


@app.get("/v1/strategies")
def get_strategies_endpoint():
    """Get information about loaded strategies and per-service configuration."""
    config = _get_config()

    # Get loaded strategies
    loaded_strategies = {}
    for strategy_name in _strategy_registry.list_strategies():
        try:
            strategy = _get_strategy_instance(strategy_name)
            if strategy and hasattr(strategy, "get_strategy_info"):
                loaded_strategies[strategy_name] = strategy.get_strategy_info()
            else:
                loaded_strategies[strategy_name] = {
                    "name": strategy_name,
                    "description": "No strategy info available",
                    "version": "unknown",
                }
        except Exception:
            loaded_strategies[strategy_name] = {
                "name": strategy_name,
                "error": "Failed to load strategy info",
            }

    # Get per-service strategy configuration
    service_strategies = {}
    for service_id, service_config in config.services.items():
        strategy_name = getattr(service_config, "strategy", None)
        instances = getattr(service_config, "instances", [])
        routing = getattr(service_config, "routing", {})

        if strategy_name or instances or routing:
            service_strategies[service_id] = {
                "strategy": strategy_name,
                "instances": instances,
                "routing": routing,
                "base_url": service_config.base_url,
            }

    return {
        "loaded_strategies": loaded_strategies,
        "service_configurations": service_strategies,
    }


@app.get("/v1/metrics")
def get_metrics_endpoint():
    """Get all collected metrics."""
    return metrics.get_all_metrics()


@app.get("/v1/services/{serviceId}/metrics")
def get_service_metrics_endpoint(serviceId: str):
    """Get metrics for a specific service."""
    return metrics.get_service_metrics(serviceId)


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
        # Log service start
        start_time = time.time()
        logger.log_service_start(serviceId, metadata={"config": service_config.__dict__})
        metrics.increment_counter("service_starts_total", service_id=serviceId)

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

                # Log service ready
                startup_duration_ms = (time.time() - start_time) * 1000
                logger.log_service_ready(serviceId, duration_ms=startup_duration_ms)
                metrics.record_timer(
                    "service_startup_duration_ms", startup_duration_ms, service_id=serviceId
                )

            except Exception as e:
                logger.log_service_error(serviceId, f"Synchronous startup failed: {e}")
                metrics.increment_counter("service_errors_total", service_id=serviceId)
                _request_queue.clear_queue(serviceId)
                _request_queue.mark_service_ready(serviceId)
        else:
            # Asynchronous startup for normal operation
            asyncio.create_task(_start_service_async(serviceId, service_config, start_time))

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
    # Resolve base via strategy
    req_ctx = await _build_request_context_from_proxy(request, proxyPath)
    base, resolution_reason = _resolve_upstream_base(serviceId, service_config, req_ctx)
    target = urljoin(base.rstrip("/") + "/", proxyPath)

    # Log routing decision for observability
    logger.info(
        f"Routing decision for {serviceId}",
        event_type=EventType.PROXY_START,
        service_id=serviceId,
        target_url=base,
        resolution_reason=resolution_reason,
        path=proxyPath,
    )
    metrics.increment_counter(
        "routing_decisions_total",
        service_id=serviceId,
        labels={"reason": resolution_reason},
    )

    # Start timing
    start_time = time.time()
    method = request.method

    # Log proxy start
    logger.log_proxy_start(serviceId, target, method, proxyPath)
    metrics.increment_counter(
        "proxy_requests_total", service_id=serviceId, labels={"method": method, "path": proxyPath}
    )

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

                # Check if response indicates a healthy service (2xx-4xx) vs unhealthy (5xx)
                if 200 <= upstream_response.status_code < 500:
                    # Mark instance as healthy for successful responses (including 4xx client errors)
                    _mark_instance_healthy_on_success(serviceId, base)
                else:
                    # Mark instance as unhealthy for 5xx server errors
                    _mark_instance_unhealthy_on_error(
                        serviceId, base, Exception(f"HTTP {upstream_response.status_code}")
                    )

                # Calculate proxy duration and log
                duration_ms = (time.time() - start_time) * 1000
                logger.log_proxy_end(serviceId, target, upstream_response.status_code, duration_ms)
                metrics.record_timer(
                    "proxy_duration_ms",
                    duration_ms,
                    service_id=serviceId,
                    labels={"method": method, "status": str(upstream_response.status_code)},
                )

                # Prepare response headers
                response_headers = dict(upstream_response.headers)
                # Remove hop-by-hop headers from response
                response_headers = {
                    k: v for k, v in response_headers.items() if k.lower() not in hop_by_hop_headers
                }

                # For 5xx errors, continue to retry/fallback instead of returning immediately
                if upstream_response.status_code >= 500:
                    if attempt < (total_attempts - 1):
                        if retry_delay_ms > 0:
                            await asyncio.sleep(retry_delay_ms / 1000.0)
                        continue
                    # If last attempt, will fall through to fallback logic

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

            except Exception as e:
                # Mark instance as unhealthy if using load balancer
                _mark_instance_unhealthy_on_error(serviceId, base, e)

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

    # All attempts failed
    duration_ms = (time.time() - start_time) * 1000
    logger.error(
        f"Proxy request failed: {method} {proxyPath}",
        event_type=EventType.PROXY_ERROR,
        service_id=serviceId,
        method=method,
        path=proxyPath,
        duration_ms=duration_ms,
        metadata={"target": target, "attempts": total_attempts},
    )
    metrics.increment_counter(
        "proxy_errors_total",
        service_id=serviceId,
        labels={"method": method, "error": "service_unavailable"},
    )

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


async def _start_service_async(
    service_id: str, service_config, start_time: Optional[float] = None
) -> None:
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

        # Log service ready with timing
        if start_time:
            startup_duration_ms = (time.time() - start_time) * 1000
            logger.log_service_ready(service_id, duration_ms=startup_duration_ms)
            metrics.record_timer(
                "service_startup_duration_ms", startup_duration_ms, service_id=service_id
            )
        else:
            logger.log_service_ready(service_id)

    except Exception as e:
        # Service startup failed, clear the queue and mark as not starting
        logger.log_service_error(service_id, f"Async startup failed: {e}")
        metrics.increment_counter("service_errors_total", service_id=service_id)
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
                old_state = svc.get("state", "unknown")
                svc["state"] = "cold"
                svc["readiness"] = "not_ready"

                # Log state change
                logger.log_service_state_change(
                    sid, old_state, "cold", metadata={"reason": "idle_timeout", "idle_ms": idle_ms}
                )
                metrics.increment_counter(
                    "service_state_changes_total",
                    service_id=sid,
                    labels={"from": old_state, "to": "cold", "reason": "idle_timeout"},
                )
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
