from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.user import User
from jizhang_mcp.exceptions import AccountDisabledError, UsernameTakenError, ValidationAppError


async def get_user_by_id(session: AsyncSession, user_id: int) -> User:
    user = await session.scalar(select(User).where(User.id == user_id))
    if user is None:
        raise ValidationAppError("用户不存在")
    return user


async def get_user_by_username_lower(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(func.lower(User.username) == username.lower()))


async def create_user(session: AsyncSession, username: str, password_hash: str, passphrase_hash: str | None) -> User:
    existing = await get_user_by_username_lower(session, username)
    if existing is not None:
        raise UsernameTakenError("用户名已被占用")
    user = User(username=username, password_hash=password_hash, passphrase_hash=passphrase_hash, tier="free")
    session.add(user)
    await session.flush()
    return user


def assert_user_active(user: User) -> None:
    if user.status != "active":
        raise AccountDisabledError("账号已禁用")
