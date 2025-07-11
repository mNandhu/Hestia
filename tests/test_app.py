"""
Tests for the main application and API endpoints.
"""

from typing import Any
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
from httpx import Response

from hestia.app import app
from hestia.schemas import NoRouteResponse, ProxyResponse, ColdStartResponse


class TestMainApp:
    """Test main application functionality."""

    def test_root_endpoint(self):
        """Test the root endpoint."""
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200
        assert response.json() == {"status": "Hestia is alive"}

    def test_gateway_nonexistent_service(self, client: TestClient) -> None:
        """Test gateway with non-existent service."""
        response: Response = client.get("/api/nonexistent_service/some/path")
        assert response.status_code == 404
        assert "not found in configuration" in response.json()["detail"]

    @patch("hestia.app.execute_strategy")
    def test_gateway_no_route_decision(
        self, mock_execute_strategy: Mock, client: TestClient
    ) -> None:
        """Test gateway when strategy returns no routes."""
        mock_execute_strategy.return_value = []

        response: Response = client.get("/api/test_service/some/path")
        assert response.status_code == 200

        data: dict[str, Any] = response.json()
        assert data["decision"] == "no_route"
        assert data["service"] == "test_service"
        assert "context" in data

    @patch("hestia.app.execute_strategy")
    def test_gateway_cold_start_decision(
        self, mock_execute_strategy: Mock, client: TestClient
    ) -> None:
        """Test gateway when service is cold and needs starting."""
        mock_execute_strategy.return_value = ["http://localhost:8001"]

        response: Response = client.get("/api/test_service/model/chat")
        assert response.status_code == 200

        data: dict[str, Any] = response.json()
        assert data["decision"] == "initiate_cold_start"
        assert data["service"] == "test_service"
        assert data["target_url"] == "http://localhost:8001"
        assert data["path"] == "model/chat"
        assert "next_steps" in data

    @patch("hestia.app.execute_strategy")
    @patch("hestia.app.get_service_state")
    @patch("hestia.app.update_service_status")
    def test_gateway_hot_service_proxy(
        self,
        mock_update_service_status: Mock,
        mock_get_service_state: Mock,
        mock_execute_strategy: Mock,
        client: TestClient,
    ) -> None:
        """Test gateway when service is hot and ready."""
        # Mock a hot service state
        mock_service_state = Mock()
        mock_service_state.status = "hot"
        mock_service_state.active_host_url = "http://localhost:8001"
        mock_get_service_state.return_value = mock_service_state

        # Mock the updated service state returned by update_service_status
        mock_updated_state = Mock()
        mock_updated_state.active_host_url = "http://localhost:8001"
        mock_update_service_status.return_value = mock_updated_state

        mock_execute_strategy.return_value = ["http://localhost:8001"]

        response: Response = client.get("/api/test_service/model/chat")
        assert response.status_code == 200

        data: dict[str, Any] = response.json()
        assert data["decision"] == "proxy_request"
        assert data["service"] == "test_service"
        assert data["target_url"] == "http://localhost:8001"
        assert data["path"] == "model/chat"

    @patch("hestia.app.execute_strategy")
    def test_gateway_strategy_execution_error(
        self, mock_execute_strategy: Mock, client: TestClient
    ) -> None:
        """Test gateway when strategy execution fails."""
        mock_execute_strategy.side_effect = FileNotFoundError("Strategy file not found")

        response: Response = client.get("/api/test_service/some/path")
        assert response.status_code == 500
        assert "Strategy execution failed" in response.json()["detail"]

    def test_gateway_different_http_methods(self, client: TestClient) -> None:
        """Test gateway with different HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]

        with patch("hestia.app.execute_strategy") as mock_strategy:
            mock_strategy.return_value = []

            for method in methods:
                response: Response = client.request(
                    method, "/api/test_service/endpoint"
                )
                assert response.status_code == 200
                data: dict[str, Any] = response.json()
                assert data["decision"] == "no_route"

    @patch("hestia.app.execute_strategy")
    def test_gateway_context_assembly(
        self, mock_execute_strategy: Mock, client: TestClient
    ) -> None:
        """Test that the gateway properly assembles context for strategies."""
        mock_execute_strategy.return_value = []

        headers = {"X-Custom-Header": "test-value", "User-Agent": "test-agent"}
        client.get(
            "/api/test_service/some/path", headers=headers
        )  # Test getting response

        # Check that execute_strategy was called with proper context
        mock_execute_strategy.assert_called_once()
        args, _ = mock_execute_strategy.call_args
        context = args[1]  # Second argument is context

        assert context["service_name"] == "test_service"
        assert context["request_method"] == "GET"
        assert context["request_path"] == "/some/path"
        assert "request_headers" in context
        assert context["request_headers"]["x-custom-header"] == "test-value"
        assert "configured_hosts" in context

    @patch("hestia.app.execute_strategy")
    def test_gateway_post_with_body(
        self, mock_execute_strategy: Mock, client: TestClient
    ) -> None:
        """Test gateway with POST request and body."""
        mock_execute_strategy.return_value = []

        test_data = {"model": "test-model", "prompt": "Hello"}
        response: Response = client.post("/api/test_service/chat", json=test_data)

        assert response.status_code == 200
        mock_execute_strategy.assert_called_once()

    def test_multiple_services_configuration(self, client: TestClient) -> None:
        """Test that multiple services can be configured and accessed."""
        with patch("hestia.app.execute_strategy") as mock_strategy:
            mock_strategy.return_value = []

            # Test first service
            response: Response = client.get("/api/test_service/endpoint1")
            assert response.status_code == 200
            assert response.json()["service"] == "test_service"

            # Test second service (empty_service from test config)
            response = client.get("/api/empty_service/endpoint2")
            assert response.status_code == 200
            assert response.json()["service"] == "empty_service"

    @patch("hestia.app.execute_strategy")
    @patch("hestia.app.get_service_state")
    @patch("hestia.app.update_service_status")
    def test_service_state_creation_on_first_access(
        self,
        mock_update_service_status: Mock,
        mock_get_service_state: Mock,
        mock_execute_strategy: Mock,
        client: TestClient,
    ) -> None:
        """Test that service state is created when accessed for the first time."""
        # Mock: service doesn't exist initially, then exists after creation
        mock_get_service_state.side_effect = [
            None,
            Mock(),
        ]  # First call returns None, second returns a mock state
        mock_execute_strategy.return_value = []

        # This should create the service state
        response: Response = client.get("/api/test_service/some/path")
        assert response.status_code == 200

        # Verify that update_service_status was called to create the state
        mock_update_service_status.assert_called_once()

    @patch("hestia.app.execute_strategy")
    def test_strategy_absolute_path_construction(
        self, mock_execute_strategy: Mock, client: TestClient
    ) -> None:
        """Test that strategy script paths are converted to absolute paths."""
        mock_execute_strategy.return_value = []

        client.get("/api/test_service/some/path")  # Test getting response

        # Check that the strategy was called with an absolute path
        mock_execute_strategy.assert_called_once()
        args, _ = mock_execute_strategy.call_args
        strategy_path = args[0]  # First argument is strategy path

        # Should be an absolute path
        import os

        assert os.path.isabs(strategy_path)
        assert strategy_path.endswith("strategies/mock_router.py")


class TestResponseModels:
    """Test response model serialization."""

    def test_no_route_response_serialization(self) -> None:
        """Test NoRouteResponse serialization."""
        response = NoRouteResponse(
            decision="no_route",
            service="test_service",
            reason="No hosts available",
            context={"test": "data"},
        )

        serialized: dict[str, Any] = response.model_dump()
        assert serialized["decision"] == "no_route"
        assert serialized["service"] == "test_service"
        assert serialized["reason"] == "No hosts available"
        assert serialized["context"]["test"] == "data"

    def test_proxy_response_serialization(self) -> None:
        """Test ProxyResponse serialization."""
        response = ProxyResponse(
            decision="proxy_request",
            service="test_service",
            reason="Service is hot",
            target_url="http://localhost:8001",
            path="model/chat",
        )

        serialized: dict[str, Any] = response.model_dump()
        assert serialized["decision"] == "proxy_request"
        assert serialized["service"] == "test_service"
        assert serialized["target_url"] == "http://localhost:8001"
        assert serialized["path"] == "model/chat"

    def test_cold_start_response_serialization(self) -> None:
        """Test ColdStartResponse serialization."""
        response = ColdStartResponse(
            decision="initiate_cold_start",
            service="test_service",
            reason="Service is cold",
            target_url="http://localhost:8001",
            path="model/chat",
            next_steps=["Start service", "Wait for health check", "Proxy request"],
        )

        serialized: dict[str, Any] = response.model_dump()
        assert serialized["decision"] == "initiate_cold_start"
        assert serialized["service"] == "test_service"
        assert serialized["target_url"] == "http://localhost:8001"
        assert serialized["path"] == "model/chat"
        assert len(serialized["next_steps"]) == 3
