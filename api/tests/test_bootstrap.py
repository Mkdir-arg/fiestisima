"""The out-of-band script that creates a business's first titolare.

It is the only way an account can exist without an invitation, it runs as
the database owner, and it is typed into a terminal once and then forgotten
- so it is exactly the kind of code that rots unnoticed. These tests pin
the two things an operator would only discover at the worst moment: that
the row it writes is a real titolare, and that the password it prints can
actually log in.
"""
import os
import subprocess
import sys
import uuid
from pathlib import Path

from app.security import verify_password

API_DIR = Path(__file__).resolve().parent.parent


def _run_bootstrap(db_url: str, name: str, email: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "DATABASE_URL": db_url}
    return subprocess.run(
        [sys.executable, str(API_DIR / "scripts" / "bootstrap.py"), name, email],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def _parse(stdout: str) -> dict[str, str]:
    out = {}
    for line in stdout.splitlines():
        key, _, value = line.partition("  ")
        out[key.strip()] = value.strip()
    return out


async def _cleanup(conn, email: str) -> None:
    cur = await conn.execute("select business_id from profiles where id = (select id from users where email = %s)", (email,))
    row = await cur.fetchone()
    if row:
        await conn.execute("delete from businesses where id = %s", (row[0],))
    await conn.execute("delete from users where email = %s", (email,))


async def test_bootstrap_creates_a_titolare_who_can_log_in(db_url, owner, client):
    suffix = uuid.uuid4().hex[:8]
    email = f"bootstrap-{suffix}@fiestisima-tests.invalid"
    name = f"Bootstrap business {suffix}"
    try:
        result = _run_bootstrap(db_url, name, email)
        assert result.returncode == 0, result.stderr
        printed = _parse(result.stdout)
        assert printed["titolare"] == email
        password = printed["password"]
        assert len(password) >= 16

        cur = await owner.execute(
            "select p.role, p.full_name, b.name, u.password_hash "
            "from profiles p join businesses b on b.id = p.business_id "
            "join users u on u.id = p.id where u.email = %s",
            (email,),
        )
        row = await cur.fetchone()
        assert row is not None, "bootstrap wrote no profile"
        role, full_name, business_name, password_hash = row
        assert role == "titolare"
        assert full_name == name
        assert business_name == name
        # The script hashes with pwdlib directly rather than importing
        # app.security (which would drag in the JWT settings). If the two
        # ever diverge, the very first account of a business could not log
        # in and nobody would find out until an operator tried.
        assert verify_password(password, password_hash)

        # And end to end, through the real endpoint.
        response = await client.post("/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        assert response.json()["profile"]["role"] == "titolare"
    finally:
        await _cleanup(owner, email)


async def test_bootstrap_refuses_an_email_that_already_exists(db_url, owner, business):
    email = business.titolare_email
    cur = await owner.execute("select count(*) from businesses")
    before = (await cur.fetchone())[0]

    result = _run_bootstrap(db_url, "Should not be created", email)

    assert result.returncode == 1
    assert "already exists" in result.stderr
    # The whole thing is one transaction: a refused run must not leave an
    # orphan business behind.
    cur = await owner.execute("select count(*) from businesses")
    assert (await cur.fetchone())[0] == before
