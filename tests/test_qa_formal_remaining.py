import json
import os

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from jizhang_mcp.config import get_settings
from jizhang_mcp.services.stats_service import _infer_default_compare_mode
from jizhang_mcp.util.time_util import default_stats_range, get_tz, month_start_local, now_local, parse_occurred_at
from datetime import datetime


@pytest.mark.asyncio
async def test_ambiguous_bare_category_rejects(user_with_key, app_db, api_client):
    token = user_with_key["token"]
    await api_client.post(
        "/api/v1/categories",
        headers={"Authorization": f"Bearer {token}"},
        json={"direction": "expense", "name": "出行"},
    )
    for parent in ("交通", "出行"):
        r = await api_client.post(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token}"},
            json={"direction": "expense", "name": "打车", "parent_path": parent},
        )
        assert r.status_code in (200, 201), r.text
    resp = await api_client.post(
        "/api/v1/ledger/entries",
        headers={"Authorization": f"Bearer {token}"},
        json={"direction": "expense", "amount": 10, "category": "打车"},
    )
    assert resp.status_code == 400
    body = resp.json()["error"]
    assert body["code"] == "validation_error"
    assert len(body.get("candidates", [])) >= 2


def test_default_compare_mode_month_and_year():
    now = now_local()
    ms = month_start_local(now.date())
    assert _infer_default_compare_mode(ms, now) == "prev_month_same_span"
    ys = datetime(now.year, 1, 1, tzinfo=get_tz())
    if now.month == 1:
        pytest.skip("年初与月初同日，无法区分")
    assert _infer_default_compare_mode(ys, now) == "prev_year_same_span"


@pytest.mark.asyncio
async def test_invalid_occurred_at_not_500(api_client, user_with_key):
    token = user_with_key["token"]
    resp = await api_client.post(
        "/api/v1/ledger/entries",
        headers={"Authorization": f"Bearer {token}"},
        json={"direction": "expense", "amount": 1, "category": "餐饮", "occurred_at": "1999-99-99"},
    )
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "validation_error"


@pytest.mark.asyncio
async def test_batch_invalid_row_index(user_with_key, app_db):
    os.environ["JIZHANG_API_KEY"] = user_with_key["api_key"]
    from jizhang_mcp.mcp_server import mcp

    async with Client(mcp) as client:
        with pytest.raises(ToolError) as err:
            await client.call_tool(
                "ledger_add_batch",
                {
                    "entries": [
                        {"direction": "expense", "amount": 1, "category": "餐饮"},
                        {"direction": "expense", "amount": 0, "category": "餐饮"},
                    ]
                },
            )
        payload = json.loads(str(err.value))
        assert payload.get("index") == 1


@pytest.mark.asyncio
async def test_register_rate_limit_by_ip(api_client, app_db, monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("JIZHANG_REGISTER_RATE_PER_HOUR", "2")
    monkeypatch.setenv("JIZHANG_TRUSTED_PROXY_HOPS", "1")
    get_settings.cache_clear()
    ip = "198.51.100.7"
    for i in range(2):
        r = await api_client.post(
            "/api/v1/auth/register",
            json={"username": f"rl{i}", "password": "Password123!"},
            headers={"X-Forwarded-For": f"203.0.113.1, {ip}"},
        )
        assert r.status_code == 201
    blocked = await api_client.post(
        "/api/v1/auth/register",
        json={"username": "rlblock", "password": "Password123!"},
        headers={"X-Forwarded-For": f"203.0.113.1, {ip}"},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "auth_rate_limited"


@pytest.mark.asyncio
async def test_openapi_lists_rest_not_only_healthz(api_client, app_db, monkeypatch):
    from jizhang_mcp.api.openapi import rest_operation_url

    monkeypatch.setenv("JIZHANG_ASGI_ROOT_PATH", "/jizhangapi")
    monkeypatch.setenv(
        "JIZHANG_PUBLIC_API_BASE",
        "https://yunqingkeji.site/jizhangapi/api",
    )
    get_settings.cache_clear()
    from jizhang_mcp.app import create_app

    app = create_app()
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        spec = await c.get("/openapi.json")
        assert spec.status_code == 200
        data = spec.json()
        server = data["servers"][0]["url"]
        assert server == "https://yunqingkeji.site/jizhangapi/api"
        assert not server.endswith("/v1")
        paths = data.get("paths") or {}
        assert "/v1/ledger/entries" in paths
        assert "/v1/auth/login" in paths
        assert "/healthz" not in paths
        login_url = rest_operation_url(server, "/v1/auth/login")
        ledger_url = rest_operation_url(server, "/v1/ledger/entries")
        assert login_url == "https://yunqingkeji.site/jizhangapi/api/v1/auth/login"
        assert ledger_url == "https://yunqingkeji.site/jizhangapi/api/v1/ledger/entries"
        assert "/v1/v1" not in login_url
        mcp = await c.get("/mcp")
        assert mcp.status_code != 404


def test_public_api_base_strips_trailing_v1_suffix(monkeypatch):
    from jizhang_mcp.config import get_settings

    monkeypatch.setenv("JIZHANG_PUBLIC_API_BASE", "https://yunqingkeji.site/jizhangapi/api/v1")
    get_settings.cache_clear()
    assert get_settings().rest_api_mount_base == "https://yunqingkeji.site/jizhangapi/api"


def test_server_json_present():
    import json
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "server.json"
    data = json.loads(p.read_text())
    assert data["name"] == "io.github.fengjinjin/jizhang"
    assert data["version"] == "1.0.0"
