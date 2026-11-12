from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import get_db

router = APIRouter(tags=["health"])
live_router = APIRouter(tags=["health"])


@live_router.get("/healthz")
async def healthz():
    return {"status": "ok"}


@router.get("/health")
async def api_health(session: AsyncSession = Depends(get_db)):
    await session.execute(text("SELECT 1"))
    return {"status": "ok"}
