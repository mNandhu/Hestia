"""
Configuration management for Hestia.

This module defines the Pydantic models for Hestia's configuration
and provides a loader to read settings from a YAML file.
"""

import os
from typing import Any, Dict, List

import yaml
from pydantic import BaseModel, Field, ValidationError


class HostConfig(BaseModel):
    """Configuration for a single host/node that can run a service."""

    name: str
    url: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ServiceConfig(BaseModel):
    """Configuration for a managed service."""

    name: str
    strategy: str
    hosts: List[HostConfig]


class AppSettings(BaseModel):
    """General application settings."""

    task_runner_api_url: str
    task_runner_api_key: str
    janitor_interval_seconds: int = 300


class AppConfig(BaseModel):
    """Root configuration model for the application."""

    app: AppSettings
    services: List[ServiceConfig]


def load_config(path: str) -> AppConfig:
    """
    Loads, validates, and returns the application configuration from a YAML file.

    Args:
        path: The path to the YAML configuration file.

    Returns:
        An AppConfig object with the loaded settings.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the configuration file is invalid.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            config_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}") from e

    if not config_data:
        raise ValueError("Configuration file is empty.")

    try:
        return AppConfig.model_validate(config_data)
    except ValidationError as e:
        raise ValueError(f"Configuration validation error: {e}") from e
