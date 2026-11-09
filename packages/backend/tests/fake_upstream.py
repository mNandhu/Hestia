"""Fake upstream for tests.

httpx.MockTransport pre-reads every response body, so it can't exercise streaming.
FakeUpstream hands the response stream through untouched and records requests.
"""

from collections.abc import AsyncIterator, Awaitable, Callable

import httpx

Handler = Callable[[httpx.Request], Awaitable[httpx.Response] | httpx.Response]


class FakeUpstream(httpx.AsyncBaseTransport):
    def __init__(self, handler: Handler | None = None):
        self.handler = handler or (lambda req: httpx.Response(200, text="ok"))
        self.requests: list[httpx.Request] = []
        self.bodies: list[bytes] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.bodies.append(await request.aread())
        self.requests.append(request)
        result = self.handler(request)
        if isinstance(result, Awaitable):
            result = await result
        if result.is_stream_consumed:
            # httpx.Response(text=/json=/content=bytes) reads itself on construction;
            # a network response never does. Re-wrap so the proxy can stream it.
            result = httpx.Response(
                result.status_code,
                headers=result.headers.raw,
                stream=Stream(_once(result.content)),
            )
        return result


class Stream(httpx.AsyncByteStream):
    """Response body from an async generator; records whether it was closed."""

    def __init__(self, gen: AsyncIterator[bytes]):
        self._gen = gen
        self.closed = False

    async def __aiter__(self):
        async for chunk in self._gen:
            yield chunk

    async def aclose(self) -> None:
        self.closed = True


async def _once(data: bytes):
    yield data


def refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("connection refused", request=request)


def read_timeout(request: httpx.Request) -> httpx.Response:
    raise httpx.ReadTimeout("timed out", request=request)
