from __future__ import annotations

import math
from datetime import timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.constants import WISHLIST_DISCLAIMER
from jizhang_mcp.db.models.ledger import LedgerEntry
from jizhang_mcp.db.models.wishlist import WishlistItem
from jizhang_mcp.exceptions import ValidationAppError
from jizhang_mcp.repositories import wishlist_repo
from jizhang_mcp.services.serializers import ListResult, WishlistItemOut, wishlist_to_out
from jizhang_mcp.util.money import money_str, quantize_money
from jizhang_mcp.util.time_util import iso_local, now_local, parse_date_only


async def add_item(session, user_id: int, title: str, **fields) -> WishlistItemOut:
    item = WishlistItem(
        user_id=user_id,
        title=title,
        estimated_price=quantize_money(fields["estimated_price"])
        if fields.get("estimated_price") is not None
        else None,
        currency=(fields.get("currency") or "CNY").upper()[:3],
        planned_at=parse_date_only(fields["planned_at"]) if fields.get("planned_at") else None,
        note=fields.get("note"),
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return wishlist_to_out(item)


async def list_items(session, user_id: int, status: str | None, limit: int, offset: int) -> ListResult:
    limit = min(limit, 200)
    items, total = await wishlist_repo.list_items(session, user_id, status, limit, offset)
    outs = [wishlist_to_out(i) for i in items]
    return ListResult(total=total, limit=limit, offset=offset, has_more=offset + limit < total, truncated=False, items=outs)


async def get_item(session, user_id: int, item_id: int) -> WishlistItemOut:
    return wishlist_to_out(await wishlist_repo.get_item(session, user_id, item_id))


async def update_item(session, user_id: int, item_id: int, patch: dict) -> WishlistItemOut:
    item = await wishlist_repo.get_item(session, user_id, item_id)
    for k, v in patch.items():
        if v is None:
            continue
        if k == "estimated_price":
            item.estimated_price = quantize_money(v)
        elif k == "planned_at":
            item.planned_at = parse_date_only(v)
        elif hasattr(item, k):
            setattr(item, k, v)
    await session.commit()
    await session.refresh(item)
    return wishlist_to_out(item)


async def delete_item(session, user_id: int, item_id: int) -> WishlistItemOut:
    row = await wishlist_repo.soft_delete(session, user_id, item_id)
    out = wishlist_to_out(row, deleted=True)
    await session.commit()
    return out


class WishlistEvaluateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    baseline: str
    recent_days: int
    total_income: str
    total_expense: str
    surplus: str
    income_count: int
    entry_count: int
    thin_data: bool
    item: dict | None = None
    coverage_ratio: float | None = None
    remaining_after_purchase: str | None = None
    days_of_surplus_needed: int | None = None
    wanted_total: str | None = None
    wanted_coverage_ratio: float | None = None
    income_warning: str | None = None
    disclaimer: str


async def evaluate(
    session,
    user_id: int,
    wishlist_item_id: int | None = None,
    estimated_price: Decimal | None = None,
    recent_days: int = 30,
    currency: str = "CNY",
    baseline: str = "rolling",
) -> WishlistEvaluateOut:
    if wishlist_item_id is None and estimated_price is None:
        raise ValidationAppError("wishlist_item_id 与 estimated_price 至少传一个")
    recent_days = max(7, min(90, recent_days))
    now = now_local()
    if baseline == "last_full_month":
        first_this = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_end = first_this - timedelta(seconds=1)
        last_start = last_end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        df, dt = last_start, last_end
    else:
        df = now - timedelta(days=recent_days)
        dt = now

    cond = and_(
        LedgerEntry.user_id == user_id,
        LedgerEntry.deleted_at.is_(None),
        LedgerEntry.currency == currency,
        LedgerEntry.occurred_at >= df,
        LedgerEntry.occurred_at <= dt,
    )
    row = await session.execute(
        select(
            func.coalesce(func.sum(case((LedgerEntry.direction == "income", LedgerEntry.amount), else_=0)), 0),
            func.coalesce(func.sum(case((LedgerEntry.direction == "expense", LedgerEntry.amount), else_=0)), 0),
            func.coalesce(func.sum(case((LedgerEntry.direction == "income", 1), else_=0)), 0),
            func.count(),
        ).where(cond)
    )
    ti, te, inc_c, ec = row.one()
    ti = quantize_money(ti or 0)
    te = quantize_money(te or 0)
    surplus = ti - te
    item_obj = None
    price = estimated_price
    if wishlist_item_id:
        item = await wishlist_repo.get_item(session, user_id, wishlist_item_id)
        item_obj = wishlist_to_out(item).model_dump()
        if price is None and item.estimated_price is not None:
            price = item.estimated_price

    coverage = None
    remaining = None
    days_needed = None
    if price is not None:
        price = quantize_money(price)
        if price > 0:
            coverage = float(surplus / price)
        remaining = money_str(surplus - price)
        window_days = max((dt - df).days, 1)
        daily = surplus / Decimal(window_days)
        if daily > 0:
            days_needed = math.ceil(float(price / daily))

    wanted_total_val = await session.scalar(
        select(func.coalesce(func.sum(WishlistItem.estimated_price), 0)).where(
            WishlistItem.user_id == user_id,
            WishlistItem.deleted_at.is_(None),
            WishlistItem.status == "wanted",
            WishlistItem.currency == currency,
            WishlistItem.estimated_price.is_not(None),
        )
    )
    wanted_total = quantize_money(wanted_total_val or 0)
    wcr = float(wanted_total / surplus) if surplus > 0 else None

    out = WishlistEvaluateOut(
        currency=currency,
        baseline=baseline,
        recent_days=recent_days,
        total_income=money_str(ti),
        total_expense=money_str(te),
        surplus=money_str(surplus),
        income_count=int(inc_c),
        entry_count=int(ec),
        thin_data=int(ec) < 5,
        item=item_obj,
        coverage_ratio=coverage,
        remaining_after_purchase=remaining,
        days_of_surplus_needed=days_needed,
        wanted_total=money_str(wanted_total),
        wanted_coverage_ratio=wcr,
        disclaimer=WISHLIST_DISCLAIMER,
    )
    if int(inc_c) == 0:
        out.income_warning = "统计区间内无收入记录，可能错开了发薪日"
    return out
