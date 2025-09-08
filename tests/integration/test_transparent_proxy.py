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


def test_transparent_proxy_post_with_json(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    payload = {"model": "llama3", "prompt": "Hello"}
    expected_response = {"response": "Hello! How can I help you today?"}

    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{upstream_base}/api/generate").respond(200, json=expected_response)

        # Act: call through Hestia transparent proxy
        resp = client.post("/services/ollama/api/generate", json=payload)

    # Assert: Hestia returned the proxied response
    assert resp.status_code == 200
    assert resp.json() == expected_response


def test_transparent_proxy_put_request(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    payload = {"name": "my-model", "modelfile": "FROM llama3"}

    with respx.mock(assert_all_called=True) as mock:
        mock.put(f"{upstream_base}/api/create").respond(201, json={"status": "success"})

        # Act: call through Hestia transparent proxy
        resp = client.put("/services/ollama/api/create", json=payload)

    # Assert: Hestia returned the proxied response
    assert resp.status_code == 201
    assert resp.json() == {"status": "success"}


def test_transparent_proxy_patch_request(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    payload = {"keep_alive": "5m"}

    with respx.mock(assert_all_called=True) as mock:
        mock.patch(f"{upstream_base}/api/generate").respond(200, json={"updated": True})

        # Act: call through Hestia transparent proxy
        resp = client.patch("/services/ollama/api/generate", json=payload)

    # Assert: Hestia returned the proxied response
    assert resp.status_code == 200
    assert resp.json() == {"updated": True}


def test_transparent_proxy_delete_request(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    with respx.mock(assert_all_called=True) as mock:
        mock.delete(f"{upstream_base}/api/delete").respond(200, json={"deleted": True})

        # Act: call through Hestia transparent proxy
        resp = client.delete("/services/ollama/api/delete")

    # Assert: Hestia returned the proxied response
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}


def test_transparent_proxy_with_query_parameters(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{upstream_base}/v1/models?format=json&limit=10").respond(
            200, json={"models": ["llama3"]}
        )

        # Act: call through Hestia transparent proxy with query params
        resp = client.get("/services/ollama/v1/models?format=json&limit=10")

    # Assert: Hestia returned the proxied response
    assert resp.status_code == 200
    assert resp.json() == {"models": ["llama3"]}


def test_transparent_proxy_preserves_headers(monkeypatch):
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{upstream_base}/v1/models").respond(
            200,
            json={"models": ["llama3"]},
            headers={"x-custom-header": "test-value", "content-type": "application/json"},
        )

        # Act: call through Hestia transparent proxy
        resp = client.get("/services/ollama/v1/models")

    # Assert: Hestia returned the proxied response with headers
    assert resp.status_code == 200
    assert resp.json() == {"models": ["llama3"]}
    assert resp.headers.get("x-custom-header") == "test-value"
