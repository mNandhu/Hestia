import time

from fastapi.testclient import TestClient

from hestia.app import app


def test_idle_shutdown_transitions_service_to_cold(monkeypatch):
    client = TestClient(app)

    # Clear any existing service state from previous tests
    from hestia.app import _services, _request_queue

    _services.clear()
    _request_queue._service_queues.clear()
    _request_queue._startup_in_progress.clear()

    # Very small idle timeout (ms) to make test fast
    monkeypatch.setenv("OLLAMA_IDLE_TIMEOUT_MS", "50")
    # Disable health URL to ensure fast startup via warmup
    monkeypatch.setenv("OLLAMA_HEALTH_URL", "")
    monkeypatch.setenv("OLLAMA_WARMUP_MS", "10")  # Very short warmup

    # Start service (or accept 501 placeholder)
    client.post("/v1/services/ollama/start")

    # Wait a moment for startup to complete
    time.sleep(0.05)

    # Wait beyond idle timeout
    time.sleep(0.1)

    # Expect status.state == 'cold' after timeout
    st = client.get("/v1/services/ollama/status")
    assert st.status_code == 200
    assert st.json().get("state") == "cold"
