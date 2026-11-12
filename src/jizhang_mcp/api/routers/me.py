from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.repositories import user_repo
from jizhang_mcp.security.passwords import hash_password, validate_password
from jizhang_mcp.services import auth_service
from jizhang_mcp.util.ids import id_str

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
async def me(user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    user = await user_repo.get_user_by_id(session, user_id)
    return {
        "id": id_str(user.id),
        "username": user.username,
        "tier": user.tier,
        "status": user.status,
        "passphrase_enabled": user.passphrase_hash is not None,
        "created_at": user.created_at.isoformat(),
    }


class PasswordBody(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/password")
async def change_password(
    body: PasswordBody, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)
):
    from jizhang_mcp.security.passwords import verify_password

    user = await user_repo.get_user_by_id(session, user_id)
    await auth_service.login(session, user.username, body.current_password)
    validate_password(body.new_password)
    user.password_hash = hash_password(body.new_password)
    await session.commit()
    return {"ok": True}


class PassphraseBody(BaseModel):
    new_passphrase: str | None = None
    current_passphrase: str | None = None


@router.post("/passphrase")
async def change_passphrase(
    body: PassphraseBody, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)
):
    await auth_service.update_passphrase(session, user_id, body.new_passphrase, body.current_passphrase)
    return {"ok": True}


class PassphraseResetBody(BaseModel):
    password: str
    new_passphrase: str | None = None


@router.post("/passphrase/reset")
async def reset_passphrase(
    body: PassphraseResetBody, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)
):
    await auth_service.reset_passphrase_with_password(session, user_id, body.password, body.new_passphrase)
    return {"ok": True}
