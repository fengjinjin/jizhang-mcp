import json

import pytest

from jizhang_mcp.middleware.mcp_protocol_asgi import (
    McpProtocolAsgiMiddleware,
    _sync_content_length,
    bridge_modern_request,
    fill_missing_envelope,
)

MODERN = "2026-07-28"


def test_fill_missing_envelope_preserves_extensions():
    params = {
        "_meta": {
            "custom.flag": True,
        }
    }
    out, changed = fill_missing_envelope(params, MODERN)
    assert changed is True
    meta = out["_meta"]
    assert meta["custom.flag"] is True
    assert meta["io.modelcontextprotocol/protocolVersion"] == MODERN


def test_bridge_adds_mcp_name_for_tools_call():
    decoded = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "auth_status", "arguments": {}},
    }
    new_body, patches, modified = bridge_modern_request(decoded, MODERN, {})
    assert modified is True
    names = {k.decode(): v.decode() for k, v in patches}
    assert names.get("mcp-method") == "tools/call"
    assert names.get("mcp-name") == "auth_status"
    assert "io.modelcontextprotocol/protocolVersion" in new_body["params"]["_meta"]


def test_content_length_updated_after_rewrite():
    decoded, patches, modified = bridge_modern_request(
        {
            "method": "tools/call",
            "params": {"name": "auth_status", "arguments": {}},
        },
        MODERN,
        {},
    )
    assert modified
    raw = json.dumps(decoded, separators=(",", ":")).encode()
    headers = [(b"content-length", b"103"), (b"content-type", b"application/json")]
    synced = _sync_content_length(headers, raw)
    cl = next(v.decode() for k, v in synced if k == b"content-length")
    assert cl == str(len(raw))


@pytest.mark.asyncio
async def test_middleware_updates_content_length():
    captured: dict = {}

    async def inner(scope, receive, send):
        captured["headers"] = {k.lower().decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}

    mw = McpProtocolAsgiMiddleware(inner)
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "auth_status", "arguments": {}},
        }
    ).encode()
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/mcp",
        "headers": [
            (b"mcp-protocol-version", MODERN.encode()),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body)).encode()),
        ],
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    await mw(scope, receive, lambda _: None)
    assert captured.get("headers"), "inner app should receive request"
    cl = captured["headers"].get("content-length")
    assert cl is not None
    assert int(cl) > len(body)
