import json
import os

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

@pytest.mark.asyncio
async def test_agent_sequence(db_session, api_client, app_db):
    """注册 → 解锁 → 记两笔（含幂等）→ 类目模糊 → stats_review"""
    reg = await api_client.post(
        "/api/v1/auth/register",
        json={"username": "agent01", "password": "Password123!"},
    )
    token = reg.json()["token"]
    await api_client.post(
        "/api/v1/me/passphrase",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_passphrase": "暗号1234"},
    )

    key_resp = await api_client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "agent"},
    )
    api_key = key_resp.json()["plaintext"]
    os.environ["JIZHANG_API_KEY"] = api_key

    from jizhang_mcp.mcp_server import mcp

    async with Client(mcp) as client:
        with pytest.raises(ToolError) as locked:
            await client.call_tool("ledger_list", {})
        payload = json.loads(str(locked.value))
        assert payload["code"] == "passphrase_locked"
        assert payload["requires_user_input"] is True
        assert payload.get("hint")

        await client.call_tool("auth_verify_passphrase", {"passphrase": "暗号1234"})

        await client.call_tool(
            "ledger_add",
            {"direction": "expense", "amount": 18, "category": "奶茶", "idempotency_key": "seq-1"},
        )
        replay = await client.call_tool(
            "ledger_add",
            {"direction": "expense", "amount": 18, "category": "奶茶", "idempotency_key": "seq-1"},
        )
        rdata = replay.structured_content or json.loads(replay.content[0].text)
        assert rdata.get("replayed") is True

        await api_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"direction": "expense", "name": "出行"},
        )
        await api_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"direction": "expense", "name": "专车", "parent_path": "交通"},
        )
        await api_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"direction": "expense", "name": "专车", "parent_path": "出行"},
        )

        with pytest.raises(ToolError) as amb:
            await client.call_tool(
                "ledger_add",
                {"direction": "expense", "amount": 20, "category": "专车"},
            )
        err = json.loads(str(amb.value))
        assert err["code"] == "validation_error"
        assert err.get("candidates")

        review = await client.call_tool("stats_review", {})
        rjson = review.structured_content or json.loads(review.content[0].text)
        assert "summary" in rjson and "compare" in rjson and "category_share" in rjson
        assert "top_expenses" in rjson
        assert "disclaimer" in rjson["summary"]
