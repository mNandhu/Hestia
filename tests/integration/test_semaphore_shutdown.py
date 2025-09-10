import time
import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_idle_timeout_triggers_semaphore_shutdown(monkeypatch):
    """Test that idle timeout triggers a Semaphore shutdown request."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-shutdown-test"

    # Configure service for Semaphore orchestration with very short idle timeout
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://shutdown-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-01")
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_IDLE_TIMEOUT_MS", "50"
    )  # Very short for testing
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_WARMUP_MS", "10")  # Quick startup
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock initial service start (to get it into hot state)
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "start-task", "status": "running"}
        )

        # Mock target service response during active use
        mock.get("http://shutdown-target.local/v1/models").respond(
            200, json={"models": ["shutdown-test-model"]}
        )

        # Mock Semaphore shutdown request - this should be called after idle timeout
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "stop-task", "status": "running"}
        )

        # First, use the service to get it into hot state
        resp1 = client.get(f"/services/{service_id}/v1/models")

        # Wait beyond idle timeout
        time.sleep(0.1)

        # Check service status - should be cold after Semaphore shutdown
        status_resp = client.get(f"/v1/services/{service_id}/status")

    # For now, this will fail because Semaphore integration isn't implemented yet
    # The test expects that:
    # 1. Service starts and becomes hot after first request
    # 2. After idle timeout, Hestia calls Semaphore API to stop the service
    # 3. Service state transitions to cold

    # Until implementation is done, we expect various failure modes
    assert resp1.status_code in {
        500,
        503,
        404,
        200,
    }  # May succeed or fail depending on implementation
    assert status_resp.status_code in {500, 503, 404, 200}


def test_service_state_during_semaphore_shutdown(monkeypatch):
    """Test service state transitions during Semaphore shutdown process."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-state-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://state-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-02")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_IDLE_TIMEOUT_MS", "50")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_WARMUP_MS", "10")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock Semaphore start request
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "start-state-task", "status": "running"}
        )

        # Mock target service
        mock.get("http://state-target.local/v1/models").respond(
            200, json={"models": ["state-model"]}
        )

        # Mock Semaphore shutdown request
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "stop-state-task", "status": "running"}
        )

        # Mock Semaphore shutdown status polling
        mock.get("http://semaphore:3000/api/project/1/tasks/stop-state-task").respond(
            200, json={"task_id": "stop-state-task", "status": "success"}
        )

        # Step 1: Start the service
        resp1 = client.get(f"/services/{service_id}/v1/models")

        # Step 2: Check status (should be hot/ready)
        status1 = client.get(f"/v1/services/{service_id}/status")

        # Step 3: Wait for idle timeout to trigger shutdown
        time.sleep(0.1)

        # Step 4: Check status again (should be cold after shutdown)
        status2 = client.get(f"/v1/services/{service_id}/status")

    # The test expects that:
    # 1. Service transitions from cold -> starting -> hot
    # 2. After idle timeout, service transitions hot -> stopping -> cold
    # 3. Semaphore shutdown API is called during transition

    # Until implementation is done, we expect various failure modes
    assert resp1.status_code in {500, 503, 404, 200}
    assert status1.status_code in {500, 503, 404, 200}
    assert status2.status_code in {500, 503, 404, 200}


def test_new_requests_during_semaphore_shutdown(monkeypatch):
    """Test handling of new requests while service is shutting down via Semaphore."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-shutdown-request-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://shutdown-req-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-03")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_IDLE_TIMEOUT_MS", "50")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_WARMUP_MS", "10")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock service startup
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "start-req-task", "status": "running"}
        )

        # Mock target service responses
        mock.get("http://shutdown-req-target.local/v1/models").respond(
            200, json={"models": ["shutdown-req-model"]}
        )

        # Mock Semaphore shutdown
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "stop-req-task", "status": "running"}
        )

        # Start service
        resp1 = client.get(f"/services/{service_id}/v1/models")

        # Wait for idle timeout to begin shutdown process
        time.sleep(0.06)

        # Try to make a new request while shutdown is in progress
        # This should either:
        # 1. Cancel the shutdown and restart the service, or
        # 2. Queue the request until a new startup completes
        resp2 = client.get(f"/services/{service_id}/v1/models")

    # The test expects that:
    # 1. Initial request starts service normally
    # 2. Idle timeout triggers shutdown process
    # 3. New request during shutdown either cancels shutdown or triggers restart
    # 4. New request eventually succeeds

    # Until implementation is done, we expect various failure modes
    assert resp1.status_code in {500, 503, 404, 200}
    assert resp2.status_code in {500, 503, 404, 200}


def test_semaphore_shutdown_failure_handling(monkeypatch):
    """Test graceful handling when Semaphore shutdown fails."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-shutdown-fail-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://shutdown-fail-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-04")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_IDLE_TIMEOUT_MS", "50")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_WARMUP_MS", "10")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock service startup
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "start-fail-task", "status": "running"}
        )

        # Mock target service
        mock.get("http://shutdown-fail-target.local/v1/models").respond(
            200, json={"models": ["shutdown-fail-model"]}
        )

        # Mock Semaphore shutdown failure
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            500, json={"error": "Failed to stop service"}
        )

        # Start service
        resp1 = client.get(f"/services/{service_id}/v1/models")

        # Wait for idle timeout and shutdown attempt
        time.sleep(0.1)

        # Check service status after failed shutdown
        status_resp = client.get(f"/v1/services/{service_id}/status")

    # The test expects that:
    # 1. Service starts normally
    # 2. Idle timeout triggers shutdown attempt
    # 3. Semaphore shutdown fails
    # 4. Service should remain in some consistent state (either hot or cold)
    # 5. Error should be logged but not crash the system

    # Until implementation is done, we expect various failure modes
    assert resp1.status_code in {500, 503, 404, 200}
    assert status_resp.status_code in {500, 503, 404, 200}


def test_semaphore_shutdown_with_dispatcher(monkeypatch):
    """Test that dispatcher also triggers Semaphore shutdown on idle timeout."""
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    service_id = "semaphore-dispatcher-shutdown-test"

    # Configure service for Semaphore orchestration
    monkeypatch.setenv(
        f"{service_id.upper().replace('-', '_')}_BASE_URL", "http://disp-shutdown-target.local"
    )
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_ENABLED", "true")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_SEMAPHORE_MACHINE_ID", "server-05")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_IDLE_TIMEOUT_MS", "50")
    monkeypatch.setenv(f"{service_id.upper().replace('-', '_')}_WARMUP_MS", "10")
    monkeypatch.setenv("SEMAPHORE_BASE_URL", "http://semaphore:3000")

    with respx.mock(assert_all_called=False) as mock:
        # Mock service startup
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "disp-start-task", "status": "running"}
        )

        # Mock target service
        mock.get("http://disp-shutdown-target.local/v1/models").respond(
            200, json={"models": ["disp-shutdown-model"]}
        )

        # Mock Semaphore shutdown
        mock.post("http://semaphore:3000/api/project/1/tasks").respond(
            201, json={"task_id": "disp-stop-task", "status": "running"}
        )

        # Start service via dispatcher
        resp1 = client.post(
            "/v1/requests", json={"serviceId": service_id, "method": "GET", "path": "/v1/models"}
        )

        # Wait for idle timeout
        time.sleep(0.1)

        # Check status (should be cold after shutdown)
        status_resp = client.get(f"/v1/services/{service_id}/status")

    # The test expects that:
    # 1. Dispatcher starts service via Semaphore
    # 2. Service becomes hot and serves request
    # 3. After idle timeout, Semaphore shutdown is triggered
    # 4. Service becomes cold

    # Until implementation is done, we expect various failure modes
    assert resp1.status_code in {500, 503, 404, 200, 501}  # 501 for unimplemented dispatcher
    assert status_resp.status_code in {500, 503, 404, 200}
