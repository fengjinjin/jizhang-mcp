import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError
from mcp.types import InitializeRequest, InitializeRequestParams, InitializeResult, Implementation

from jizhang_mcp.config import get_settings
from jizhang_mcp.middleware.mcp_auth import extract_api_key
from jizhang_mcp.middleware.mcp_protocol import McpProductProtocolMiddleware
from jizhang_mcp.middleware.mcp_protocol_asgi import McpProtocolAsgiMiddleware, _needs_envelope, bridge_modern_request

MODERN = "2026-07-28"


def test_mcp_auth_reads_bearer_and_session_headers():
    with patch(
        "jizhang_mcp.middleware.mcp_auth.get_http_headers",
        return_value={"authorization": "Bearer jz_live_x", "mcp-session-id": "sess-9"},
    ):
        from jizhang_mcp.middleware.mcp_auth import extract_api_key, session_key_from_headers

        assert extract_api_key() == "jz_live_x"
        assert session_key_from_headers() == "sess-9"


@pytest.mark.asyncio
async def test_ledger_list_and_export_not_500(api_client, user_with_key, app_db):
    token = user_with_key["token"]
    added = await api_client.post(
        "/api/v1/ledger/entries",
        headers={"Authorization": f"Bearer {token}"},
        json={"direction": "expense", "amount": 12.5, "category": "餐饮"},
    )
    assert added.status_code == 201
    listed = await api_client.get("/api/v1/ledger/entries", headers={"Authorization": f"Bearer {token}"})
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert body["total"] >= 1
    assert body["items"]
    exported = await api_client.get("/api/v1/ledger/export", headers={"Authorization": f"Bearer {token}"})
    assert exported.status_code == 200, exported.text[:200]
    assert "text/csv" in exported.headers.get("content-type", "")

    os.environ["JIZHANG_API_KEY"] = user_with_key["api_key"]
    from jizhang_mcp.mcp_server import mcp

    async with Client(mcp) as client:
        out = await client.call_tool("ledger_list", {})
        data = out.structured_content or json.loads(out.content[0].text)
        assert data["total"] >= 1


@pytest.mark.asyncio
async def test_wrong_passphrase_not_internal_error(user_with_key, app_db, api_client):
    token = user_with_key["token"]
    await api_client.post(
        "/api/v1/me/passphrase",
        headers={"Authorization": f"Bearer {token}"},
        json={"new_passphrase": "暗号1234"},
    )
    os.environ["JIZHANG_API_KEY"] = user_with_key["api_key"]
    from jizhang_mcp.mcp_server import mcp
    from jizhang_mcp.security.fail_store import fail_store

    fail_store._auth.clear()
    settings = get_settings()
    async with Client(mcp) as client:
        for _ in range(settings.auth_max_failures):
            with pytest.raises(ToolError) as err:
                await client.call_tool("auth_verify_passphrase", {"passphrase": "错误暗号"})
            payload = json.loads(str(err.value))
            assert payload["code"] == "invalid_passphrase"
        with pytest.raises(ToolError) as locked:
            await client.call_tool("auth_verify_passphrase", {"passphrase": "错误暗号"})
        payload = json.loads(str(locked.value))
        assert payload["code"] == "auth_rate_limited"


@pytest.mark.asyncio
async def test_initialize_middleware_accepts_modern_protocol():
    middleware = McpProductProtocolMiddleware()
    init = InitializeRequest(
        method="initialize",
        params=InitializeRequestParams(
            protocol_version=MODERN,
            capabilities={},
            client_info=Implementation(name="qa", version="1"),
        ),
    )
    base = InitializeResult(
        protocol_version="2025-11-25",
        capabilities={},
        server_info=Implementation(name="jizhang", version="4.1.8"),
    )
    ctx = MagicMock(message=init)

    async def call_next(_):
        return base

    result = await middleware.on_initialize(ctx, call_next)
    assert result.protocol_version == MODERN
    assert result.server_info.version == "1.0.0"


def test_modern_header_envelope_bridge():
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "auth_status", "arguments": {}},
    }
    assert _needs_envelope(body["params"])
    bridged, _, modified = bridge_modern_request(body, MODERN, {})
    assert modified
    assert not _needs_envelope(bridged["params"])


@pytest.mark.asyncio
async def test_asgi_middleware_strips_header_on_initialize():
    inner = AsyncMock()
    mw = McpProtocolAsgiMiddleware(inner)
    init_body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": MODERN, "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}},
        }
    ).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [(b"mcp-protocol-version", MODERN.encode()), (b"content-type", b"application/json")],
    }
    sent = False

    async def receive():
        return {"type": "http.request", "body": init_body, "more_body": False}

    async def send(_):
        nonlocal sent
        sent = True

    await mw(scope, receive, send)
    assert inner.await_count == 1
    passed_scope = inner.await_args.args[0]
    header_names = {k.decode() for k, _ in passed_scope["headers"]}
    assert "mcp-protocol-version" not in header_names
