import asyncio

import pytest

from worker.pollers.http import poll_http
from worker.pollers.tcp import poll_tcp


@pytest.fixture
async def tcp_server():
    async def handle(reader, writer):
        writer.close()
        try:
            await writer.wait_closed()
        except OSError:
            pass

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        task = asyncio.ensure_future(server.serve_forever())
        yield port
        task.cancel()


@pytest.fixture
async def http_server():
    async def handle(reader, writer):
        try:
            await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
        except (TimeoutError, asyncio.IncompleteReadError):
            pass
        body = b"ok"
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(body)).encode() + b"\r\nConnection: close\r\n\r\n" + body
        )
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        task = asyncio.ensure_future(server.serve_forever())
        yield port
        task.cancel()


async def test_poll_tcp_reachable(tcp_server):
    result = await poll_tcp("127.0.0.1", tcp_server, timeout=2)
    assert result["reachable"] is True
    assert result["response_time_ms"] is not None


async def test_poll_tcp_unreachable():
    result = await poll_tcp("127.0.0.1", 1, timeout=0.5)  # nothing listens on port 1
    assert result["reachable"] is False


async def test_poll_http_reachable(http_server):
    result = await poll_http(f"http://127.0.0.1:{http_server}/", timeout=2)
    assert result["reachable"] is True
    assert result["status_code"] == 200


async def test_poll_http_unreachable():
    result = await poll_http("http://127.0.0.1:1/", timeout=0.5)
    assert result["reachable"] is False
