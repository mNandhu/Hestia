"""Transparent reverse proxy: forward one request to a Service and stream the reply back.

Invariants:
- Bodies are never buffered in either direction (LLM tokens / SSE must flow as produced).
- Every accepted request is in flight in ActivityTracker until the upstream response
  is closed, whatever way the stream ends.
- Transport failures become UpstreamUnreachable / UpstreamTimeout before any byte is
  sent; failures mid-stream abort the client connection (never a silent truncation).
"""

import logging

import anyio
import httpx
from starlette.requests import Request
from starlette.responses import StreamingResponse

from hestia.core.config import PROXY_PREFIX
from hestia.services.activity import ActivityTracker
from hestia.services.registry import Service

log = logging.getLogger(__name__)

# RFC 9110 §7.6.1 connection-specific headers, plus ones the proxy must recompute.
HOP_BY_HOP = frozenset(
    {
        b"connection",
        b"keep-alive",
        b"proxy-authenticate",
        b"proxy-authorization",
        b"proxy-connection",
        b"te",
        b"trailer",
        b"transfer-encoding",
        b"upgrade",
    }
)


class UpstreamError(Exception):
    kind = "upstream_error"
    status_code = 502


class UpstreamUnreachable(UpstreamError):
    kind = "upstream_unreachable"
    status_code = 502


class UpstreamTimeout(UpstreamError):
    kind = "upstream_timeout"
    status_code = 504


def strip_hop_by_hop(raw: list[tuple[bytes, bytes]]) -> list[tuple[bytes, bytes]]:
    """Drop hop-by-hop headers and any header the Connection header names."""
    named = {
        token.strip().lower()
        for k, v in raw
        if k.lower() == b"connection"
        for token in v.split(b",")
    }
    drop = HOP_BY_HOP | named
    return [(k, v) for k, v in raw if k.lower() not in drop]


def _request_headers(request: Request, service: Service) -> list[tuple[bytes, bytes]]:
    headers = [
        (k, v) for k, v in strip_hop_by_hop(request.headers.raw) if k.lower() != b"host"
    ]
    client_ip = request.client.host if request.client else None
    prior = request.headers.get("x-forwarded-for")
    if client_ip:
        xff = f"{prior}, {client_ip}" if prior else client_ip
        headers = [(k, v) for k, v in headers if k.lower() != b"x-forwarded-for"]
        headers.append((b"x-forwarded-for", xff.encode("latin-1")))
    headers += [
        (b"x-forwarded-proto", request.url.scheme.encode("latin-1")),
        (b"x-forwarded-host", request.headers.get("host", "").encode("latin-1")),
        (b"x-forwarded-prefix", f"{PROXY_PREFIX}/{service.id}".encode("latin-1")),
    ]
    return headers


def _has_body(request: Request) -> bool:
    h = request.headers
    return "transfer-encoding" in h or h.get("content-length", "0") not in ("", "0")


def upstream_url(service: Service, path: str, query: str) -> str:
    url = (
        f"{service.upstream_base}/{path.lstrip('/')}"
        if path
        else service.upstream_base + "/"
    )
    return f"{url}?{query}" if query else url


async def forward(
    client: httpx.AsyncClient,
    service: Service,
    path: str,
    request: Request,
    activity: ActivityTracker,
) -> StreamingResponse:
    t = service.timeouts
    upstream_req = client.build_request(
        request.method,
        upstream_url(service, path, request.url.query),
        headers=_request_headers(request, service),
        content=request.stream() if _has_body(request) else None,
        timeout=httpx.Timeout(
            connect=t.connect_s, read=t.read_s, write=t.read_s, pool=t.connect_s
        ),
    )

    activity.begin(service.id)
    try:
        upstream = await client.send(upstream_req, stream=True)
    except BaseException as e:
        activity.end(service.id)
        if isinstance(e, httpx.TimeoutException) and not isinstance(
            e, httpx.ConnectTimeout
        ):
            raise UpstreamTimeout(
                f"{service.id}: upstream timed out ({e.__class__.__name__})"
            ) from e
        if isinstance(e, httpx.TransportError):
            raise UpstreamUnreachable(
                f"{service.id}: cannot reach {service.upstream_base} ({e.__class__.__name__})"
            ) from e
        raise

    response = StreamingResponse(
        _relay(upstream, service.id, activity), status_code=upstream.status_code
    )
    # Raw list keeps repeated headers (Set-Cookie) and the upstream's own
    # content-length / content-encoding, which match the raw bytes we relay.
    response.raw_headers = strip_hop_by_hop(upstream.headers.raw)
    return response


async def _relay(upstream: httpx.Response, service_id: str, activity: ActivityTracker):
    try:
        async for chunk in upstream.aiter_raw():
            yield chunk
    except httpx.TransportError as e:
        log.warning("%s: upstream stream broke mid-response: %r", service_id, e)
        raise
    finally:
        activity.end(service_id)
        # Shield: on client disconnect we're inside a cancelled scope, and an
        # unshielded await here would be cancelled too, leaking the connection.
        with anyio.CancelScope(shield=True):
            await upstream.aclose()
