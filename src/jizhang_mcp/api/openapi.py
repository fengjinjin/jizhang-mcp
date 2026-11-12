from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import JSONResponse

from jizhang_mcp.config import Settings


def mount_rest_openapi(parent: FastAPI, rest_app: FastAPI, settings: Settings) -> None:
    """在父应用暴露 REST 子应用的 OpenAPI（/docs、/openapi.json）。"""

    root = settings.root_path_normalized
    openapi_path = "/openapi.json"
    docs_path = "/docs"
    if root:
        openapi_path = f"{root}{openapi_path}"
        docs_path = f"{root}{docs_path}"

    @parent.get("/openapi.json", include_in_schema=False)
    async def rest_openapi():
        schema = rest_app.openapi()
        schema["servers"] = [{"url": settings.openapi_server_url}]
        return JSONResponse(schema)

    @parent.get("/docs", include_in_schema=False)
    async def rest_docs():
        return get_swagger_ui_html(openapi_url=openapi_path, title=f"{rest_app.title} — Docs")
