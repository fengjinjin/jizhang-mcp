from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.exceptions import ValidationAppError
from jizhang_mcp.repositories import idempotency_repo, ledger_repo, wishlist_repo
from jizhang_mcp.services import category_service
from jizhang_mcp.services.serializers import LedgerEntryOut, ListResult, ledger_to_out
from jizhang_mcp.util.money import quantize_money
from jizhang_mcp.util.time_util import parse_occurred_at, utcnow


class LedgerAddBatchOut(BaseModel):
    dry_run: bool
    replayed: bool
    items: list


async def add_entry(
    session: AsyncSession,
    user_id: int,
    *,
    direction: str,
    amount: Decimal | float | str,
    category: str,
    occurred_at: str | None = None,
    note: str | None = None,
    currency: str = "CNY",
    wishlist_item_id: int | None = None,
    mark_wishlist_bought: bool = False,
    idempotency_key: str | None = None,
) -> LedgerEntryOut:
    amt = quantize_money(amount)
    if amt <= 0:
        raise ValidationAppError("金额须大于 0")
    if note and len(note) > 2000:
        raise ValidationAppError("备注过长")

    body = {
        "direction": direction,
        "amount": str(amt),
        "category": category,
        "occurred_at": occurred_at,
        "note": note,
        "currency": currency,
        "wishlist_item_id": wishlist_item_id,
        "mark_wishlist_bought": mark_wishlist_bought,
    }
    replayed = False
    if idempotency_key:
        req_hash = idempotency_repo.canonical_hash(body)
        existing = await idempotency_repo.begin_idempotency(
            session, user_id, "ledger_add", idempotency_key, req_hash
        )
        if existing and existing.response_json:
            replayed = True
            data = existing.response_json
            data["replayed"] = True
            return LedgerEntryOut.model_validate(data)

    resolved = await category_service.resolve_or_create(session, user_id, direction, category)
    occurred = parse_occurred_at(occurred_at)
    if wishlist_item_id:
        await wishlist_repo.get_item(session, user_id, wishlist_item_id)

    entry = await ledger_repo.insert_entry(
        session,
        user_id=user_id,
        direction=direction,
        amount=amt,
        currency=currency.upper()[:3],
        category_id=resolved.category.id,
        root_category_id=resolved.root.id,
        category_path=resolved.path,
        occurred_at=occurred,
        note=note,
        wishlist_item_id=wishlist_item_id,
    )
    if mark_wishlist_bought and wishlist_item_id:
        item = await wishlist_repo.get_item(session, user_id, wishlist_item_id)
        item.status = "bought"

    out = await ledger_to_out(session, entry, resolution=resolved.resolution, replayed=replayed)
    if idempotency_key:
        from sqlalchemy import select
        from jizhang_mcp.db.models.idempotency import IdempotencyRecord

        row = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.tool_name == "ledger_add",
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if row:
            row.response_json = out.model_dump()
    await session.commit()
    return out


async def add_batch(
    session: AsyncSession,
    user_id: int,
    entries: list[dict[str, Any]],
    dry_run: bool = False,
    idempotency_key: str | None = None,
) -> LedgerAddBatchOut:
    if not entries or len(entries) > 20:
        raise ValidationAppError("批量记账须 1～20 笔")

    if dry_run:
        previews = []
        for i, e in enumerate(entries):
            try:
                resolved = await category_service.resolve_or_create(
                    session, user_id, e["direction"], e["category"]
                )
                previews.append(
                    {
                        "direction": e["direction"],
                        "amount": str(quantize_money(e["amount"])),
                        "occurred_at": iso_local(parse_occurred_at(e.get("occurred_at"))),
                        "resolved_path": resolved.path,
                        "resolution": resolved.resolution,
                        "note": e.get("note"),
                    }
                )
            except Exception as exc:
                raise ValidationAppError(
                    f"第 {i} 笔校验失败: {exc}",
                    hint="修正该笔后重试整批",
                ) from exc
        return LedgerAddBatchOut(dry_run=True, replayed=False, items=previews)

    batch_body = {"entries": entries}
    if idempotency_key:
        req_hash = idempotency_repo.canonical_hash(batch_body)
        existing = await idempotency_repo.begin_idempotency(
            session, user_id, "ledger_add_batch", idempotency_key, req_hash
        )
        if existing and existing.response_json:
            data = existing.response_json
            data["replayed"] = True
            return LedgerAddBatchOut.model_validate(data)

    items_out: list[LedgerEntryOut] = []
    try:
        for i, e in enumerate(entries):
            try:
                resolved = await category_service.resolve_or_create(
                    session, user_id, e["direction"], e["category"]
                )
                amt = quantize_money(e["amount"])
                if amt <= 0:
                    raise ValidationAppError("金额须大于 0")
                entry = await ledger_repo.insert_entry(
                    session,
                    user_id=user_id,
                    direction=e["direction"],
                    amount=amt,
                    currency=(e.get("currency") or "CNY").upper()[:3],
                    category_id=resolved.category.id,
                    root_category_id=resolved.root.id,
                    category_path=resolved.path,
                    occurred_at=parse_occurred_at(e.get("occurred_at")),
                    note=e.get("note"),
                )
                items_out.append(
                    await ledger_to_out(session, entry, resolution=resolved.resolution)
                )
            except ValidationAppError as exc:
                exc.message = f"第 {i} 笔: {exc.message}"
                raise
    except Exception:
        await session.rollback()
        raise

    result = LedgerAddBatchOut(dry_run=False, replayed=False, items=[i.model_dump() for i in items_out])
    if idempotency_key:
        from sqlalchemy import select
        from jizhang_mcp.db.models.idempotency import IdempotencyRecord

        row = await session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.tool_name == "ledger_add_batch",
                IdempotencyRecord.idempotency_key == idempotency_key,
            )
        )
        if row:
            row.response_json = result.model_dump()
    await session.commit()
    return LedgerAddBatchOut(dry_run=False, replayed=False, items=items_out)


from jizhang_mcp.util.time_util import iso_local  # noqa: E402


async def list_entries(session, user_id: int, **filters) -> ListResult:
    limit = min(int(filters.get("limit", 50)), 200)
    offset = int(filters.get("offset", 0))
    items, total = await ledger_repo.list_entries(session, user_id, limit=limit, offset=offset, **filters)
    outs = [await ledger_to_out(session, e) for e in items]
    truncated = False
    return ListResult(
        total=total,
        limit=limit,
        offset=offset,
        has_more=offset + limit < total,
        truncated=truncated,
        items=outs,
    )


async def get_entry(session, user_id: int, entry_id: int) -> LedgerEntryOut:
    row = await ledger_repo.get_entry(session, user_id, entry_id)
    return await ledger_to_out(session, row)


async def update_entry(session, user_id: int, entry_id: int, patch: dict) -> dict:
    row = await ledger_repo.get_entry(session, user_id, entry_id)
    before_out = await ledger_to_out(session, row)
    before = row
    if "amount" in patch and patch["amount"] is not None:
        before.amount = quantize_money(patch["amount"])
    if "note" in patch:
        before.note = patch["note"]
    if "direction" in patch and patch["direction"]:
        before.direction = patch["direction"]
    if "occurred_at" in patch and patch["occurred_at"]:
        before.occurred_at = parse_occurred_at(patch["occurred_at"])
    if "category" in patch and patch["category"]:
        resolved = await category_service.resolve_or_create(
            session, user_id, before.direction, patch["category"]
        )
        before.category_id = resolved.category.id
        before.root_category_id = resolved.root.id
        before.category_path = resolved.path
    await session.commit()
    await session.refresh(before)
    after_out = await ledger_to_out(session, before)
    return {"before": before_out.model_dump(), "after": after_out.model_dump()}


async def delete_entry(session, user_id: int, entry_id: int) -> LedgerEntryOut:
    row = await ledger_repo.soft_delete(session, user_id, entry_id, utcnow())
    out = await ledger_to_out(session, row)
    out.deleted = True
    await session.commit()
    return out
