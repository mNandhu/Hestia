"""/api/v1/services — read-only view of the registry plus live activity."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from hestia.services.health_probe import probe
from hestia.services.registry import Service
from hestia.services.runtime import Runtime, get_runtime

router = APIRouter(prefix="/services", tags=["services"])


class ServiceView(BaseModel):
    id: str
    upstream: str
    health_path: str
    in_flight: int
    idle_s: float


class HealthView(BaseModel):
    id: str
    ok: bool
    status_code: int | None
    latency_ms: float
    error: str | None


def _view(rt: Runtime, s: Service) -> ServiceView:
    a = rt.activity.get(s.id)
    return ServiceView(
        id=s.id,
        upstream=s.upstream_base,
        health_path=s.health_path,
        in_flight=a.in_flight,
        idle_s=round(a.idle_for(), 1),
    )


def _service(rt: Runtime, service_id: str) -> Service:
    s = rt.registry.get(service_id)
    if s is None:
        raise HTTPException(404, f"unknown service {service_id!r}")
    return s


@router.get("", response_model=list[ServiceView])
async def list_services(rt: Runtime = Depends(get_runtime)):
    return [_view(rt, s) for s in rt.registry.all()]


@router.get("/{service_id}", response_model=ServiceView)
async def get_service(service_id: str, rt: Runtime = Depends(get_runtime)):
    return _view(rt, _service(rt, service_id))


@router.get("/{service_id}/health", response_model=HealthView)
async def service_health(service_id: str, rt: Runtime = Depends(get_runtime)):
    s = _service(rt, service_id)
    assert rt.client is not None
    r = await probe(rt.client, s)
    return HealthView(
        id=s.id,
        ok=r.ok,
        status_code=r.status_code,
        latency_ms=r.latency_ms,
        error=r.error,
    )
