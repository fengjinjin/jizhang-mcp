import json
import logging
from functools import wraps

from fastmcp.exceptions import ToolError

from jizhang_mcp.exceptions import JizhangError

logger = logging.getLogger("jizhang")


def mcp_boundary(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except JizhangError as exc:
            raise ToolError(json.dumps(exc.to_payload(), ensure_ascii=False)) from exc
        except Exception as exc:
            logger.exception("unhandled mcp error")
            raise ToolError(
                json.dumps(
                    {
                        "code": "internal_error",
                        "message": "服务内部错误",
                        "hint": "请稍后再试，不要把这次失败当成功",
                        "retryable": False,
                        "requires_user_input": False,
                    },
                    ensure_ascii=False,
                )
            ) from exc

    return wrapper
