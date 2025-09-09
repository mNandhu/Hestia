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

    # Apply environment variable overrides for ollama service
    ollama_config = config_data["services"]["ollama"]

    # Environment variable mappings
    env_mappings = {
        "OLLAMA_BASE_URL": "base_url",
        "OLLAMA_RETRY_COUNT": "retry_count",
        "OLLAMA_RETRY_DELAY_MS": "retry_delay_ms",
        "OLLAMA_HEALTH_URL": "health_url",
        "OLLAMA_WARMUP_MS": "warmup_ms",
        "OLLAMA_IDLE_TIMEOUT_MS": "idle_timeout_ms",
        "OLLAMA_FALLBACK_URL": "fallback_url",
        "OLLAMA_QUEUE_SIZE": "queue_size",
        "OLLAMA_REQUEST_TIMEOUT_SECONDS": "request_timeout_seconds",
    }

    for env_var, config_key in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            # Convert to appropriate type
            if config_key in [
                "retry_count",
                "retry_delay_ms",
                "warmup_ms",
                "idle_timeout_ms",
                "queue_size",
                "request_timeout_seconds",
            ]:
                try:
                    ollama_config[config_key] = int(env_value)
                except ValueError:
                    print(f"Warning: Invalid integer value for {env_var}: {env_value}")
            else:
                ollama_config[config_key] = env_value

    return HestiaConfig(**config_data)
