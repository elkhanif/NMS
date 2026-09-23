import asyncio
import time


async def poll_tcp(ip: str, port: int, timeout: float = 5.0) -> dict:
    start = time.monotonic()
    writer = None
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        elapsed_ms = (time.monotonic() - start) * 1000
        return {"reachable": True, "response_time_ms": elapsed_ms}
    except (TimeoutError, OSError):
        return {"reachable": False, "response_time_ms": None}
    finally:
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
