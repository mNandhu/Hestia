"""Streaming through a real uvicorn server: the legacy Hestia buffered whole
responses, so this is the regression test that matters most."""

import asyncio
import socket

import httpx
import pytest
import uvicorn

from hestia.core.config import Settings
from hestia.main import create_app
from hestia.services.registry import Registry

from conftest import SERVICES
from fake_upstream import FakeUpstream, Stream


@pytest.fixture
async def serve(tmp_path):
    servers = []

    async def _serve(up: FakeUpstream):
        app = create_app(Settings(home=tmp_path), Registry.from_dict(SERVICES), up)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan="on"))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        while not server.started:
            await asyncio.sleep(0.01)
        servers.append((server, task))
        return f"http://127.0.0.1:{sock.getsockname()[1]}", app

    yield _serve
    for server, task in servers:
        server.should_exit = True
        await task


async def test_chunks_reach_client_before_upstream_finishes(serve):
    gate = asyncio.Event()

    async def body():
        yield b"data: first\n\n"
        await gate.wait()
        yield b"data: second\n\n"

    stream = Stream(body())
    up = FakeUpstream(
        lambda r: httpx.Response(
            200, headers={"content-type": "text/event-stream"}, stream=stream
        )
    )
    base, app = await serve(up)
    activity = app.state.runtime.activity.get("ollama")

    async with httpx.AsyncClient(base_url=base, timeout=5) as c:
        async with c.stream("GET", "/services/ollama/api/chat") as r:
            chunks = r.aiter_raw()
            first = await asyncio.wait_for(anext(chunks), timeout=2)
            assert first == b"data: first\n\n"
            assert activity.in_flight == 1, (
                "request still streaming must count as in flight"
            )
            gate.set()
            rest = b"".join([c async for c in chunks])
            assert rest == b"data: second\n\n"

    for _ in range(100):
        if activity.in_flight == 0 and stream.closed:
            break
        await asyncio.sleep(0.01)
    assert activity.in_flight == 0 and stream.closed


async def test_client_disconnect_releases_in_flight_and_closes_upstream(serve):
    async def body():
        yield b"tick"
        await asyncio.Event().wait()  # upstream never finishes on its own

    stream = Stream(body())
    base, app = await serve(FakeUpstream(lambda r: httpx.Response(200, stream=stream)))
    activity = app.state.runtime.activity.get("ollama")

    async with httpx.AsyncClient(base_url=base, timeout=5) as c:
        async with c.stream("GET", "/services/ollama/x") as r:
            assert await anext(r.aiter_raw()) == b"tick"
            assert activity.in_flight == 1
    # client gone: Hestia must notice, release the slot and close the upstream

    for _ in range(200):
        if activity.in_flight == 0 and stream.closed:
            break
        await asyncio.sleep(0.01)
    assert activity.in_flight == 0 and stream.closed


# --- Two real hops: client → Hestia (uvicorn) → echo upstream (uvicorn) ---------
# FakeUpstream bypasses httpcore, so request framing on the upstream hop is only
# exercised here.


async def _echo_app(scope, receive, send):
    """Tiny ASGI upstream: /echo reports framing headers + body; /sse streams."""
    if scope["type"] != "http":
        return
    headers = {k.decode(): v.decode() for k, v in scope["headers"]}
    if scope["path"].endswith("/sse"):
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"text/event-stream")],
            }
        )
        await send(
            {"type": "http.response.body", "body": b"data: one\n\n", "more_body": True}
        )
        await _ECHO_GATE.wait()
        await send({"type": "http.response.body", "body": b"data: two\n\n"})
        return
    body = b""
    while True:
        msg = await receive()
        body += msg.get("body", b"")
        if not msg.get("more_body"):
            break
    import json

    payload = json.dumps(
        {
            "method": scope["method"],
            "content_length": headers.get("content-length"),
            "transfer_encoding": headers.get("transfer-encoding"),
            "body": body.decode(),
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": payload})


_ECHO_GATE = asyncio.Event()


async def _start(app, lifespan="off"):
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, log_config=None, lifespan=lifespan))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    while not server.started:
        await asyncio.sleep(0.01)
    return f"http://127.0.0.1:{sock.getsockname()[1]}", server, task


@pytest.fixture
async def two_hops(tmp_path):
    _ECHO_GATE.clear()
    up_url, up_server, up_task = await _start(_echo_app)
    reg = Registry.from_dict({"services": {"echo": {"upstream": up_url + "/base"}}})
    hestia_url, h_server, h_task = await _start(
        create_app(Settings(home=tmp_path), reg), lifespan="on"
    )
    yield hestia_url
    for s, t in ((h_server, h_task), (up_server, up_task)):
        s.should_exit = True
        await t


async def test_two_hops_fixed_length_body(two_hops):
    async with httpx.AsyncClient(base_url=two_hops, timeout=5) as c:
        r = await c.post("/services/echo/api/chat", content=b'{"model":"m"}')
    e = r.json()
    assert e == {
        "method": "POST",
        "content_length": "13",
        "transfer_encoding": None,
        "body": '{"model":"m"}',
    }


async def test_two_hops_chunked_body(two_hops):
    async def gen():
        yield b"hello "
        yield b"world"

    async with httpx.AsyncClient(base_url=two_hops, timeout=5) as c:
        r = await c.post("/services/echo/x", content=gen())
    e = r.json()
    assert e["body"] == "hello world"
    assert e["transfer_encoding"] == "chunked" and e["content_length"] is None


async def test_two_hops_streams_before_upstream_finishes(two_hops):
    async with httpx.AsyncClient(base_url=two_hops, timeout=5) as c:
        async with c.stream("GET", "/services/echo/sse") as r:
            chunks = r.aiter_raw()
            assert await asyncio.wait_for(anext(chunks), timeout=2) == b"data: one\n\n"
            _ECHO_GATE.set()
            assert b"".join([x async for x in chunks]) == b"data: two\n\n"
