import hashlib
import json
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.idempotency import IdempotencyRecord
from jizhang_mcp.exceptions import IdempotencyConflictError
from jizhang_mcp.util.time_util import utcnow


def canonical_hash(payload: dict[str, Any]) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def purge_old(session: AsyncSession, user_id: int, tool_name: str, key: str) -> None:
    cutoff = utcnow() - timedelta(hours=24)
    await session.execute(
        delete(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.tool_name == tool_name,
            IdempotencyRecord.idempotency_key == key,
            IdempotencyRecord.created_at < cutoff,
        )
    )


async def begin_idempotency(
    session: AsyncSession, user_id: int, tool_name: str, key: str, request_hash: str
) -> IdempotencyRecord | None:
    """INSERT DO NOTHING；rowcount=0 时返回已有行或 None。"""
    await purge_old(session, user_id, tool_name, key)
    stmt = (
        insert(IdempotencyRecord)
        .values(
            user_id=user_id,
            tool_name=tool_name,
            idempotency_key=key,
            request_hash=request_hash,
        )
        .on_conflict_do_nothing(index_elements=["user_id", "tool_name", "idempotency_key"])
    )
    result = await session.execute(stmt)
    if result.rowcount == 1:
        return None
    existing = await session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.tool_name == tool_name,
            IdempotencyRecord.idempotency_key == key,
        )
    )
    if existing is None:
        return None
    if existing.request_hash != request_hash:
        raise IdempotencyConflictError("同一幂等 key 已用于不同内容")
    return existing


async def save_response(session: AsyncSession, record_id: int, response: dict[str, Any]) -> None:
    row = await session.get(IdempotencyRecord, record_id)
    if row:
        row.response_json = response
        await session.flush()
