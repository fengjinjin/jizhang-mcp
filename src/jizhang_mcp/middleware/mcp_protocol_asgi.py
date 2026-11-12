from __future__ import annotations

import json
from typing import Any

from mcp_types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY

MODERN_PROTOCOL_VERSION = "2026-07-28"
_MCP_PV = b"mcp-protocol-version"
_MCP_METHOD = b"mcp-method"


def _header_map(headers: list[tuple[bytes, bytes]]) -> dict[str, str]:
    return {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in headers}


def _strip_header(headers: list[tuple[bytes, bytes]], name: bytes) -> list[tuple[bytes, bytes]]:
    lower = name.lower()
    return [(k, v) for k, v in headers if k.lower() != lower]


def _set_header(headers: list[tuple[bytes, bytes]], name: bytes, value: str) -> list[tuple[bytes, bytes]]:
    cleaned = _strip_header(headers, name)
    cleaned.append((name, value.encode("latin-1")))
    return cleaned


def _needs_envelope(params: Any) -> bool:
    if not isinstance(params, dict):
        return True
    meta = params.get("_meta")
    if not isinstance(meta, dict):
        return True
    return PROTOCOL_VERSION_META_KEY not in meta


class McpProtocolAsgiMiddleware:
    """让带现代协议头的请求不必只靠手写 params._meta 才能进站。"""

    def __init__(self, app):
        self.app = app

    def __getattr__(self, name: str):
        return getattr(self.app, name)

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path.rstrip("/") != "/mcp":
            await self.app(scope, receive, send)
            return

        chunks: list[bytes] = []
        more = True
        while more:
            message = await receive()
            chunks.append(message.get("body", b""))
            more = message.get("more_body", False)
        body = b"".join(chunks)

        headers = list(scope.get("headers", []))
        header_lookup = _header_map(headers)
        protocol_header = header_lookup.get("mcp-protocol-version")

        if body and protocol_header == MODERN_PROTOCOL_VERSION:
            try:
                decoded = json.loads(body)
            except (json.JSONDecodeError, UnicodeDecodeError):
                decoded = None
            if isinstance(decoded, dict):
                method = decoded.get("method")
                if method == "initialize":
                    headers = _strip_header(headers, _MCP_PV)
                    scope = {**scope, "headers": headers}
                elif isinstance(method, str):
                    params = decoded.get("params")
                    if not isinstance(params, dict):
                        params = {}
                    if _needs_envelope(params):
                        params = {
                            **params,
                            "_meta": {
                                PROTOCOL_VERSION_META_KEY: MODERN_PROTOCOL_VERSION,
                                CLIENT_CAPABILITIES_META_KEY: {},
                            },
                        }
                        decoded["params"] = params
                        body = json.dumps(decoded, separators=(",", ":")).encode("utf-8")
                    if header_lookup.get("mcp-method") != method:
                        headers = _set_header(headers, _MCP_METHOD, method)
                        scope = {**scope, "headers": headers}

        async def replay_receive():
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)
