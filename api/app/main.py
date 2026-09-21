import logging
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from .config import settings
from .db import pool, as_owner
from .routers.auth import router as auth_router
from .routers.businesses import router as businesses_router
from .routers.invitations import router as invitations_router
from .routers.products import router as products_router
from .routers.users import router as users_router

logger = logging.getLogger("fiestisima")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await pool.open()
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(psycopg.errors.InsufficientPrivilege)
async def insufficient_privilege_handler(request: Request, exc: psycopg.errors.InsufficientPrivilege):
    return JSONResponse(status_code=403, content={"detail": "forbidden"})


@app.exception_handler(psycopg.errors.UniqueViolation)
async def unique_violation_handler(request: Request, exc: psycopg.errors.UniqueViolation):
    return JSONResponse(status_code=409, content={"detail": "conflict"})


@app.exception_handler(psycopg.errors.ForeignKeyViolation)
async def foreign_key_violation_handler(request: Request, exc: psycopg.errors.ForeignKeyViolation):
    return JSONResponse(status_code=409, content={"detail": "conflict"})


@app.exception_handler(psycopg.errors.CheckViolation)
async def check_violation_handler(request: Request, exc: psycopg.errors.CheckViolation):
    return JSONResponse(status_code=422, content={"detail": "invalid"})


@app.exception_handler(psycopg.errors.NotNullViolation)
async def not_null_violation_handler(request: Request, exc: psycopg.errors.NotNullViolation):
    # Safety net for every router, not just products: a request that
    # somehow gets an explicit null past its own Pydantic model onto a NOT
    # NULL column (23502) should still 422, never surface as a bare 500.
    return JSONResponse(status_code=422, content={"detail": "invalid"})


app.include_router(auth_router)
app.include_router(invitations_router)
app.include_router(users_router)
app.include_router(businesses_router)
app.include_router(products_router)


# Only these mean "the database is not reachable right now". Class 08 is
# every connection exception; 57P01/02/03 are admin shutdown, crash
# shutdown and cannot-connect-now. Everything else that happens to be an
# OperationalError - a statement_timeout (57014), a deadlock (40P01), a
# lock_timeout (55P03) - is a bug in a query, not an outage, and must stay
# a loud 500 instead of hiding behind a retryable 503.
_UNAVAILABLE_SQLSTATES = frozenset({"57P01", "57P02", "57P03"})


def _is_unavailable(exc: psycopg.OperationalError) -> bool:
    # PoolTimeout carries no sqlstate: the pool gave up before it ever
    # reached the server, which is the outage case by definition.
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate is None:
        return isinstance(exc, PoolTimeout)
    return sqlstate.startswith("08") or sqlstate in _UNAVAILABLE_SQLSTATES


@app.exception_handler(psycopg.OperationalError)
async def operational_error_handler(request: Request, exc: psycopg.OperationalError):
    if not _is_unavailable(exc):
        # Re-raised, not swallowed: ServerErrorMiddleware turns it into a
        # 500 with a traceback, which is what a query bug deserves.
        raise exc
    # Logged rather than silently retried: an outage that lasts is
    # something we want to find in the logs afterwards.
    logger.error("database unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "database_unavailable"},
        headers={"Retry-After": "5"},
    )


@app.get("/health")
async def health():
    # Runs as owner: a health check has no caller identity to set as
    # app.user_id, and it only needs to prove the database is reachable.
    # A dead pooled connection no longer reaches here (the pool checks on
    # checkout); an unreachable database surfaces as 503 via the handler
    # above, which is what Railway's healthcheck should see while the
    # database is restarting.
    async with as_owner() as conn:
        await conn.execute("select 1")
    return {"ok": True}
