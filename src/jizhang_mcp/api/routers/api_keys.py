from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.config import get_settings
from jizhang_mcp.exceptions import ApiKeyLimitError
from jizhang_mcp.repositories import api_key_repo
from jizhang_mcp.security.api_keys import generate_api_key, hash_api_key, key_prefix
from jizhang_mcp.util.ids import IdInt, id_str
from jizhang_mcp.util.time_util import iso_local

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class CreateKeyBody(BaseModel):
    name: str
    expires_at: datetime | None = None


@router.get("")
async def list_keys(user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    rows = await api_key_repo.list_keys(session, user_id)
    return {
        "items": [
            {
                "id": id_str(k.id),
                "name": k.name,
                "key_prefix": k.key_prefix,
                "expires_at": iso_local(k.expires_at) if k.expires_at else None,
                "revoked_at": iso_local(k.revoked_at) if k.revoked_at else None,
                "last_used_at": iso_local(k.last_used_at) if k.last_used_at else None,
                "created_at": iso_local(k.created_at),
            }
            for k in rows
        ]
    }


@router.post("", status_code=201)
async def create_key(
    body: CreateKeyBody, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)
):
    settings = get_settings()
    if await api_key_repo.count_active_keys(session, user_id) >= settings.api_key_max_active:
        raise ApiKeyLimitError("未吊销密钥已达上限")
    raw = generate_api_key()
    row = await api_key_repo.create_key(
        session, user_id, body.name, hash_api_key(raw), key_prefix(raw), body.expires_at
    )
    await session.commit()
    return {
        "id": id_str(row.id),
        "name": row.name,
        "key_prefix": row.key_prefix,
        "plaintext": raw,
        "expires_at": iso_local(row.expires_at) if row.expires_at else None,
        "created_at": iso_local(row.created_at),
        "warning": "明文密钥只出现这一次，关闭对话框前请保存。",
    }


@router.post("/{key_id}/revoke")
async def revoke_key(key_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    await api_key_repo.revoke_key(session, user_id, key_id)
    await session.commit()
    return {"ok": True}
