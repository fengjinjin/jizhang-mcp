#!/usr/bin/env bash
# 生产 Docker 同款：隔离构建 wheel → 安装 → 导入与 create_app 冒烟（不发网络请求）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> 构建 wheel"
python3 -m pip install -q build
python3 -m build --wheel -o "$TMP/dist" "$ROOT"

WHEEL="$(ls -1 "$TMP/dist"/*.whl | head -1)"
echo "==> 安装 $WHEEL"
VENVDIR="$TMP/venv"
python3 -m venv "$VENVDIR" 2>/dev/null || {
  python3 -m pip install -q virtualenv
  python3 -m virtualenv "$VENVDIR"
}
# shellcheck source=/dev/null
source "$VENVDIR/bin/activate"
pip install -q --upgrade pip
pip install -q "$WHEEL"

echo "==> 解析依赖（与生产 pip install . 一致）"
pip show fastmcp mcp | sed -n '1,20p'

echo "==> 导入与 create_app 冒烟"
export JIZHANG_DATABASE_URL="${JIZHANG_DATABASE_URL:-postgresql+asyncpg://jizhang:jizhang@127.0.0.1:5432/jizhang}"
export JIZHANG_JWT_SECRET="${JIZHANG_JWT_SECRET:-build-verify-jwt-secret-min-16-chars}"

python3 <<'PY'
import jizhang_mcp
from jizhang_mcp.app import create_app

assert jizhang_mcp.__version__
app = create_app()
assert app.title == "jizhang"
print("smoke_ok", jizhang_mcp.__version__)
PY

echo "==> verify_build 通过"
