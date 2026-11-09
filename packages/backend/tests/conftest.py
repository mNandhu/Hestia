import contextlib

import httpx
import pytest

from hestia.core.config import Settings
from hestia.main import create_app
from hestia.services.registry import Registry

from fake_upstream import FakeUpstream

SERVICES = {
    "services": {
        "ollama": {"upstream": "http://ollama.test:11434", "health_path": "/api/tags"},
        "sub": {"upstream": "http://sub.test/base/"},
    }
}


@pytest.fixture
def upstream() -> FakeUpstream:
    return FakeUpstream()


@pytest.fixture
def make_client(tmp_path):
    """make_client(upstream) -> async context yielding (client, app)."""

    @contextlib.asynccontextmanager
    async def _make(up: FakeUpstream, services: dict = SERVICES):
        app = create_app(Settings(home=tmp_path), Registry.from_dict(services), up)
        async with app.router.lifespan_context(app):
            transport = httpx.ASGITransport(app=app, client=("10.0.0.7", 5555))
            async with httpx.AsyncClient(
                transport=transport, base_url="http://hestia.test"
            ) as c:
                yield c, app

    return _make
