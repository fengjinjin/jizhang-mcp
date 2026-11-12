import subprocess
import sys
import tempfile
from pathlib import Path


def test_wheel_build_succeeds():
    """回归：wheel 不得出现 duplicate jizhang_mcp/__init__.py（Hatch force-include 冲突）。"""
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-q", "build"],
        check=True,
        capture_output=True,
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, "-m", "build", "--wheel", "-o", tmp, str(root)],
            capture_output=True,
            text=True,
            cwd=root,
            timeout=180,
        )
    assert result.returncode == 0, result.stderr or result.stdout


def test_psycopg2_available_for_alembic_cli():
    import psycopg2  # noqa: F401 — Docker/生产 Alembic 同步方言回退
