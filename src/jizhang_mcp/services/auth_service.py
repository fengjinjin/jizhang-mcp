from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.config import get_settings
from jizhang_mcp.db.models.api_key import ApiKey
from jizhang_mcp.exceptions import (
    InvalidCredentialsError,
    InvalidPassphraseError,
    PassphraseNotEnabledError,
    PassphraseRequiredError,
    ValidationAppError,
)
from jizhang_mcp.repositories import api_key_repo, user_repo
from jizhang_mcp.security.fail_store import fail_store
from jizhang_mcp.security.passwords import PASSWORD_HASHER, verify_password
from jizhang_mcp.security.unlock_store import unlock_store
from jizhang_mcp.util.time_util import utcnow


def _auth_key_user(user_id: int) -> str:
    return f"user:{user_id}"


def _auth_key_name(username: str) -> str:
    return f"name:{username.lower()}"


async def login(session: AsyncSession, username: str, password: str) -> int:
    key = _auth_key_name(username)
    fail_store.check_auth_locked(key)
    user = await user_repo.get_user_by_username_lower(session, username)
    if user is None or not verify_password(user.password_hash, password):
        fail_store.record_auth_failure(key)
        raise InvalidCredentialsError("用户名或密码错误")
    user_repo.assert_user_active(user)
    fail_store.clear_auth(key)
    return user.id


async def verify_passphrase_for_user(session: AsyncSession, user_id: int, passphrase: str, api_key_id: int, session_key: str):
    user = await user_repo.get_user_by_id(session, user_id)
    if not user.passphrase_hash:
        raise PassphraseNotEnabledError("未启用暗号")
    akey = _auth_key_user(user_id)
    fail_store.check_auth_locked(akey)
    if not verify_password(user.passphrase_hash, passphrase):
        fail_store.record_auth_failure(akey)
        raise InvalidPassphraseError("暗号不正确")
    fail_store.clear_auth(akey)
    unlock_store.unlock(api_key_id, session_key)
    return get_settings().passphrase_ttl_seconds


async def update_passphrase(
    session: AsyncSession, user_id: int, new_passphrase: str | None, current: str | None
) -> None:
    user = await user_repo.get_user_by_id(session, user_id)
    if user.passphrase_hash:
        if not current:
            raise PassphraseRequiredError("需要提供当前暗号")
        akey = _auth_key_user(user_id)
        fail_store.check_auth_locked(akey)
        if not verify_password(user.passphrase_hash, current):
            fail_store.record_auth_failure(akey)
            raise InvalidPassphraseError("暗号不正确")
        fail_store.clear_auth(akey)
    if new_passphrase in (None, ""):
        user.passphrase_hash = None
    else:
        from jizhang_mcp.security.passwords import validate_passphrase

        validate_passphrase(new_passphrase)
        user.passphrase_hash = PASSWORD_HASHER.hash(new_passphrase)
    keys = list(
        await session.scalars(select(ApiKey.id).where(ApiKey.user_id == user_id))
    )
    unlock_store.clear_user(user_id, keys)
    await session.commit()


async def reset_passphrase_with_password(
    session: AsyncSession, user_id: int, password: str, new_passphrase: str | None
) -> None:
    user = await user_repo.get_user_by_id(session, user_id)
    akey = _auth_key_user(user_id)
    fail_store.check_auth_locked(akey)
    if not verify_password(user.password_hash, password):
        fail_store.record_auth_failure(akey)
        raise InvalidCredentialsError("用户名或密码错误")
    fail_store.clear_auth(akey)
    if new_passphrase in (None, ""):
        user.passphrase_hash = None
    else:
        from jizhang_mcp.security.passwords import validate_passphrase

        validate_passphrase(new_passphrase)
        user.passphrase_hash = PASSWORD_HASHER.hash(new_passphrase)
    keys = list(await session.scalars(select(ApiKey.id).where(ApiKey.user_id == user_id)))
    unlock_store.clear_user(user_id, keys)
    await session.commit()
