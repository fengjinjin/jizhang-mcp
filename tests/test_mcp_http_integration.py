import json
import os

import pytest
from fastmcp.exceptions import ToolError

MODERN = "2026-07-28"
MCP_ACCEPT = {"Accept": "application/json", "Content-Type": "application/json"}


def _json_result(resp) -> dict:
    assert resp.status_code == 200, resp.text[:800]
    return resp.json()


def _tool_payload(result: dict) -> dict:
    if result.get("structuredContent"):
        return result["structuredContent"]
    content = result.get("content") or []
    return json.loads(content[0]["text"])


def _tool_error_payload(payload: dict) -> dict | None:
    result = payload.get("result")
    if isinstance(result, dict) and result.get("isError"):
        return _tool_payload(result)
    err = payload.get("error")
    return err if isinstance(err, dict) else None


@pytest.mark.asyncio
async def test_modern_http_tools_call_without_client_meta(mcp_http_client, user_with_key):
    os.environ.pop("JIZHANG_API_KEY", None)
    body = {
        "jsonrpc": "2.0",
        "id": 10,
        "method": "tools/call",
        "params": {"name": "auth_status", "arguments": {}},
    }
    headers = {
        **MCP_ACCEPT,
        "Authorization": f"Bearer {user_with_key['api_key']}",
        "MCP-Protocol-Version": MODERN,
        "Mcp-Session-Id": "sess-a",
    }
    resp = await mcp_http_client.post("/mcp", content=json.dumps(body).encode(), headers=headers)
    payload = _json_result(resp)
    assert "error" not in payload
    data = _tool_payload(payload["result"])
    assert data["authenticated"] is True
    assert data["session_key"] == "sess-a"


@pytest.mark.asyncio
async def test_bearer_only_no_query_or_env(mcp_http_client, user_with_key):
    os.environ.pop("JIZHANG_API_KEY", None)
    key = user_with_key["api_key"]
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MODERN,
            "capabilities": {},
            "clientInfo": {"name": "qa", "version": "1"},
        },
    }
    h = {**MCP_ACCEPT, "Authorization": f"Bearer {key}"}
    init_resp = await mcp_http_client.post("/mcp", json=init, headers=h)
    init_body = _json_result(init_resp)
    assert init_body["result"]["protocolVersion"] == MODERN

    for method, extra in (
        ("tools/list", {"params": {}}),
        ("tools/call", {"params": {"name": "auth_status", "arguments": {}}}),
    ):
        req = {"jsonrpc": "2.0", "id": 2, "method": method, **extra}
        headers = {**MCP_ACCEPT, "Authorization": f"Bearer {key}", "MCP-Protocol-Version": MODERN}
        resp = await mcp_http_client.post("/mcp", json=req, headers=headers)
        body = _json_result(resp)
        assert "error" not in body, body


@pytest.mark.asyncio
async def test_passphrase_unlock_isolated_per_mcp_session(mcp_http_client, user_with_key, api_client):
    os.environ.pop("JIZHANG_API_KEY", None)
    token = user_with_key["token"]
    api_key = user_with_key["api_key"]
    await api_client.post(
        "/api/v1/me/passphrase",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_passphrase": "暗号1234"},
    )

    async def call_tool(session_id: str, tool: str, args: dict | None = None):
        body = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args or {}},
        }
        headers = {
            **MCP_ACCEPT,
            "Authorization": f"Bearer {api_key}",
            "MCP-Protocol-Version": MODERN,
            "Mcp-Session-Id": session_id,
        }
        return await mcp_http_client.post("/mcp", json=body, headers=headers)

    locked = _json_result(await call_tool("sess-1", "ledger_list"))
    err = _tool_error_payload(locked)
    assert err and err.get("code") == "passphrase_locked"

    unlock = _json_result(await call_tool("sess-1", "auth_verify_passphrase", {"passphrase": "暗号1234"}))
    assert _tool_error_payload(unlock) is None

    still_locked = _json_result(await call_tool("sess-2", "ledger_list"))
    err2 = _tool_error_payload(still_locked)
    assert err2 and err2.get("code") == "passphrase_locked"


@pytest.mark.asyncio
async def test_conflicting_meta_not_silently_patched(mcp_http_client, user_with_key):
    os.environ.pop("JIZHANG_API_KEY", None)
    body = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "auth_status",
            "arguments": {},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2025-11-25",
                "io.modelcontextprotocol/clientCapabilities": {},
            },
        },
    }
    headers = {
        **MCP_ACCEPT,
        "Authorization": f"Bearer {user_with_key['api_key']}",
        "MCP-Protocol-Version": MODERN,
    }
    resp = await mcp_http_client.post("/mcp", json=body, headers=headers)
    payload = resp.json()
    assert payload.get("error") is not None
