from worker.pollers.icmp import poll_icmp


async def test_poll_icmp_returns_expected_shape():
    """Real reachability depends on the container having NET_RAW (see docker-compose
    cap_add: NET_RAW/NET_ADMIN on monitoring-worker) -- this just checks the poller
    never raises and always returns the expected keys, even without that capability.
    Actual ping behavior is validated in the full-stack docker-compose smoke test."""
    result = await poll_icmp("127.0.0.1", timeout=1.0, count=1)
    assert "reachable" in result
    assert "avg_rtt_ms" in result
    assert "packet_loss_pct" in result
