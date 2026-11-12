from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.config import get_settings
from jizhang_mcp.exceptions import ApiKeyLimitError, ValidationAppError
from jizhang_mcp.repositories import api_key_repo, user_repo
from jizhang_mcp.security.api_keys import generate_api_key, hash_api_key, key_prefix
from jizhang_mcp.security.fail_store import fail_store
from jizhang_mcp.security.passwords import (
    PASSWORD_HASHER,
    hash_password,
    validate_passphrase,
    validate_password,
    validate_username,
)
from jizhang_mcp.services import category_service


async def register_user(
    session: AsyncSession,
    username: str,
    password: str,
    passphrase: str | None,
    client_ip: str,
    *,
    commit: bool = True,
):
    fail_store.check_register_ip(client_ip)
    username = validate_username(username)
    validate_password(password)
    pw_hash = hash_password(password)
    phash = None
    if passphrase:
        validate_passphrase(passphrase)
        phash = PASSWORD_HASHER.hash(passphrase)
    user = await user_repo.create_user(session, username, pw_hash, phash)
    await category_service.seed_default_categories(session, user.id)
    fail_store.record_register_ip(client_ip)
    if commit:
        await session.commit()
        await session.refresh(user)
    return user


async def register_with_default_key(
    session: AsyncSession,
    username: str,
    password: str,
    passphrase: str | None,
    client_ip: str,
) -> tuple:
    settings = get_settings()
    user = await register_user(session, username, password, passphrase, client_ip, commit=False)
    if await api_key_repo.count_active_keys(session, user.id) >= settings.api_key_max_active:
        raise ApiKeyLimitError("密钥数量已达上限")
    raw = generate_api_key()
    if not raw.startswith("jz_live_"):
        raise ValidationAppError("密钥前缀异常")
    key = await api_key_repo.create_key(
        session, user.id, "默认密钥", hash_api_key(raw), key_prefix(raw), None
    )
    await session.commit()
    await session.refresh(user)
    return user, raw, key.key_prefix
