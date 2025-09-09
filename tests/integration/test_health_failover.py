import respx
from fastapi.testclient import TestClient

from hestia.app import app
from hestia.config import HestiaConfig, ServiceConfig


def build_config_with_instances(service_id: str, instances: list[dict]):
    """Helper to build a HestiaConfig with multiple instances and load_balancer strategy."""
    svc_cfg = ServiceConfig(
        base_url="http://fallback.local",
        retry_count=1,
        retry_delay_ms=0,
        warmup_ms=0,
        idle_timeout_ms=0,
        queue_size=100,
        request_timeout_seconds=5,
    )
    # Inject strategy-related dynamic attributes
    setattr(svc_cfg, "instances", instances)
    setattr(svc_cfg, "strategy", "load_balancer")
    return HestiaConfig(services={service_id: svc_cfg})


def test_health_tracking_marks_instance_unhealthy_on_failure(monkeypatch):
    """Test that failed requests mark instances as unhealthy and next request uses different instance."""
    client = TestClient(app)

    service_id = "test-health-failover"
    inst_a = "http://a.local"
    inst_b = "http://b.local"

    config = build_config_with_instances(
        service_id,
        instances=[{"url": inst_a}, {"url": inst_b}],
    )

    # Make the app use our config
    monkeypatch.setattr("hestia.app._get_config", lambda: config)

    with respx.mock(assert_all_called=True) as mock:
        # First request: inst_a fails (503), should mark it unhealthy
        mock.post(f"{inst_a}/api/generate").respond(503, json={"error": "service down"})

        # Second request: should go to inst_b since inst_a is marked unhealthy
        mock.post(f"{inst_b}/api/generate").respond(200, json={"ok": True, "from": "B"})

        # First request - should fail and mark inst_a unhealthy
        resp1 = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "test", "prompt": "hi"},
        )
        assert resp1.status_code == 503

        # Second request - should succeed with inst_b
        resp2 = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "test", "prompt": "hi"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["from"] == "B"


def test_health_tracking_marks_instance_healthy_on_success(monkeypatch):
    """Test that successful requests mark instances as healthy."""
    client = TestClient(app)

    service_id = "test-health-recovery"
    inst_a = "http://a2.local"
    inst_b = "http://b2.local"

    config = build_config_with_instances(
        service_id,
        instances=[{"url": inst_a}, {"url": inst_b}],
    )

    # Make the app use our config
    monkeypatch.setattr("hestia.app._get_config", lambda: config)

    with respx.mock(assert_all_called=False) as mock:  # Allow unused mocks
        # First request: inst_a fails
        mock.post(f"{inst_a}/api/generate").respond(503, json={"error": "service down"})

        # Second and third requests: inst_b succeeds (we'll call it twice)
        mock.post(f"{inst_b}/api/generate").respond(200, json={"ok": True, "from": "B"})

        # Fail inst_a
        resp1 = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "test", "prompt": "hi"},
        )
        assert resp1.status_code == 503

        # Use inst_b successfully (first time)
        resp2 = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "test", "prompt": "hi"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["from"] == "B"

        # inst_b should continue to work (stays healthy)
        resp3 = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "test", "prompt": "hi"},
        )
        assert resp3.status_code == 200
        assert resp3.json()["from"] == "B"


def test_transparent_proxy_health_tracking(monkeypatch):
    """Test that transparent proxy also participates in health tracking."""
    client = TestClient(app)

    service_id = "test-proxy-health"
    inst_a = "http://a3.local"
    inst_b = "http://b3.local"

    config = build_config_with_instances(
        service_id,
        instances=[{"url": inst_a}, {"url": inst_b}],
    )

    # Make the app use our config
    monkeypatch.setattr("hestia.app._get_config", lambda: config)

    with respx.mock(assert_all_called=True) as mock:
        # First request: inst_a fails
        mock.get(f"{inst_a}/v1/models").respond(503, json={"error": "service down"})

        # Second request: inst_b succeeds
        mock.get(f"{inst_b}/v1/models").respond(200, json={"models": ["test-model"]})

        # First request should fail with inst_a
        resp1 = client.get(f"/services/{service_id}/v1/models")
        assert resp1.status_code == 503

        # Second request should succeed with inst_b
        resp2 = client.get(f"/services/{service_id}/v1/models")
        assert resp2.status_code == 200
        assert resp2.json()["models"] == ["test-model"]
