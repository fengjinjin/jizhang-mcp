from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.repositories import recurring_repo
from jizhang_mcp.services import recurring_service
from jizhang_mcp.services.serializers import recurring_to_out
from jizhang_mcp.util.ids import IdInt

router = APIRouter(prefix="/recurring", tags=["recurring"])


@router.post("/rules", status_code=201)
async def add_rule(body: dict, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await recurring_service.add_rule(session, user_id, body)


@router.get("/rules")
async def list_rules(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return await recurring_service.list_rules(session, user_id, status, limit, offset)


@router.get("/rules/{rule_id}")
async def get_rule(rule_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return recurring_to_out(await recurring_repo.get_rule(session, user_id, rule_id))


@router.patch("/rules/{rule_id}")
async def update_rule(rule_id: IdInt, patch: dict, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    rule = await recurring_repo.get_rule(session, user_id, rule_id)
    merged = {
        "frequency": rule.frequency,
        "day_of_week": rule.day_of_week,
        "day_of_month": rule.day_of_month,
        "month_of_year": rule.month_of_year,
        **{k: v for k, v in patch.items() if v is not None},
    }
    recurring_service.validate_recurring_schedule(merged)
    for k, v in patch.items():
        if hasattr(rule, k) and v is not None:
            setattr(rule, k, v)
    await session.commit()
    return recurring_to_out(rule)


@router.post("/rules/{rule_id}/pause")
async def pause(rule_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    rule = await recurring_repo.get_rule(session, user_id, rule_id)
    rule.status = "paused"
    await session.commit()
    return recurring_to_out(rule)


@router.post("/rules/{rule_id}/resume")
async def resume(rule_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    rule = await recurring_repo.get_rule(session, user_id, rule_id)
    rule.status = "active"
    today = recurring_service.today_in_rule_tz(rule)
    if rule.next_run_date < today:
        rule.next_run_date = recurring_service.first_occurrence(rule, today)
    await session.commit()
    return recurring_to_out(rule)


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    rule = await recurring_repo.soft_delete(session, user_id, rule_id)
    out = recurring_to_out(rule, deleted=True)
    await session.commit()
    return out
