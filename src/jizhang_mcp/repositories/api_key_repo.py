from datetime import datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.api_key import ApiKey
from jizhang_mcp.db.models.user import User
from jizhang_mcp.exceptions import InvalidApiKeyError
from jizhang_mcp.security.api_keys import hash_api_key
from jizhang_mcp.repositories.user_repo import assert_user_active
from jizhang_mcp.util.time_util import utcnow


async def get_active_key_by_plaintext(session: AsyncSession, raw_key: str) -> ApiKey:
    digest = hash_api_key(raw_key)
    stmt = (
        select(ApiKey)
        .join(User, User.id == ApiKey.user_id)
        .where(
            ApiKey.key_hash == digest,
            ApiKey.revoked_at.is_(None),
            User.status == "active",
        )
    )
    key = await session.scalar(stmt)
    if key is None:
        raise InvalidApiKeyError("连接密钥无效")
    if key.expires_at is not None and key.expires_at <= utcnow():
        raise InvalidApiKeyError("连接密钥无效")
    return key


async def count_active_keys(session: AsyncSession, user_id: int) -> int:
    stmt = select(func.count()).select_from(ApiKey).where(
        ApiKey.user_id == user_id, ApiKey.revoked_at.is_(None)
    )
    return int(await session.scalar(stmt) or 0)


async def create_key(
    session: AsyncSession, user_id: int, name: str, key_hash: str, key_prefix: str, expires_at: datetime | None
) -> ApiKey:
    row = ApiKey(
        user_id=user_id,
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        expires_at=expires_at,
    )
    session.add(row)
    await session.flush()
    return row


async def list_keys(session: AsyncSession, user_id: int) -> list[ApiKey]:
    stmt = select(ApiKey).where(ApiKey.user_id == user_id).order_by(ApiKey.created_at.desc())
    return list((await session.scalars(stmt)).all())


async def revoke_key(session: AsyncSession, user_id: int, key_id: int) -> ApiKey:
    key = await session.scalar(select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id))
    if key is None:
        raise InvalidApiKeyError("连接密钥无效")
    if key.revoked_at is None:
        key.revoked_at = utcnow()
    return key


async def touch_last_used(session: AsyncSession, key_id: int) -> None:
    key = await session.get(ApiKey, key_id)
    if key is None:
        return
    now = utcnow()
    if key.last_used_at is None or (now - key.last_used_at) > timedelta(seconds=60):
        await session.execute(update(ApiKey).where(ApiKey.id == key_id).values(last_used_at=now))
