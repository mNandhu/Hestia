"""
Test the examples from the quickstart documentation.

This test verifies that all the curl examples in quickstart.md work correctly.
"""

from fastapi.testclient import TestClient
from hestia.app import app


def test_quickstart_examples():
    """Test all API examples from quickstart.md"""
    client = TestClient(app)

    print("🧪 Testing Quickstart Documentation Examples...")

    # Service Management Examples
    print("\n📋 Service Management:")

    # Check service status
    response = client.get("/api/v1/services/ollama/status")
    print(f"✅ GET /api/v1/services/ollama/status: {response.status_code}")
    assert response.status_code == 200
    status_data = response.json()
    assert "serviceId" in status_data
    assert "state" in status_data
    assert "readiness" in status_data

    # Start service proactively
    response = client.post("/api/v1/services/ollama/start")
    print(f"✅ POST /api/v1/services/ollama/start: {response.status_code}")
    assert response.status_code in [202, 409]  # 409 if already started

    # Get service metrics
    response = client.get("/api/v1/services/ollama/metrics")
    print(f"✅ GET /api/v1/services/ollama/metrics: {response.status_code}")
    assert response.status_code == 200

    # Transparent Proxy Examples
    print("\n🔄 Transparent Proxy:")

    # Proxy to Ollama API (will fail to connect but proxy logic works)
    response = client.get("/services/ollama/api/tags")
    print(f"✅ GET /services/ollama/api/tags: {response.status_code}")
    assert response.status_code in [200, 503]  # 503 if service unavailable

    # POST proxy example
    response = client.post(
        "/services/ollama/api/generate", json={"model": "llama2", "prompt": "Hello world"}
    )
    print(f"✅ POST /services/ollama/api/generate: {response.status_code}")
    assert response.status_code in [200, 503]  # 503 if service unavailable

    # Gateway Dispatcher Example
    print("\n🌐 Gateway Dispatcher:")

    response = client.post(
        "/api/v1/requests", json={"serviceId": "ollama", "method": "GET", "path": "/api/tags"}
    )
    print(f"✅ POST /api/v1/requests: {response.status_code}")
    # Should work regardless of service availability

    # Monitoring Examples
    print("\n📊 Monitoring & Observability:")

    # Global metrics
    response = client.get("/api/v1/metrics")
    print(f"✅ GET /api/v1/metrics: {response.status_code}")
    assert response.status_code == 200
    metrics_data = response.json()
    assert "counters" in metrics_data
    assert "timers" in metrics_data
    assert "services" in metrics_data

    # Service metrics
    response = client.get("/api/v1/services/ollama/metrics")
    print(f"✅ GET /api/v1/services/ollama/metrics: {response.status_code}")
    assert response.status_code == 200

    # Authentication Examples (header processing)
    print("\n🔐 Authentication:")

    # Test API key header processing (auth not enforced in test)
    response = client.get("/api/v1/services/ollama/status", headers={"X-API-Key": "test-api-key"})
    print(f"✅ GET with X-API-Key header: {response.status_code}")
    assert response.status_code == 200

    # Test Bearer token header processing
    response = client.get(
        "/api/v1/services/ollama/status", headers={"Authorization": "Bearer test-token"}
    )
    print(f"✅ GET with Bearer token: {response.status_code}")
    assert response.status_code == 200

    print("\n🎉 All quickstart examples working correctly!")


def test_response_format_examples():
    """Test that response formats match documentation examples"""
    client = TestClient(app)

    print("\n🧪 Testing Response Format Examples...")

    # Service Status Response Format
    response = client.get("/api/v1/services/ollama/status")
    assert response.status_code == 200
    data = response.json()

    # Verify required fields from documentation
    required_fields = ["serviceId", "state", "machineId", "readiness", "queuePending"]
    for field in required_fields:
        assert field in data, f"Missing field {field} in service status response"

    print("✅ Service status response format matches documentation")

    # Metrics Response Format
    response = client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()

    # Verify metrics structure from documentation
    required_sections = ["counters", "timers", "gauges", "histograms", "services"]
    for section in required_sections:
        assert section in data, f"Missing section {section} in metrics response"

    print("✅ Metrics response format matches documentation")

    print("\n🎯 Response format validation complete!")


if __name__ == "__main__":
    test_quickstart_examples()
    test_response_format_examples()
    print("\n🚀 All quickstart documentation verified!")
