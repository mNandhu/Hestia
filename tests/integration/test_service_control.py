import time

from fastapi.testclient import TestClient

from hestia.app import app


def test_stop_service_endpoint_stops_hot_service(monkeypatch):
    monkeypatch.setenv("OLLAMA_WARMUP_MS", "0")
    monkeypatch.setenv("OLLAMA_HEALTH_URL", "")

    client = TestClient(app)

    start_response = client.post("/api/v1/services/ollama/start")
    assert start_response.status_code in [202, 409]

    stop_response = client.post("/api/v1/services/ollama/stop")
    assert stop_response.status_code == 202
    assert stop_response.json()["message"] == "Service stop initiated"

    status_response = client.get("/api/v1/services/ollama/status")
    assert status_response.status_code == 200
    assert status_response.json()["state"] == "cold"
    assert status_response.json()["readiness"] == "not_ready"


def test_stop_service_endpoint_conflict_when_already_stopped():
    client = TestClient(app)

    # Use a unique service id that should be cold by default
    service_id = "stopped-service-unique"
    stop_response = client.post(f"/api/v1/services/{service_id}/stop")

    assert stop_response.status_code == 409
    assert "already stopped" in stop_response.json()["message"].lower()


def test_restart_service_endpoint_initiates_restart(monkeypatch):
    monkeypatch.setenv("OLLAMA_WARMUP_MS", "0")
    monkeypatch.setenv("OLLAMA_HEALTH_URL", "")

    client = TestClient(app)

    restart_response = client.post("/api/v1/services/ollama/restart")
    assert restart_response.status_code == 202
    assert restart_response.json()["message"] == "Service restart initiated"

    # Give async startup a brief moment and validate expected transitional/final states
    time.sleep(0.05)
    status_response = client.get("/api/v1/services/ollama/status")
    assert status_response.status_code == 200
    assert status_response.json()["state"] in ["starting", "hot"]
