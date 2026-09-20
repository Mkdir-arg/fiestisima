"""Apply pending SQL migrations in order. Idempotent; safe to run on every deploy."""
import asyncio, os, re, sys
from pathlib import Path
import psycopg

# psycopg's async mode cannot run on Windows' default ProactorEventLoop;
# it needs a selector-based loop. This is a no-op on Linux/macOS, which
# already default to a selector loop (Railway's containers included).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")

async def main() -> int:
    url = os.environ["DATABASE_URL"]
    files = sorted(p for p in MIGRATIONS.iterdir() if NAME.match(p.name))
    async with await psycopg.AsyncConnection.connect(url) as conn:
        await conn.execute(
            "create table if not exists schema_migrations "
            "(version text primary key, applied_at timestamptz not null default now())"
        )
        await conn.commit()
        cur = await conn.execute("select version from schema_migrations")
        applied = {r[0] for r in await cur.fetchall()}
        for path in files:
            version = NAME.match(path.name).group(1)
            if version in applied:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "insert into schema_migrations (version) values (%s)", (version,)
                )
            print(f"applied {path.name}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
