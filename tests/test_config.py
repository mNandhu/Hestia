"""
Tests for the configuration module.
"""

import pytest
import yaml
from typing import Dict, Union, List
from pathlib import Path

from hestia.config import load_config, AppConfig, ServiceConfig, HostConfig, AppSettings


class TestConfigLoading:
    """Test configuration loading functionality."""

    def test_load_valid_config(self, tmp_path: Path):
        """Test loading a valid configuration file."""
        config_file = tmp_path / "valid_config.yml"
        config_data: Dict[
            str,
            Union[
                Dict[str, Union[str, int]],
                List[Dict[str, str | List[Dict[str, str | Dict[str, str]]]]],
            ],
        ] = {
            "app": {
                "task_runner_api_url": "http://localhost:8080/run",
                "task_runner_api_key": "secret-key",
                "janitor_interval_seconds": 300,
            },
            "services": [
                {
                    "name": "test_service",
                    "strategy": "strategies/test_router.py",
                    "hosts": [
                        {
                            "name": "host1",
                            "url": "http://localhost:8001",
                            "metadata": {"type": "local"},
                        }
                    ],
                }
            ],
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))

        assert isinstance(config, AppConfig)
        assert config.app.task_runner_api_url == "http://localhost:8080/run"
        assert config.app.task_runner_api_key == "secret-key"
        assert config.app.janitor_interval_seconds == 300
        assert len(config.services) == 1
        assert config.services[0].name == "test_service"
        assert config.services[0].strategy == "strategies/test_router.py"
        assert len(config.services[0].hosts) == 1
        assert config.services[0].hosts[0].name == "host1"
        assert config.services[0].hosts[0].url == "http://localhost:8001"

    def test_load_nonexistent_config(self):
        """Test loading a non-existent configuration file."""
        with pytest.raises(FileNotFoundError, match="Configuration file not found"):
            load_config("nonexistent.yml")

    def test_load_invalid_yaml(self, tmp_path: Path):
        """Test loading an invalid YAML file."""
        config_file = tmp_path / "invalid.yml"
        config_file.write_text("invalid: yaml: content: [")

        with pytest.raises(ValueError, match="Error parsing YAML file"):
            load_config(str(config_file))

    def test_load_empty_config(self, tmp_path: Path):
        """Test loading an empty configuration file."""
        config_file = tmp_path / "empty.yml"
        config_file.write_text("")

        with pytest.raises(ValueError, match="Configuration file is empty"):
            load_config(str(config_file))

    def test_missing_required_fields(self, tmp_path: Path):
        """Test configuration with missing required fields."""
        config_file = tmp_path / "missing_fields.yml"
        config_data: Dict[str, Dict[str, str] | List[None]] = {
            "app": {
                "task_runner_api_url": "http://localhost:8080/run"
                # Missing task_runner_api_key
            },
            "services": [],
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(ValueError, match="Configuration validation error"):
            load_config(str(config_file))

    def test_default_janitor_interval(self, tmp_path: Path):
        """Test that janitor_interval_seconds has a default value."""
        config_file = tmp_path / "default_interval.yml"
        config_data: Dict[str, Dict[str, str] | List[None]] = {
            "app": {
                "task_runner_api_url": "http://localhost:8080/run",
                "task_runner_api_key": "secret-key",
            },
            "services": [],
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        assert config.app.janitor_interval_seconds == 300  # Default value

    def test_host_metadata_optional(self, tmp_path: Path):
        """Test that host metadata is optional."""
        config_file = tmp_path / "no_metadata.yml"
        config_data: Dict[
            str, Dict[str, str] | List[Dict[str, str | List[Dict[str, str]]]]
        ] = {
            "app": {
                "task_runner_api_url": "http://localhost:8080/run",
                "task_runner_api_key": "secret-key",
            },
            "services": [
                {
                    "name": "test_service",
                    "strategy": "strategies/test_router.py",
                    "hosts": [
                        {
                            "name": "host1",
                            "url": "http://localhost:8001",
                            # No metadata field
                        }
                    ],
                }
            ],
        }

        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(str(config_file))
        assert config.services[0].hosts[0].metadata == {}


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_host_config_creation(self):
        """Test HostConfig model creation."""
        host = HostConfig(
            name="test-host", url="http://localhost:8001", metadata={"key": "value"}
        )
        assert host.name == "test-host"
        assert host.url == "http://localhost:8001"
        assert host.metadata == {"key": "value"}

    def test_host_config_empty_metadata(self):
        """Test HostConfig with empty metadata."""
        host = HostConfig(name="test-host", url="http://localhost:8001")
        assert host.metadata == {}

    def test_service_config_creation(self):
        """Test ServiceConfig model creation."""
        hosts = [HostConfig(name="host1", url="http://localhost:8001")]
        service = ServiceConfig(
            name="test-service", strategy="strategies/test.py", hosts=hosts
        )
        assert service.name == "test-service"
        assert service.strategy == "strategies/test.py"
        assert len(service.hosts) == 1

    def test_app_settings_creation(self):
        """Test AppSettings model creation."""
        settings = AppSettings(
            task_runner_api_url="http://localhost:8080/run",
            task_runner_api_key="secret",
        )
        assert settings.task_runner_api_url == "http://localhost:8080/run"
        assert settings.task_runner_api_key == "secret"
        assert settings.janitor_interval_seconds == 300  # Default

    def test_app_config_creation(self):
        """Test AppConfig model creation."""
        app_settings = AppSettings(
            task_runner_api_url="http://localhost:8080/run",
            task_runner_api_key="secret",
        )
        services = [ServiceConfig(name="test", strategy="strategies/test.py", hosts=[])]
        config = AppConfig(app=app_settings, services=services)
        assert config.app.task_runner_api_url == "http://localhost:8080/run"
        assert len(config.services) == 1
