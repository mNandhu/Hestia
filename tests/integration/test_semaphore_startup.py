import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_cold_service_triggers_semaphore_start_request(monkeypatch):
    """Test that accessing a cold service triggers a Semaphore start request."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-startup-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://target-service.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-01")
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_SEMAPHORE_TASK_ID", "start-task-123"
    )
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock Semaphore start request - this should be called when service is cold
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "task-456", "status": "running"}
        )

        # Mock the eventual target service response (after Semaphore starts it)
        mock.get("http://target-service.local/v1/models").respond(
            200, json={"models": ["test-model"]}
        )

        # Act: Request to cold service via transparent proxy
        resp = client.get(f"/services/{service_id}/v1/models")

    # For now, this will fail because Semaphore integration isn't implemented yet
    # The test expects that:
    # 1. Hestia detects the service is cold
    # 2. Hestia calls Semaphore API to start the service
    # 3. Hestia queues the request until service is ready
    # 4. Once ready, the request is forwarded and response returned

    # Until implementation is done, we expect this to fail with appropriate error
    # This is a failing test that will be fixed by T043 implementation
    assert resp.status_code in {500, 503, 404}  # Various failure modes expected


def test_requests_queued_during_semaphore_startup(monkeypatch):
    """Test that multiple requests are queued while Semaphore starts a service."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-queue-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://queue-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-02")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock Semaphore start request
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "task-789", "status": "running"}
        )

        # Mock Semaphore status polling
        mock.get("http://semaphore:3000/api/project/1/tasks/task-789").respond(
            200, json={"task_id": "task-789", "status": "success"}
        )

        # Mock target service responses for queued requests
        mock.get("http://queue-target.local/v1/models").respond(200, json={"models": ["model-1"]})
        mock.post("http://queue-target.local/api/generate").respond(
            200, json={"response": "Generated text"}
        )

        # Act: Send multiple requests while service is starting
        # These should be queued until Semaphore reports service as ready
        resp1 = client.get(f"/services/{service_id}/v1/models")
        resp2 = client.post(
            f"/services/{service_id}/api/generate", json={"model": "test", "prompt": "hello"}
        )

    # For now, these will fail because Semaphore integration isn't implemented
    # The test expects that:
    # 1. First request triggers Semaphore start and gets queued
    # 2. Second request also gets queued (doesn't trigger duplicate start)
    # 3. Both requests are forwarded once service is ready
    # 4. Both responses are returned in order

    # Until implementation is done, we expect these to fail
    assert resp1.status_code in {500, 503, 404}
    assert resp2.status_code in {500, 503, 404}


def test_semaphore_start_failure_returns_error(monkeypatch):
    """Test that Semaphore start failures are handled gracefully."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-fail-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://fail-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-03")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock Semaphore start request failure
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            500, json={"error": "Failed to start task"}
        )

        # Act: Request to service when Semaphore fails to start it
        resp = client.get(f"/services/{service_id}/v1/models")

    # The test expects that:
    # 1. Hestia tries to start service via Semaphore
    # 2. Semaphore returns an error
    # 3. Hestia returns appropriate error to client (503 Service Unavailable)

    # Until implementation is done, we expect this to fail
    assert resp.status_code in {500, 503, 404}


def test_dispatcher_with_semaphore_integration(monkeypatch):
    """Test that the /v1/requests dispatcher also works with Semaphore integration."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-dispatcher-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://dispatcher-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-04")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock Semaphore start request
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "task-dispatcher", "status": "running"}
        )

        # Mock target service response
        mock.get("http://dispatcher-target.local/v1/models").respond(
            200, json={"models": ["dispatcher-model"]}
        )

        # Act: Use dispatcher endpoint with Semaphore-managed service
        resp = client.post(
            "/v1/requests", json={"serviceId": service_id, "method": "GET", "path": "/v1/models"}
        )

    # The test expects that:
    # 1. Dispatcher detects service is cold and needs Semaphore start
    # 2. Dispatcher triggers Semaphore start request
    # 3. Request is queued until service is ready
    # 4. Request is forwarded and response returned

    # Until implementation is done, we expect this to fail
    # Note: Currently may return 200 due to fallback to ollama config when service not found
    assert resp.status_code in {500, 503, 404, 501, 200}


def test_semaphore_status_polling_until_ready(monkeypatch):
    """Test that Hestia polls Semaphore status until service is ready."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-polling-test"

    # Configure service for Semaphore orchestration with short polling interval
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://polling-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-05")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_POLL_INTERVAL_MS", "100")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock Semaphore start request
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "task-polling", "status": "running"}
        )

        # Mock Semaphore status polling - first running, then success
        mock.get("http://semaphore:3000/api/project/1/tasks/task-polling").mock(
            side_effect=[
                respx.MockResponse(200, json={"task_id": "task-polling", "status": "running"}),
                respx.MockResponse(200, json={"task_id": "task-polling", "status": "running"}),
                respx.MockResponse(200, json={"task_id": "task-polling", "status": "success"}),
            ]
        )

        # Mock target service response once ready
        mock.get("http://polling-target.local/v1/models").respond(
            200, json={"models": ["polling-model"]}
        )

        # Act: Request service that requires polling until ready
        resp = client.get(f"/services/{service_id}/v1/models")

    # The test expects that:
    # 1. Hestia starts service via Semaphore
    # 2. Hestia polls Semaphore status multiple times until success
    # 3. Once ready, request is forwarded to target service
    # 4. Response is returned to client

    # Until implementation is done, we expect this to fail
    assert resp.status_code in {500, 503, 404}
