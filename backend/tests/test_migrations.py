"""TASK-0103 — тест миграций Alembic: upgrade head и downgrade base
проходят без ошибок (запуск в подпроцессе, чтобы не мешать event loop тестов)."""
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent


def _alembic(*args):
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND, capture_output=True, text=True,
    )


def test_migration_upgrade_then_downgrade():
    up = _alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
    down = _alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr
