from contextlib import asynccontextmanager

from fastapi import FastAPI

from jizhang_mcp.config import get_settings
from jizhang_mcp.db import dispose_engine, init_engine
from jizhang_mcp.mcp_server import mcp
from jizhang_mcp.middleware.mcp_protocol_asgi import McpProtocolAsgiMiddleware
from jizhang_mcp.services.scheduler import RecurringScheduler

mcp_app = McpProtocolAsgiMiddleware(
    mcp.http_app(
        path="/mcp",
        transport="streamable-http",
        stateless_http=True,
    )
)


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    await init_engine()
    settings = get_settings()
    scheduler = RecurringScheduler(interval_seconds=settings.scheduler_interval_seconds)
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await dispose_engine()


@asynccontextmanager
async def combined_lifespan(app: FastAPI):
    async with app_lifespan(app):
        async with mcp_app.lifespan(app):
            yield


def create_app() -> FastAPI:
    settings = get_settings()
    # JIZHANG_ASGI_ROOT_PATH 仅用于公网 OpenAPI 文档 URL；不可设 FastAPI.root_path，
    # 否则 nginx 剥 /jizhangapi 后容器内 /api/v1/* 会 404。
    app = FastAPI(
        title="jizhang",
        version="1.0.0",
        lifespan=combined_lifespan,
        redirect_slashes=False,
        docs_url=None,
        openapi_url=None,
    )
    from jizhang_mcp.api.error_handlers import register_error_handlers
    from jizhang_mcp.api.router import register_rest_routes

    register_error_handlers(app)
    register_rest_routes(app, settings)
    app.mount("/", mcp_app)
    return app
