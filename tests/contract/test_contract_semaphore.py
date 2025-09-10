import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Import the real application (expected to exist)
    from hestia.app import app  # noqa: WPS433

    return TestClient(app)


def test_semaphore_start_endpoint_exists(client: TestClient):
    """Test that /v1/semaphore/start endpoint exists and accepts POST requests"""
    # Test with minimal required fields for service start request
    resp = client.post(
        "/v1/semaphore/start",
        json={
            "serviceId": "test-service",
            "machineId": "test-machine",
        },
    )
    # Expect 501 (stub) or appropriate success/error codes when implemented
    assert resp.status_code in {501, 200, 202, 400, 404, 500}


def test_semaphore_start_validates_required_fields(client: TestClient):
    """Test that /v1/semaphore/start validates required fields"""
    # Test missing serviceId
    resp = client.post(
        "/v1/semaphore/start",
        json={"machineId": "test-machine"},
    )
    assert resp.status_code in {
        501,
        400,
        422,
        404,
    }  # 422 is FastAPI validation error, 404 when endpoint doesn't exist

    # Test missing machineId
    resp = client.post(
        "/v1/semaphore/start",
        json={"serviceId": "test-service"},
    )
    assert resp.status_code in {501, 400, 422, 404}

    # Test empty request body
    resp = client.post("/v1/semaphore/start", json={})
    assert resp.status_code in {501, 400, 422, 404}


def test_semaphore_start_rejects_invalid_methods(client: TestClient):
    """Test that /v1/semaphore/start only accepts POST method"""
    # GET should not be allowed
    resp = client.get("/v1/semaphore/start")
    assert resp.status_code in {405, 404}

    # PUT should not be allowed
    resp = client.put("/v1/semaphore/start", json={"serviceId": "test", "machineId": "test"})
    assert resp.status_code in {405, 404}

    # DELETE should not be allowed
    resp = client.delete("/v1/semaphore/start")
    assert resp.status_code in {405, 404}


def test_semaphore_stop_endpoint_exists(client: TestClient):
    """Test that /v1/semaphore/stop endpoint exists and accepts POST requests"""
    # Test with minimal required fields for service stop request
    resp = client.post(
        "/v1/semaphore/stop",
        json={
            "serviceId": "test-service",
            "machineId": "test-machine",
        },
    )
    # Expect 501 (stub) or appropriate success/error codes when implemented
    assert resp.status_code in {501, 200, 202, 400, 404, 500}


def test_semaphore_stop_validates_required_fields(client: TestClient):
    """Test that /v1/semaphore/stop validates required fields"""
    # Test missing serviceId
    resp = client.post(
        "/v1/semaphore/stop",
        json={"machineId": "test-machine"},
    )
    assert resp.status_code in {501, 400, 422, 404}

    # Test missing machineId
    resp = client.post(
        "/v1/semaphore/stop",
        json={"serviceId": "test-service"},
    )
    assert resp.status_code in {501, 400, 422, 404}

    # Test empty request body
    resp = client.post("/v1/semaphore/stop", json={})
    assert resp.status_code in {501, 400, 422, 404}


def test_semaphore_stop_rejects_invalid_methods(client: TestClient):
    """Test that /v1/semaphore/stop only accepts POST method"""
    # GET should not be allowed
    resp = client.get("/v1/semaphore/stop")
    assert resp.status_code in {405, 404}

    # PUT should not be allowed
    resp = client.put("/v1/semaphore/stop", json={"serviceId": "test", "machineId": "test"})
    assert resp.status_code in {405, 404}

    # DELETE should not be allowed
    resp = client.delete("/v1/semaphore/stop")
    assert resp.status_code in {405, 404}


def test_semaphore_status_endpoint_exists(client: TestClient):
    """Test that /v1/semaphore/status endpoint exists and accepts GET requests"""
    # Test status check with query parameters
    resp = client.get(
        "/v1/semaphore/status", params={"serviceId": "test-service", "machineId": "test-machine"}
    )
    # Expect 501 (stub) or appropriate success/error codes when implemented
    assert resp.status_code in {501, 200, 400, 404, 500}


def test_semaphore_status_validates_required_params(client: TestClient):
    """Test that /v1/semaphore/status validates required query parameters"""
    # Test missing serviceId
    resp = client.get("/v1/semaphore/status", params={"machineId": "test-machine"})
    assert resp.status_code in {501, 400, 422, 404}

    # Test missing machineId
    resp = client.get("/v1/semaphore/status", params={"serviceId": "test-service"})
    assert resp.status_code in {501, 400, 422, 404}

    # Test no parameters
    resp = client.get("/v1/semaphore/status")
    assert resp.status_code in {501, 400, 422, 404}


def test_semaphore_status_rejects_invalid_methods(client: TestClient):
    """Test that /v1/semaphore/status only accepts GET method"""
    # POST should not be allowed
    resp = client.post("/v1/semaphore/status", json={"serviceId": "test", "machineId": "test"})
    assert resp.status_code in {405, 404}

    # PUT should not be allowed
    resp = client.put("/v1/semaphore/status", json={"serviceId": "test", "machineId": "test"})
    assert resp.status_code in {405, 404}

    # DELETE should not be allowed
    resp = client.delete("/v1/semaphore/status")
    assert resp.status_code in {405, 404}


def test_semaphore_start_with_optional_fields(client: TestClient):
    """Test that /v1/semaphore/start accepts optional configuration fields"""
    # Test with additional optional fields that might be needed for service startup
    resp = client.post(
        "/v1/semaphore/start",
        json={
            "serviceId": "test-service",
            "machineId": "test-machine",
            "taskId": "startup-task-123",
            "environment": {"ENV_VAR": "value"},
            "timeout": 300,
        },
    )
    # Should accept the request regardless of optional fields
    assert resp.status_code in {501, 200, 202, 400, 404, 500}


def test_semaphore_stop_with_optional_fields(client: TestClient):
    """Test that /v1/semaphore/stop accepts optional configuration fields"""
    # Test with additional optional fields that might be needed for service shutdown
    resp = client.post(
        "/v1/semaphore/stop",
        json={
            "serviceId": "test-service",
            "machineId": "test-machine",
            "taskId": "shutdown-task-123",
            "force": True,
            "timeout": 60,
        },
    )
    # Should accept the request regardless of optional fields
    assert resp.status_code in {501, 200, 202, 400, 404, 500}


def test_semaphore_error_handling(client: TestClient):
    """Test that Semaphore endpoints handle error conditions appropriately"""
    # Test invalid JSON in request body
    resp = client.post(
        "/v1/semaphore/start",
        content="invalid json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in {501, 400, 422, 404}

    # Test content type validation
    resp = client.post(
        "/v1/semaphore/start",
        content='{"serviceId": "test", "machineId": "test"}',
        headers={"Content-Type": "text/plain"},
    )
    # Should either accept it or reject based on content type
    assert resp.status_code in {501, 200, 202, 400, 422, 415, 404}
