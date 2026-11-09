"""App factory. Wires Runtime, routers and the shared upstream HTTP client."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from hestia import __version__
from hestia.api import proxy, services
from hestia.core.config import API_PREFIX, Settings
from hestia.core.logging_setup import setup_logging
from hestia.services.registry import Registry
from hestia.services.runtime import Runtime


def create_app(
    settings: Settings | None = None,
    registry: Registry | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """`registry` and `transport` are injection points for tests."""
    settings = settings or Settings()
    setup_logging(settings.log_level)
    runtime = Runtime(
        settings=settings, registry=registry or Registry.load(settings.config_path)
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # trust_env=False: a gateway must not route through HTTP(S)_PROXY from its env.
        # timeout=None here; each proxied request sets its Service's own timeouts.
        async with httpx.AsyncClient(
            transport=transport, trust_env=False, timeout=None
        ) as client:
            runtime.client = client
            try:
                yield
            finally:
                runtime.client = None

    app = FastAPI(title="Hestia", version=__version__, lifespan=lifespan)
    app.state.runtime = runtime

    @app.get("/health", include_in_schema=False)
    async def health():
        return {"status": "ok"}

    app.include_router(services.router, prefix=API_PREFIX)
    app.include_router(proxy.router)
    return app


def app_factory() -> FastAPI:
    """Entry for `uvicorn --factory hestia.main:app_factory` (dev reload)."""
    return create_app()
