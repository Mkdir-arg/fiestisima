"""Create the first business and its titolare.

The API has no public signup: every account is born from an invitation, and
an invitation can only be sent by a titolare. That leaves the very first
titolare with no way in, so it is created here, out of band, as the database
owner - the same owner-mode exception the migration runner uses.

Run once per business:

    DATABASE_URL=... python scripts/bootstrap.py "Nome del locale" owner@example.com

The password is generated and printed once; it is never stored in plain
text and cannot be recovered afterwards (use the password-reset flow).
Set BOOTSTRAP_PASSWORD to choose it instead - only worth doing from a
script, since an environment variable is easier to leak than one line of
terminal output.
Re-running with an email that already exists fails instead of overwriting.
"""
import asyncio, os, secrets, string, sys

import psycopg
from pwdlib import PasswordHash

# pwdlib directly rather than app.security: importing that module pulls in
# app.config, whose Settings demand JWT_SECRET and friends. Bootstrapping
# needs nothing but a database connection.
hash_password = PasswordHash.recommended().hash

# psycopg's async mode cannot run on Windows' default ProactorEventLoop.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

ALPHABET = string.ascii_letters + string.digits


def generate_password() -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(20))


async def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    business_name, email = sys.argv[1], sys.argv[2].strip().lower()
    password = os.environ.get("BOOTSTRAP_PASSWORD") or generate_password()

    async with await psycopg.AsyncConnection.connect(os.environ["DATABASE_URL"]) as conn:
        async with conn.transaction():
            cur = await conn.execute("select 1 from users where email = %s", (email,))
            if await cur.fetchone():
                print(f"user {email} already exists; nothing done", file=sys.stderr)
                return 1
            cur = await conn.execute(
                "insert into businesses (name) values (%s) returning id", (business_name,)
            )
            row = await cur.fetchone()
            business_id = row[0]
            cur = await conn.execute(
                "insert into users (email, password_hash) values (%s, %s) returning id",
                (email, hash_password(password)),
            )
            row = await cur.fetchone()
            user_id = row[0]
            await conn.execute(
                "insert into profiles (id, business_id, full_name, role) "
                "values (%s, %s, %s, 'titolare')",
                (user_id, business_id, business_name),
            )

    print(f"business  {business_id}  {business_name}")
    print(f"titolare  {email}")
    print(f"password  {password}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
