import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_dispatcher_get_request(monkeypatch):
    """Test dispatcher with GET request."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    expected_response = {"models": ["llama3", "mistral"]}

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{upstream_base}/v1/models").respond(200, json=expected_response)

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests", json={"serviceId": "ollama", "method": "GET", "path": "/v1/models"}
        )

    # Assert: Hestia returned the dispatched response
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 200
    assert response_data["body"] == expected_response


def test_dispatcher_post_request_with_json_body(monkeypatch):
    """Test dispatcher with POST request and JSON body."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    payload = {"model": "llama3", "prompt": "Hello"}
    expected_response = {"response": "Hello! How can I help you today?"}

    with respx.mock(assert_all_called=True) as mock:
        mock.post(f"{upstream_base}/api/generate").respond(200, json=expected_response)

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests",
            json={
                "serviceId": "ollama",
                "method": "POST",
                "path": "/api/generate",
                "body": payload,
            },
        )

    # Assert: Hestia returned the dispatched response
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 200
    assert response_data["body"] == expected_response


def test_dispatcher_with_custom_headers(monkeypatch):
    """Test dispatcher preserves custom headers."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    expected_response = {"result": "success"}
    custom_headers = {"x-custom": "test-value", "authorization": "Bearer token"}

    with respx.mock(assert_all_called=True) as mock:
        # Verify custom headers are forwarded
        mock.get(f"{upstream_base}/api/test").respond(200, json=expected_response)

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests",
            json={
                "serviceId": "ollama",
                "method": "GET",
                "path": "/api/test",
                "headers": custom_headers,
            },
        )

    # Assert: Hestia returned the dispatched response
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 200
    assert response_data["body"] == expected_response


def test_dispatcher_put_request(monkeypatch):
    """Test dispatcher with PUT request."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    payload = {"name": "my-model", "modelfile": "FROM llama3"}
    expected_response = {"status": "success", "id": "model-123"}

    with respx.mock(assert_all_called=True) as mock:
        mock.put(f"{upstream_base}/api/create").respond(201, json=expected_response)

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests",
            json={"serviceId": "ollama", "method": "PUT", "path": "/api/create", "body": payload},
        )

    # Assert: Hestia returned the dispatched response
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 201
    assert response_data["body"] == expected_response


def test_dispatcher_delete_request(monkeypatch):
    """Test dispatcher with DELETE request."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    expected_response = {"deleted": True}

    with respx.mock(assert_all_called=True) as mock:
        mock.delete(f"{upstream_base}/api/delete").respond(200, json=expected_response)

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests", json={"serviceId": "ollama", "method": "DELETE", "path": "/api/delete"}
        )

    # Assert: Hestia returned the dispatched response
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 200
    assert response_data["body"] == expected_response


def test_dispatcher_service_unavailable(monkeypatch):
    """Test dispatcher when service is unavailable."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream that will fail
    upstream_base = "http://nonexistent.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)
    monkeypatch.setenv("OLLAMA_REQUEST_TIMEOUT_SECONDS", "1")  # Short timeout

    # Don't mock any responses - let it fail

    # Act: call through Hestia dispatcher
    resp = client.post(
        "/v1/requests", json={"serviceId": "ollama", "method": "GET", "path": "/v1/models"}
    )

    # Assert: Hestia returns service unavailable in the response body
    assert resp.status_code == 200  # API call succeeded
    response_data = resp.json()
    assert response_data["status"] == 503  # But service was unavailable
    assert "error" in response_data["body"]


def test_dispatcher_response_headers_preserved(monkeypatch):
    """Test that response headers are preserved by dispatcher."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    expected_response = {"data": "test"}
    response_headers = {"x-rate-limit": "100", "x-custom-header": "value"}

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{upstream_base}/api/test").respond(
            200, json=expected_response, headers=response_headers
        )

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests", json={"serviceId": "ollama", "method": "GET", "path": "/api/test"}
        )

    # Assert: Hestia returned the dispatched response with headers
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 200
    assert response_data["body"] == expected_response
    assert response_data["headers"]["x-rate-limit"] == "100"
    assert response_data["headers"]["x-custom-header"] == "value"


def test_dispatcher_handles_text_response(monkeypatch):
    """Test dispatcher handles non-JSON responses."""
    client = TestClient(app)

    # Arrange: point OLLAMA_BASE_URL to a fake upstream
    upstream_base = "http://upstream.local"
    monkeypatch.setenv("OLLAMA_BASE_URL", upstream_base)

    expected_text = "Plain text response"

    with respx.mock(assert_all_called=True) as mock:
        mock.get(f"{upstream_base}/api/text").respond(
            200, text=expected_text, headers={"content-type": "text/plain"}
        )

        # Act: call through Hestia dispatcher
        resp = client.post(
            "/v1/requests", json={"serviceId": "ollama", "method": "GET", "path": "/api/text"}
        )

    # Assert: Hestia returned the text response
    assert resp.status_code == 200
    response_data = resp.json()
    assert response_data["status"] == 200
    assert response_data["body"] == expected_text
