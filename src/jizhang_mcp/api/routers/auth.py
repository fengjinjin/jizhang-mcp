from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import client_ip, get_db
from jizhang_mcp.security.jwt import create_token
from jizhang_mcp.services import account_service, auth_service
from jizhang_mcp.util.ids import id_str

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    username: str
    password: str = Field(min_length=8, max_length=128)


class LoginBody(BaseModel):
    username: str
    password: str


def _user_payload(user) -> dict:
    return {
        "id": id_str(user.id),
        "username": user.username,
        "tier": user.tier,
        "status": user.status,
        "passphrase_enabled": user.passphrase_hash is not None,
    }


@router.post("/register", status_code=201)
async def register(body: RegisterBody, request: Request, session: AsyncSession = Depends(get_db)):
    user = await account_service.register_user(
        session, body.username, body.password, None, client_ip(request)
    )
    token = create_token(user.id, user.username)
    return {"token": token, "user": _user_payload(user)}


@router.post("/login")
async def login(body: LoginBody, session: AsyncSession = Depends(get_db)):
    user_id = await auth_service.login(session, body.username, body.password)
    from jizhang_mcp.repositories import user_repo

    user = await user_repo.get_user_by_id(session, user_id)
    token = create_token(user_id, user.username)
    return {"token": token, "user": _user_payload(user)}
