from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.services import category_service
from jizhang_mcp.util.ids import IdInt, id_str

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
async def list_categories(
    direction: Literal["expense", "income"] | None = Query(default=None),
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await category_service.list_category_tree(session, user_id, direction)


class CategoryAddBody(BaseModel):
    direction: Literal["expense", "income"]
    name: str
    parent_id: IdInt | None = None
    parent_path: str | None = None


@router.post("")
async def add_category(body: CategoryAddBody, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    cat = await category_service.add_category(
        session, user_id, body.direction, body.name, body.parent_id, body.parent_path
    )
    await session.commit()
    path, _, _ = await category_service.path_for_node(session, cat)
    return {"id": id_str(cat.id), "category_path": path, "level": cat.level, "is_system": cat.is_system}


@router.delete("/{category_id}")
async def delete_category(category_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    await category_service.delete_category(session, user_id, category_id)
    await session.commit()
    return {"deleted": True, "category_id": id_str(category_id)}
