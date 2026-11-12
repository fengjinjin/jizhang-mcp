import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

os.environ.setdefault(
    "JIZHANG_DATABASE_URL",
    "postgresql+asyncpg://jizhang:jizhang@127.0.0.1:5432/jizhang",
)
os.environ.setdefault("JIZHANG_JWT_SECRET", "test-jwt-secret-32chars-minimum")
os.environ["JIZHANG_REGISTER_RATE_PER_HOUR"] = "1000"


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    from jizhang_mcp.security.fail_store import fail_store
    from jizhang_mcp.security.unlock_store import unlock_store

    fail_store._auth.clear()
    fail_store._register_ip.clear()
    unlock_store._records.clear()
    os.environ.pop("JIZHANG_API_KEY", None)
    from jizhang_mcp.config import get_settings

    get_settings.cache_clear()
    yield
    os.environ.pop("JIZHANG_API_KEY", None)
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def app_db():
    from jizhang_mcp.db import dispose_engine, init_engine

    await init_engine()
    yield
    await dispose_engine()


@pytest_asyncio.fixture
async def db_session(app_db):
    from jizhang_mcp.db.engine import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        for table in (
            "idempotency_records",
            "ledger_entries",
            "recurring_rules",
            "wishlist_items",
            "categories",
            "api_keys",
            "users",
        ):
            await session.execute(text(f"TRUNCATE {table} RESTART IDENTITY CASCADE"))
        await session.commit()
        yield session


@pytest_asyncio.fixture
async def api_client(app_db):
    from jizhang_mcp.app import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest_asyncio.fixture
async def user_with_key(api_client):
    import secrets

    uname = "u" + secrets.token_hex(4)
    pw = "Password123!"
    reg = await api_client.post("/api/v1/auth/register", json={"username": uname, "password": pw})
    assert reg.status_code == 201
    token = reg.json()["token"]
    key_resp = await api_client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "test"},
    )
    assert key_resp.status_code == 201
    plaintext = key_resp.json()["plaintext"]
    assert plaintext.startswith("jz_live_")
    return {"username": uname, "password": pw, "token": token, "api_key": plaintext}
