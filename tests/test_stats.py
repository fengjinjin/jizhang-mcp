import pytest


@pytest.mark.asyncio
async def test_stats_summary(api_client, user_with_key):
    token = user_with_key["token"]
    await api_client.post(
        "/api/v1/ledger/entries",
        headers={"Authorization": f"Bearer {token}"},
        json={"direction": "expense", "amount": 12, "category": "餐饮"},
    )
    resp = await api_client.get("/api/v1/stats/summary", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert "disclaimer" in body
    assert body["has_any_entries"] is True
