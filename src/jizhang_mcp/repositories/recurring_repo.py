from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.recurring import RecurringRule
from jizhang_mcp.db.models.user import User
from jizhang_mcp.exceptions import RecurringRuleNotFoundError, ValidationAppError
from jizhang_mcp.util.time_util import utcnow


def _active(user_id: int):
    return and_(RecurringRule.user_id == user_id, RecurringRule.deleted_at.is_(None))


async def get_rule(session: AsyncSession, user_id: int, rule_id: int) -> RecurringRule:
    row = await session.scalar(select(RecurringRule).where(_active(user_id), RecurringRule.id == rule_id))
    if row is None:
        raise RecurringRuleNotFoundError("定时规则不存在")
    return row


async def list_rules(
    session: AsyncSession, user_id: int, status: str | None, limit: int, offset: int
) -> tuple[list[RecurringRule], int]:
    cond = [_active(user_id)]
    if status:
        cond.append(RecurringRule.status == status)
    where = and_(*cond)
    total = int(await session.scalar(select(func.count()).select_from(RecurringRule).where(where)) or 0)
    stmt = (
        select(RecurringRule)
        .where(where)
        .order_by(RecurringRule.status != "active", RecurringRule.next_run_date, RecurringRule.id)
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(stmt)).all()), total


async def list_due_candidates(session: AsyncSession, horizon: date) -> list[int]:
    stmt = (
        select(RecurringRule.id)
        .join(User, User.id == RecurringRule.user_id)
        .where(
            RecurringRule.status == "active",
            RecurringRule.deleted_at.is_(None),
            RecurringRule.next_run_date <= horizon,
            User.status == "active",
        )
    )
    return list((await session.scalars(stmt)).all())


async def lock_rule_for_settle(session: AsyncSession, rule_id: int) -> RecurringRule | None:
    stmt = (
        select(RecurringRule)
        .where(
            RecurringRule.id == rule_id,
            RecurringRule.status == "active",
            RecurringRule.deleted_at.is_(None),
        )
        .with_for_update(skip_locked=True)
    )
    return await session.scalar(stmt)


async def soft_delete(session: AsyncSession, user_id: int, rule_id: int) -> RecurringRule:
    row = await get_rule(session, user_id, rule_id)
    row.deleted_at = utcnow()
    return row
