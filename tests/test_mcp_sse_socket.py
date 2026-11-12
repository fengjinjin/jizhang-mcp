"""默认 SSE 模式端到端：真实 TCP + uvicorn（非 ASGITransport / 非 FASTMCP_JSON_RESPONSE）。"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

MODERN = "2026-07-28"
MCP_ACCEPT = "application/json, text/event-stream"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _parse_sse_messages(raw: str) -> list[dict]:
    out: list[dict] = []
    data_lines: list[str] = []
    for line in raw.splitlines():
        if line.startswith("data:"):
            data_lines.append(line[5:].strip())
        elif line == "" and data_lines:
            out.append(json.loads("\n".join(data_lines)))
            data_lines = []
    return out


def _post_sse(client: httpx.Client, body: dict, headers: dict[str, str], timeout: float = 10.0) -> tuple[int, str, list[dict]]:
    hdrs = {
        "Content-Type": "application/json",
        "Accept": MCP_ACCEPT,
        **headers,
    }
    with client.stream("POST", "/mcp", json=body, headers=hdrs, timeout=timeout) as resp:
        text = resp.read().decode()
        return resp.status_code, resp.headers.get("content-type", ""), _parse_sse_messages(text)


def _post_mcp_json(client: httpx.Client, body: dict, headers: dict[str, str], timeout: float = 10.0) -> dict:
    hdrs = {
        "Content-Type": "application/json",
        "Accept": MCP_ACCEPT,
        **headers,
    }
    with client.stream("POST", "/mcp", json=body, headers=hdrs, timeout=timeout) as resp:
        raw = resp.read().decode()
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            msgs = _parse_sse_messages(raw)
            assert msgs, raw[:300]
            return msgs[0]
        return json.loads(raw)


@pytest.fixture(scope="module")
def sse_uvicorn_server():
    os.environ.pop("FASTMCP_JSON_RESPONSE", None)
    from jizhang_mcp.config import get_settings

    get_settings.cache_clear()
    port = _free_port()
    root = Path(__file__).resolve().parents[1]
    env = {
        **os.environ,
        "JIZHANG_DATABASE_URL": os.environ.get(
            "JIZHANG_DATABASE_URL",
            "postgresql+asyncpg://jizhang:jizhang@127.0.0.1:5432/jizhang",
        ),
        "JIZHANG_JWT_SECRET": os.environ.get("JIZHANG_JWT_SECRET", "test-jwt-secret-32chars-minimum"),
        "JIZHANG_REGISTER_RATE_PER_HOUR": "1000",
    }
    env.pop("FASTMCP_JSON_RESPONSE", None)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "jizhang_mcp.app:create_app",
            "--factory",
            "--host",
            "127.0.0.1",
            f"--port",
            str(port),
            "--workers",
            "1",
        ],
        cwd=root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    base = f"http://127.0.0.1:{port}"
    deadline = time.time() + 25
    ready = False
    while time.time() < deadline:
        try:
            r = httpx.get(f"{base}/healthz", timeout=1.0)
            if r.status_code == 200:
                ready = True
                break
        except httpx.HTTPError:
            pass
        if proc.poll() is not None:
            break
        time.sleep(0.15)
    if not ready:
        proc.kill()
        out, err = proc.communicate(timeout=3)
        raise RuntimeError(f"uvicorn failed to start: {err.decode()[:500]} {out.decode()[:200]}")
    yield base, proc
    proc.send_signal(signal.SIGINT)
    try:
        proc.wait(timeout=8)
    except subprocess.TimeoutExpired:
        proc.kill()
    os.environ.setdefault("FASTMCP_JSON_RESPONSE", "true")
    get_settings.cache_clear()


@pytest.fixture
def sse_client(sse_uvicorn_server):
    base, _ = sse_uvicorn_server
    with httpx.Client(base_url=base, timeout=15.0) as client:
        yield client


@pytest_asyncio.fixture
async def sse_user(api_client):
    import secrets

    uname = "sse" + secrets.token_hex(4)
    reg = await api_client.post("/api/v1/auth/register", json={"username": uname, "password": "Password123!"})
    assert reg.status_code == 201
    token = reg.json()["token"]
    key_resp = await api_client.post(
        "/api/v1/api-keys",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "sse-test"},
    )
    assert key_resp.status_code == 201
    return key_resp.json()["plaintext"]


def test_legacy_initialize_sse(sse_client):
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "socket-test", "version": "1"},
        },
    }
    status, ctype, msgs = _post_sse(sse_client, init, {})
    assert status == 200
    assert "text/event-stream" in ctype
    assert msgs, "expected SSE message event"
    assert msgs[0]["result"]["serverInfo"]["version"] == "1.0.0"


def test_modern_initialize_sse(sse_client):
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MODERN,
            "capabilities": {},
            "clientInfo": {"name": "socket-test", "version": "1"},
        },
    }
    status, _, msgs = _post_sse(sse_client, init, {"MCP-Protocol-Version": MODERN})
    assert status == 200 and msgs
    assert msgs[0]["result"]["protocolVersion"] == MODERN


def test_sse_tools_list_and_call_bearer(sse_client, sse_user):
    api_key = sse_user
    init = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MODERN,
            "capabilities": {},
            "clientInfo": {"name": "socket-test", "version": "1"},
        },
    }
    _post_sse(sse_client, init, {"Authorization": f"Bearer {api_key}", "MCP-Protocol-Version": MODERN})

    list_body = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}
    list_resp = _post_mcp_json(
        sse_client,
        list_body,
        {"Authorization": f"Bearer {api_key}", "MCP-Protocol-Version": MODERN},
    )
    assert "error" not in list_resp
    assert list_resp["result"]["tools"]

    call_resp = _post_mcp_json(
        sse_client,
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "auth_status", "arguments": {}},
        },
        {"Authorization": f"Bearer {api_key}", "MCP-Protocol-Version": MODERN},
    )
    assert "error" not in call_resp
    assert call_resp["result"]["structuredContent"]["authenticated"] is True


def test_mcp_mount_unaffected_with_root_path(sse_client):
    r = sse_client.get("/mcp", headers={"Accept": MCP_ACCEPT})
    assert r.status_code != 404
