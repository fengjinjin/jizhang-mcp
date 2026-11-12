from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.ledger import LedgerEntry
from jizhang_mcp.exceptions import LedgerEntryNotFoundError


def _active(user_id: int):
    return and_(LedgerEntry.user_id == user_id, LedgerEntry.deleted_at.is_(None))


async def get_entry(session: AsyncSession, user_id: int, entry_id: int) -> LedgerEntry:
    row = await session.scalar(select(LedgerEntry).where(_active(user_id), LedgerEntry.id == entry_id))
    if row is None:
        raise LedgerEntryNotFoundError("记录不存在")
    return row


async def insert_entry(session: AsyncSession, **kwargs) -> LedgerEntry:
    row = LedgerEntry(**kwargs)
    session.add(row)
    await session.flush()
    return row


async def soft_delete(session: AsyncSession, user_id: int, entry_id: int, deleted_at: datetime) -> LedgerEntry:
    row = await get_entry(session, user_id, entry_id)
    row.deleted_at = deleted_at
    return row


async def insert_recurring_entry_on_conflict_nothing(session: AsyncSession, values: dict) -> int:
    stmt = (
        insert(LedgerEntry)
        .values(**values)
        .on_conflict_do_nothing(
            index_elements=["recurring_rule_id", "scheduled_for_date"],
            index_where=LedgerEntry.recurring_rule_id.is_not(None),
        )
    )
    result = await session.execute(stmt)
    return result.rowcount


async def count_any_entries(session: AsyncSession, user_id: int) -> bool:
    stmt = select(LedgerEntry.id).where(_active(user_id)).limit(1)
    return (await session.scalar(stmt)) is not None


async def list_entries(
    session: AsyncSession,
    user_id: int,
    *,
    date_from: datetime | None,
    date_to: datetime | None,
    direction: str | None,
    category_id: int | None,
    root_category_id: int | None,
    currency: str | None,
    keyword: str | None,
    min_amount: Decimal | None,
    max_amount: Decimal | None,
    recurring_rule_id: int | None,
    limit: int,
    offset: int,
) -> tuple[list[LedgerEntry], int]:
    cond = [_active(user_id)]
    if date_from:
        cond.append(LedgerEntry.occurred_at >= date_from)
    if date_to:
        cond.append(LedgerEntry.occurred_at <= date_to)
    if direction:
        cond.append(LedgerEntry.direction == direction)
    if category_id is not None:
        cond.append(LedgerEntry.category_id == category_id)
    if root_category_id is not None:
        cond.append(LedgerEntry.root_category_id == root_category_id)
    if currency:
        cond.append(LedgerEntry.currency == currency)
    if min_amount is not None:
        cond.append(LedgerEntry.amount >= min_amount)
    if max_amount is not None:
        cond.append(LedgerEntry.amount <= max_amount)
    if recurring_rule_id is not None:
        cond.append(LedgerEntry.recurring_rule_id == recurring_rule_id)
    if keyword:
        esc = keyword.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pat = f"%{esc}%"
        cond.append(
            or_(LedgerEntry.note.ilike(pat, escape="\\"), LedgerEntry.category_path.ilike(pat, escape="\\"))
        )

    where = and_(*cond)
    total = int(await session.scalar(select(func.count()).select_from(LedgerEntry).where(where)) or 0)
    stmt = (
        select(LedgerEntry)
        .where(where)
        .order_by(LedgerEntry.occurred_at.desc(), LedgerEntry.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list((await session.scalars(stmt)).all())
    return items, total
