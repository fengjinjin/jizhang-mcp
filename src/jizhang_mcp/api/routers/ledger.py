import csv
import io
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.services import ledger_service
from jizhang_mcp.util.ids import IdInt
from jizhang_mcp.util.time_util import iso_local, parse_occurred_at

router = APIRouter(prefix="/ledger", tags=["ledger"])


class LedgerAddBody(BaseModel):
    direction: Literal["expense", "income"]
    amount: float
    category: str
    occurred_at: str | None = None
    note: str | None = None
    currency: str = "CNY"


@router.post("/entries", status_code=201)
async def add_entry(body: LedgerAddBody, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await ledger_service.add_entry(
        session,
        user_id,
        direction=body.direction,
        amount=body.amount,
        category=body.category,
        occurred_at=body.occurred_at,
        note=body.note,
        currency=body.currency,
    )


@router.get("/entries")
async def list_entries(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    direction: Literal["expense", "income"] | None = None,
    category_id: IdInt | None = None,
    root_category_id: IdInt | None = None,
    currency: str | None = None,
    keyword: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return await ledger_service.list_entries(
        session,
        user_id,
        date_from=parse_occurred_at(date_from) if date_from else None,
        date_to=parse_occurred_at(date_to) if date_to else None,
        direction=direction,
        category_id=category_id,
        root_category_id=root_category_id,
        currency=currency,
        keyword=keyword,
        limit=limit,
        offset=offset,
    )


@router.get("/entries/{entry_id}")
async def get_entry(entry_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await ledger_service.get_entry(session, user_id, entry_id)


@router.patch("/entries/{entry_id}")
async def update_entry(entry_id: IdInt, patch: dict, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await ledger_service.update_entry(session, user_id, entry_id, patch)


@router.delete("/entries/{entry_id}")
async def delete_entry(entry_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await ledger_service.delete_entry(session, user_id, entry_id)


def _csv_cell(value: str | None) -> str:
    if not value:
        return ""
    s = value.strip()
    if s and s[0] in "=+-@":
        return "'" + s
    return s


@router.get("/export")
async def export_csv(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    direction: Literal["expense", "income"] | None = None,
    currency: str | None = None,
):
    result = await ledger_service.list_entries(
        session,
        user_id,
        date_from=parse_occurred_at(date_from) if date_from else None,
        date_to=parse_occurred_at(date_to) if date_to else None,
        direction=direction,
        currency=currency,
        limit=100000,
        offset=0,
    )
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(["id", "occurred_at", "direction", "amount", "currency", "category_path", "note", "created_at"])
    for item in result.items:
        writer.writerow(
            [
                item.id,
                item.occurred_at,
                item.direction,
                item.amount,
                item.currency,
                _csv_cell(item.category_path),
                _csv_cell(item.note),
                item.created_at,
            ]
        )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="jizhang-ledger.csv"'},
    )
