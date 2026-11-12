from __future__ import annotations

import calendar
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.recurring import RecurringRule
from jizhang_mcp.exceptions import RecurringRuleNotFoundError, ValidationAppError
from jizhang_mcp.repositories import ledger_repo, recurring_repo
from jizhang_mcp.services import category_service
from jizhang_mcp.services.serializers import ListResult, RecurringRuleOut, recurring_to_out
from jizhang_mcp.util.money import quantize_money
from jizhang_mcp.util.time_util import parse_date_only, utcnow

logger = logging.getLogger("jizhang")


def _rule_tz(rule: RecurringRule) -> ZoneInfo:
    return ZoneInfo(rule.timezone)


def today_in_rule_tz(rule: RecurringRule) -> date:
    return datetime.now(tz=_rule_tz(rule)).date()


def clamp_day(year: int, month: int, dom: int) -> date:
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(dom, last))


def next_occurrence(rule: RecurringRule, after: date) -> date:
    if rule.frequency == "daily":
        return after + timedelta(days=1)
    if rule.frequency == "weekly":
        target = rule.day_of_week or 1
        d = after + timedelta(days=1)
        for _ in range(370):
            if d.isoweekday() == target:
                return d
            d += timedelta(days=1)
        raise ValidationAppError("无法计算下一账期")
    if rule.frequency == "monthly":
        dom = rule.day_of_month or 1
        y, m = after.year, after.month
        if after.day >= min(dom, calendar.monthrange(y, m)[1]):
            if m == 12:
                y, m = y + 1, 1
            else:
                m += 1
        return clamp_day(y, m, dom)
    if rule.frequency == "yearly":
        my = rule.month_of_year or 1
        dom = rule.day_of_month or 1
        y = after.year
        candidate = clamp_day(y, my, dom)
        if candidate <= after:
            candidate = clamp_day(y + 1, my, dom)
        return candidate
    raise ValidationAppError("frequency 不合法")


def first_occurrence(rule: RecurringRule, start: date) -> date:
    if rule.frequency == "daily":
        return start
    if rule.frequency == "weekly":
        target = rule.day_of_week or 1
        d = start
        for _ in range(8):
            if d.isoweekday() == target:
                return d
            d += timedelta(days=1)
        return next_occurrence(rule, start)
    if rule.frequency == "monthly":
        dom = rule.day_of_month or 1
        cand = clamp_day(start.year, start.month, dom)
        if cand >= start:
            return cand
        y, m = start.year, start.month
        if m == 12:
            y, m = y + 1, 1
        else:
            m += 1
        return clamp_day(y, m, dom)
    if rule.frequency == "yearly":
        my = rule.month_of_year or 1
        dom = rule.day_of_month or 1
        cand = clamp_day(start.year, my, dom)
        if cand >= start:
            return cand
        return clamp_day(start.year + 1, my, dom)
    raise ValidationAppError("frequency 不合法")


def occurred_at_for(period: date, rule: RecurringRule) -> datetime:
    tz = _rule_tz(rule)
    return datetime.combine(period, time(9, 0), tzinfo=tz)


async def add_rule(session, user_id: int, payload: dict) -> RecurringRuleOut:
    direction = payload["direction"]
    resolved = await category_service.resolve_or_create(session, user_id, direction, payload["category"])
    tzname = payload.get("timezone") or "Asia/Shanghai"
    try:
        ZoneInfo(tzname)
    except Exception as exc:
        raise ValidationAppError("timezone 不合法") from exc
    start_date = parse_date_only(payload.get("start_date") or str(today_in_rule_tz_temp(tzname)))
    if (today_in_rule_tz_temp(tzname) - start_date).days > 31:
        raise ValidationAppError("start_date 不能早于 31 天前")
    end_date = parse_date_only(payload["end_date"]) if payload.get("end_date") else None
    rule = RecurringRule(
        user_id=user_id,
        title=payload["title"],
        direction=direction,
        amount=quantize_money(payload["amount"]),
        currency=(payload.get("currency") or "CNY").upper()[:3],
        category_id=resolved.category.id,
        root_category_id=resolved.root.id,
        category_path=resolved.path,
        note=payload.get("note"),
        frequency=payload["frequency"],
        day_of_week=payload.get("day_of_week"),
        day_of_month=payload.get("day_of_month"),
        month_of_year=payload.get("month_of_year"),
        timezone=tzname,
        start_date=start_date,
        end_date=end_date,
        next_run_date=first_occurrence_temp(payload, start_date),
        status="active",
    )
    session.add(rule)
    await session.commit()
    await session.refresh(rule)
    if payload.get("catch_up_today", True):
        await settle_one(session, rule.id)
    return recurring_to_out(rule)


def today_in_rule_tz_temp(tzname: str) -> date:
    return datetime.now(ZoneInfo(tzname)).date()


def first_occurrence_temp(payload: dict, start: date) -> date:
    tmp = RecurringRule(
        user_id=0,
        title="",
        direction="expense",
        amount=1,
        category_id=1,
        root_category_id=1,
        category_path="其他",
        frequency=payload["frequency"],
        day_of_week=payload.get("day_of_week"),
        day_of_month=payload.get("day_of_month"),
        month_of_year=payload.get("month_of_year"),
        timezone=payload.get("timezone") or "Asia/Shanghai",
        start_date=start,
        next_run_date=start,
    )
    return first_occurrence(tmp, start)


async def list_rules(session, user_id, status, limit, offset) -> ListResult:
    limit = min(limit, 200)
    rows, total = await recurring_repo.list_rules(session, user_id, status, limit, offset)
    return ListResult(
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
        truncated=False,
        items=[recurring_to_out(r) for r in rows],
    )


async def settle_one(session: AsyncSession, rule_id: int) -> None:
    rule = await recurring_repo.lock_rule_for_settle(session, rule_id)
    if rule is None:
        return
    today = today_in_rule_tz(rule)
    periods = []
    cur = rule.next_run_date
    while cur <= today and len(periods) < 31:
        if rule.end_date and cur > rule.end_date:
            rule.status = "ended"
            break
        periods.append(cur)
        cur = next_occurrence(rule, cur)
    for period in periods:
        values = dict(
            user_id=rule.user_id,
            direction=rule.direction,
            amount=rule.amount,
            currency=rule.currency,
            category_id=rule.category_id,
            root_category_id=rule.root_category_id,
            category_path=rule.category_path,
            note=rule.note or rule.title,
            occurred_at=occurred_at_for(period, rule),
            recurring_rule_id=rule.id,
            scheduled_for_date=period,
        )
        await ledger_repo.insert_recurring_entry_on_conflict_nothing(session, values)
        rule.last_run_date = period
        rule.next_run_date = next_occurrence(rule, period)
    if rule.end_date and rule.next_run_date > rule.end_date:
        rule.status = "ended"
    await session.commit()


async def settle_due_rules(session: AsyncSession, user_id: int | None = None) -> None:
    from jizhang_mcp.util.time_util import utcnow as _utcnow

    horizon = _utcnow().date() + timedelta(days=1)
    ids = await recurring_repo.list_due_candidates(session, horizon)
    for rid in ids:
        if user_id is not None:
            rule = await session.get(RecurringRule, rid)
            if not rule or rule.user_id != user_id:
                continue
        try:
            await settle_one(session, rid)
        except Exception:
            logger.exception("settle recurring rule failed id=%s", rid)
