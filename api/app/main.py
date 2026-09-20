from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .db import pool, as_owner
from .routers.auth import router as auth_router


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


app.include_router(auth_router)


@app.get("/health")
async def health():
    # Runs as owner: a health check has no caller identity to set as
    # app.user_id, and it only needs to prove the database is reachable.
    async with as_owner() as conn:
        await conn.execute("select 1")
    return {"ok": True}
