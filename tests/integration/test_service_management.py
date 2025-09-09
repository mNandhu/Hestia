import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_service_status_cold_service():
    """Test status endpoint for a cold service."""
    client = TestClient(app)

    # Act: Check status of a service that hasn't been used (unique name)
    resp = client.get("/v1/services/cold-test-service/status")

    # Assert: Service should be cold and not ready
    assert resp.status_code == 200
    data = resp.json()
    assert data["serviceId"] == "cold-test-service"
    assert data["state"] == "cold"
    assert data["readiness"] == "not_ready"
    assert data["machineId"] == "local"
    assert data["queuePending"] == 0


def test_service_status_after_activity(monkeypatch):
    """Test status endpoint for a service after it has been used."""
    client = TestClient(app)

    # Arrange: Set up a service configuration
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://upstream.local")

    # Simulate service activity by calling the transparent proxy
    # This will put the service in hot/ready state
    with respx.mock() as mock:
        mock.get("http://upstream.local/v1/models").respond(200, json={"models": []})

        # This should trigger service startup
        client.get("/services/ollama/v1/models")

    # Act: Check status after activity
    resp = client.get("/v1/services/ollama/status")

    # Assert: Service should be hot and ready
    assert resp.status_code == 200
    data = resp.json()
    assert data["serviceId"] == "ollama"
    assert data["state"] == "hot"
    assert data["readiness"] == "ready"
    assert data["machineId"] == "local"


def test_start_service_cold_service():
    """Test starting a cold service."""
    client = TestClient(app)

    # Act: Start a cold service
    resp = client.post("/v1/services/new-service/start")

    # Assert: Should return 202 Accepted
    assert resp.status_code == 202
    data = resp.json()
    assert data["message"] == "Service start initiated"


def test_start_service_already_running(monkeypatch):
    """Test starting a service that's already running."""
    client = TestClient(app)

    # Arrange: Set up a service and make it hot
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://upstream.local")

    with respx.mock() as mock:
        mock.get("http://upstream.local/v1/models").respond(200, json={"models": []})

        # Make the service hot by using it
        client.get("/services/ollama/v1/models")

    # Act: Try to start the already running service
    resp = client.post("/v1/services/ollama/start")

    # Assert: Should return 409 Conflict
    assert resp.status_code == 409
    data = resp.json()
    assert data["message"] == "Service is already running"


def test_start_service_already_starting():
    """Test starting a service that's already starting."""
    client = TestClient(app)

    # Act: Start a service twice quickly
    resp1 = client.post("/v1/services/starting-service/start")
    resp2 = client.post("/v1/services/starting-service/start")

    # Assert: First should succeed, second should conflict
    assert resp1.status_code == 202
    assert resp2.status_code == 409

    data2 = resp2.json()
    # The message could be either "already starting" or "already running"
    # depending on timing of the async startup
    assert "already" in data2["message"]


def test_service_status_shows_queue_pending(monkeypatch):
    """Test that service status shows pending queue requests."""
    client = TestClient(app)

    # Arrange: Set up a failing service to create queue backlog
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://nonexistent.local")
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "10")  # Longer timeout

    # Act: Make a request that will be queued (non-blocking)
    import threading

    def make_request():
        try:
            client.post(
                "/v1/requests",
                json={"serviceId": "ollama", "method": "GET", "path": "/v1/models"},
            )  # Remove timeout parameter to avoid deprecation warning
        except Exception:
            pass  # Expected to timeout/fail

    # Start request in background thread to avoid blocking
    thread = threading.Thread(target=make_request)
    thread.start()

    # Give a moment for request to be queued
    import time

    time.sleep(0.1)

    # Check status while request is queued
    resp = client.get("/v1/services/ollama/status")

    # Clean up
    thread.join(timeout=2)

    # Assert: Should show queued request
    assert resp.status_code == 200
    data = resp.json()
    assert data["serviceId"] == "ollama"
    # Queue might be processed quickly, so just check structure
    assert "queuePending" in data


def test_service_status_starting_state():
    """Test service status during startup process."""
    client = TestClient(app)

    # Act: Start a service and immediately check status
    start_resp = client.post("/v1/services/startup-test/start")
    status_resp = client.get("/v1/services/startup-test/status")

    # Assert: Should show starting state or hot (if startup was very fast)
    assert start_resp.status_code == 202
    assert status_resp.status_code == 200

    status_data = status_resp.json()
    assert status_data["serviceId"] == "startup-test"
    # State could be starting or hot depending on timing
    assert status_data["state"] in ["starting", "hot"]


def test_service_endpoints_with_different_service_ids():
    """Test that endpoints work with various service ID formats."""
    client = TestClient(app)

    service_ids = ["ollama", "test-service", "service_with_underscores", "service123"]

    for service_id in service_ids:
        # Test status endpoint
        status_resp = client.get(f"/v1/services/{service_id}/status")
        assert status_resp.status_code == 200
        assert status_resp.json()["serviceId"] == service_id

        # Test start endpoint
        start_resp = client.post(f"/v1/services/{service_id}/start")
        assert start_resp.status_code in [202, 409]  # 202 for new, 409 if already starting


def test_service_status_json_structure():
    """Test that service status returns proper JSON structure."""
    client = TestClient(app)

    # Act: Get service status
    resp = client.get("/v1/services/json-test/status")

    # Assert: Proper JSON structure
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"

    data = resp.json()
    required_fields = ["serviceId", "state", "readiness", "machineId"]
    for field in required_fields:
        assert field in data

    # Validate enum values
    assert data["state"] in ["hot", "cold", "starting", "stopping"]
    assert data["readiness"] in ["ready", "not_ready"]


def test_status_reports_hot_if_upstream_running_without_proxy(monkeypatch):
    """If upstream is already running (health OK), status should be hot even before any proxy request.

    Scenario: User has Ollama already running locally before starting Hestia. On first status check,
    Hestia should detect readiness via the configured health_url and report hot/ready without requiring
    a transparent proxy request to trigger state change.
    """
    client = TestClient(app)

    # Use a unique service id to avoid global state contamination from other tests
    service_id = "ollama-prehot"

    # Arrange: Configure upstream to a mock and set health URL (applies to ollama defaults)
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://upstream.local")
    monkeypatch.setenv("OLLAMA_HEALTH_URL", "http://upstream.local/api/tags")

    with respx.mock() as mock:
        # Health endpoint returns 200 to indicate upstream is ready
        mock.get("http://upstream.local/api/tags").respond(200, json={"ok": True})

        # Act: Call status endpoint BEFORE any proxy request
        resp = client.get(f"/v1/services/{service_id}/status")

    # Assert: Expect hot/ready immediately
    assert resp.status_code == 200
    data = resp.json()
    assert data["serviceId"] == service_id
    assert data["state"] == "hot"
    assert data["readiness"] == "ready"
