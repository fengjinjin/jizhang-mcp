import re

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from jizhang_mcp.exceptions import ValidationAppError

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2, hash_len=32, salt_len=16)

_USERNAME_RE = re.compile(r"^[\w\u4e00-\u9fff]{3,32}$", re.UNICODE)


def hash_password(password: str) -> str:
    validate_password(password)
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def validate_password(password: str) -> None:
    if not (8 <= len(password) <= 128):
        raise ValidationAppError("密码长度须在 8～128 之间")


def validate_username(username: str) -> str:
    username = username.strip()
    if username != username.strip():
        raise ValidationAppError("用户名首尾不能有空格")
    if not _USERNAME_RE.fullmatch(username):
        raise ValidationAppError("用户名长度 3～32，仅字母数字下划线中文")
    return username


def validate_passphrase(passphrase: str) -> None:
    if not (1 <= len(passphrase) <= 30):
        raise ValidationAppError("暗号长度须在 1～30 之间")
