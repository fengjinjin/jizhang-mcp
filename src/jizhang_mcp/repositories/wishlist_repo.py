from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.wishlist import WishlistItem
from jizhang_mcp.exceptions import WishlistItemNotFoundError
from jizhang_mcp.util.time_util import utcnow


def _active(user_id: int):
    return and_(WishlistItem.user_id == user_id, WishlistItem.deleted_at.is_(None))


async def get_item(session: AsyncSession, user_id: int, item_id: int) -> WishlistItem:
    row = await session.scalar(select(WishlistItem).where(_active(user_id), WishlistItem.id == item_id))
    if row is None:
        raise WishlistItemNotFoundError("愿望清单项不存在")
    return row


async def list_items(
    session: AsyncSession, user_id: int, status: str | None, limit: int, offset: int
) -> tuple[list[WishlistItem], int]:
    cond = [_active(user_id)]
    if status:
        cond.append(WishlistItem.status == status)
    where = and_(*cond)
    total = int(await session.scalar(select(func.count()).select_from(WishlistItem).where(where)) or 0)
    stmt = (
        select(WishlistItem)
        .where(where)
        .order_by(
            WishlistItem.status != "wanted",
            WishlistItem.planned_at.is_(None),
            WishlistItem.created_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )
    return list((await session.scalars(stmt)).all()), total


async def soft_delete(session: AsyncSession, user_id: int, item_id: int) -> WishlistItem:
    row = await get_item(session, user_id, item_id)
    row.deleted_at = utcnow()
    return row
