import logging
import os
import sys

import uvicorn

from jizhang_mcp.config import get_settings


def main() -> None:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
    if settings.transport == "stdio":
        from jizhang_mcp.db import init_engine
        from jizhang_mcp.mcp_server import mcp

        async def _boot():
            await init_engine()
            raw = os.environ.get("JIZHANG_API_KEY")
            if raw:
                from jizhang_mcp.db.engine import get_session_factory
                from jizhang_mcp.repositories import api_key_repo
                from jizhang_mcp.services.recurring_service import settle_due_rules

                factory = get_session_factory()
                async with factory() as session:
                    key = await api_key_repo.get_active_key_by_plaintext(session, raw)
                    await settle_due_rules(session, user_id=key.user_id)

        import asyncio

        asyncio.run(_boot())
        mcp.run(transport="stdio")
        return
    uvicorn.run(
        "jizhang_mcp.app:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        workers=1,
    )


if __name__ == "__main__":
    if sys.stderr:
        pass
    main()
