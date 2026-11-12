from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.mcp_tools.boundary import mcp_boundary
from jizhang_mcp.security.principal import get_principal
from jizhang_mcp.services import ledger_service
from jizhang_mcp.services.serializers import LedgerEntryOut
from jizhang_mcp.util.ids import IdInt


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="ledger_add", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def ledger_add(
        direction: Annotated[Literal["expense", "income"], Field(description="支出或收入")],
        amount: Annotated[float, Field(description="金额，两位小数", gt=0)],
        category: Annotated[str, Field(description="类目路径或口语，例 餐饮-奶茶")],
        occurred_at: Annotated[str | None, Field(description="YYYY-MM-DD 或 ISO-8601")] = None,
        note: Annotated[str | None, Field(description="备注，≤2000")] = None,
        currency: Annotated[str, Field(description="三位货币码")] = "CNY",
        wishlist_item_id: IdInt | None = None,
        mark_wishlist_bought: bool = False,
        idempotency_key: Annotated[str | None, Field(description="幂等键，≤64")] = None,
    ) -> LedgerEntryOut:
        factory = get_session_factory()
        async with factory() as session:
            return await ledger_service.add_entry(
                session,
                get_principal().user_id,
                direction=direction,
                amount=amount,
                category=category,
                occurred_at=occurred_at,
                note=note,
                currency=currency,
                wishlist_item_id=wishlist_item_id,
                mark_wishlist_bought=mark_wishlist_bought,
                idempotency_key=idempotency_key,
            )

    @mcp.tool(name="ledger_add_batch", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def ledger_add_batch(
        entries: Annotated[list[dict], Field(description="流水数组，每笔字段同 ledger_add")],
        dry_run: bool = False,
        idempotency_key: str | None = None,
    ):
        factory = get_session_factory()
        async with factory() as session:
            return await ledger_service.add_batch(
                session, get_principal().user_id, entries, dry_run=dry_run, idempotency_key=idempotency_key
            )

    @mcp.tool(name="ledger_list", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def ledger_list(
        date_from: str | None = None,
        date_to: str | None = None,
        direction: Literal["expense", "income"] | None = None,
        category: str | None = None,
        category_id: IdInt | None = None,
        root_category_id: IdInt | None = None,
        currency: str | None = None,
        keyword: str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        recurring_rule_id: IdInt | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        from jizhang_mcp.util.time_util import parse_occurred_at

        factory = get_session_factory()
        async with factory() as session:
            return await ledger_service.list_entries(
                session,
                get_principal().user_id,
                date_from=parse_occurred_at(date_from) if date_from else None,
                date_to=parse_occurred_at(date_to) if date_to else None,
                direction=direction,
                category_id=category_id,
                root_category_id=root_category_id,
                currency=currency,
                keyword=keyword,
                min_amount=min_amount,
                max_amount=max_amount,
                recurring_rule_id=recurring_rule_id,
                limit=limit,
                offset=offset,
            )

    @mcp.tool(name="ledger_get", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def ledger_get(entry_id: IdInt) -> LedgerEntryOut:
        factory = get_session_factory()
        async with factory() as session:
            return await ledger_service.get_entry(session, get_principal().user_id, entry_id)

    @mcp.tool(name="ledger_update", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def ledger_update(
        entry_id: IdInt,
        direction: Literal["expense", "income"] | None = None,
        amount: float | None = None,
        category: str | None = None,
        occurred_at: str | None = None,
        note: str | None = None,
        currency: str | None = None,
    ):
        patch = {
            k: v
            for k, v in {
                "direction": direction,
                "amount": amount,
                "category": category,
                "occurred_at": occurred_at,
                "note": note,
                "currency": currency,
            }.items()
            if v is not None
        }
        factory = get_session_factory()
        async with factory() as session:
            return await ledger_service.update_entry(session, get_principal().user_id, entry_id, patch)

    @mcp.tool(name="ledger_delete", annotations={"destructiveHint": True})
    @mcp_boundary
    async def ledger_delete(entry_id: IdInt) -> LedgerEntryOut:
        factory = get_session_factory()
        async with factory() as session:
            return await ledger_service.delete_entry(session, get_principal().user_id, entry_id)
