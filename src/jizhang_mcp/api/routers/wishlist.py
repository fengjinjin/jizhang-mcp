from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.api.deps import current_user_id, get_db
from jizhang_mcp.services import wishlist_service
from jizhang_mcp.util.ids import IdInt

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.post("/items", status_code=201)
async def add_item(body: dict, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    title = body["title"]
    fields = {k: v for k, v in body.items() if k != "title"}
    return await wishlist_service.add_item(session, user_id, title, **fields)


@router.get("/items")
async def list_items(
    user_id: int = Depends(current_user_id),
    session: AsyncSession = Depends(get_db),
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return await wishlist_service.list_items(session, user_id, status, limit, offset)


@router.get("/items/{item_id}")
async def get_item(item_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await wishlist_service.get_item(session, user_id, item_id)


@router.patch("/items/{item_id}")
async def update_item(item_id: IdInt, patch: dict, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await wishlist_service.update_item(session, user_id, item_id, patch)


@router.delete("/items/{item_id}")
async def delete_item(item_id: IdInt, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await wishlist_service.delete_item(session, user_id, item_id)


@router.post("/evaluate")
async def evaluate(body: dict, user_id: int = Depends(current_user_id), session: AsyncSession = Depends(get_db)):
    return await wishlist_service.evaluate(session, user_id, **body)
