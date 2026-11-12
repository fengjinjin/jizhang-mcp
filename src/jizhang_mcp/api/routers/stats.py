from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.services import stats_service

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary")
async def summary(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    granularity: Literal["auto", "day", "month"] = "auto",
):
    return await stats_service.stats_summary(session, user_id, date_from, date_to, currency, granularity)


@router.get("/compare")
async def compare(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    compare_mode: str | None = None,
):
    return await stats_service.stats_compare(session, user_id, date_from, date_to, currency, compare_mode)


@router.get("/category-share")
async def category_share(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    direction: Literal["expense", "income"] = "expense",
    group_by: Literal["primary", "leaf"] = "primary",
):
    return await stats_service.stats_category_share(
        session, user_id, date_from, date_to, currency, direction, group_by
    )


@router.get("/top-expenses")
async def top_expenses(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
    limit: int = 10,
):
    return await stats_service.stats_top_expenses(session, user_id, date_from, date_to, currency, limit)


@router.get("/review")
async def review(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    date_from: str | None = None,
    date_to: str | None = None,
    currency: str = "CNY",
):
    return await stats_service.stats_review(session, user_id, date_from=date_from, date_to=date_to, currency=currency)
