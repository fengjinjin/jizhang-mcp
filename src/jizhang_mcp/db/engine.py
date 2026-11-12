import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from jizhang_mcp.config import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_bound_loop: int | None = None


async def init_engine() -> None:
    global _engine, _session_factory, _bound_loop
    loop_id = id(asyncio.get_running_loop())
    if _engine is not None and _bound_loop == loop_id:
        return
    if _engine is not None:
        await _engine.dispose()
    settings = get_settings()
    _engine = create_async_engine(settings.database_url, poolclass=NullPool, pool_pre_ping=True)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    _bound_loop = loop_id


async def dispose_engine() -> None:
    global _engine, _session_factory, _bound_loop
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _bound_loop = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("数据库引擎未初始化")
    return _session_factory


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
