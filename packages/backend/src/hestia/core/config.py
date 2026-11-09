"""Process settings (env / .env). Service definitions live in the registry YAML, not here."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

API_PREFIX = "/api/v1"
PROXY_PREFIX = "/services"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HESTIA_", env_file=".env", extra="ignore"
    )

    # Root for relative paths below. Defaults to the working directory.
    home: Path = Field(default_factory=Path.cwd)
    # Service registry YAML. Relative paths resolve against `home`.
    config_file: Path = Path("hestia.yml")
    # Bind address for `hestia serve`.
    host: str = "0.0.0.0"
    port: int = 8080
    # Root log level (DEBUG, INFO, WARNING, ...).
    log_level: str = "INFO"

    @property
    def config_path(self) -> Path:
        p = self.config_file.expanduser()
        return p if p.is_absolute() else self.home / p
