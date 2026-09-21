"""Current stock, read from the views - never written, never computed here.

No owner mode anywhere in this file: both endpoints run as_user.
product_stock/lot_stock (see migrations/0001_init.sql) are security_barrier
views that already filter to app_business_id() themselves, and select on
them is granted to app_user unconditionally - there is no role gate on
reading stock (docs/02: "Escanear y consultar ... stock" is an all-roles
row), so nothing here reads current_user.role either.

GET /stock/products is the shopping-list source (docs/09: "Ordine
suggerito" groups products under their minimum): each row carries the
product's own min_stock alongside its live stock and a server-computed
below_min flag, computed from a LEFT JOIN starting at products (not at
product_stock), so a product with zero lots - which never gets a row in
product_stock at all, since that view is grouped out of lot_stock - still
shows stock 0 and is correctly flagged below_min when its minimum is above
zero.

GET /stock/lots is deliberately a thinner sibling of GET /lots (which
already carries a `stock` field for its own list/detail views): this one
returns exactly lot_stock's own shape (lot_id, product_id, stock) for a
caller that only needs the raw number - e.g. a quick post-movement stock
check - without paying for lots_view's join or its price-masking case
expression.
"""
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..db import as_user
from ..security import CurrentUser, require_user

router = APIRouter(prefix="/stock", tags=["stock"])


class ProductStockOut(BaseModel):
    product_id: UUID
    # Decimal, not float - same reasoning as products.py's min_stock:
    # serialises to a JSON string, never a float-rounded number.
    stock: Decimal
    min_stock: Decimal
    below_min: bool


class LotStockOut(BaseModel):
    lot_id: UUID
    product_id: UUID
    stock: Decimal


def _product_stock_out(row) -> ProductStockOut:
    return ProductStockOut(product_id=row[0], stock=row[1], min_stock=row[2], below_min=row[3])


def _lot_stock_out(row) -> LotStockOut:
    return LotStockOut(lot_id=row[0], product_id=row[1], stock=row[2])


# --------------------------------------------------------------- products

@router.get("/products", response_model=list[ProductStockOut])
async def list_product_stock(
    below_min_only: bool = Query(default=False),
    include_inactive: bool = Query(default=False),
    search: str | None = Query(default=None),
    current_user: CurrentUser = Depends(require_user),
):
    like_term = f"%{search}%" if search else None
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            """
            select p.id, coalesce(ps.stock, 0) as stock, p.min_stock,
                   coalesce(ps.stock, 0) < p.min_stock as below_min
            from products p
            left join product_stock ps on ps.product_id = p.id
            where (%s or p.active)
              and (%s::text is null or p.name ilike %s)
              and (%s = false or coalesce(ps.stock, 0) < p.min_stock)
            order by p.name
            """,
            (include_inactive, like_term, like_term, below_min_only),
        )
        rows = await cur.fetchall()
        return [_product_stock_out(row) for row in rows]


# -------------------------------------------------------------------- lots

@router.get("/lots", response_model=list[LotStockOut])
async def list_lot_stock(
    product_id: UUID | None = Query(default=None),
    lot_id: UUID | None = Query(default=None),
    current_user: CurrentUser = Depends(require_user),
):
    async with as_user(current_user.id) as conn:
        cur = await conn.execute(
            """
            select lot_id, product_id, stock
            from lot_stock
            where (%s::uuid is null or product_id = %s)
              and (%s::uuid is null or lot_id = %s)
            order by lot_id
            """,
            (product_id, product_id, lot_id, lot_id),
        )
        rows = await cur.fetchall()
        return [_lot_stock_out(row) for row in rows]
