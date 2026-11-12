from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from jizhang_mcp.db.models.category import Category
from jizhang_mcp.db.models.ledger import LedgerEntry
from jizhang_mcp.db.models.recurring import RecurringRule
from jizhang_mcp.db.models.wishlist import WishlistItem
from jizhang_mcp.services import category_service
from jizhang_mcp.util.ids import id_str
from jizhang_mcp.util.money import money_str
from jizhang_mcp.util.time_util import iso_local


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    summary: str
    direction: str
    amount: str
    currency: str
    category_id: str
    root_category_id: str
    category_path: str
    category_primary: str
    category_secondary: str | None
    category_resolution: str | None = None
    occurred_at: str
    note: str | None
    wishlist_item_id: str | None
    recurring_rule_id: str | None
    scheduled_for_date: str | None
    replayed: bool = False
    created_at: str
    deleted: bool | None = None


def _summary(entry: LedgerEntry) -> str:
    dt = entry.occurred_at.astimezone()
    dpart = dt.strftime("%m-%d")
    note = (entry.note or "")[:20]
    return f"{dpart} {entry.direction} {money_str(entry.amount)} {entry.category_path} {note}".strip()


async def ledger_to_out(session, entry: LedgerEntry, resolution: str | None = None, replayed: bool = False) -> LedgerEntryOut:
    parts = entry.category_path.split("-")
    primary = parts[0]
    secondary = parts[1] if len(parts) > 1 else None
    return LedgerEntryOut(
        id=id_str(entry.id),
        summary=_summary(entry),
        direction=entry.direction,
        amount=money_str(entry.amount),
        currency=entry.currency,
        category_id=id_str(entry.category_id),
        root_category_id=id_str(entry.root_category_id),
        category_path=entry.category_path,
        category_primary=primary,
        category_secondary=secondary,
        category_resolution=resolution,
        occurred_at=iso_local(entry.occurred_at),
        note=entry.note,
        wishlist_item_id=id_str(entry.wishlist_item_id) if entry.wishlist_item_id else None,
        recurring_rule_id=id_str(entry.recurring_rule_id) if entry.recurring_rule_id else None,
        scheduled_for_date=entry.scheduled_for_date.isoformat() if entry.scheduled_for_date else None,
        replayed=replayed,
        created_at=iso_local(entry.created_at),
    )


class WishlistItemOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    estimated_price: str | None
    currency: str
    planned_at: str | None
    status: str
    note: str | None
    created_at: str
    deleted: bool | None = None


def wishlist_to_out(item: WishlistItem, deleted: bool = False) -> WishlistItemOut:
    return WishlistItemOut(
        id=id_str(item.id),
        title=item.title,
        estimated_price=money_str(item.estimated_price) if item.estimated_price is not None else None,
        currency=item.currency,
        planned_at=item.planned_at.isoformat() if item.planned_at else None,
        status=item.status,
        note=item.note,
        created_at=iso_local(item.created_at),
        deleted=True if deleted else None,
    )


class RecurringRuleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    direction: str
    amount: str
    currency: str
    category_id: str
    root_category_id: str
    category_path: str
    category_primary: str
    category_secondary: str | None
    note: str | None
    frequency: str
    day_of_week: int | None
    day_of_month: int | None
    month_of_year: int | None
    timezone: str
    start_date: str
    end_date: str | None
    next_run_date: str
    last_run_date: str | None
    status: str
    created_at: str
    deleted: bool | None = None


def recurring_to_out(rule: RecurringRule, deleted: bool = False) -> RecurringRuleOut:
    parts = rule.category_path.split("-")
    return RecurringRuleOut(
        id=id_str(rule.id),
        title=rule.title,
        direction=rule.direction,
        amount=money_str(rule.amount),
        currency=rule.currency,
        category_id=id_str(rule.category_id),
        root_category_id=id_str(rule.root_category_id),
        category_path=rule.category_path,
        category_primary=parts[0],
        category_secondary=parts[1] if len(parts) > 1 else None,
        note=rule.note,
        frequency=rule.frequency,
        day_of_week=rule.day_of_week,
        day_of_month=rule.day_of_month,
        month_of_year=rule.month_of_year,
        timezone=rule.timezone,
        start_date=rule.start_date.isoformat(),
        end_date=rule.end_date.isoformat() if rule.end_date else None,
        next_run_date=rule.next_run_date.isoformat(),
        last_run_date=rule.last_run_date.isoformat() if rule.last_run_date else None,
        status=rule.status,
        created_at=iso_local(rule.created_at),
        deleted=True if deleted else None,
    )


class ListResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int
    limit: int
    offset: int
    has_more: bool
    truncated: bool
    items: list
