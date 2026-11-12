from typing import Literal

from fastmcp import FastMCP

from jizhang_mcp.db.engine import get_session_factory
from jizhang_mcp.mcp_tools.boundary import mcp_boundary
from jizhang_mcp.security.principal import get_principal
from jizhang_mcp.services import category_service
from jizhang_mcp.util.ids import IdInt, id_str


def register(mcp: FastMCP) -> None:
    @mcp.tool(name="category_list", annotations={"readOnlyHint": True})
    @mcp_boundary
    async def category_list(direction: Literal["expense", "income"] | None = None):
        factory = get_session_factory()
        async with factory() as session:
            tree = await category_service.list_category_tree(session, get_principal().user_id, direction)
            return tree

    @mcp.tool(name="category_add", annotations={"readOnlyHint": False})
    @mcp_boundary
    async def category_add(
        direction: Literal["expense", "income"],
        name: str,
        parent_id: IdInt | None = None,
        parent_path: str | None = None,
    ):
        factory = get_session_factory()
        async with factory() as session:
            cat = await category_service.add_category(
                session, get_principal().user_id, direction, name, parent_id, parent_path
            )
            await session.commit()
            path, _, _ = await category_service.path_for_node(session, cat)
            return {
                "id": id_str(cat.id),
                "name": cat.name,
                "level": cat.level,
                "is_system": cat.is_system,
                "parent_id": id_str(cat.parent_id) if cat.parent_id else None,
                "category_path": path,
            }

    @mcp.tool(name="category_delete", annotations={"destructiveHint": True})
    @mcp_boundary
    async def category_delete(category_id: IdInt):
        factory = get_session_factory()
        async with factory() as session:
            await category_service.delete_category(session, get_principal().user_id, category_id)
            await session.commit()
            return {"deleted": True, "category_id": id_str(category_id)}
