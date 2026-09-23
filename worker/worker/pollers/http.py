import time

import httpx


async def poll_http(url: str, timeout: float = 5.0, expected_status: int = 200) -> dict:
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(verify=False, timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
        elapsed_ms = (time.monotonic() - start) * 1000
        return {
            "reachable": resp.status_code == expected_status,
            "response_time_ms": elapsed_ms,
            "status_code": resp.status_code,
        }
    except httpx.HTTPError:
        return {"reachable": False, "response_time_ms": None, "status_code": None}
