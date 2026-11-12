from __future__ import annotations

import json
import os
from urllib.parse import parse_qs

from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_http_headers, get_http_request
from fastmcp.server.middleware import Middleware, MiddlewareContext
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.constants import ALL_AUTHENTICATED_TOOLS, GUEST_TOOLS, PROTECTED_TOOL_NAMES
from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.exceptions import (
    AlreadyAuthenticatedError,
    JizhangError,
    PassphraseLockedError,
    UnauthenticatedError,
)
from jizhang_mcp.middleware.mcp_protocol_asgi import MCP_HTTP_HEADERS_INCLUDE
from jizhang_mcp.repositories import api_key_repo, user_repo
from jizhang_mcp.security.principal import Principal, get_principal, set_principal
from jizhang_mcp.security.unlock_store import unlock_store
from jizhang_mcp.services.recurring_service import settle_due_rules


def tools_visible_to(principal: Principal) -> list[str]:
    if not principal.authenticated:
        return sorted(GUEST_TOOLS)
    return sorted(ALL_AUTHENTICATED_TOOLS)


def extract_api_key() -> str | None:
    headers = get_http_headers(include=set(MCP_HTTP_HEADERS_INCLUDE)) or {}
    auth = headers.get("authorization") or headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1].strip()
    try:
        request = get_http_request()
        qs = parse_qs(request.url.query)
        if "api_key" in qs and qs["api_key"]:
            return qs["api_key"][0]
    except RuntimeError:
        pass
    return os.environ.get("JIZHANG_API_KEY") or None


def session_key_from_headers() -> str:
    headers = get_http_headers(include=set(MCP_HTTP_HEADERS_INCLUDE)) or {}
    sid = headers.get("mcp-session-id") or headers.get("Mcp-Session-Id")
    if sid:
        return sid
    return "default"


async def resolve_principal() -> Principal:
    session_key = session_key_from_headers()
    raw = extract_api_key()
    if not raw:
        return Principal(session_key=session_key)
    factory = get_session_factory()
    async with factory() as session:
        key = await api_key_repo.get_active_key_by_plaintext(session, raw)
        user = await user_repo.get_user_by_id(session, key.user_id)
        user_repo.assert_user_active(user)
        await api_key_repo.touch_last_used(session, key.id)
        await session.commit()
        unlocked = not user.passphrase_hash or unlock_store.is_unlocked(key.id, session_key)
        return Principal(
            guest=False,
            user_id=user.id,
            username=user.username,
            tier=user.tier,
            api_key_id=key.id,
            passphrase_enabled=user.passphrase_hash is not None,
            session_key=session_key,
            unlocked=unlocked,
        )


def require_unlocked(tool_name: str) -> None:
    p = get_principal()
    if not p.authenticated:
        raise UnauthenticatedError("需要有效连接密钥")
    if tool_name in PROTECTED_TOOL_NAMES:
        if p.passphrase_enabled and not p.unlocked:
            raise PassphraseLockedError("当前会话已锁定")
        if p.api_key_id:
            unlock_store.touch(p.api_key_id, p.session_key)


class McpAuthMiddleware(Middleware):
    async def on_list_tools(self, context: MiddlewareContext, call_next):
        try:
            principal = await resolve_principal()
            set_principal(principal)
            tools = await call_next(context)
            allowed = set(tools_visible_to(principal))
            return [t for t in tools if t.name in allowed]
        except JizhangError as exc:
            raise ToolError(json.dumps(exc.to_payload(), ensure_ascii=False)) from exc

    async def on_call_tool(self, context: MiddlewareContext, call_next):
        try:
            principal = await resolve_principal()
            set_principal(principal)
            tool_name = context.message.name  # type: ignore[union-attr]
            if tool_name == "account_register" and principal.authenticated:
                raise AlreadyAuthenticatedError("已认证用户不能注册")
            if tool_name not in GUEST_TOOLS:
                if not principal.authenticated:
                    raise UnauthenticatedError("需要有效连接密钥")
            if tool_name in PROTECTED_TOOL_NAMES:
                require_unlocked(tool_name)
                factory = get_session_factory()
                async with factory() as session:
                    await settle_due_rules(session, user_id=principal.user_id)
            result = await call_next(context)
            if tool_name in PROTECTED_TOOL_NAMES and principal.api_key_id:
                unlock_store.touch(principal.api_key_id, principal.session_key)
            return result
        except JizhangError as exc:
            raise ToolError(json.dumps(exc.to_payload(), ensure_ascii=False)) from exc
