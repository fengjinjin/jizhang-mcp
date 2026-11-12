# jizhang-mcp

jizhang 公开后端：FastAPI REST + FastMCP 单进程（`workers=1`），PostgreSQL 账本存储，配套 Skill。

## 本地开发

依赖：Python 3.12+、PostgreSQL 16+（可用 `docker compose` 仅起库）。

```bash
cp .env.example .env
# 填写 JIZHANG_DATABASE_URL、JIZHANG_JWT_SECRET

docker compose up -d   # 本地开发用，默认用户/密码均为 jizhang，勿用于生产

pip install -e ".[dev]"
alembic upgrade head
uvicorn jizhang_mcp.app:create_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

stdio 调试（另开终端）：

```bash
export JIZHANG_TRANSPORT=stdio
export JIZHANG_API_KEY=jz_live_你的密钥
python -m jizhang_mcp
```

## 生产部署

- 使用仓库内 `Dockerfile` 构建镜像；连接**已存在的空库** `jizhang`（PostgreSQL 16/17），通过环境变量注入 `JIZHANG_DATABASE_URL` 与 `JIZHANG_JWT_SECRET`，不要把生产凭据写进仓库。
- 必须 `--workers 1`（暗号解锁与限流在进程内存）。

## 测试

```bash
pytest
```

## Skill

目录 `skills/jizhang/` 可拷贝到 Cursor / Claude 技能目录。
