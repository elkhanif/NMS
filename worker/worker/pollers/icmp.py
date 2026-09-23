from icmplib import async_ping


async def poll_icmp(ip: str, timeout: float = 2.0, count: int = 3) -> dict:
    """ICMP echo sweep. Requires NET_RAW (see docker-compose cap_add) since it uses
    privileged raw sockets -- more portable across environments than the unprivileged
    SOCK_DGRAM mode, which needs a host sysctl tweak that's awkward inside containers.
    """
    try:
        host = await async_ping(ip, count=count, timeout=timeout, privileged=True)
        return {
            "reachable": host.is_alive,
            "avg_rtt_ms": host.avg_rtt if host.avg_rtt >= 0 else None,
            "packet_loss_pct": host.packet_loss * 100,
        }
    except Exception:
        return {"reachable": False, "avg_rtt_ms": None, "packet_loss_pct": 100.0}
