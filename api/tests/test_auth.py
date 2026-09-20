"""Auth flows: login, refresh rotation, logout, /me, lockout, password reset.

Exercised end to end through httpx against the real FastAPI app (ASGI
transport) and the real database - no mocking of psycopg or JWT.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.db import as_owner


async def _login(client, email: str, password: str):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def test_login_ok_returns_tokens_and_profile(client, business):
    resp = await _login(client, business.titolare_email, business.password)
    assert resp.status_code == 200
    body = resp.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["profile"]["id"] == str(business.titolare_id)
    assert body["profile"]["role"] == "titolare"
    assert body["profile"]["business"]["id"] == str(business.business_id)


async def test_login_wrong_password_is_401_invalid_credentials(client, business):
    resp = await _login(client, business.operatore_email, "not-the-password")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


async def test_login_unknown_email_is_401_same_detail(client, business):
    resp = await _login(client, "nobody-at-all@fiestisima-tests.invalid", "whatever")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "invalid_credentials"


async def test_login_deactivated_profile_is_403(client, business):
    # A dedicated as_owner() block, not the shared `owner` fixture: the
    # fixture holds one long-lived transaction across the whole test, so an
    # update made through it is invisible to the separate pool connection
    # the login endpoint opens for itself until that fixture's transaction
    # commits at teardown - too late for this test to see the effect.
    async with as_owner() as conn:
        await conn.execute(
            "update profiles set active = false where id = %s", (business.operatore_id,)
        )
    resp = await _login(client, business.operatore_email, business.password)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "deactivated"


async def test_five_failed_attempts_lock_out_the_sixth_even_with_right_password(
    client, business
):
    email = business.responsabile_email
    for _ in range(5):
        resp = await _login(client, email, "wrong-password")
        assert resp.status_code == 401

    resp = await _login(client, email, business.password)
    assert resp.status_code == 423
    assert resp.json()["detail"] == "too_many_attempts"


async def test_refresh_rotates_and_old_token_then_fails(client, business):
    login_resp = await _login(client, business.titolare_email, business.password)
    old_refresh = login_resp.json()["refresh_token"]

    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_body = refresh_resp.json()
    assert new_body["refresh_token"]
    assert new_body["refresh_token"] != old_refresh
    assert new_body["access_token"]

    replay_resp = await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_resp.status_code == 401
    assert replay_resp.json()["detail"] == "invalid_token"


async def test_refresh_rejects_a_user_deactivated_after_login(client, business):
    login_resp = await _login(client, business.operatore_email, business.password)
    refresh_token = login_resp.json()["refresh_token"]

    async with as_owner() as conn:
        await conn.execute(
            "update profiles set active = false where id = %s", (business.operatore_id,)
        )

    first = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 403
    assert first.json()["detail"] == "deactivated"

    # The token was revoked as part of closing the session, not just
    # rejected-and-left-alone: replaying it gets the ordinary revoked
    # response, not a repeat of the deactivation check.
    second = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert second.status_code == 401
    assert second.json()["detail"] == "invalid_token"


async def test_logout_revokes_the_refresh_token(client, business):
    login_resp = await _login(client, business.titolare_email, business.password)
    refresh_token = login_resp.json()["refresh_token"]

    logout_resp = await client.post("/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200

    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["detail"] == "invalid_token"


@pytest.mark.parametrize("role_attr,email_attr", [
    ("titolare_id", "titolare_email"),
    ("responsabile_id", "responsabile_email"),
    ("operatore_id", "operatore_email"),
])
async def test_me_returns_the_right_role_for_each_user(client, business, role_attr, email_attr):
    email = getattr(business, email_attr)
    login_resp = await _login(client, email, business.password)
    access_token = login_resp.json()["access_token"]

    me_resp = await client.get(
        "/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )
    assert me_resp.status_code == 200
    body = me_resp.json()
    expected_role = role_attr.removesuffix("_id")
    assert body["role"] == expected_role
    assert body["id"] == str(getattr(business, role_attr))
    assert body["business"]["id"] == str(business.business_id)


async def test_me_with_expired_access_token_is_401(client, business):
    now = datetime.now(timezone.utc)
    expired = jwt.encode(
        {
            "sub": str(business.titolare_id),
            "bid": str(business.business_id),
            "role": "titolare",
            "iat": now - timedelta(minutes=30),
            "exp": now - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm="HS256",
    )
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


async def test_me_with_tampered_token_is_401(client, business):
    login_resp = await _login(client, business.titolare_email, business.password)
    access_token = login_resp.json()["access_token"]
    tampered = access_token[:-1] + ("A" if access_token[-1] != "A" else "B")

    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {tampered}"})
    assert resp.status_code == 401


async def test_me_without_header_is_401(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_forgot_password_for_unknown_email_is_still_202(client):
    resp = await client.post(
        "/auth/password/forgot", json={"email": "nobody-here@fiestisima-tests.invalid"}
    )
    assert resp.status_code == 202


async def _forgot_and_capture_token(client, caplog, email: str) -> str:
    """Drives /auth/password/forgot for real and recovers the raw reset
    token from ConsoleMailer's log line - the only place the raw token
    exists outside the (one-way-hashed) database row, exactly mirroring
    what a real mailbox would hand the user."""
    with caplog.at_level("INFO", logger="app.mail"):
        resp = await client.post("/auth/password/forgot", json={"email": email})
    assert resp.status_code == 202
    for record in caplog.records:
        if email in record.getMessage():
            return record.getMessage().rsplit("/", 1)[-1]
    raise AssertionError("reset token was not logged by ConsoleMailer")


async def test_reset_password_with_valid_token_allows_login_with_new_password(
    client, business, caplog
):
    raw_token = await _forgot_and_capture_token(client, caplog, business.operatore_email)

    new_password = "New-Correct-Horse-Battery-2"
    reset_resp = await client.post(
        "/auth/password/reset", json={"token": raw_token, "password": new_password}
    )
    assert reset_resp.status_code == 200

    old_login = await _login(client, business.operatore_email, business.password)
    assert old_login.status_code == 401

    new_login = await _login(client, business.operatore_email, new_password)
    assert new_login.status_code == 200


async def test_reset_password_revokes_existing_refresh_tokens(client, business, caplog):
    login_resp = await _login(client, business.responsabile_email, business.password)
    refresh_token = login_resp.json()["refresh_token"]

    raw_token = await _forgot_and_capture_token(client, caplog, business.responsabile_email)

    new_password = "Another-New-Password-3"
    reset_resp = await client.post(
        "/auth/password/reset", json={"token": raw_token, "password": new_password}
    )
    assert reset_resp.status_code == 200

    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401


async def test_password_reset_rejects_a_user_deactivated_after_the_request(
    client, business, caplog
):
    login_resp = await _login(client, business.titolare_email, business.password)
    refresh_token = login_resp.json()["refresh_token"]

    raw_token = await _forgot_and_capture_token(client, caplog, business.titolare_email)

    async with as_owner() as conn:
        await conn.execute(
            "update profiles set active = false where id = %s", (business.titolare_id,)
        )

    first = await client.post(
        "/auth/password/reset", json={"token": raw_token, "password": "Whatever-New-Pass-4"}
    )
    assert first.status_code == 403
    assert first.json()["detail"] == "deactivated"

    # The pre-existing session was closed as part of that rejection.
    second_refresh = await client.post(
        "/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert second_refresh.status_code == 401
    assert second_refresh.json()["detail"] == "invalid_token"
