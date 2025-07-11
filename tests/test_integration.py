"""
Integration tests for the complete Hestia system.
"""

import pytest
import yaml
from fastapi.testclient import TestClient
from pathlib import Path
from typing import Tuple, Any, Dict, List, Union

from hestia.app import app, get_app_config
from hestia.config import load_config


@pytest.mark.integration
class TestHestiaIntegration:
    """End-to-end integration tests."""

    def create_test_environment(self, tmp_path: Path) -> Tuple[str, str]:
        """Create a complete test environment with config and strategy files."""
        # Create strategies directory
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()

        # Create a working strategy file
        test_strategy = strategies_dir / "test_router.py"
        test_strategy.write_text('''
def decide_route(context):
    """Test strategy that returns first configured host."""
    configured_hosts = context.get("configured_hosts", [])
    if configured_hosts:
        return [configured_hosts[0]["url"]]
    return []
''')

        # Create config file
        config_data: Dict[str, Any] = {
            "app": {
                "task_runner_api_url": "http://test-runner:8080/run",
                "task_runner_api_key": "test-secret",
                "janitor_interval_seconds": 300,
            },
            "services": [
                {
                    "name": "integration_service",
                    "strategy": str(test_strategy),
                    "hosts": [
                        {
                            "name": "test_host",
                            "url": "http://localhost:9001",
                            "metadata": {"type": "test"},
                        }
                    ],
                }
            ],
        }

        config_file = tmp_path / "integration_config.yml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        return str(config_file), str(test_strategy)

    def test_complete_workflow_cold_service(self, tmp_path: Path) -> None:
        """Test complete workflow for a cold service."""
        config_file, _ = self.create_test_environment(tmp_path)

        # Override the configuration
        test_config = load_config(config_file)

        with TestClient(app) as client:
            # Override config dependency
            def override_get_app_config():
                return test_config

            app.dependency_overrides[get_app_config] = override_get_app_config

            # Make a request to the integration service
            response = client.get("/api/integration_service/test/endpoint")

            assert response.status_code == 200
            data = response.json()

            # Should be a cold start since service hasn't been accessed before
            assert data["decision"] == "initiate_cold_start"
            assert data["service"] == "integration_service"
            assert data["target_url"] == "http://localhost:9001"
            assert data["path"] == "test/endpoint"

    def test_service_state_persistence(self, tmp_path: Path) -> None:
        """Test that service state persists across requests."""
        config_file, _ = self.create_test_environment(tmp_path)
        test_config = load_config(config_file)

        with TestClient(app) as client:

            def override_get_app_config():
                return test_config

            app.dependency_overrides[get_app_config] = override_get_app_config

            # First request - should create service state
            response1 = client.get("/api/integration_service/endpoint1")
            assert response1.status_code == 200

            # Second request - service state should exist
            response2 = client.get("/api/integration_service/endpoint2")
            assert response2.status_code == 200

            # Both should have same decision logic based on service state

    def test_multiple_services_isolation(self, tmp_path: Path) -> None:
        """Test that multiple services work independently."""
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()

        # Create two different strategies
        strategy1 = strategies_dir / "service1_router.py"
        strategy1.write_text("""
def decide_route(context):
    return ["http://service1:8001"]
""")

        strategy2 = strategies_dir / "service2_router.py"
        strategy2.write_text("""
def decide_route(context):
    return ["http://service2:8002"]
""")

        # Create config with multiple services
        config_data: Dict[
            str, Union[Dict[str, str], List[Dict[str, str | List[Dict[str, str]]]]]
        ] = {
            "app": {
                "task_runner_api_url": "http://test-runner:8080/run",
                "task_runner_api_key": "test-secret",
            },
            "services": [
                {
                    "name": "service1",
                    "strategy": str(strategy1),
                    "hosts": [{"name": "host1", "url": "http://service1:8001"}],
                },
                {
                    "name": "service2",
                    "strategy": str(strategy2),
                    "hosts": [{"name": "host2", "url": "http://service2:8002"}],
                },
            ],
        }

        config_file = tmp_path / "multi_service_config.yml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_config = load_config(str(config_file))

        with TestClient(app) as client:

            def override_get_app_config():
                return test_config

            app.dependency_overrides[get_app_config] = override_get_app_config

            # Test service1
            response1 = client.get("/api/service1/endpoint")
            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["service"] == "service1"
            assert data1["target_url"] == "http://service1:8001"

            # Test service2
            response2 = client.get("/api/service2/endpoint")
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["service"] == "service2"
            assert data2["target_url"] == "http://service2:8002"

    def test_error_handling_integration(self, tmp_path: Path) -> None:
        """Test error handling in complete workflow."""
        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()

        # Create a strategy that raises an error
        error_strategy = strategies_dir / "error_router.py"
        error_strategy.write_text("""
def decide_route(context):
    raise ValueError("Strategy error for testing")
""")

        config_data: Dict[
            str, Union[Dict[str, str], List[Dict[str, str | List[Dict[str, str]]]]]
        ] = {
            "app": {
                "task_runner_api_url": "http://test-runner:8080/run",
                "task_runner_api_key": "test-secret",
            },
            "services": [
                {
                    "name": "error_service",
                    "strategy": str(error_strategy),
                    "hosts": [{"name": "host", "url": "http://localhost:8001"}],
                }
            ],
        }

        config_file = tmp_path / "error_config.yml"
        with open(config_file, "w") as f:
            yaml.dump(config_data, f)

        test_config = load_config(str(config_file))

        with TestClient(app) as client:

            def override_get_app_config():
                return test_config

            app.dependency_overrides[get_app_config] = override_get_app_config

            # Request should return 500 error
            response = client.get("/api/error_service/endpoint")
            assert response.status_code == 500
            assert "Strategy execution failed" in response.json()["detail"]

    def test_config_validation_integration(self, tmp_path: Path) -> None:
        """Test that configuration validation works end-to-end."""
        # Test with invalid config
        invalid_config = tmp_path / "invalid_config.yml"
        invalid_config.write_text("invalid yaml content [")

        with pytest.raises(ValueError, match="Configuration validation error"):
            load_config(str(invalid_config))

        # Test with missing required fields
        incomplete_config = tmp_path / "incomplete_config.yml"
        config_data: Dict[
            str, Union[Dict[str, str], List[Dict[str, str | List[Dict[str, str]]]]]
        ] = {
            "app": {
                "task_runner_api_url": "http://test:8080"
                # Missing task_runner_api_key
            },
            "services": [],
        }

        with open(incomplete_config, "w") as f:
            yaml.dump(config_data, f)

        with pytest.raises(ValueError, match="Configuration validation error"):
            load_config(str(incomplete_config))
