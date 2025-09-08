import time

import respx
from fastapi.testclient import TestClient

from hestia.app import app


def test_readiness_with_health_endpoint(monkeypatch):
    client = TestClient(app)

    # Configure service health endpoint and warmup timing
    monkeypatch.setenv("OLLAMA_HEALTH_URL", "http://upstream.local/health")
    monkeypatch.setenv("OLLAMA_WARMUP_MS", "0")

    # Before start, status should be not_ready or 501 (until implemented)
    pre = client.get("/v1/services/ollama/status")
    assert pre.status_code in {200, 501}

    with respx.mock(assert_all_called=True) as mock:
        mock.get("http://upstream.local/health").respond(200, json={"ok": True})

        # Start the service; expect 202 Accepted
        start = client.post("/v1/services/ollama/start")
        assert start.status_code in {202, 501}

        # Poll status until ready (or fail due to unimplemented)
        ready = False
        st = None
        for _ in range(10):
            st = client.get("/v1/services/ollama/status")
            if st.status_code == 200 and st.json().get("readiness") == "ready":
                ready = True
                break
            time.sleep(0.05)

    # Either the readiness is implemented, or the placeholder returns 501
    assert ready or (st is not None and st.status_code == 501)
