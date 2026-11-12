from __future__ import annotations

import json
from typing import Any

from mcp.shared.inbound import NAME_BEARING_METHODS, MCP_METHOD_HEADER, MCP_NAME_HEADER
from mcp_types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY

MODERN_PROTOCOL_VERSION = "2026-07-28"
_MCP_PV = b"mcp-protocol-version"
_MCP_METHOD = b"mcp-method"
_CONTENT_LENGTH = b"content-length"

MCP_HTTP_HEADERS_INCLUDE = frozenset({"authorization", "mcp-session-id"})


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


def _meta_conflicts_protocol(meta: dict, protocol_header: str) -> bool:
    existing = meta.get(PROTOCOL_VERSION_META_KEY)
    return existing is not None and existing != protocol_header


def fill_missing_envelope(params: dict, protocol_version: str) -> tuple[dict, bool]:
    """补全现代协议信封；已有且与请求头冲突的 _meta 不改动（交给 SDK 拒绝）。"""
    if not isinstance(params, dict):
        params = {}
    meta = params.get("_meta")
    if isinstance(meta, dict) and _meta_conflicts_protocol(meta, protocol_version):
        return params, False
    if isinstance(meta, dict):
        merged = dict(meta)
    else:
        merged = {}
    changed = False
    if PROTOCOL_VERSION_META_KEY not in merged:
        merged[PROTOCOL_VERSION_META_KEY] = protocol_version
        changed = True
    if CLIENT_CAPABILITIES_META_KEY not in merged:
        merged[CLIENT_CAPABILITIES_META_KEY] = {}
        changed = True
    if not changed and meta is merged:
        return params, False
    out = dict(params)
    out["_meta"] = merged
    return out, True


def bridge_modern_request(
    decoded: dict,
    protocol_header: str,
    header_lookup: dict[str, str],
) -> tuple[dict, list[tuple[bytes, bytes]], bool]:
    """为 legacy 现代协议调用补齐路由头与信封。返回 (body, header_patches, modified)。"""
    header_patches: list[tuple[bytes, bytes]] = []
    modified = False
    method = decoded.get("method")
    if method == "initialize" or not isinstance(method, str):
        return decoded, header_patches, False

    params = decoded.get("params")
    if not isinstance(params, dict):
        params = {}
        decoded = {**decoded, "params": params}
        modified = True

    meta = params.get("_meta")
    if isinstance(meta, dict) and _meta_conflicts_protocol(meta, protocol_header):
        return decoded, header_patches, False

    if _needs_envelope(params):
        params, env_changed = fill_missing_envelope(params, protocol_header)
        if env_changed:
            decoded = {**decoded, "params": params}
            modified = True

    if MCP_METHOD_HEADER in header_lookup and header_lookup[MCP_METHOD_HEADER] != method:
        return decoded, header_patches, False
    if header_lookup.get(MCP_METHOD_HEADER) != method:
        header_patches.append((MCP_METHOD_HEADER.encode("latin-1"), method.encode("latin-1")))
        modified = True

    name_key = NAME_BEARING_METHODS.get(method)
    if name_key is not None:
        body_name = params.get(name_key)
        if body_name is not None:
            existing = header_lookup.get(MCP_NAME_HEADER)
            if existing is not None and existing != body_name:
                return decoded, header_patches, False
            if existing != body_name:
                header_patches.append((MCP_NAME_HEADER.encode("latin-1"), str(body_name).encode("latin-1")))
                modified = True

    return decoded, header_patches, modified


async def _read_http_body(receive) -> bytes | None:
    chunks: list[bytes] = []
    more = True
    while more:
        message = await receive()
        if message["type"] == "http.disconnect":
            return None
        chunks.append(message.get("body", b""))
        more = message.get("more_body", False)
    return b"".join(chunks)


def _apply_header_patches(
    base: list[tuple[bytes, bytes]], patches: list[tuple[bytes, bytes]]
) -> list[tuple[bytes, bytes]]:
    out = list(base)
    for name, value in patches:
        out = _set_header(out, name, value.decode("latin-1"))
    return out


def _sync_content_length(headers: list[tuple[bytes, bytes]], body: bytes) -> list[tuple[bytes, bytes]]:
    headers = _strip_header(headers, _CONTENT_LENGTH)
    headers.append((_CONTENT_LENGTH, str(len(body)).encode("ascii")))
    return headers


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

        body = await _read_http_body(receive)
        if body is None:
            return

        headers = list(scope.get("headers", []))
        header_lookup = _header_map(headers)
        protocol_header = header_lookup.get("mcp-protocol-version")
        if not body or protocol_header != MODERN_PROTOCOL_VERSION:
            async def replay_raw():
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay_raw, send)
            return

        try:
            decoded = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            async def replay_raw():
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app({**scope, "headers": headers}, replay_raw, send)
            return

        if not isinstance(decoded, dict):
            async def replay_raw():
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay_raw, send)
            return

        method = decoded.get("method")
        if method == "initialize":
            headers = _strip_header(headers, _MCP_PV)
            scope = {**scope, "headers": headers}
            async def replay_raw():
                return {"type": "http.request", "body": body, "more_body": False}

            await self.app(scope, replay_raw, send)
            return

        decoded, header_patches, modified = bridge_modern_request(decoded, protocol_header, header_lookup)
        if header_patches:
            headers = _apply_header_patches(headers, header_patches)

        if modified:
            body = json.dumps(decoded, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            headers = _sync_content_length(headers, body)
            scope = {**scope, "headers": headers}

        async def replay_receive():
            return {"type": "http.request", "body": body, "more_body": False}

        await self.app(scope, replay_receive, send)
