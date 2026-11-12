from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JIZHANG_", env_file=".env", extra="ignore")

    env: Literal["dev", "prod"] = "dev"
    host: str = "127.0.0.1"
    port: int = 8000
    transport: Literal["http", "stdio"] = "http"
    database_url: str = Field(..., description="asyncpg URL")
    jwt_secret: str = Field(..., min_length=16)
    jwt_expire_minutes: int = 10080
    cors_origins: str = "http://127.0.0.1:5173"
    public_mcp_url: str = "http://127.0.0.1:8000/mcp"
    asgi_root_path: str = ""
    public_api_base: str = ""
    timezone: str = "Asia/Shanghai"
    passphrase_ttl_seconds: int = 7200
    auth_max_failures: int = 5
    auth_lockout_seconds: int = 300
    register_rate_per_hour: int = 10
    trusted_proxy_hops: int = 0
    api_key_max_active: int = 10
    scheduler_interval_seconds: int = 60
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def root_path_normalized(self) -> str:
        p = (self.asgi_root_path or "").strip().rstrip("/")
        if p and not p.startswith("/"):
            p = f"/{p}"
        return p

    @property
    def openapi_server_url(self) -> str:
        if self.public_api_base.strip():
            return self.public_api_base.strip().rstrip("/")
        root = self.root_path_normalized
        return f"{root}/api/v1" if root else "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
