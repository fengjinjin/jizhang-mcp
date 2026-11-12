import json

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from jizhang_mcp.security.api_keys import hash_api_key


@pytest.mark.asyncio
async def test_web_register_and_key_hash(db_session, api_client):
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={"username": "alice001", "password": "Password123!"},
    )
    assert reg.status_code == 201
    body = reg.json()
    assert body["user"]["tier"] == "free"
    token = body["token"]
    keys = await api_client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "k1"},
    )
    assert keys.status_code == 201
    plain = keys.json()["plaintext"]
    digest = hash_api_key(plain)
    assert len(digest) == 64


@pytest.mark.asyncio
async def test_duplicate_username_case_insensitive(api_client):
    await api_client.post("/api/v1/auth/register", json={"username": "Bob88", "password": "Password123!"})
    dup = await api_client.post("/api/v1/auth/register", json={"username": "bob88", "password": "Password123!"})
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "username_taken"


@pytest.mark.asyncio
async def test_password_min_length(api_client):
    bad = await api_client.post("/api/v1/auth/register", json={"username": "shortpw", "password": "1234567"})
    assert bad.status_code == 400


@pytest.mark.asyncio
async def test_mcp_account_register(db_session, app_db):
    from jizhang_mcp.mcp_server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools}
        assert names == {"account_register", "auth_status"}
        result = await client.call_tool(
            "account_register",
            {"username": "mcpuser1", "password": "Password123!"},
        )
        data = result.structured_content or json.loads(result.content[0].text)
        assert data["api_key"].startswith("jz_live_")
