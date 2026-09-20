"""GET/PATCH /businesses/me."""
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
async def test_get_me_returns_own_business_for_every_role(client, business, email_attr):
    token = await _access_token(client, getattr(business, email_attr), business.password)
    resp = await client.get("/businesses/me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(business.business_id)


async def test_patch_me_by_titolare_succeeds(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        "/businesses/me", headers=_auth(token), json={"name": "Nuovo Nome SRL"}
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Nuovo Nome SRL"

    async with as_owner() as conn:
        cur = await conn.execute(
            "select name from businesses where id = %s", (business.business_id,)
        )
        (name,) = await cur.fetchone()
        assert name == "Nuovo Nome SRL"


async def test_patch_me_by_responsabile_is_404(client, business):
    # businesses_update's USING clause is role-gated with no trigger: a
    # non-titolare's UPDATE matches no row (Postgres filters silently, no
    # error), same reasoning as routers/invitations.py's resend/delete.
    token = await _access_token(client, business.responsabile_email, business.password)
    resp = await client.patch(
        "/businesses/me", headers=_auth(token), json={"name": "Should Not Apply"}
    )
    assert resp.status_code == 404


async def test_patch_me_expiry_threshold_zero_is_422(client, business):
    token = await _access_token(client, business.titolare_email, business.password)
    resp = await client.patch(
        "/businesses/me", headers=_auth(token), json={"expiry_threshold_days": 0}
    )
    assert resp.status_code == 422
