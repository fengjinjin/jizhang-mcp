from typing import Literal

from fastmcp import FastMCP

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.mcp_tools.boundary import mcp_boundary
from jizhang_mcp.security.principal import get_principal
from jizhang_mcp.services import stats_service


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="stats_summary", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def stats_summary(
        date_from: str | None = None,
        date_to: str | None = None,
        currency: str = "CNY",
        granularity: Literal["auto", "day", "month"] = "auto",
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await stats_service.stats_summary(
                session, get_principal().user_id, date_from, date_to, currency, granularity
            )

    @mcp.tool(name="stats_compare", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def stats_compare(
        date_from: str | None = None,
        date_to: str | None = None,
        currency: str = "CNY",
        compare_mode: str | None = None,
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await stats_service.stats_compare(
                session, get_principal().user_id, date_from, date_to, currency, compare_mode
            )

    @mcp.tool(name="stats_category_share", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def stats_category_share(
        date_from: str | None = None,
        date_to: str | None = None,
        currency: str = "CNY",
        direction: Literal["expense", "income"] = "expense",
        group_by: Literal["primary", "leaf"] = "primary",
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await stats_service.stats_category_share(
                session, get_principal().user_id, date_from, date_to, currency, direction, group_by
            )

    @mcp.tool(name="stats_top_expenses", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def stats_top_expenses(
        date_from: str | None = None,
        date_to: str | None = None,
        currency: str = "CNY",
        limit: int = 10,
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await stats_service.stats_top_expenses(
                session, get_principal().user_id, date_from, date_to, currency, limit
            )

    @mcp.tool(name="stats_review", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def stats_review(date_from: str | None = None, date_to: str | None = None, currency: str = "CNY"):
        factory = get_session_factory()
        async with factory() as session:
            return await stats_service.stats_review(
                session, get_principal().user_id, date_from=date_from, date_to=date_to, currency=currency
            )
