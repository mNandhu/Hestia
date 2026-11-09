"""/services/<id>/<path> — transparent proxy route. Logic lives in services.proxy_stream."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response

from hestia.core.config import PROXY_PREFIX
from hestia.services.proxy_stream import UpstreamError, forward
from hestia.services.runtime import Runtime, get_runtime

router = APIRouter(include_in_schema=False)

METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


@router.api_route(PROXY_PREFIX + "/{service_id}", methods=METHODS)
@router.api_route(PROXY_PREFIX + "/{service_id}/{path:path}", methods=METHODS)
async def proxy(
    service_id: str,
    request: Request,
    path: str = "",
    rt: Runtime = Depends(get_runtime),
) -> Response:
    service = rt.registry.get(service_id)
    if service is None:
        return JSONResponse(
            {"detail": f"unknown service {service_id!r}", "kind": "unknown_service"},
            404,
        )
    assert rt.client is not None, "proxy used outside app lifespan"
    try:
        return await forward(rt.client, service, path, request, rt.activity)
    except UpstreamError as e:
        return JSONResponse({"detail": str(e), "kind": e.kind}, e.status_code)
