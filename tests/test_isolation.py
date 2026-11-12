import pytest


@pytest.mark.asyncio
async def test_cross_user_not_found(api_client, user_with_key):
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={"username": "otheru", "password": "Password123!"},
    )
    token = reg.json()["token"]
    # user_with_key creates first user; second user cannot see first user's entry id 1
    resp = await api_client.get(
        "/api/v1/ledger/entries/1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404
