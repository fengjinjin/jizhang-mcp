from dataclasses import dataclass
from contextvars import ContextVar


@dataclass(frozen=True)
class Principal:
    guest: bool = True
    user_id: int | None = None
    username: str | None = None
    tier: str | None = None
    api_key_id: int | None = None
    passphrase_enabled: bool = False
    session_key: str = "default"
    unlocked: bool = False

    @property
    def authenticated(self) -> bool:
        return self.user_id is not None


principal_ctx: ContextVar[Principal] = ContextVar("jizhang_principal", default=Principal())


def get_principal() -> Principal:
    return principal_ctx.get()


def set_principal(principal: Principal) -> None:
    principal_ctx.set(principal)
