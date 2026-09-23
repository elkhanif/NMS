async def test_discovery_rejects_oversized_range(client, admin_token):
    resp = await client.post(
        "/api/v1/discovery/", json={"cidr": "10.0.0.0/8"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 422


async def test_discovery_accepts_small_range(client, admin_token):
    resp = await client.post(
        "/api/v1/discovery/", json={"cidr": "10.10.0.0/28"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp.status_code == 201
    assert resp.json()["cidr"] == "10.10.0.0/28"
    assert resp.json()["status"] == "PENDING"


async def test_discovery_cooldown_blocks_rapid_second_job(client, admin_token):
    first = await client.post(
        "/api/v1/discovery/", json={"cidr": "10.10.0.0/29"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/discovery/", json={"cidr": "10.10.0.16/29"}, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert second.status_code == 429
