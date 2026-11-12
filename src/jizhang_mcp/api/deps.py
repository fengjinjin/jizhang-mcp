from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.exceptions import UnauthenticatedError
from jizhang_mcp.repositories import user_repo
from jizhang_mcp.security.jwt import decode_token


async def get_db() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session


def client_ip(request: Request) -> str:
    from jizhang_mcp.config import get_settings

    hops = get_settings().trusted_proxy_hops
    if hops > 0:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            parts = [p.strip() for p in xff.split(",") if p.strip()]
            if len(parts) >= hops:
                return parts[-hops]
    return request.client.host if request.client else "127.0.0.1"


async def current_user_id(
    authorization: Annotated[str | None, Header()] = None,
    session: AsyncSession = Depends(get_db),
) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthenticatedError("需要登录")
    token = authorization.split(" ", 1)[1].strip()
    user_id, _ = decode_token(token)
    user = await user_repo.get_user_by_id(session, user_id)
    user_repo.assert_user_active(user)
    return user_id
