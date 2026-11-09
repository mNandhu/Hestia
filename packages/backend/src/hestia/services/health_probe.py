"""Health probe: one GET to a Service's health_path. Never raises."""

import time
from dataclasses import dataclass

import httpx

from hestia.services.registry import Service

PROBE_TIMEOUT_S = 5.0


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    status_code: int | None
    latency_ms: float
    error: str | None = None


async def probe(client: httpx.AsyncClient, service: Service) -> ProbeResult:
    start = time.perf_counter()
    try:
        r = await client.get(
            service.upstream_base + service.health_path, timeout=PROBE_TIMEOUT_S
        )
    except httpx.HTTPError as e:
        return ProbeResult(
            False, None, _ms(start), f"{e.__class__.__name__}: {e}".rstrip(": ")
        )
    return ProbeResult(r.is_success, r.status_code, _ms(start))


def _ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)
