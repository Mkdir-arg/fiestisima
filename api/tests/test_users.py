"""GET /users, PATCH /users/{id}: listing, role changes, deactivation, and
the one Python-side permission rule (last active titolare).
"""
import pytest

from app.db import as_owner


async def _login(client, email: str, password: str):
    return await client.post("/auth/login", json={"email": email, "password": password})


async def _access_token(client, email: str, password: str) -> str:
    resp = await _login(client, email, password)
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("email_attr", ["titolare_email", "responsabile_email", "operatore_email"])
async def test_list_users_returns_all_three_with_emails(client, business, email_attr):
    token = await _access_token(client, getattr(business, email_attr), business.password)
    resp = await client.get("/users", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 3
    emails = {row["email"] for row in body}
    assert emails == {business.titolare_email, business.responsabile_email, business.operatore_email}
    for row in body:
        assert set(row.keys()) >= {"id", "email", "full_name", "role", "active", "created_at"}


async def test_titolare_demotes_responsabile_and_me_reflects_it(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/users/{business.responsabile_id}",
        headers=_auth(titolare_token),
        json={"role": "operatore"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "operatore"

    responsabile_token = await _access_token(
        client, business.responsabile_email, business.password
    )
    me_resp = await client.get("/auth/me", headers=_auth(responsabile_token))
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "operatore"


async def test_operatore_cannot_self_promote(client, business):
    operatore_token = await _access_token(client, business.operatore_email, business.password)
    resp = await client.patch(
        f"/users/{business.operatore_id}",
        headers=_auth(operatore_token),
        json={"role": "titolare"},
    )
    assert resp.status_code == 403


async def test_titolare_deactivates_operatore_and_refresh_then_fails(client, business):
    operatore_login = await _login(client, business.operatore_email, business.password)
    refresh_token = operatore_login.json()["refresh_token"]

    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/users/{business.operatore_id}",
        headers=_auth(titolare_token),
        json={"active": False},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"] is False

    # Asserted directly, not "401 or 403": PATCH's own as_owner() revoke
    # must be what closed this session. If that revoke block were deleted,
    # /auth/refresh would still independently notice the profile is
    # inactive and answer 403 on its own - a test that accepted either
    # status would not catch that regression. The database row is the
    # unambiguous proof; the response code is corroborating evidence.
    async with as_owner() as conn:
        cur = await conn.execute(
            "select revoked_at from refresh_tokens where user_id = %s", (business.operatore_id,)
        )
        (revoked_at,) = await cur.fetchone()
        assert revoked_at is not None

    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
    assert refresh_resp.json()["detail"] == "invalid_token"


async def test_last_titolare_cannot_deactivate_self(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/users/{business.titolare_id}",
        headers=_auth(titolare_token),
        json={"active": False},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "last_titolare"


async def test_last_titolare_cannot_demote_self(client, business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/users/{business.titolare_id}",
        headers=_auth(titolare_token),
        json={"role": "responsabile"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "last_titolare"


async def test_with_second_titolare_demoting_one_succeeds(client, business):
    # Promote the responsabile to a second titolare directly (owner mode,
    # test setup only) so the last-titolare guard no longer applies to
    # business.titolare_id.
    async with as_owner() as conn:
        await conn.execute(
            "update profiles set role = 'titolare' where id = %s",
            (business.responsabile_id,),
        )

    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/users/{business.responsabile_id}",
        headers=_auth(titolare_token),
        json={"role": "responsabile"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["role"] == "responsabile"


async def test_patch_id_from_another_business_is_404(client, business, other_business):
    titolare_token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        f"/users/{other_business.titolare_id}",
        headers=_auth(titolare_token),
        json={"active": False},
    )
    assert resp.status_code == 404


async def test_non_titolare_patch_colleague_is_404(client, business):
    # profiles_update_titolare's using clause requires the caller be
    # titolare - a responsabile's UPDATE on a colleague's row (not their
    # own) matches 0 rows before the profiles_block_self_role_change
    # trigger ever runs, so this is 404, not the trigger's 403. Contrast
    # with test_operatore_cannot_self_promote, a *self*-update, where
    # profiles_update_self always makes the row visible and the trigger
    # does fire.
    responsabile_token = await _access_token(
        client, business.responsabile_email, business.password
    )
    resp = await client.patch(
        f"/users/{business.operatore_id}",
        headers=_auth(responsabile_token),
        json={"role": "titolare"},
    )
    assert resp.status_code == 404


async def test_titolare_with_co_titolare_deactivates_self_200_and_own_refresh_401(
    client, business
):
    # Regression guard: a titolare stepping down while a co-titolare
    # exists must not 500. The old code re-read business_users *after*
    # committing the caller's own deactivation, by which point the
    # caller's own app_business_id() had already gone NULL (it only
    # resolves for an active profile), so the "fetch the updated row to
    # respond with" query returned nothing and building the response
    # crashed - after the DB write and the refresh-token revoke had
    # already committed. This is exactly the ownership-handoff request the
    # last-titolare guard exists to allow.
    async with as_owner() as conn:
        await conn.execute(
            "update profiles set role = 'titolare' where id = %s",
            (business.responsabile_id,),
        )

    login_resp = await _login(client, business.titolare_email, business.password)
    refresh_token = login_resp.json()["refresh_token"]
    titolare_token = login_resp.json()["access_token"]

    resp = await client.patch(
        f"/users/{business.titolare_id}",
        headers={"Authorization": f"Bearer {titolare_token}"},
        json={"active": False},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active"] is False
    assert body["id"] == str(business.titolare_id)
    assert body["role"] == "titolare"

    refresh_resp = await client.post("/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 401
