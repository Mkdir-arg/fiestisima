from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import pool, as_owner
from .routers.auth import router as auth_router
from .routers.businesses import router as businesses_router
from .routers.invitations import router as invitations_router
from .routers.products import router as products_router
from .routers.users import router as users_router


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


@app.get("/health")
async def health():
    # Runs as owner: a health check has no caller identity to set as
    # app.user_id, and it only needs to prove the database is reachable.
    async with as_owner() as conn:
        await conn.execute("select 1")
    return {"ok": True}
