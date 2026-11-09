"""Activity: per-Service in-flight count and last-activity time.

A request is in flight from the moment the proxy accepts it until its response
stream is fully closed (finished, failed, or client gone). Idle shutdown (phase 2)
must only fire when in_flight == 0, so long LLM streams are never cut off.
"""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class ServiceActivity:
    in_flight: int = 0
    last_activity: float = field(default_factory=time.monotonic)

    def idle_for(self, now: float | None = None) -> float:
        """Seconds since the last request ended; 0 while anything is in flight."""
        if self.in_flight:
            return 0.0
        return (now if now is not None else time.monotonic()) - self.last_activity


class ActivityTracker:
    def __init__(self) -> None:
        self._by_id: dict[str, ServiceActivity] = {}

    def get(self, service_id: str) -> ServiceActivity:
        return self._by_id.setdefault(service_id, ServiceActivity())

    def begin(self, service_id: str) -> None:
        a = self.get(service_id)
        a.in_flight += 1
        a.last_activity = time.monotonic()

    def end(self, service_id: str) -> None:
        a = self.get(service_id)
        a.in_flight = max(0, a.in_flight - 1)
        a.last_activity = time.monotonic()

    @contextmanager
    def track(self, service_id: str):
        self.begin(service_id)
        try:
            yield
        finally:
            self.end(service_id)
