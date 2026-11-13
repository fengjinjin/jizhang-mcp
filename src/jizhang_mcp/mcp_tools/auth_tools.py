from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from jizhang_mcp.constants import ALL_AUTHENTICATED_TOOLS, GUEST_TOOLS
from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.mcp_tools.boundary import mcp_boundary
from jizhang_mcp.middleware.mcp_auth import extract_api_key
from jizhang_mcp.repositories import category_repo
from jizhang_mcp.security.principal import get_principal
from jizhang_mcp.security.unlock_store import unlock_store
from jizhang_mcp.services import account_service, auth_service
from jizhang_mcp.util.ids import id_str
from jizhang_mcp.util.time_util import now_local, weekday_cn, iso_local


class AuthStatusOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    authenticated: bool
    guest: bool
    username: str | None
    tier: str | None
    passphrase_enabled: bool
    session_unlocked: bool
    session_key: str
    server_time: str
    weekday: str
    available_tools: list[str]
    primary_categories: dict[str, list[str]] | None = None


class RegisterOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str
    user_id: str
    api_key: str
    api_key_prefix: str
    passphrase_enabled: bool
    warning: str


class SessionUnlockOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_unlocked: bool
    ttl_seconds: int | None = None
    passphrase_enabled: bool | None = None


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="auth_status", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def auth_status() -> AuthStatusOut:
        p = get_principal()
        tools = sorted(GUEST_TOOLS if not p.authenticated else ALL_AUTHENTICATED_TOOLS)
        primary = None
        if p.authenticated and (not p.passphrase_enabled or p.unlocked):
            factory = get_session_factory()
            async with factory() as session:
                exp = [
                    c.name
                    for c in await category_repo.list_active_categories(session, p.user_id, "expense")
                    if c.parent_id is None
                ]
                inc = [
                    c.name
                    for c in await category_repo.list_active_categories(session, p.user_id, "income")
                    if c.parent_id is None
                ]
                primary = {"expense": exp, "income": inc}
        return AuthStatusOut(
            authenticated=p.authenticated,
            guest=not p.authenticated,
            username=p.username,
            tier=p.tier,
            passphrase_enabled=p.passphrase_enabled,
            session_unlocked=p.unlocked,
            session_key=p.session_key,
            server_time=iso_local(now_local()),
            weekday=weekday_cn(),
            available_tools=tools,
            primary_categories=primary,
        )

    @mcp.tool(name="account_register", annotations={"readOnlyHint": False, "destructiveHint": False})
    @mcp_boundary
    async def account_register(
        username: Annotated[str, Field(description="用户名，3～32")],
        password: Annotated[str, Field(description="密码，8～128")],
        passphrase: Annotated[str | None, Field(description="可选暗号，1～30")] = None,
    ) -> RegisterOut:
        factory = get_session_factory()
        async with factory() as session:
            user, raw, prefix = await account_service.register_with_default_key(
                session, username, password, passphrase, "127.0.0.1"
            )
        return RegisterOut(
            username=user.username,
            user_id=id_str(user.id),
            api_key=raw,
            api_key_prefix=prefix,
            passphrase_enabled=user.passphrase_hash is not None,
            warning=(
                "请立刻把连接密钥写进客户端并重新连接。密钥只显示这一次。"
                "对话记录可能被第三方保存，不要在公共场合反复粘贴密钥。"
                "登录密码若出现在聊天里，请尽快到 Web 控制台修改。密码无法自助找回。"
            ),
        )

    @mcp.tool(name="auth_verify_passphrase")
    @mcp_boundary
    async def auth_verify_passphrase(
        passphrase: Annotated[str, Field(description="本轮用户输入的暗号")],
    ) -> SessionUnlockOut:
        p = get_principal()
        factory = get_session_factory()
        async with factory() as session:
            ttl = await auth_service.verify_passphrase_for_user(
                session, p.user_id, passphrase, p.api_key_id, p.session_key
            )
            await session.commit()
        return SessionUnlockOut(session_unlocked=True, ttl_seconds=ttl)

    @mcp.tool(name="auth_lock_session", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def auth_lock_session() -> SessionUnlockOut:
        p = get_principal()
        if not p.passphrase_enabled:
            return SessionUnlockOut(session_unlocked=True, passphrase_enabled=False)
        unlock_store.lock(p.api_key_id, p.session_key)
        return SessionUnlockOut(session_unlocked=False, passphrase_enabled=True)

    @mcp.tool(name="auth_update_passphrase", annotations={"destructiveHint": True})
    @mcp_boundary
    async def auth_update_passphrase(
        new_passphrase: Annotated[str | None, Field(description="新暗号；null 关闭")] = None,
        current_passphrase: Annotated[str | None, Field(description="当前暗号，已启用时必填")] = None,
    ) -> SessionUnlockOut:
        p = get_principal()
        factory = get_session_factory()
        async with factory() as session:
            await auth_service.update_passphrase(session, p.user_id, new_passphrase, current_passphrase)
        return SessionUnlockOut(session_unlocked=False, passphrase_enabled=new_passphrase not in (None, ""))
