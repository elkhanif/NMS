import asyncio

from worker.pollers.http import poll_http
from worker.pollers.tcp import poll_tcp


async def test_poll_tcp_open_port():
    async def handler(reader, writer):
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        result = await poll_tcp("127.0.0.1", port, timeout=1.0)
    assert result["reachable"] is True
    assert result["response_time_ms"] is not None


async def test_poll_tcp_refused_port():
    # An arbitrary high port nothing is listening on should be refused quickly.
    result = await poll_tcp("127.0.0.1", 1, timeout=0.5)
    assert result["reachable"] is False
    assert result["response_time_ms"] is None


async def test_poll_http_ok():
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        body = b"ok"
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Length: "
            + str(len(body)).encode()
            + b"\r\nConnection: close\r\n\r\n"
            + body
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    async with server:
        result = await poll_http(f"http://127.0.0.1:{port}/", timeout=2.0)
    assert result["reachable"] is True
    assert result["status_code"] == 200


async def test_poll_http_unreachable():
    result = await poll_http("http://127.0.0.1:1/", timeout=0.5)
    assert result["reachable"] is False
