from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.db.models.category import Category
from jizhang_mcp.exceptions import CategoryNotFoundError, CategoryNameTakenError


async def list_active_categories(session: AsyncSession, user_id: int, direction: str | None = None) -> list[Category]:
    cond = [Category.user_id == user_id, Category.deleted_at.is_(None)]
    if direction:
        cond.append(Category.direction == direction)
    stmt = select(Category).where(and_(*cond)).order_by(Category.sort_order, Category.id)
    return list((await session.scalars(stmt)).all())


async def get_category(session: AsyncSession, user_id: int, category_id: int) -> Category:
    row = await session.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.user_id == user_id,
            Category.deleted_at.is_(None),
        )
    )
    if row is None:
        raise CategoryNotFoundError("类目不存在")
    return row


async def find_root_by_name(session: AsyncSession, user_id: int, direction: str, name: str) -> Category | None:
    return await session.scalar(
        select(Category).where(
            Category.user_id == user_id,
            Category.direction == direction,
            Category.parent_id.is_(None),
            Category.deleted_at.is_(None),
            func.lower(Category.name) == name.lower(),
        )
    )


async def find_child(session: AsyncSession, user_id: int, parent_id: int, name: str) -> Category | None:
    return await session.scalar(
        select(Category).where(
            Category.user_id == user_id,
            Category.parent_id == parent_id,
            Category.deleted_at.is_(None),
            func.lower(Category.name) == name.lower(),
        )
    )


async def name_taken_sibling(
    session: AsyncSession, user_id: int, direction: str, name: str, parent_id: int | None
) -> bool:
    cond = [
        Category.user_id == user_id,
        Category.direction == direction,
        Category.deleted_at.is_(None),
        func.lower(Category.name) == name.lower(),
    ]
    if parent_id is None:
        cond.append(Category.parent_id.is_(None))
    else:
        cond.append(Category.parent_id == parent_id)
    row = await session.scalar(select(Category.id).where(and_(*cond)).limit(1))
    return row is not None


async def insert_category(
    session: AsyncSession,
    user_id: int,
    direction: str,
    name: str,
    level: int,
    parent_id: int | None,
    is_system: bool,
    sort_order: int,
) -> Category:
    if await name_taken_sibling(session, user_id, direction, name, parent_id):
        raise CategoryNameTakenError("同级已有同名类目")
    cat = Category(
        user_id=user_id,
        direction=direction,
        name=name,
        level=level,
        parent_id=parent_id,
        is_system=is_system,
        sort_order=sort_order,
    )
    session.add(cat)
    await session.flush()
    return cat


async def soft_delete_category_tree(session: AsyncSession, user_id: int, root: Category) -> None:
    from jizhang_mcp.util.time_util import utcnow

    now = utcnow()
    all_cats = await list_active_categories(session, user_id, root.direction)
    by_parent: dict[int | None, list[Category]] = {}
    for c in all_cats:
        by_parent.setdefault(c.parent_id, []).append(c)

    stack = [root.id]
    to_delete: list[int] = []
    while stack:
        cid = stack.pop()
        to_delete.append(cid)
        for child in by_parent.get(cid, []):
            stack.append(child.id)

    for cid in to_delete:
        cat = await session.get(Category, cid)
        if cat and cat.deleted_at is None:
            cat.deleted_at = now


async def find_paths_for_bare_name(session: AsyncSession, user_id: int, direction: str, bare: str) -> list[str]:
    """裸词命中多条叶子/二级时收集路径候选。"""
    cats = await list_active_categories(session, user_id, direction)
    by_id = {c.id: c for c in cats}
    candidates: list[str] = []

    def build_path(node: Category) -> str:
        parts = [node.name]
        p = node.parent_id
        while p:
            parent = by_id.get(p)
            if not parent:
                break
            parts.insert(0, parent.name)
            p = parent.parent_id
        return "-".join(parts)

    for c in cats:
        if c.name.lower() == bare.lower():
            candidates.append(build_path(c))
    return candidates[:5]
