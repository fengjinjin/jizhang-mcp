import pytest


@pytest.mark.asyncio
async def test_wishlist_crud(api_client, user_with_key):
    token = user_with_key["token"]
    created = await api_client.post(
        "/api/v1/wishlist/items",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "耳机", "estimated_price": 1280},
    )
    assert created.status_code == 201
    item_id = created.json()["id"]
    deleted = await api_client.delete(
        f"/api/v1/wishlist/items/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 200
    assert deleted.json().get("deleted") is True
