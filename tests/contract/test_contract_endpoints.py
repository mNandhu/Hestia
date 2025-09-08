import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    # Import the real application (expected to exist)
    from hestia.app import app  # noqa: WPS433

    return TestClient(app)


def test_openapi_contract_routes_exist(client: TestClient):
    # These endpoint stubs must exist in the FastAPI app per contracts/openapi.yaml
    # 1) Transparent proxy under /services/{serviceId}/{proxyPath}
    # We can't call with path params directly here; just verify 404 vs 405 semantics once implemented
    # 2) Generic dispatcher /v1/requests
    # 3) Service status /v1/services/{serviceId}/status
    # 4) Proactive start /v1/services/{serviceId}/start

    # Expect 501 (stub) or 200 when implemented
    resp = client.post(
        "/v1/requests",
        json={"serviceId": "ollama", "method": "GET", "path": "/v1/models"},
    )
    assert resp.status_code in {501, 200}

    resp = client.get("/v1/services/test-service/status")
    assert resp.status_code in {501, 200}

    resp = client.post("/v1/services/test-service/start")
    assert resp.status_code in {501, 202, 409}
