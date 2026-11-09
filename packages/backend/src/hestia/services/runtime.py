"""Runtime: everything one running Hestia process shares, hung off app.state.

No module-level singletons: tests build a fresh Runtime per app.
"""

from dataclasses import dataclass, field

import httpx
from starlette.requests import HTTPConnection

from hestia.core.config import Settings
from hestia.services.activity import ActivityTracker
from hestia.services.registry import Registry


@dataclass
class Runtime:
    settings: Settings
    registry: Registry
    activity: ActivityTracker = field(default_factory=ActivityTracker)
    # Set in the app lifespan; None outside it.
    client: httpx.AsyncClient | None = None


def get_runtime(conn: HTTPConnection) -> Runtime:
    """FastAPI dependency."""
    return conn.app.state.runtime
