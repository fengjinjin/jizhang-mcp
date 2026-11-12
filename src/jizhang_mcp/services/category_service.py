from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jizhang_mcp.constants import (
    DEFAULT_EXPENSE_PRIMARIES,
    DEFAULT_INCOME_PRIMARIES,
    EXPENSE_ALIASES,
    INCOME_ALIASES,
)
from jizhang_mcp.db.models.category import Category
from jizhang_mcp.exceptions import (
    CategoryNotFoundError,
    SystemCategoryProtectedError,
    ValidationAppError,
)
from jizhang_mcp.repositories import category_repo


def build_path(names: list[str]) -> str:
    return "-".join(names)


async def path_for_node(session: AsyncSession, node: Category) -> tuple[str, str, str | None]:
    names: list[str] = [node.name]
    p = node.parent_id
    while p:
        parent = await session.get(Category, p)
        if not parent:
            break
        names.insert(0, parent.name)
        p = parent.parent_id
    path = build_path(names)
    primary = names[0]
    secondary = names[1] if len(names) > 1 else None
    return path, primary, secondary


async def root_of(session: AsyncSession, node: Category) -> Category:
    cur = node
    while cur.parent_id:
        cur = await session.get(Category, cur.parent_id)
        if cur is None:
            raise CategoryNotFoundError("类目不存在")
    return cur


async def seed_default_categories(session: AsyncSession, user_id: int) -> None:
    for i, name in enumerate(DEFAULT_EXPENSE_PRIMARIES):
        if await category_repo.find_root_by_name(session, user_id, "expense", name) is None:
            await category_repo.insert_category(
                session, user_id, "expense", name, 1, None, True, i
            )
    for i, name in enumerate(DEFAULT_INCOME_PRIMARIES):
        if await category_repo.find_root_by_name(session, user_id, "income", name) is None:
            await category_repo.insert_category(
                session, user_id, "income", name, 1, None, True, i
            )


@dataclass
class ResolveResult:
    category: Category
    root: Category
    path: str
    primary: str
    secondary: str | None
    resolution: str


async def _ensure_child(session: AsyncSession, user_id: int, direction: str, parent: Category, name: str) -> Category:
    child = await category_repo.find_child(session, user_id, parent.id, name)
    if child:
        return child
    if parent.level >= 3:
        raise ValidationAppError("类目最多支持三级")
    return await category_repo.insert_category(
        session, user_id, direction, name, parent.level + 1, parent.id, False, 0
    )


async def resolve_or_create(session: AsyncSession, user_id: int, direction: str, raw: str) -> ResolveResult:
    raw = (raw or "").strip()
    if not raw:
        raise ValidationAppError("类目不能为空")

    if "-" in raw:
        parts = [p.strip() for p in raw.split("-")]
        if len(parts) > 3 or any(not p for p in parts):
            raise ValidationAppError("类目路径不合法")
        root_name = parts[0]
        root = await category_repo.find_root_by_name(session, user_id, direction, root_name)
        if root is None:
            raise ValidationAppError(
                "一级类目不存在，请先用已有大类或 category_add 建自定义一级",
            )
        node = root
        resolution = "exact"
        for seg in parts[1:]:
            node = await _ensure_child(session, user_id, direction, node, seg)
        path, primary, secondary = await path_for_node(session, node)
        root_cat = await root_of(session, node)
        return ResolveResult(node, root_cat, path, primary, secondary, resolution)

    root_exact = await category_repo.find_root_by_name(session, user_id, direction, raw)
    if root_exact:
        path, primary, secondary = await path_for_node(session, root_exact)
        return ResolveResult(root_exact, root_exact, path, primary, secondary, "exact")

    paths = await category_repo.find_paths_for_bare_name(session, user_id, direction, raw)
    if len(paths) > 1:
        raise ValidationAppError(
            "类目存在多个候选，请指定完整路径",
            candidates=paths,
            hint="从 candidates 里选一条路径再写",
        )
    if len(paths) == 1:
        return await resolve_or_create(session, user_id, direction, paths[0])

    aliases = EXPENSE_ALIASES if direction == "expense" else INCOME_ALIASES
    if raw in aliases:
        p_name, c_name = aliases[raw]
        root = await category_repo.find_root_by_name(session, user_id, direction, p_name)
        if root is None:
            raise ValidationAppError("默认一级缺失，请联系服务端")
        if c_name:
            leaf = await _ensure_child(session, user_id, direction, root, c_name)
        else:
            leaf = root
        path, primary, secondary = await path_for_node(session, leaf)
        root_cat = await root_of(session, leaf)
        return ResolveResult(leaf, root_cat, path, primary, secondary, "alias")

    other = await category_repo.find_root_by_name(session, user_id, direction, "其他")
    if other is None:
        raise ValidationAppError("系统类目「其他」不存在")
    leaf = await _ensure_child(session, user_id, direction, other, raw)
    path, primary, secondary = await path_for_node(session, leaf)
    return ResolveResult(leaf, other, path, primary, secondary, "fallback_other")


async def resolve_category_filter(
    session: AsyncSession, user_id: int, direction: str, raw: str
) -> Category | None:
    raw = raw.strip()
    if not raw:
        return None
    if "-" in raw:
        parts = raw.split("-")
        root = await category_repo.find_root_by_name(session, user_id, direction, parts[0])
        if not root:
            return None
        node = root
        for seg in parts[1:]:
            node = await category_repo.find_child(session, user_id, node.id, seg)
            if not node:
                return None
        return node
    return await category_repo.find_root_by_name(session, user_id, direction, raw)


async def list_category_tree(session: AsyncSession, user_id: int, direction: str | None) -> dict:
    from jizhang_mcp.schemas.common import CategoryTreeNode
    from jizhang_mcp.util.ids import id_str

    dirs = [direction] if direction else ["expense", "income"]
    out: dict = {}
    for d in dirs:
        cats = await category_repo.list_active_categories(session, user_id, d)
        nodes = {
            c.id: CategoryTreeNode(
                id=id_str(c.id),
                name=c.name,
                level=c.level,
                is_system=c.is_system,
                sort_order=c.sort_order,
                children=[],
            )
            for c in cats
        }
        roots: list[CategoryTreeNode] = []
        by_id = {c.id: c for c in cats}
        for c in cats:
            node = nodes[c.id]
            if c.parent_id and c.parent_id in nodes:
                nodes[c.parent_id].children.append(node)
            elif c.parent_id is None:
                roots.append(node)
        out[d] = roots
    if direction:
        return {direction: out[direction]}
    return out


async def add_category(
    session: AsyncSession,
    user_id: int,
    direction: str,
    name: str,
    parent_id: int | None,
    parent_path: str | None,
) -> Category:
    parent: Category | None = None
    if parent_id is not None:
        parent = await category_repo.get_category(session, user_id, parent_id)
    elif parent_path:
        parent = await resolve_category_filter(session, user_id, direction, parent_path)
        if parent is None:
            raise CategoryNotFoundError("父类目不存在")
    if parent is None:
        return await category_repo.insert_category(session, user_id, direction, name, 1, None, False, 0)
    if parent.level >= 3:
        raise ValidationAppError("类目最多支持三级")
    return await category_repo.insert_category(
        session, user_id, direction, name, parent.level + 1, parent.id, False, 0
    )


async def delete_category(session: AsyncSession, user_id: int, category_id: int) -> Category:
    cat = await category_repo.get_category(session, user_id, category_id)
    if cat.is_system:
        raise SystemCategoryProtectedError("系统类目不可删除")
    await category_repo.soft_delete_category_tree(session, user_id, cat)
    return cat
