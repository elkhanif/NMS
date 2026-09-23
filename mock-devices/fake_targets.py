"""Fake TCP/HTTP targets for exercising the TCP and HTTP checks, and discovery's
port-probing, without touching the real network. Not a real service on any of these
ports -- just enough of a handshake to look "open" or return a health-check response.
"""
import asyncio

RAW_OPEN_PORTS = [22, 23, 554, 9100, 3389]
HTTP_PORT = 8080


async def handle_raw(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        await asyncio.wait_for(reader.read(100), timeout=0.5)
    except TimeoutError:
        pass
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass


async def handle_http(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=2)
    except (TimeoutError, asyncio.IncompleteReadError):
        pass
    body = b'{"status":"ok"}'
    response = (
        b"HTTP/1.1 200 OK\r\n"
        b"Content-Type: application/json\r\n"
        b"Content-Length: " + str(len(body)).encode() + b"\r\n"
        b"Connection: close\r\n\r\n" + body
    )
    writer.write(response)
    try:
        await writer.drain()
    except OSError:
        pass
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass


async def main() -> None:
    servers = [await asyncio.start_server(handle_raw, "0.0.0.0", port) for port in RAW_OPEN_PORTS]
    servers.append(await asyncio.start_server(handle_http, "0.0.0.0", HTTP_PORT))
    print(f"Mock targets listening on {RAW_OPEN_PORTS} (raw TCP) and {HTTP_PORT} (HTTP)")
    await asyncio.gather(*(s.serve_forever() for s in servers))


if __name__ == "__main__":
    asyncio.run(main())
