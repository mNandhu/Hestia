import os
from typing import Dict, Optional, Any, List

import yaml
from pydantic import BaseModel, Field, field_validator


class ServiceConfig(BaseModel):
    base_url: str = "http://localhost:11434"
    retry_count: int = Field(default=1, ge=0)
    retry_delay_ms: int = Field(default=0, ge=0)
    health_url: Optional[str] = None
    warmup_ms: int = Field(default=0, ge=0)
    idle_timeout_ms: int = Field(default=0, ge=0)
    fallback_url: Optional[str] = None
    # Request queue configuration
    queue_size: int = Field(default=100, ge=1)
    request_timeout_seconds: int = Field(default=60, ge=1)
    # Strategy-based routing (optional)
    instances: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of upstream instances for strategies like load_balancer/model_router",
    )
    strategy: Optional[str] = Field(
        default=None, description="Optional strategy name to select upstream per-request"
    )
    routing: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary strategy-specific routing configuration (e.g., by_model)",
    )

    # Semaphore automation configuration
    semaphore_enabled: bool = Field(
        default=False, description="Enable Semaphore automation for this service"
    )
    semaphore_machine_id: Optional[str] = Field(
        default=None, description="Target machine ID for Semaphore tasks"
    )
    semaphore_start_template_id: int = Field(
        default=1, description="Semaphore template ID for start tasks"
    )
    semaphore_stop_template_id: int = Field(
        default=2, description="Semaphore template ID for stop tasks"
    )
    semaphore_task_timeout: int = Field(
        default=300, description="Maximum time to wait for Semaphore tasks (seconds)"
    )
    semaphore_poll_interval: float = Field(
        default=2.0, description="Interval between Semaphore status polls (seconds)"
    )

    @field_validator("retry_count")
    @classmethod
    def validate_retry_count(cls, v):
        if v < 0:
            raise ValueError("retry_count must be >= 0")
        return v

    @field_validator("idle_timeout_ms")
    @classmethod
    def validate_idle_timeout(cls, v):
        if v < 0:
            raise ValueError("idle_timeout_ms must be >= 0")
        return v


class HestiaConfig(BaseModel):
    services: Dict[str, ServiceConfig] = Field(default_factory=dict)

    # Global Semaphore configuration
    semaphore_base_url: Optional[str] = Field(default=None, description="Semaphore server base URL")
    semaphore_timeout: int = Field(
        default=30, description="HTTP timeout for Semaphore API calls (seconds)"
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Ensure ollama service always exists with defaults
        if "ollama" not in self.services:
            self.services["ollama"] = ServiceConfig()


def load_config(config_path: str = "hestia_config.yml") -> HestiaConfig:
    """Load configuration from YAML file with environment variable overrides."""
    config_data = {}

    # Try to load from YAML file
    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f) or {}
    except FileNotFoundError:
        # File doesn't exist, use defaults
        pass
    except Exception as e:
        # Log error but continue with defaults
        print(f"Warning: Failed to load config from {config_path}: {e}")

    # Ensure services section exists
    if "services" not in config_data:
        config_data["services"] = {}

    # Ensure ollama service exists
    if "ollama" not in config_data["services"]:
        config_data["services"]["ollama"] = {}

    # Load global Semaphore configuration from environment
    semaphore_base_url = os.getenv("SEMAPHORE_BASE_URL")
    if semaphore_base_url:
        config_data["semaphore_base_url"] = semaphore_base_url

    semaphore_timeout = os.getenv("SEMAPHORE_TIMEOUT")
    if semaphore_timeout:
        try:
            config_data["semaphore_timeout"] = int(semaphore_timeout)
        except ValueError:
            print(f"Warning: Invalid integer value for SEMAPHORE_TIMEOUT: {semaphore_timeout}")

    # Load services from environment variables
    # Format: <SERVICE_ID>_<CONFIG_KEY> = value
    _load_services_from_environment(config_data["services"])

    return HestiaConfig(**config_data)


def _load_services_from_environment(services_config: Dict[str, Any]):
    """Load service configurations from environment variables."""

    # Standard field mappings for all services
    field_mappings = {
        "BASE_URL": ("base_url", str),
        "RETRY_COUNT": ("retry_count", int),
        "RETRY_DELAY_MS": ("retry_delay_ms", int),
        "HEALTH_URL": ("health_url", str),
        "WARMUP_MS": ("warmup_ms", int),
        "IDLE_TIMEOUT_MS": ("idle_timeout_ms", int),
        "FALLBACK_URL": ("fallback_url", str),
        "QUEUE_SIZE": ("queue_size", int),
        "REQUEST_TIMEOUT_SECONDS": ("request_timeout_seconds", int),
        # Semaphore fields
        "SEMAPHORE_ENABLED": ("semaphore_enabled", bool),
        "SEMAPHORE_MACHINE_ID": ("semaphore_machine_id", str),
        "SEMAPHORE_START_TEMPLATE_ID": ("semaphore_start_template_id", int),
        "SEMAPHORE_STOP_TEMPLATE_ID": ("semaphore_stop_template_id", int),
        "SEMAPHORE_TASK_TIMEOUT": ("semaphore_task_timeout", int),
        "SEMAPHORE_POLL_INTERVAL": ("semaphore_poll_interval", float),
    }

    # Collect all environment variables that match service patterns
    service_env_vars = {}
    for env_key, env_value in os.environ.items():
        if env_value is None:
            continue

        # Look for pattern: <SERVICE_ID>_<FIELD_NAME>
        found_field = None
        service_id = None

        for field_name in field_mappings.keys():
            if env_key.endswith(f"_{field_name}"):
                # Extract service ID
                service_id = env_key[: -len(f"_{field_name}")].lower().replace("_", "-")
                found_field = field_name
                break

        if found_field and service_id:
            if service_id not in service_env_vars:
                service_env_vars[service_id] = {}
            service_env_vars[service_id][found_field] = env_value

    # Apply environment variables to service configurations
    for service_id, env_vars in service_env_vars.items():
        if service_id not in services_config:
            services_config[service_id] = {}

        service_config = services_config[service_id]

        for env_field, env_value in env_vars.items():
            config_field, field_type = field_mappings[env_field]

            try:
                if field_type is bool:
                    # Handle boolean values
                    service_config[config_field] = env_value.lower() in ("true", "1", "yes", "on")
                elif field_type is int:
                    service_config[config_field] = int(env_value)
                elif field_type is float:
                    service_config[config_field] = float(env_value)
                else:
                    service_config[config_field] = env_value
            except (ValueError, TypeError) as e:
                print(
                    f"Warning: Invalid {field_type.__name__} value for {service_id}.{config_field}: {env_value} ({e})"
                )
