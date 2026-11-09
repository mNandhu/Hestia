import asyncio

import httpx

from fake_upstream import FakeUpstream, Stream, read_timeout, refuse


def activity(app, sid):
    return app.state.runtime.activity.get(sid)


async def test_forwards_path_query_method_and_body(make_client):
    up = FakeUpstream(lambda r: httpx.Response(201, json={"ok": True}))
    async with make_client(up) as (c, app):
        r = await c.post("/services/ollama/api/chat?stream=true", content=b'{"m":1}')
    assert r.status_code == 201 and r.json() == {"ok": True}
    req = up.requests[0]
    assert req.method == "POST"
    assert str(req.url) == "http://ollama.test:11434/api/chat?stream=true"
    assert up.bodies[0] == b'{"m":1}'


async def test_upstream_base_path_is_kept(make_client):
    up = FakeUpstream()
    async with make_client(up) as (c, _):
        await c.get("/services/sub/x/y")
        await c.get("/services/sub")
    assert [str(r.url) for r in up.requests] == [
        "http://sub.test/base/x/y",
        "http://sub.test/base/",
    ]


async def test_bodyless_get_sends_no_body_headers(make_client):
    up = FakeUpstream()
    async with make_client(up) as (c, _):
        await c.get("/services/ollama/api/tags")
    h = up.requests[0].headers
    assert "transfer-encoding" not in h and "content-length" not in h


async def test_request_headers(make_client):
    up = FakeUpstream()
    async with make_client(up) as (c, _):
        await c.get(
            "/services/ollama/x",
            headers={
                "authorization": "Bearer t",
                "connection": "keep-alive, x-secret-hop",
                "x-secret-hop": "drop me",
                "x-forwarded-for": "1.2.3.4",
            },
        )
    h = up.requests[0].headers
    assert h["authorization"] == "Bearer t"
    assert h["host"] == "ollama.test:11434"
    assert "x-secret-hop" not in h
    # httpx sets its own `connection: keep-alive` for the upstream hop; the client's
    # Connection value (naming x-secret-hop) must not be forwarded.
    assert "x-secret-hop" not in h.get("connection", "")
    assert h["x-forwarded-for"] == "1.2.3.4, 10.0.0.7"
    assert h["x-forwarded-host"] == "hestia.test"
    assert h["x-forwarded-prefix"] == "/services/ollama"


async def test_response_keeps_repeated_headers_and_drops_hop_by_hop(make_client):
    headers = [
        ("set-cookie", "a=1"),
        ("set-cookie", "b=2"),
        ("x-up", "1"),
        ("keep-alive", "timeout=5"),
    ]
    up = FakeUpstream(lambda r: httpx.Response(200, headers=headers, text="hi"))
    async with make_client(up) as (c, _):
        r = await c.get("/services/ollama/")
    assert r.headers.get_list("set-cookie") == ["a=1", "b=2"]
    assert r.headers["x-up"] == "1" and "keep-alive" not in r.headers
    assert r.text == "hi"


async def test_unknown_service_404(make_client):
    async with make_client(FakeUpstream()) as (c, _):
        r = await c.get("/services/nope/x")
    assert r.status_code == 404 and r.json()["kind"] == "unknown_service"


async def test_unreachable_502_and_not_left_in_flight(make_client):
    async with make_client(FakeUpstream(refuse)) as (c, app):
        r = await c.get("/services/ollama/x")
        assert r.status_code == 502 and r.json()["kind"] == "upstream_unreachable"
        assert activity(app, "ollama").in_flight == 0


async def test_timeout_504(make_client):
    async with make_client(FakeUpstream(read_timeout)) as (c, app):
        r = await c.get("/services/ollama/x")
        assert r.status_code == 504 and r.json()["kind"] == "upstream_timeout"
        assert activity(app, "ollama").in_flight == 0


async def test_in_flight_released_and_upstream_closed_after_stream(make_client):
    async def body():
        yield b"a"
        yield b"b"

    stream = Stream(body())
    async with make_client(
        FakeUpstream(lambda r: httpx.Response(200, stream=stream))
    ) as (c, app):
        r = await c.get("/services/ollama/x")
        assert r.content == b"ab"
        assert activity(app, "ollama").in_flight == 0
        assert stream.closed


async def test_upstream_error_mid_stream_does_not_look_complete(make_client):
    async def body():
        yield b"partial"
        raise httpx.RemoteProtocolError("peer closed")

    stream = Stream(body())
    async with make_client(
        FakeUpstream(lambda r: httpx.Response(200, stream=stream))
    ) as (c, app):
        try:
            r = await c.get("/services/ollama/x")
            completed = r.content == b"partial"
        except Exception:
            completed = False
        assert not completed, (
            "truncated upstream body must not be delivered as a complete response"
        )
        await asyncio.sleep(0)
        assert activity(app, "ollama").in_flight == 0
        assert stream.closed
