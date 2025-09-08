import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_startup_policy_retry_fallback_then_error(monkeypatch):
    client = TestClient(app)

    # Configure retry attempts and fallback URL
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://primary.local")
    monkeypatch.setenv("OLLAMA_RETRY_COUNT", "2")
    monkeypatch.setenv("OLLAMA_RETRY_DELAY_MS", "0")
    monkeypatch.setenv("OLLAMA_FALLBACK_URL", "http://fallback.local")

    with respx.mock(assert_all_called=False) as mock:
        primary_route = mock.get("http://primary.local/v1/models").mock(
            side_effect=Exception("connect error")
        )
        fallback_route = mock.get("http://fallback.local/v1/models").mock(
            side_effect=Exception("connect error")
        )

        resp = client.get("/services/ollama/v1/models")

    # Expect 503 after 2 retries on primary and 1 attempt on fallback
    assert resp.status_code == 503
    assert primary_route.call_count == 2
    assert fallback_route.call_count == 1
