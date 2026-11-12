import re
from typing import Annotated

from pydantic import BeforeValidator, WithJsonSchema

_ID_STR = re.compile(r"^[1-9][0-9]*$")


def parse_id(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("id 不合法")
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("id 必须为正整数")
        return value
    if isinstance(value, str) and _ID_STR.fullmatch(value):
        return int(value)
    raise ValueError("id 必须是正整数或十进制数字字符串")


def id_str(value: int) -> str:
    return str(value)


IdInt = Annotated[
    int,
    BeforeValidator(parse_id),
    WithJsonSchema(
        {
            "oneOf": [
                {"type": "integer", "minimum": 1},
                {"type": "string", "pattern": r"^[1-9][0-9]*$"},
            ]
        }
    ),
]
