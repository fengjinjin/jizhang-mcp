from datetime import datetime, timedelta, timezone

import jwt

from jizhang_mcp.config import get_settings
from jizhang_mcp.exceptions import UnauthenticatedError


def create_token(user_id: int, username: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> tuple[int, str]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise UnauthenticatedError("登录状态无效，请重新登录") from exc
    user_id = int(payload["sub"])
    username = payload.get("username", "")
    return user_id, username
