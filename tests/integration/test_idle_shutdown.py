import time

from fastapi.testclient import TestClient

from hestia.app import app


def test_idle_shutdown_transitions_service_to_cold(monkeypatch):
    client = TestClient(app)

    # Very small idle timeout (ms) to make test fast
    monkeypatch.setenv("OLLAMA_IDLE_TIMEOUT_MS", "50")

    # Start service (or accept 501 placeholder)
    client.post("/v1/services/ollama/start")

    # Wait beyond idle timeout
    time.sleep(0.1)

    # Expect status.state == 'cold' after timeout
    st = client.get("/v1/services/ollama/status")
    assert st.status_code == 200
    assert st.json().get("state") == "cold"
