"""Invite -> preview -> accept, resend, cancel. Exercised end to end through
httpx against the real FastAPI app, mirroring test_auth.py's style.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.db import as_owner
from app.mail import get_mailer
import app.routers.invitations as invitations_module


async def _login(client, email: str, password: str):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _access_token(client, email: str, password: str) -> str:
    resp = await _login(client, email, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class _CapturingMailer:
    """Records every send() call instead of touching the network or the
    log - lets tests assert on the exact link mailed without depending on
    ConsoleMailer's log format."""

    def __init__(self):
        self.sent = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body})


@pytest.fixture
def capturing_mailer(monkeypatch):
    mailer = _CapturingMailer()
    monkeypatch.setattr(invitations_module, "get_mailer", lambda: mailer)
    return mailer


async def test_titolare_invites_gets_201_and_mail_has_invito_link(
    client, business, capturing_mailer
):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.post(
        "/invitations",
        headers=_auth(token),
        json={
            "email": "new-invitee@fiestisima-tests.invalid",
            "full_name": "Nuovo Invitato",
            "role": "operatore",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["email"] == "new-invitee@fiestisima-tests.invalid"
    assert body["role"] == "operatore"
    assert "token" not in body
    assert "id" not in body or body["id"]

    assert len(capturing_mailer.sent) == 1
    mail = capturing_mailer.sent[0]
    assert mail["to"] == "new-invitee@fiestisima-tests.invalid"
    assert "/invito/" in mail["body"]

    async with as_owner() as conn:
        cur = await conn.execute(
            "delete from invitations where business_id = %s returning id",
            (business.business_id,),
        )
        assert (await cur.fetchall())


async def test_operatore_cannot_invite(client, business):
    token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.post(
        "/invitations",
        headers=_auth(token),
        json={
            "email": "blocked@fiestisima-tests.invalid",
            "full_name": "Blocked",
            "role": "operatore",
        },
    )
    assert resp.status_code == 403


async def test_duplicate_pending_invitation_is_409(client, business, capturing_mailer):
    token = await _access_token(client, business.titolare_email, business.password)
    payload = {
        "email": "dup@fiestisima-tests.invalid",
        "full_name": "Dup",
        "role": "operatore",
    }
    first = await client.post("/invitations", headers=_auth(token), json=payload)
    assert first.status_code == 201

    second = await client.post("/invitations", headers=_auth(token), json=payload)
    assert second.status_code == 409
    assert second.json()["detail"] == "invitation_pending"

    async with as_owner() as conn:
        await conn.execute(
            "delete from invitations where business_id = %s", (business.business_id,)
        )


async def _create_invitation(conn, business_id, email="invitee@fiestisima-tests.invalid",
                              full_name="Invitato", role="operatore", expires_in=timedelta(days=7),
                              invited_by=None):
    cur = await conn.execute(
        """
        insert into invitations (business_id, email, full_name, role, expires_at, invited_by)
        values (%s, %s, %s, %s, now() + %s, %s)
        returning id, token
        """,
        (business_id, email, full_name, role, expires_in, invited_by),
    )
    return await cur.fetchone()


async def test_get_invitation_returns_name_and_business_never_email(client, business):
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(conn, business.business_id)

    resp = await client.get(f"/invitations/{token}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_name"] == "Invitato"
    assert "business_name" in body
    assert "email" not in body
    assert "business_id" not in body

    async with as_owner() as conn:
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_accept_returns_tokens_and_then_login_works(client, business):
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(
            conn, business.business_id, email="accepted@fiestisima-tests.invalid"
        )

    resp = await client.post(
        f"/invitations/{token}/accept",
        json={"full_name": "Accettato", "password": "Brand-New-Password-9"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["profile"]["full_name"] == "Accettato"
    assert body["profile"]["role"] == "operatore"

    login_resp = await _login(client, "accepted@fiestisima-tests.invalid", "Brand-New-Password-9")
    assert login_resp.status_code == 200

    new_user_id = body["profile"]["id"]
    async with as_owner() as conn:
        await conn.execute("delete from profiles where id = %s", (new_user_id,))
        await conn.execute("delete from users where id = %s", (new_user_id,))
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_accept_twice_is_410(client, business):
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(
            conn, business.business_id, email="twice@fiestisima-tests.invalid"
        )

    first = await client.post(
        f"/invitations/{token}/accept",
        json={"full_name": "Uno", "password": "First-Password-111"},
    )
    assert first.status_code == 200
    user_id = first.json()["profile"]["id"]

    second = await client.post(
        f"/invitations/{token}/accept",
        json={"full_name": "Due", "password": "Second-Password-222"},
    )
    assert second.status_code == 410
    assert second.json()["detail"] == "invitation_expired"

    async with as_owner() as conn:
        await conn.execute("delete from profiles where id = %s", (user_id,))
        await conn.execute("delete from users where id = %s", (user_id,))
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_accept_with_email_already_a_user_is_409_and_invitation_stays_pending(
    client, business
):
    # business.titolare_email already has a `users` row (the fixture
    # created it) - accepting an invitation to that same address must fail
    # without silently creating a duplicate account.
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(
            conn, business.business_id, email=business.titolare_email
        )

    resp = await client.post(
        f"/invitations/{token}/accept",
        json={"full_name": "Colide", "password": "Whatever-Password-333"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "email_taken"

    async with as_owner() as conn:
        cur = await conn.execute(
            "select accepted_at from invitations where id = %s", (invitation_id,)
        )
        (accepted_at,) = await cur.fetchone()
        assert accepted_at is None
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_expired_invitation_accept_is_410(client, business):
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(
            conn,
            business.business_id,
            email="expired@fiestisima-tests.invalid",
            expires_in=timedelta(days=-1),
        )

    resp = await client.post(
        f"/invitations/{token}/accept",
        json={"full_name": "Tardi", "password": "Too-Late-Password-4"},
    )
    assert resp.status_code == 410
    assert resp.json()["detail"] == "invitation_expired"

    preview = await client.get(f"/invitations/{token}")
    assert preview.status_code == 404

    async with as_owner() as conn:
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_resend_by_titolare_moves_expires_at(client, business, capturing_mailer):
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(
            conn,
            business.business_id,
            email="resend-me@fiestisima-tests.invalid",
            expires_in=timedelta(hours=1),
        )
        cur = await conn.execute(
            "select expires_at from invitations where id = %s", (invitation_id,)
        )
        (original_expires_at,) = await cur.fetchone()

    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.post(
        f"/invitations/{invitation_id}/resend", headers=_auth(titolare_token)
    )
    assert resp.status_code == 200, resp.text
    new_expires_at = datetime.fromisoformat(resp.json()["expires_at"])
    assert new_expires_at > original_expires_at
    assert len(capturing_mailer.sent) == 1

    async with as_owner() as conn:
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_resend_by_responsabile_is_404(client, business):
    # invitations_all's USING clause is role-gated but has no trigger: a
    # non-titolare's UPDATE simply matches no row (Postgres filters it,
    # no error) rather than raising 42501 - see routers/invitations.py's
    # module comment. The endpoint therefore reports 404, not 403, exactly
    # like PATCH /users/{id} and PATCH /businesses/me for the same reason.
    async with as_owner() as conn:
        invitation_id, _token = await _create_invitation(
            conn, business.business_id, email="resend-blocked@fiestisima-tests.invalid"
        )

    responsabile_token = await _access_token(
        client, business.responsabile_email, business.password
    )
    resp = await client.post(
        f"/invitations/{invitation_id}/resend", headers=_auth(responsabile_token)
    )
    assert resp.status_code == 404

    async with as_owner() as conn:
        await conn.execute("delete from invitations where id = %s", (invitation_id,))


async def test_delete_by_titolare_then_get_is_404(client, business):
    async with as_owner() as conn:
        invitation_id, token = await _create_invitation(
            conn, business.business_id, email="to-delete@fiestisima-tests.invalid"
        )

    titolare_token = await _access_token(client, business.titolare_email, business.password)
    delete_resp = await client.delete(
        f"/invitations/{invitation_id}", headers=_auth(titolare_token)
    )
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/invitations/{token}")
    assert get_resp.status_code == 404
