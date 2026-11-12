from typing import Literal

from fastmcp import FastMCP

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.mcp_tools.boundary import mcp_boundary
from jizhang_mcp.security.principal import get_principal
from jizhang_mcp.services import wishlist_service
from jizhang_mcp.util.ids import IdInt


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="wishlist_add", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def wishlist_add(
        title: str,
        estimated_price: float | None = None,
        currency: str = "CNY",
        planned_at: str | None = None,
        note: str | None = None,
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await wishlist_service.add_item(
                session,
                get_principal().user_id,
                title,
                estimated_price=estimated_price,
                currency=currency,
                planned_at=planned_at,
                note=note,
            )

    @mcp.tool(name="wishlist_list", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def wishlist_list(status: str | None = None, limit: int = 50, offset: int = 0):
        factory = get_session_factory()
        async with factory() as session:
            return await wishlist_service.list_items(session, get_principal().user_id, status, limit, offset)

    @mcp.tool(name="wishlist_get", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def wishlist_get(wishlist_item_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            return await wishlist_service.get_item(session, get_principal().user_id, wishlist_item_id)

    @mcp.tool(name="wishlist_update", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def wishlist_update(
        wishlist_item_id: IdInt,
        title: str | None = None,
        estimated_price: float | None = None,
        planned_at: str | None = None,
        status: Literal["wanted", "bought", "cancelled"] | None = None,
        note: str | None = None,
        currency: str | None = None,
    ):
        patch = {
            k: v
            for k, v in {
                "title": title,
                "estimated_price": estimated_price,
                "planned_at": planned_at,
                "status": status,
                "note": note,
                "currency": currency,
            }.items()
            if v is not None
        }
        factory = get_session_factory()
        async with factory() as session:
            return await wishlist_service.update_item(session, get_principal().user_id, wishlist_item_id, patch)

    @mcp.tool(name="wishlist_delete", annotations={"destructiveHint": True})
    @mcp_boundary
    async def wishlist_delete(wishlist_item_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            return await wishlist_service.delete_item(session, get_principal().user_id, wishlist_item_id)

    @mcp.tool(name="wishlist_evaluate", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def wishlist_evaluate(
        wishlist_item_id: IdInt | None = None,
        estimated_price: float | None = None,
        recent_days: int = 30,
        currency: str = "CNY",
        baseline: Literal["rolling", "last_full_month"] = "rolling",
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await wishlist_service.evaluate(
                session,
                get_principal().user_id,
                wishlist_item_id=wishlist_item_id,
                estimated_price=estimated_price,
                recent_days=recent_days,
                currency=currency,
                baseline=baseline,
            )
