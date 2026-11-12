from __future__ import annotations

from fastmcp.server.middleware import Middleware, MiddlewareContext
from jizhang_mcp import __version__ as PRODUCT_VERSION

MODERN_PROTOCOL_VERSION = "2026-07-28"


class McpProductProtocolMiddleware(Middleware):
    async def on_initialize(self, context: MiddlewareContext, call_next):
        result = await call_next(context)
        if result is None:
            return result
        message = context.message
        requested = None
        if message is not None and message.params is not None:
            requested = message.params.protocol_version
        if requested == MODERN_PROTOCOL_VERSION:
            updates: dict = {"protocol_version": MODERN_PROTOCOL_VERSION}
            if result.server_info is not None and result.server_info.version != PRODUCT_VERSION:
                updates["server_info"] = result.server_info.model_copy(
                    update={"version": PRODUCT_VERSION}
                )
            return result.model_copy(update=updates)
        if result.server_info is not None and result.server_info.version != PRODUCT_VERSION:
            return result.model_copy(
                update={
                    "server_info": result.server_info.model_copy(update={"version": PRODUCT_VERSION})
                }
            )
        return result
