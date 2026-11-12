from typing import Literal

from fastmcp import FastMCP
from pydantic import Field
from typing import Annotated

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.mcp_tools.boundary import mcp_boundary
from jizhang_mcp.repositories import recurring_repo
from jizhang_mcp.security.principal import get_principal
from jizhang_mcp.services import recurring_service
from jizhang_mcp.services.serializers import recurring_to_out
from jizhang_mcp.util.ids import IdInt


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="recurring_add", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def recurring_add(
        title: Annotated[str, Field(description="规则标题")],
        direction: Literal["expense", "income"],
        amount: Annotated[float, Field(gt=0)],
        category: str,
        frequency: Literal["daily", "weekly", "monthly", "yearly"],
        day_of_week: int | None = None,
        day_of_month: int | None = None,
        month_of_year: int | None = None,
        timezone: str = "Asia/Shanghai",
        start_date: str | None = None,
        end_date: str | None = None,
        note: str | None = None,
        currency: str = "CNY",
        catch_up_today: bool = True,
    ):
        payload = {
            "title": title,
            "direction": direction,
            "amount": amount,
            "category": category,
            "frequency": frequency,
            "day_of_week": day_of_week,
            "day_of_month": day_of_month,
            "month_of_year": month_of_year,
            "timezone": timezone,
            "start_date": start_date,
            "end_date": end_date,
            "note": note,
            "currency": currency,
            "catch_up_today": catch_up_today,
        }
        factory = get_session_factory()
        async with factory() as session:
            return await recurring_service.add_rule(session, get_principal().user_id, payload)

    @mcp.tool(name="recurring_list", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def recurring_list(status: str | None = None, limit: int = 50, offset: int = 0):
        factory = get_session_factory()
        async with factory() as session:
            return await recurring_service.list_rules(session, get_principal().user_id, status, limit, offset)

    @mcp.tool(name="recurring_get", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def recurring_get(rule_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            return recurring_to_out(await recurring_repo.get_rule(session, get_principal().user_id, rule_id))

    @mcp.tool(name="recurring_update", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def recurring_update(
        rule_id: IdInt,
        title: str | None = None,
        amount: float | None = None,
        category: str | None = None,
        frequency: Literal["daily", "weekly", "monthly", "yearly"] | None = None,
        day_of_week: int | None = None,
        day_of_month: int | None = None,
        month_of_year: int | None = None,
        timezone: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        note: str | None = None,
        currency: str | None = None,
    ):
        patch = {
            k: v
            for k, v in {
                "title": title,
                "amount": amount,
                "category": category,
                "frequency": frequency,
                "day_of_week": day_of_week,
                "day_of_month": day_of_month,
                "month_of_year": month_of_year,
                "timezone": timezone,
                "start_date": start_date,
                "end_date": end_date,
                "note": note,
                "currency": currency,
            }.items()
            if v is not None
        }
        factory = get_session_factory()
        async with factory() as session:
            rule = await recurring_repo.get_rule(session, get_principal().user_id, rule_id)
            for k, v in patch.items():
                if hasattr(rule, k):
                    setattr(rule, k, v)
            await session.commit()
            return recurring_to_out(rule)

    @mcp.tool(name="recurring_pause", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def recurring_pause(rule_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            rule = await recurring_repo.get_rule(session, get_principal().user_id, rule_id)
            rule.status = "paused"
            await session.commit()
            return recurring_to_out(rule)

    @mcp.tool(name="recurring_resume", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def recurring_resume(rule_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            rule = await recurring_repo.get_rule(session, get_principal().user_id, rule_id)
            rule.status = "active"
            today = recurring_service.today_in_rule_tz(rule)
            if rule.next_run_date < today:
                rule.next_run_date = recurring_service.first_occurrence(rule, today)
            await session.commit()
            return recurring_to_out(rule)

    @mcp.tool(name="recurring_delete", annotations={"destructiveHint": True})
    @mcp_boundary
    async def recurring_delete(rule_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            rule = await recurring_repo.soft_delete(session, get_principal().user_id, rule_id)
            out = recurring_to_out(rule, deleted=True)
            await session.commit()
            return out
