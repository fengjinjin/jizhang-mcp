from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jizhang_mcp.api.error_handlers import register_error_handlers
from jizhang_mcp.api.openapi import mount_rest_openapi
from jizhang_mcp.api.routers import (
    api_keys,
    auth,
    categories,
    health,
    ledger,
    me,
    meta,
    recurring,
    stats,
    wishlist,
)


def register_rest_routes(app: FastAPI, settings) -> None:
    api = FastAPI(
        title="jizhang REST API",
        version="1.0.0",
        redirect_slashes=False,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    register_error_handlers(api)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )
    api.include_router(health.router, prefix="/v1")
    api.include_router(meta.router, prefix="/v1")
    api.include_router(auth.router, prefix="/v1")
    api.include_router(me.router, prefix="/v1")
    api.include_router(api_keys.router, prefix="/v1")
    api.include_router(categories.router, prefix="/v1")
    api.include_router(ledger.router, prefix="/v1")
    api.include_router(recurring.router, prefix="/v1")
    api.include_router(stats.router, prefix="/v1")
    api.include_router(wishlist.router, prefix="/v1")
    app.mount("/api", api)
    mount_rest_openapi(app, api, settings)
    app.include_router(health.live_router)
