import pytest


@pytest.mark.asyncio
async def test_default_categories_after_register(api_client):
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={"username": "catuser", "password": "Password123!"},
    )
    token = reg.json()["token"]
    cats = await api_client.get("/api/v1/categories", headers={"Authorization": f"Bearer {token}"})
    assert cats.status_code == 200
    exp = cats.json()["expense"]
    names = [n["name"] for n in exp]
    assert "其他" in names
    assert len([n for n in names if n]) == 15
