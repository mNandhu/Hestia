"""Service registry: the declarative list of Services, loaded from YAML.

The YAML never holds secrets. Phase 2 adds lifecycle fields (driver, idle timeout);
until then a Service is just an upstream Hestia proxies to.
"""

import re
from pathlib import Path

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    field_validator,
)

SERVICE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class RegistryError(Exception):
    """Registry file missing or invalid. Message is safe to show to the user."""


class Timeouts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Time to open a TCP connection to the upstream.
    connect_s: float = Field(default=10.0, gt=0)
    # Max gap between bytes from the upstream. Generous: a cold model load can
    # stall the first token for minutes. None disables it.
    read_s: float | None = Field(default=600.0, gt=0)


class Service(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    # Base URL requests are forwarded to; the path after /services/<id> is appended.
    upstream: HttpUrl
    # Path on the upstream that answers 2xx when the service is ready.
    health_path: str = "/"
    timeouts: Timeouts = Timeouts()

    @field_validator("health_path")
    @classmethod
    def _leading_slash(cls, v: str) -> str:
        return v if v.startswith("/") else "/" + v

    @property
    def upstream_base(self) -> str:
        return str(self.upstream).rstrip("/")


class Registry:
    def __init__(self, services: list[Service]):
        self._by_id = {s.id: s for s in services}

    def get(self, service_id: str) -> Service | None:
        return self._by_id.get(service_id)

    def all(self) -> list[Service]:
        return list(self._by_id.values())

    @classmethod
    def from_dict(cls, data: dict | None) -> "Registry":
        raw = (data or {}).get("services") or {}
        if not isinstance(raw, dict):
            raise RegistryError("`services` must be a mapping of id -> service")
        services = []
        for sid, body in raw.items():
            if not isinstance(sid, str) or not SERVICE_ID.match(sid):
                raise RegistryError(
                    f"invalid service id {sid!r}: use lowercase letters, digits, '-'"
                )
            try:
                services.append(Service.model_validate({**(body or {}), "id": sid}))
            except ValidationError as e:
                raise RegistryError(f"service {sid!r}: {e}") from e
        return cls(services)

    @classmethod
    def load(cls, path: Path) -> "Registry":
        if not path.exists():
            raise RegistryError(f"registry file not found: {path}")
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise RegistryError(f"{path}: invalid YAML: {e}") from e
        if data is not None and not isinstance(data, dict):
            raise RegistryError(f"{path}: top level must be a mapping")
        return cls.from_dict(data)
