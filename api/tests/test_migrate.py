"""Exercises the migration runner itself: applying twice is idempotent."""
import os
import subprocess
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parent.parent


def _run_migrate(db_url: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, str(API_DIR / "scripts" / "migrate.py")],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


async def test_running_the_runner_twice_is_idempotent(db_url, owner):
    first = _run_migrate(db_url)
    assert first.returncode == 0, f"first run failed: {first.stderr}"

    second = _run_migrate(db_url)
    assert second.returncode == 0, f"second run failed: {second.stderr}"
    assert second.stdout.strip() == "", (
        f"second run should apply nothing, printed: {second.stdout!r}"
    )

    cur = await owner.execute("select version from schema_migrations order by version")
    rows = await cur.fetchall()
    assert [r[0] for r in rows] == ["0001", "0002", "0003"]
