from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, timedelta
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.constants import (
    CATEGORY_SHARE_DISCLAIMER,
    COMPARE_DISCLAIMER,
    STATS_DISCLAIMER,
    TOP_EXPENSES_DISCLAIMER,
)
from jizhang_mcp.db.models.ledger import LedgerEntry
from jizhang_mcp.exceptions import ValidationAppError
from jizhang_mcp.repositories import ledger_repo
from jizhang_mcp.util.money import money_str, quantize_money
from jizhang_mcp.util.time_util import default_stats_range, get_tz, iso_local, month_start_local, now_local, parse_occurred_at


def _parse_range(date_from: str | None, date_to: str | None) -> tuple[datetime, datetime]:
    if date_from and date_to:
        df = parse_occurred_at(date_from)
        dt = parse_occurred_at(date_to)
    else:
        df, dt = default_stats_range()
    if (dt - df).days > 366:
        raise ValidationAppError("统计区间不能超过 366 天")
    return df, dt


async def _agg(session: AsyncSession, user_id: int, df: datetime, dt: datetime, currency: str):
    cond = and_(
        LedgerEntry.user_id == user_id,
        LedgerEntry.deleted_at.is_(None),
        LedgerEntry.occurred_at >= df,
        LedgerEntry.occurred_at <= dt,
        LedgerEntry.currency == currency,
    )
    inc = func.coalesce(
        func.sum(case((LedgerEntry.direction == "income", LedgerEntry.amount), else_=0)), 0
    )
    exp = func.coalesce(
        func.sum(case((LedgerEntry.direction == "expense", LedgerEntry.amount), else_=0)), 0
    )
    inc_c = func.coalesce(
        func.sum(case((LedgerEntry.direction == "income", 1), else_=0)), 0
    )
    exp_c = func.coalesce(
        func.sum(case((LedgerEntry.direction == "expense", 1), else_=0)), 0
    )
    row = await session.execute(select(inc, exp, inc_c, exp_c).where(cond))
    ti, te, ic, ec = row.one()
    ti = quantize_money(ti or 0)
    te = quantize_money(te or 0)
    return ti, te, ic, ec


class StatsSummaryOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    granularity: str
    date_from: str
    date_to: str
    total_income: str
    total_expense: str
    surplus: str
    income_count: int
    expense_count: int
    entry_count: int
    has_any_entries: bool
    available_currencies: list[str]
    series: list[dict]
    daily: list[dict]
    disclaimer: str


async def stats_summary(
    session: AsyncSession,
    user_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    granularity: str = "auto",
) -> StatsSummaryOut:
    df, dt = _parse_range(date_from, date_to)
    ti, te, ic, ec = await _agg(session, user_id, df, dt, currency)
    span = (dt.date() - df.date()).days
    gran = granularity
    if gran == "auto":
        gran = "day" if span <= 90 else "month"
    if gran not in ("day", "month"):
        raise ValidationAppError("granularity 不合法")

    series: list[dict] = []
    if gran == "day":
        stmt = (
            select(
                func.date_trunc("day", LedgerEntry.occurred_at).label("d"),
                func.sum(case((LedgerEntry.direction == "income", LedgerEntry.amount), else_=0)),
                func.sum(case((LedgerEntry.direction == "expense", LedgerEntry.amount), else_=0)),
            )
            .where(
                LedgerEntry.user_id == user_id,
                LedgerEntry.deleted_at.is_(None),
                LedgerEntry.currency == currency,
                LedgerEntry.occurred_at >= df,
                LedgerEntry.occurred_at <= dt,
            )
            .group_by("d")
            .order_by("d")
        )
        for d, inc, exp in (await session.execute(stmt)).all():
            inc_d = quantize_money(inc or 0)
            exp_d = quantize_money(exp or 0)
            series.append(
                {
                    "date": d.date().isoformat(),
                    "income": money_str(inc_d),
                    "expense": money_str(exp_d),
                    "surplus": money_str(inc_d - exp_d),
                }
            )
    else:
        stmt = (
            select(
                func.to_char(LedgerEntry.occurred_at, "YYYY-MM").label("m"),
                func.sum(case((LedgerEntry.direction == "income", LedgerEntry.amount), else_=0)),
                func.sum(case((LedgerEntry.direction == "expense", LedgerEntry.amount), else_=0)),
            )
            .where(
                LedgerEntry.user_id == user_id,
                LedgerEntry.deleted_at.is_(None),
                LedgerEntry.currency == currency,
                LedgerEntry.occurred_at >= df,
                LedgerEntry.occurred_at <= dt,
            )
            .group_by("m")
            .order_by("m")
        )
        for m, inc, exp in (await session.execute(stmt)).all():
            inc_d = quantize_money(inc or 0)
            exp_d = quantize_money(exp or 0)
            series.append(
                {
                    "date": m,
                    "income": money_str(inc_d),
                    "expense": money_str(exp_d),
                    "surplus": money_str(inc_d - exp_d),
                }
            )

    cur_stmt = (
        select(LedgerEntry.currency, func.count())
        .where(LedgerEntry.user_id == user_id, LedgerEntry.deleted_at.is_(None))
        .group_by(LedgerEntry.currency)
        .order_by(func.count().desc())
    )
    curs = [r[0] for r in (await session.execute(cur_stmt)).all()]
    if "CNY" in curs:
        curs.remove("CNY")
        curs = ["CNY", *curs]
    elif not curs:
        curs = ["CNY"]

    has_any = await ledger_repo.count_any_entries(session, user_id)
    daily = series if gran == "day" else []
    return StatsSummaryOut(
        currency=currency,
        granularity=gran,
        date_from=iso_local(df),
        date_to=iso_local(dt),
        total_income=money_str(ti),
        total_expense=money_str(te),
        surplus=money_str(ti - te),
        income_count=int(ic),
        expense_count=int(ec),
        entry_count=int(ic + ec),
        has_any_entries=has_any,
        available_currencies=curs,
        series=series,
        daily=daily,
        disclaimer=STATS_DISCLAIMER,
    )


def _prev_month_same_span(df: datetime, dt: datetime) -> tuple[datetime, datetime]:
    tz = get_tz()

    def shift(d: datetime) -> datetime:
        y, m = d.year, d.month
        if m == 1:
            py, pm = y - 1, 12
        else:
            py, pm = y, m - 1
        last = monthrange(py, pm)[1]
        day = min(d.day, last)
        return d.replace(year=py, month=pm, day=day)

    return shift(df), shift(dt)


def _prev_adjacent(df: datetime, dt: datetime) -> tuple[datetime, datetime]:
    delta = dt - df
    return df - delta - timedelta(seconds=1), df - timedelta(seconds=1)


def _infer_default_compare_mode(df: datetime, dt: datetime) -> str:
    """当前自然月 / 年初至今的默认环比方式（正式 spec）。"""
    now = now_local()
    ms = month_start_local(now.date())
    ys = datetime(now.year, 1, 1, tzinfo=get_tz())
    if df >= ms and df.date() == ms.date() and dt.date() == now.date():
        return "prev_month_same_span"
    if df >= ys and df.date() == ys.date() and dt.date() == now.date():
        return "prev_year_same_span"
    return "prev_adjacent_period"


def _prev_year_same(df: datetime, dt: datetime) -> tuple[datetime, datetime]:
    def sh(d: datetime) -> datetime:
        try:
            return d.replace(year=d.year - 1)
        except ValueError:
            return d.replace(year=d.year - 1, day=28)

    return sh(df), sh(dt)


class StatsCompareOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    compare_mode: str
    current: dict
    previous: dict
    delta: dict
    disclaimer: str


async def stats_compare(
    session: AsyncSession,
    user_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    compare_mode: str | None = None,
) -> StatsCompareOut:
    df, dt = _parse_range(date_from, date_to)
    mode = compare_mode
    if not mode:
        mode = _infer_default_compare_mode(df, dt)
    if mode == "prev_month_same_span":
        pdf, pdt = _prev_month_same_span(df, dt)
    elif mode == "prev_year_same_span":
        pdf, pdt = _prev_year_same(df, dt)
    else:
        mode = "prev_adjacent_period"
        pdf, pdt = _prev_adjacent(df, dt)

    cti, cte, _, _ = await _agg(session, user_id, df, dt, currency)
    pti, pte, _, _ = await _agg(session, user_id, pdf, pdt, currency)
    expense_ratio = None
    if pte > 0:
        expense_ratio = float((cte - pte) / pte)
    return StatsCompareOut(
        currency=currency,
        compare_mode=mode,
        current={
            "date_from": iso_local(df),
            "date_to": iso_local(dt),
            "total_income": money_str(cti),
            "total_expense": money_str(cte),
            "surplus": money_str(cti - cte),
        },
        previous={
            "date_from": iso_local(pdf),
            "date_to": iso_local(pdt),
            "total_income": money_str(pti),
            "total_expense": money_str(pte),
            "surplus": money_str(pti - pte),
        },
        delta={
            "income": money_str(cti - pti),
            "expense": money_str(cte - pte),
            "surplus": money_str((cti - cte) - (pti - pte)),
            "expense_ratio": expense_ratio,
        },
        disclaimer=COMPARE_DISCLAIMER,
    )


async def stats_category_share(
    session: AsyncSession,
    user_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    direction: str = "expense",
    group_by: str = "primary",
) -> dict:
    df, dt = _parse_range(date_from, date_to)
    if group_by == "primary":
        key = LedgerEntry.root_category_id
        path = func.split_part(LedgerEntry.category_path, "-", 1)
    else:
        key = LedgerEntry.category_id
        path = LedgerEntry.category_path
    stmt = (
        select(
            key,
            path,
            LedgerEntry.root_category_id,
            func.sum(LedgerEntry.amount),
            func.count(),
        )
        .where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.deleted_at.is_(None),
            LedgerEntry.direction == direction,
            LedgerEntry.currency == currency,
            LedgerEntry.occurred_at >= df,
            LedgerEntry.occurred_at <= dt,
        )
        .group_by(key, path, LedgerEntry.root_category_id)
        .order_by(func.sum(LedgerEntry.amount).desc())
    )
    rows = (await session.execute(stmt)).all()
    total = sum(quantize_money(r[3] or 0) for r in rows)
    items = []
    for cid, cpath, rid, amt, cnt in rows:
        amt_d = quantize_money(amt or 0)
        ratio = float(amt_d / total) if total > 0 else 0.0
        parts = cpath.split("-")
        items.append(
            {
                "category_id": str(cid),
                "root_category_id": str(rid),
                "category_path": cpath,
                "category_primary": parts[0],
                "category_secondary": parts[1] if len(parts) > 1 else None,
                "amount": money_str(amt_d),
                "count": int(cnt),
                "ratio": ratio,
            }
        )
    return {
        "currency": currency,
        "direction": direction,
        "group_by": group_by,
        "date_from": iso_local(df),
        "date_to": iso_local(dt),
        "total": money_str(total),
        "items": items,
        "disclaimer": CATEGORY_SHARE_DISCLAIMER,
    }


async def stats_top_expenses(
    session: AsyncSession,
    user_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    limit: int = 10,
) -> dict:
    df, dt = _parse_range(date_from, date_to)
    limit = min(limit, 50)
    stmt = (
        select(LedgerEntry)
        .where(
            LedgerEntry.user_id == user_id,
            LedgerEntry.deleted_at.is_(None),
            LedgerEntry.direction == "expense",
            LedgerEntry.currency == currency,
            LedgerEntry.occurred_at >= df,
            LedgerEntry.occurred_at <= dt,
        )
        .order_by(LedgerEntry.amount.desc(), LedgerEntry.id.desc())
        .limit(limit)
    )
    rows = list((await session.scalars(stmt)).all())
    items = []
    for rank, e in enumerate(rows, 1):
        parts = e.category_path.split("-")
        items.append(
            {
                "rank": rank,
                "id": str(e.id),
                "amount": money_str(e.amount),
                "category_id": str(e.category_id),
                "root_category_id": str(e.root_category_id),
                "category_path": e.category_path,
                "category_primary": parts[0],
                "category_secondary": parts[1] if len(parts) > 1 else None,
                "occurred_at": iso_local(e.occurred_at),
                "note": e.note,
            }
        )
    return {
        "currency": currency,
        "date_from": iso_local(df),
        "date_to": iso_local(dt),
        "items": items,
        "disclaimer": TOP_EXPENSES_DISCLAIMER,
    }


async def stats_review(session: AsyncSession, user_id: int, **kwargs) -> dict:
    summary = await stats_summary(session, user_id, **kwargs)
    compare = await stats_compare(session, user_id, **kwargs)
    share = await stats_category_share(session, user_id, **kwargs)
    top = await stats_top_expenses(session, user_id, limit=5, **kwargs)
    return {
        "summary": summary.model_dump(),
        "compare": compare.model_dump(),
        "category_share": share,
        "top_expenses": top,
    }
