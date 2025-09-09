import respx
from fastapi.testclient import TestClient

from hestia.app import app
from hestia.config import HestiaConfig, ServiceConfig


def build_config_with_strategy(service_id: str, instances: list[dict], routing: dict):
    # Helper to build a HestiaConfig with strategy-enabled service
    svc_cfg = ServiceConfig(
        base_url="http://fallback.local",
        retry_count=1,
        retry_delay_ms=0,
        warmup_ms=0,
        idle_timeout_ms=0,
        queue_size=100,
        request_timeout_seconds=5,
    )
    # Inject strategy-related dynamic attributes (will be added to ServiceConfig later)
    setattr(svc_cfg, "instances", instances)
    setattr(svc_cfg, "strategy", "model_router")
    setattr(svc_cfg, "routing", routing)
    return HestiaConfig(services={service_id: svc_cfg})


def test_strategy_routes_by_model(monkeypatch):
    client = TestClient(app)

    service_id = "svc-model"
    inst_a = "http://a.local"
    inst_b = "http://b.local"

    config = build_config_with_strategy(
        service_id,
        instances=[{"url": inst_a}, {"url": inst_b}],
        routing={
            "by_model": {
                "llama3": inst_a,
                "mistral": inst_b,
            },
            # optional override for key name
            "model_key": "model",
        },
    )

    # Make the app use our config
    monkeypatch.setattr("hestia.app.load_config", lambda: config)

    with respx.mock(assert_all_called=True) as mock:
        # Expect request to be routed to instance A based on model
        mock.post(f"{inst_a}/api/generate").respond(200, json={"ok": True, "to": "A"})

        resp = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "llama3", "prompt": "hi"},
        )

    assert resp.status_code == 200
    assert resp.json()["to"] == "A"


def test_strategy_falls_back_to_load_balancer(monkeypatch):
    client = TestClient(app)

    service_id = "svc-fallback"
    inst_a = "http://a2.local"
    inst_b = "http://b2.local"

    config = build_config_with_strategy(
        service_id,
        instances=[{"url": inst_a}, {"url": inst_b}],
        routing={
            # No mapping for given model => should use LB (first instance expected deterministically)
            "by_model": {"some-other": inst_b}
        },
    )

    # Make the app use our config
    monkeypatch.setattr("hestia.app.load_config", lambda: config)

    with respx.mock(assert_all_called=True) as mock:
        # With a fresh service_id, LB should pick first instance (inst_a)
        mock.post(f"{inst_a}/api/generate").respond(200, json={"ok": True, "to": "A"})

        resp = client.post(
            f"/services/{service_id}/api/generate",
            json={"model": "unmapped", "prompt": "hi"},
        )

    assert resp.status_code == 200
    assert resp.json()["to"] == "A"
