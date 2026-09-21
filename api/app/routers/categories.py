"""List, create, rename and delete product categories.

No owner mode anywhere in this file: every endpoint runs as_user, and
categories_select/categories_write (see migrations/0002_rls.sql) decide
who may read or write, never current_user.role or .business_id in Python
(see db.py's as_user() and the module comment in routers/auth.py for the
same rule).

categories_write is a single FOR ALL policy scoped to
app_role() in ('titolare', 'responsabile') - the same shape products.py's
products_write uses, with the same v2-15 asymmetry: an operatore's POST
fails the WITH CHECK (a genuine psycopg.errors.InsufficientPrivilege,
uncaught here, mapped to 403 by main.py) while an operatore's PATCH or
DELETE fails the USING clause instead (Postgres just excludes the row -
rowcount 0, reported here as 404, never an exception). See products.py's
module comment for the full reasoning; it applies unchanged here.

Unlike products/suppliers, categories really are deletable (0004 grants
DELETE on this table - a category is a free-text label whose only
reference, products.category_id, is "on delete set null", so removing one
orphans nothing - see 0004's own comment). DELETE goes through the same
categories_write policy as PATCH, so an operatore's DELETE gets the same
404-by-filtering treatment, not a privilege error.

Duplicate name (unique(business_id, name)) answers a plain 409 "name_taken"
string, not products.py's richer {"code", "name"} object: unlike a barcode
collision, the caller already knows which name collided (they just typed
it), so there is nothing extra worth carrying in the body.
"""
from uuid import UUID

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from ..db import as_user
from ..security import CurrentUser, require_user

router = APIRouter(prefix="/categories", tags=["categories"])


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class CategoryOut(BaseModel):
    id: UUID
    name: str


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    _strip_name = field_validator("name", mode="before")(_strip)


class CategoryPatch(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    _strip_name = field_validator("name", mode="before")(_strip)


def _category_out(row) -> CategoryOut:
    return CategoryOut(id=row[0], name=row[1])


# ------------------------------------------------------------------- list

@router.get("", response_model=list[CategoryOut])
async def list_categories(current_user: CurrentUser = Depends(require_user)):
    # Read-only: raising inside is fine (see the exemption noted in
    # routers/auth.py's module comment). Every role may read the catalog -
    # categories_select has no role condition, only categories_write does.
    async with as_user(current_user.id) as conn:
        cur = await conn.execute("select id, name from categories order by name")
        rows = await cur.fetchall()
        return [_category_out(row) for row in rows]


# ----------------------------------------------------------------- create

@router.post("", response_model=CategoryOut, status_code=201)
async def create_category(body: CategoryIn, current_user: CurrentUser = Depends(require_user)):
    error: HTTPException | None = None
    created: CategoryOut | None = None

    async with as_user(current_user.id) as conn:
        try:
            cur = await conn.execute(
                "insert into categories (business_id, name) values (app_business_id(), %s) "
                "returning id, name",
                (body.name,),
            )
            row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            error = HTTPException(status_code=409, detail="name_taken")
        else:
            created = _category_out(row)

    if error is not None:
        raise error
    return created


# ------------------------------------------------------------------- patch

@router.patch("/{category_id}", response_model=CategoryOut)
async def rename_category(
    category_id: UUID, body: CategoryPatch, current_user: CurrentUser = Depends(require_user)
):
    error: HTTPException | None = None
    updated: CategoryOut | None = None

    async with as_user(current_user.id) as conn:
        try:
            cur = await conn.execute(
                "update categories set name = %s where id = %s returning id, name",
                (body.name, category_id),
            )
            row = await cur.fetchone()
        except psycopg.errors.UniqueViolation:
            error = HTTPException(status_code=409, detail="name_taken")
        else:
            if row is None:
                error = HTTPException(status_code=404, detail="not_found")
            else:
                updated = _category_out(row)

    if error is not None:
        raise error
    return updated


# ------------------------------------------------------------------ delete

@router.delete("/{category_id}", status_code=204)
async def delete_category(category_id: UUID, current_user: CurrentUser = Depends(require_user)):
    async with as_user(current_user.id) as conn:
        cur = await conn.execute("delete from categories where id = %s", (category_id,))
        deleted = cur.rowcount
    if deleted == 0:
        raise HTTPException(status_code=404, detail="not_found")
