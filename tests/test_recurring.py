import pytest


@pytest.mark.asyncio
async def test_recurring_monthly_add(api_client, user_with_key):
    token = user_with_key["token"]
    resp = await api_client.post(
        "/api/v1/recurring/rules",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "房租",
            "direction": "expense",
            "amount": 2500,
            "category": "住房-房租",
            "frequency": "monthly",
            "day_of_month": 1,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["frequency"] == "monthly"
