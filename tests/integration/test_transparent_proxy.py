import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_transparent_proxy_get_with_service_prefix(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{upstream_base}/v1/models").respond(200, json={"models": ["llama3"]})

        # Act: call through Hestia transparent proxy
        resp = client.get("/services/ollama/v1/models")

    # Assert: Hestia returned the proxied response
    assert resp.status_code == 200
    assert resp.json() == {"models": ["llama3"]}
