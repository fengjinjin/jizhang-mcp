import json
import os

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


@pytest.mark.asyncio
async def test_ledger_add_aliases(user_with_key, app_db):
    os.environ["JIZHANG_API_KEY"] = user_with_key["api_key"]
    from jizhang_mcp.mcp_server import mcp

    async with Client(mcp) as client:
        out = await client.call_tool(
            "ledger_add",
            {"direction": "expense", "amount": 35, "category": "午饭", "note": "午饭"},
        )
        data = out.structured_content or json.loads(out.content[0].text)
        assert data["category_path"] == "餐饮-午餐"
        assert data["direction"] == "expense"


@pytest.mark.asyncio
async def test_idempotency_replay(user_with_key, app_db):
    os.environ["JIZHANG_API_KEY"] = user_with_key["api_key"]
    from jizhang_mcp.mcp_server import mcp

    key = "idem-test-1"
    async with Client(mcp) as client:
        a = await client.call_tool(
            "ledger_add",
            {
                "direction": "expense",
                "amount": 10,
                "category": "餐饮",
                "idempotency_key": key,
            },
        )
        b = await client.call_tool(
            "ledger_add",
            {
                "direction": "expense",
                "amount": 10,
                "category": "餐饮",
                "idempotency_key": key,
            },
        )
        da = a.structured_content or json.loads(a.content[0].text)
        db = b.structured_content or json.loads(b.content[0].text)
        assert da["id"] == db["id"]
        assert db.get("replayed") is True
