import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from jizhang_mcp.exceptions import JizhangError

logger = logging.getLogger("jizhang")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(JizhangError)
    async def handle_domain_error(_request: Request, exc: JizhangError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content={"error": exc.to_payload()})

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "参数不合法",
                    "hint": "对照工具 schema 检查必填项和枚举值，不要编造字段",
                    "retryable": False,
                    "requires_user_input": False,
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unknown_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error")
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "服务内部错误",
                    "hint": "请稍后再试，不要把这次失败当成功",
                    "retryable": False,
                    "requires_user_input": False,
                }
            },
        )
