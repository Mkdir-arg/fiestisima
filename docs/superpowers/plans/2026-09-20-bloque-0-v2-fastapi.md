# Bloque 0 v2 · API FastAPI + backoffice — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reemplazar Supabase por una API propia en FastAPI y dejar Fiestisima desplegada en Railway junto a cauce: base migrada por la API, login e invitaciones propios, permisos en Postgres vía RLS con `set local`, cliente Expo hablando con la API, backoffice web con URL estable e instalable en el iPhone.

**Architecture:** Tres servicios en el proyecto Railway `faithful-commitment`: `fiestisima-db` (existe), `fiestisima-api` (FastAPI, psycopg 3, SQL a mano, migraciones en pre-deploy) y `fiestisima-web` (Expo web estático). La identidad viaja en un JWT; por request la API abre una transacción con `set local role app_user` y `set local app.user_id`, y las políticas RLS ya escritas deciden. Sin ORM. Tipos del cliente generados desde OpenAPI.

**Tech Stack:** Python 3.12 · FastAPI · pydantic v2 · psycopg 3 async + psycopg_pool · pwdlib[argon2] · PyJWT · uv · pytest + pytest-asyncio + httpx · Expo SDK 57 · TanStack Query 5 · openapi-typescript · Railway (Docker) · GitHub Actions.

**Spec:** [docs/superpowers/specs/2026-09-20-backend-fastapi-design.md](../specs/2026-09-20-backend-fastapi-design.md) — y, para negocio, modelo y visual, [2026-09-20-fundaciones-design.md](../specs/2026-09-20-fundaciones-design.md).

## Global Constraints

- **Idiomas**: código, comentarios y commits en inglés (también en `.sql` y `.py`); documentación en español; textos de UI en italiano en `src/i18n/it.ts`. Sustantivos del dominio sin traducir: `carico`, `scarico_uso`, `scarico_vendita`, `scarto`, `titolare`, `responsabile`, `operatore`, `frigo`, `freezer`, `dispensa`.
- **Conventional Commits.** Ramas: se trabaja en `feat/bloque-0-fundaciones` y se empuja a `origin`; `main` se actualiza al cerrar el bloque.
- **Migraciones** en `api/migrations/NNNN_descripcion.sql`. Una migración aplicada no se edita. El runner registra en `public.schema_migrations`.
- **Permisos**: toda regla de acceso tiene política RLS. La API no filtra por rol en Python salvo para traducir errores. Sólo tres caminos corren como dueño de la base (sin `set local role`): login, aceptar invitación, migraciones. Cada uno lleva un comentario `-- runs as owner:` explicando por qué.
- **Nunca un secreto en un archivo commiteado.** `.env`, `.env.test`, `api/.env` están en `.gitignore`.
- **Los tests de componentes RN son `async`** (`await render`, `await fireEvent`), ver plan v1.
- **Python 3.12** en producción (Dockerfile). Local hay 3.14: `uv` con `requires-python = ">=3.12"`.
- **Conexión a la base durante el bloque**: `postgresql://fiestisima:<PGPASSWORD>@iriguchi.proxy.rlwy.net:14064/fiestisima` (proxy TCP de `fiestisima-db`). La contraseña se lee con `railway variables --service fiestisima-db ... --json`, nunca se escribe en un archivo commiteado. Al cerrar el bloque el proxy se elimina.
- **Node 24 / Expo 57** como en v1.
- **Mapa de errores de Postgres → HTTP** (de la revisión de la Task 1): 42501 `InsufficientPrivilege` (RLS with-check y el trigger) → 403; 23505 `UniqueViolation` → 409; 23503 `ForeignKeyViolation` (restrict) → 409; 23514 `CheckViolation` → 422. **Un UPDATE cuya fila no pasa el USING no da error: `rowcount` 0** → el router devuelve 404. Nunca SQL por f-string: `set local role` es reversible con `reset role` dentro de la misma transacción, así que una sola inyección tumba el modelo entero.
- **`app_user` no tiene DELETE** salvo en `invitations` y `categories` (migración 0004). Los routers no exponen borrado de nada más; se desactiva.

---

## Estructura de archivos (nueva o cambiada)

| Ruta | Responsabilidad |
|---|---|
| `api/pyproject.toml`, `api/uv.lock` | Proyecto Python, deps fijadas. |
| `api/Dockerfile` | `python:3.12-slim`, uv, `uvicorn app.main:app`. |
| `api/railway.json` | preDeploy `python scripts/migrate.py`, healthcheck `/health`. |
| `api/migrations/0001_init.sql` | Esquema. Traducido de `supabase/migrations/0001_init.sql`: `users` propia, `profiles.id → users.id`. |
| `api/migrations/0002_rls.sql` | Permisos. Traducido de `supabase/migrations/0002_rls.sql` con las sustituciones de la spec §4. |
| `api/migrations/0003_auth_tables.sql` | `refresh_tokens`, `login_attempts`, `password_resets`. |
| `api/scripts/migrate.py` | Runner idempotente. |
| `api/app/main.py` | App, routers, CORS, `/health`, handler de errores Postgres → HTTP. |
| `api/app/config.py` | Settings desde env (pydantic-settings). |
| `api/app/db.py` | Pool; `as_user(user_id)`; `as_owner()`. |
| `api/app/security.py` | argon2, JWT, `CurrentUser`, dependencia `require_user`. |
| `api/app/mail.py` | `Mailer`, `ConsoleMailer`, `ResendMailer`. |
| `api/app/routers/{auth,invitations,users,businesses,products}.py` | Endpoints de la spec §5. |
| `api/tests/` | pytest: `conftest.py` (fixtures negocio+usuarios), `test_migrate.py`, `test_privileges.py`, `test_auth.py`, `test_invitations.py`, `test_users.py`, `test_products.py`, `test_rls_matrix.py`. |
| `src/lib/api.ts` | fetch tipado, token, refresh-and-retry. Reemplaza `src/lib/supabase.ts`. |
| `src/types/api.ts` | Generado por `openapi-typescript`. |
| `src/features/auth/{api,useSession}.ts` | Contra `/auth/*`. |
| `src/features/products/{queries,mutations,schema}.ts` | Contra `/products`. |
| `app/(auth)/…`, `app/(app)/…` | Pantallas del plan v1, misma UI, capa de datos nueva. |
| `app/+html.tsx`, `public/manifest.json` | PWA. |
| `.github/workflows/ci.yml` | test + typecheck + pytest. |
| `supabase/` | **Se elimina** al final de la Task 1 (queda en git history). |

---

## Task 1: API scaffold, migraciones traducidas y runner, aplicadas a `fiestisima-db`

**Files:**
- Create: `api/pyproject.toml`, `api/.python-version`, `api/Dockerfile`, `api/railway.json`, `api/.gitignore`
- Create: `api/app/__init__.py`, `api/app/main.py`, `api/app/config.py`, `api/app/db.py`
- Create: `api/migrations/0001_init.sql`, `api/migrations/0002_rls.sql`, `api/migrations/0003_auth_tables.sql`
- Create: `api/scripts/migrate.py`
- Create: `api/tests/conftest.py`, `api/tests/test_migrate.py`, `api/tests/test_privileges.py`
- Delete: `supabase/` (todo), `tests/rls.integration.test.ts`, `jest.rls.config.js`, script `test:rls` y `tests/README.md`; quitar `@supabase/supabase-js` y `pg` de `package.json`.
- Modify: `.gitignore` (añadir `api/.env`, `api/.venv/`, `__pycache__/`, `.pytest_cache/`).

**Interfaces:**
- Produces: `python scripts/migrate.py` (idempotente); `app.db.pool`, `app.db.as_user(user_id: UUID) -> AsyncContextManager[AsyncConnection]`, `app.db.as_owner() -> AsyncContextManager[AsyncConnection]`; roles `app_user`; funciones SQL `app_user_id()`, `app_business_id()`, `app_role()`; tablas nuevas `users`, `refresh_tokens`, `login_attempts`, `password_resets`; `GET /health`.

- [ ] **Step 1: Proyecto Python con uv**

```bash
cd api && uv init --no-readme --python 3.12 . 
uv add "fastapi>=0.115" "uvicorn[standard]" "psycopg[binary,pool]>=3.2" "pydantic-settings>=2" "pwdlib[argon2]" "PyJWT>=2.9" "httpx"
uv add --dev pytest pytest-asyncio anyio
```

`pyproject.toml` debe quedar con `[tool.pytest.ini_options] asyncio_mode = "auto"` y `pythonpath = ["."]`.

- [ ] **Step 2: Traducir las migraciones**

Copiar `supabase/migrations/0001_init.sql` a `api/migrations/0001_init.sql` y aplicar exactamente estos cambios:

```sql
-- al principio, después de las extensiones:
create table users (
  id uuid primary key default gen_random_uuid(),
  email citext not null unique,
  password_hash text not null,
  created_at timestamptz not null default now()
);

-- profiles: la referencia deja de ser auth.users
--   antes:  id uuid primary key references auth.users (id) on delete cascade,
--   ahora:  id uuid primary key references users (id) on delete cascade,

-- rol de aplicación. NOLOGIN: sólo se asume con `set local role` dentro de una transacción.
do $$ begin
  if not exists (select 1 from pg_roles where rolname = 'app_user') then
    create role app_user nologin;
  end if;
end $$;
grant app_user to current_user;
grant usage on schema public to app_user;

-- funciones de identidad: leen la variable de sesión que fija la API por request.
-- security definer por la misma razón de siempre: se llaman desde las políticas de profiles.
create or replace function app_user_id() returns uuid
language sql stable security definer set search_path = public as $$
  select nullif(current_setting('app.user_id', true), '')::uuid
$$;
create or replace function app_business_id() returns uuid
language sql stable security definer set search_path = public as $$
  select business_id from profiles where id = app_user_id() and active
$$;
create or replace function app_role() returns user_role
language sql stable security definer set search_path = public as $$
  select role from profiles where id = app_user_id() and active
$$;
```

Eliminar `auth_business_id()` y `auth_role()`. En las tres vistas, sustituir `auth_business_id()` → `app_business_id()` y `auth_role()` → `app_role()`. Comentarios en inglés, sustantivos del dominio intactos.

Copiar `supabase/migrations/0002_rls.sql` a `api/migrations/0002_rls.sql` y aplicar: `to authenticated` → `to app_user`; `auth.uid()` → `app_user_id()`; `auth_business_id()` → `app_business_id()`; `auth_role()` → `app_role()`; eliminar toda línea que mencione `anon`. Añadir al final:

```sql
-- Default privileges: app_user gets nothing it is not explicitly granted.
grant select, insert, update on
  businesses, profiles, invitations, suppliers, categories, products, events, movements
  to app_user;
-- lots keeps the column-scoped grants defined above; do not grant table-level here.
grant select on lots_view, lot_stock, product_stock to app_user;
grant usage on all sequences in schema public to app_user;
```

Revisar que el `revoke select on lots from authenticated` del original pasa a `revoke select on lots from app_user` **después** del grant anterior, y que el patrón revoke-tabla/grant-columnas para SELECT y UPDATE se conserva. El disparador `profiles_block_self_role_change_trg`: `auth.uid() is not null` → `app_user_id() is not null`.

Crear `api/migrations/0003_auth_tables.sql`:

```sql
-- Tokens and attempt tracking for the API's own auth. Owner-only tables:
-- app_user never reads them, so no RLS and no grants.
create table refresh_tokens (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  revoked_at timestamptz,
  created_at timestamptz not null default now()
);
create index refresh_tokens_user_idx on refresh_tokens (user_id);

create table login_attempts (
  email citext not null,
  attempted_at timestamptz not null default now(),
  succeeded boolean not null
);
create index login_attempts_email_time_idx on login_attempts (email, attempted_at desc);

create table password_resets (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references users (id) on delete cascade,
  token_hash text not null unique,
  expires_at timestamptz not null,
  used_at timestamptz
);
```

- [ ] **Step 3: El runner**

`api/scripts/migrate.py`:

```python
"""Apply pending SQL migrations in order. Idempotent; safe to run on every deploy."""
import asyncio, os, re, sys
from pathlib import Path
import psycopg

MIGRATIONS = Path(__file__).resolve().parent.parent / "migrations"
NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")

async def main() -> int:
    url = os.environ["DATABASE_URL"]
    files = sorted(p for p in MIGRATIONS.iterdir() if NAME.match(p.name))
    async with await psycopg.AsyncConnection.connect(url) as conn:
        await conn.execute(
            "create table if not exists schema_migrations "
            "(version text primary key, applied_at timestamptz not null default now())"
        )
        await conn.commit()
        cur = await conn.execute("select version from schema_migrations")
        applied = {r[0] for r in await cur.fetchall()}
        for path in files:
            version = NAME.match(path.name).group(1)
            if version in applied:
                continue
            async with conn.transaction():
                await conn.execute(path.read_text(encoding="utf-8"))
                await conn.execute(
                    "insert into schema_migrations (version) values (%s)", (version,)
                )
            print(f"applied {path.name}")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

- [ ] **Step 4: `db.py`, `config.py`, `main.py` con `/health`**

`api/app/db.py`:

```python
from contextlib import asynccontextmanager
from uuid import UUID
from psycopg_pool import AsyncConnectionPool
from .config import settings

pool = AsyncConnectionPool(settings.database_url, open=False, min_size=1, max_size=10)

@asynccontextmanager
async def as_user(user_id: UUID):
    """One transaction as the application role, with the caller's identity set.
    RLS policies read app.user_id through app_user_id(). set local is undone at commit/rollback."""
    async with pool.connection() as conn:
        async with conn.transaction():
            await conn.execute("set local role app_user")
            await conn.execute("select set_config('app.user_id', %s, true)", (str(user_id),))
            yield conn

@asynccontextmanager
async def as_owner():
    """-- runs as owner: no set role, RLS does not apply. Only login, invitation
    acceptance and migrations may use this. Say why at every call site."""
    async with pool.connection() as conn:
        async with conn.transaction():
            yield conn
```

`config.py`: `Settings(BaseSettings)` con `database_url: str`, `jwt_secret: str`, `site_url: str = "http://localhost:8081"`, `cors_origins: list[str] = ["http://localhost:8081"]`, `resend_api_key: str | None = None`, `access_token_minutes: int = 15`, `refresh_token_days: int = 30`. `model_config = SettingsConfigDict(env_file=".env")`.

`main.py`: lifespan abre/cierra el pool; CORS con `settings.cors_origins`; `GET /health` hace `select 1` como dueño y devuelve `{"ok": true}`; manejador de `psycopg.errors.InsufficientPrivilege` → 403 y `psycopg.errors.UniqueViolation` → 409 (detalle genérico; los routers lo especializan).

- [ ] **Step 5: Aplicar contra `fiestisima-db` y tests**

```bash
cd api && DATABASE_URL="postgresql://fiestisima:<pw>@iriguchi.proxy.rlwy.net:14064/fiestisima" uv run python scripts/migrate.py
```

Esperado: `applied 0001_init.sql`, `applied 0002_rls.sql`, `applied 0003_auth_tables.sql`. Segunda ejecución: sin salida (idempotente).

`api/tests/conftest.py`: fixture `db_url` desde `.env.test`; fixture `owner` (conexión dueño); fixture `business` que crea negocio + tres `users`/`profiles` (titolare, responsabile, operatore) y los borra al final en orden movements → lots → profiles → users → businesses.

`test_migrate.py`: correr el runner dos veces, la segunda no aplica nada; `schema_migrations` tiene 3 filas.

`test_privileges.py`: la matriz del ledger v1, contra la base real, como dueño:
`has_column_privilege('app_user','public.lots','unit_price','SELECT')` false; `document_url` false; `lot_code` true; `has_table_privilege('app_user','public.lots','UPDATE')` false; `created_by`/`business_id` UPDATE false; `lot_code` UPDATE true; INSERT true; ninguna política UPDATE/DELETE en `movements`; trigger en `profiles` sólo UPDATE; `pg_roles` no contiene `anon` ni `authenticated`.

Run: `uv run pytest -q` → verde.

- [ ] **Step 6: Limpiar Supabase del repo** (borrar `supabase/`, tests TS de RLS, `jest.rls.config.js`, deps `@supabase/supabase-js` y `pg`; `npm install`; `npm test` sigue 20/20; `npm run typecheck` limpio).

- [ ] **Step 7: Commit** `feat(api): scaffold fastapi with translated migrations and runner`

---

## Task 2: `fiestisima-api` en Railway desde GitHub

**Files:** `api/Dockerfile`, `api/railway.json` (ya creados), sin código nuevo.

**Interfaces:** Produces: URL pública `https://fiestisima-api-production.up.railway.app` (o la que Railway asigne) con `/health` → 200.

- [ ] Push: `git push -u origin feat/bloque-0-fundaciones`.
- [ ] Crear servicio `fiestisima-api` en `faithful-commitment` conectado a `Mkdir-arg/fiestisima`, rama `feat/bloque-0-fundaciones`, `rootDirectory: api`, builder Dockerfile.
- [ ] Variables: `DATABASE_URL=${{fiestisima-db.DATABASE_URL}}` (URL privada, no el proxy), `JWT_SECRET=${{ secret(48) }}`, `SITE_URL` provisional `http://localhost:8081`, `CORS_ORIGINS=["http://localhost:8081"]`, `PORT=8000`.
- [ ] `railway.json`: `{"build":{"builder":"DOCKERFILE"},"deploy":{"preDeployCommand":["python scripts/migrate.py"],"healthcheckPath":"/health","healthcheckTimeout":120,"startCommand":"uvicorn app.main:app --host :: --port $PORT"}}`.
- [ ] Generar dominio; `curl /health` → `{"ok":true}`; logs del pre-deploy muestran el runner sin aplicar nada (ya migrado desde fuera) — la idempotencia queda probada en producción.
- [ ] Commit si hubo cambios: `chore(api): railway deploy config`.

---

## Task 3: Autenticación

**Files:** `api/app/security.py`, `api/app/routers/auth.py`, `api/tests/test_auth.py`; registrar router en `main.py`.

**Interfaces:** Produces: `hash_password`, `verify_password`, `create_access_token(user_id, business_id, role)`, `decode_access_token`, `issue_refresh_token(conn, user_id) -> str`, `rotate_refresh_token(conn, raw) -> (user_id, new_raw)`, dependencia `require_user() -> CurrentUser(id, business_id, role)`; endpoints `/auth/login|refresh|logout|me|password/forgot|password/reset`.

- [ ] `security.py`: `pwdlib.PasswordHash.recommended()`; JWT HS256 con `exp`, `sub`, `bid`, `role`; refresh opaco `secrets.token_urlsafe(32)`, guardado `sha256`. `require_user` lee `Authorization: Bearer`, decodifica, devuelve `CurrentUser`; 401 en cualquier fallo.
- [ ] `routers/auth.py`:
  - `POST /auth/login {email,password}` — `-- runs as owner:` needs `users.password_hash`. Comprueba `login_attempts` (≥5 fallos en 15 min → 423 con `t.auth` equivalente "Troppi tentativi"). Inserta el intento. Si ok: carga `profiles`; si `active=false` → 403 `deactivated`. Devuelve `{access_token, refresh_token, profile}`.
  - `POST /auth/refresh {refresh_token}` — rota; el viejo se marca `revoked_at`. 401 si inválido/expirado/revocado.
  - `POST /auth/logout` — revoca el refresh recibido.
  - `GET /auth/me` — `as_user`: perfil + negocio.
  - `POST /auth/password/forgot {email}` — siempre 202; si existe, crea `password_resets` y manda mail. `POST /auth/password/reset {token,password}`.
- [ ] Tests: login ok / mal password / usuario desactivado / bloqueo tras 5 fallos; refresh rota y el viejo deja de servir; `me` devuelve rol correcto para los tres; token expirado → 401.
- [ ] Commit `feat(api): jwt auth with refresh rotation and lockout`.

---

## Task 4: Invitaciones, usuarios, negocio, mailer, y la suite de permisos traducida

**Files:** `api/app/mail.py`, `api/app/routers/{invitations,users,businesses}.py`, `api/migrations/0005_business_users_view.sql`, `api/tests/{test_invitations,test_users,test_rls_matrix}.py`.

**Interfaces:** Produces: `Mailer.send(to, subject, text)`; endpoints de la spec §5 para invitaciones/usuarios/negocio.

- [ ] `mail.py`: `ConsoleMailer` (logging.info del cuerpo) y `ResendMailer` (POST `https://api.resend.com/emails` con httpx). `get_mailer()` elige por `settings.resend_api_key`.
- [ ] `routers/invitations.py`: `POST /invitations` (`as_user`; la RLS ya limita a titolare); `GET /invitations/{token}` (owner, sólo lectura de `full_name`, `business.name`, `expires_at`; 404 si aceptada/expirada); `POST /invitations/{token}/accept {full_name,password}` — `-- runs as owner:` creates users + profiles atomically; 410 si expirada; marca `accepted_at`.
- [ ] `migrations/0005_business_users_view.sql`: `app_user` no puede leer `users` (ahí vive `password_hash`), pero `GET /users` necesita los emails. Vista `business_users` con `security_barrier`, dueña del owner, `profiles ⋈ users` proyectando `id, email, full_name, role, active, last_seen_at`, filtrada por `business_id = app_business_id()`; `grant select on business_users to app_user`. Mismo patrón que `lots_view`. **No** un cuarto camino como dueño. Test de privilegios: `app_user` sigue sin SELECT sobre `users`.
- [ ] `routers/users.py`: `GET /users` (lee `business_users`), `PATCH /users/{id} {role?,active?}` con `as_user`. La RLS y el disparador deciden; 42501 → 403. Regla del último titolare: **en la API**, con comentario explicando que es la única regla de permisos fuera de la base y por qué (necesita un conteo).
- [ ] `routers/businesses.py`: `GET /businesses/me`, `PATCH /businesses/me`.
- [ ] `test_rls_matrix.py`: traducir las invariantes del ledger v1 — cross-tenant FK rechazada; operatore no ve `unit_price` ni `document_url` vía `lots_view` y no puede `select unit_price` de `lots`; operatore no crea producto ni invita; nadie hace update/delete en `movements` (fila intacta tras el intento); `client_id` idempotente; `scarto_needs_reason`; `nulls not distinct` con NULLs; dos productos sin barcode; `lot_stock` = 0 sin movimientos; los cuatro casos de signo de anulación; `set null (col)` deja `business_id` intacto; borrar un evento como app_user es 42501 (no hay privilegio DELETE; la FK restrict queda como segunda barrera para el dueño); usuario desactivado → `app_business_id()` NULL y cero filas; operatore no se autoasciende (trigger → 42501), titolare degrada a responsabile; titolare corrige `lot_code` pero no `created_by`; `received_on` fecha de Roma; `occurred_at` retro-datado se conserva. Todo por `as_user(...)`.
- [ ] `test_invitations.py`, `test_users.py`: ciclo completo invito → aceptar → login; operatore no puede invitar (403); último titolare no puede degradarse (409).
- [ ] Commit `feat(api): invitations, users, business and the permission suite`.

---

## Task 5: Catálogo

**Files:** `api/app/routers/products.py`, `api/tests/test_products.py`.

- [ ] `GET /products?search=` (ilike sobre nombre y barcode, `active=true`, orden nombre); `POST /products`; `GET/PATCH /products/{id}`. Pydantic: `ProductIn(name, barcode|None, brand|None, unit: Literal[...], storage: Literal[...], min_stock: Decimal>=0, has_expiry: bool)`. 23505 sobre barcode → 409 `{"detail": {"code": "duplicate_barcode", "name": "<producto existente>"}}`.
- [ ] Tests: operatore lista, no crea (403); titolare crea; barcode duplicado → 409 con el nombre; búsqueda parcial.
- [ ] Commit `feat(api): product catalogue endpoints`.

---

## Task 6: Cliente — capa de datos contra la API

**Files:** `src/lib/api.ts`, `src/types/api.ts` (generado), `src/features/auth/{api,useSession,useSession.test}.ts(x)`, `src/features/products/{queries,mutations,schema,schema.test}.ts`; `package.json` script `"types": "openapi-typescript $EXPO_PUBLIC_API_URL/openapi.json -o src/types/api.ts"`; `.env.example` con `EXPO_PUBLIC_API_URL`.

**Interfaces:** Produces: `api.get/post/patch<T>(path, body?)` con auth y refresh-and-retry; `useSession(): {session, profile, isLoading}` (misma forma que v1); `signIn`, `signOut`, `acceptInvitation`; `useProducts(search)`, `useProduct(id)`, `useCreateProduct()`, `useUpdateProduct(id)`; `productSchema`.

- [ ] `src/lib/api.ts`: base URL de `EXPO_PUBLIC_API_URL`; tokens en `sessionStorage` (el `secureStorage` de v1, renombrado `tokenStorage`); ante 401 con refresh disponible → `POST /auth/refresh` una vez y reintenta; errores → `ApiError(status, detail)`.
- [ ] `useSession`: al montar lee tokens; si hay, `GET /auth/me`; expone la misma forma que v1.
- [ ] `schema.ts` y su test: los mismos 6 casos de v1.
- [ ] `useSession.test.tsx` mockeando `src/lib/api.ts` (no `fetch` global): sin tokens → `session` null; con tokens → perfil cargado.
- [ ] `npm run types` contra la API desplegada; `npm run typecheck`; `npm test`.
- [ ] Commit `feat(app): typed api client and auth session against fastapi`.

---

## Task 7: Cliente — pantallas

**Files:** `app/(auth)/_layout.tsx`, `app/(auth)/accedi.tsx`, `app/(auth)/invito/[token].tsx`, `app/(app)/_layout.tsx`, `app/(app)/(tabs)/{_layout,prodotti,scadenze,altro}.tsx`, `app/(app)/prodotti/{nuovo,[id]}.tsx`, `src/ui/{Screen,useLayout}.tsx`, `app/_layout.tsx`, `app/index.tsx`; `src/i18n/it.ts` (+ `nav`, + `auth.tooManyAttempts`).

La UI es **exactamente la del plan v1**, Tasks 6–9: leer esos bloques de código en `docs/superpowers/plans/2026-09-20-bloque-0-fundaciones.md` (líneas de cada tarea) y transcribirlos, cambiando sólo las llamadas de datos por los hooks de la Task 6. `Field` ya no tiene `error`; el error va como `<Text tone="red">` debajo del grupo.

- [ ] Login → redirige a `/(app)/(tabs)/prodotti`; credenciales malas muestran `t.auth.invalidCredentials`; 5 fallos muestran `t.auth.tooManyAttempts`.
- [ ] Invito: `GET /invitations/{token}` para mostrar nombre/negocio; aceptar → sesión → prodotti.
- [ ] Prodotti: lista con búsqueda, `Nuovo prodotto` sólo si el rol lo permite (la API igual lo rechaza), alta con 409 → mensaje `t.products.duplicateBarcode(name)`, ficha.
- [ ] Prueba manual en web contra la API desplegada: los cuatro puntos de la Task 9 de v1.
- [ ] Commit `feat(app): login, invitation, shell and product screens`.

---

## Task 8: `fiestisima-web` en Railway, PWA, y cierre del circuito

**Files:** `app/+html.tsx`, `public/manifest.json`, `public/icon-192.png`, `public/icon-512.png`, `railway.web.json` o `package.json` script `"start:web": "npx serve dist -s -l $PORT"`; dep dev `serve`.

- [ ] `+html.tsx` y `manifest.json` como en la Task 10 de v1.
- [ ] Servicio `fiestisima-web` desde GitHub, `rootDirectory: .`, build `npm ci && npx expo export -p web`, start `npx serve dist -s -l $PORT`. Variable `EXPO_PUBLIC_API_URL` = URL de `fiestisima-api`. Dominio generado.
- [ ] En `fiestisima-api`: `SITE_URL` = URL de la web; `CORS_ORIGINS` = `["<url web>"]`. Redeploy.
- [ ] Ciclo completo desde la web desplegada: invitar → aceptar (el enlace del email apunta a la web) → login → crear producto. Y en el iPhone: Safari → añadir a inicio → abrir → login persiste tras cerrar.
- [ ] Commit `feat(web): railway static deploy as installable pwa`.

---

## Task 9: Respaldos, CI, cierre de infraestructura y documentación

- [ ] **PITR** en `fiestisima-db`: `railway postgres pitr enable --service fiestisima-db` (o pestaña Backups). Verificar `pitr status`. Anotar en `docs/14`.
- [ ] **Eliminar el proxy TCP** de `fiestisima-db` (`delete-tcp-proxy`): la API llega por red privada; los tests de CI usarán un secreto con la URL del proxy sólo si se decide mantenerlo — **ruling por defecto: se elimina, y `pytest` en CI corre contra una base efímera con `services: postgres:18` en el workflow**. Ajustar `conftest.py` para aceptar `DATABASE_URL` de CI.
- [ ] `.github/workflows/ci.yml`: jobs `web` (`npm ci`, `npm run typecheck`, `npm test`) y `api` (`uv sync`, `uv run python scripts/migrate.py`, `uv run pytest`) con servicio Postgres 18 + `citext`.
- [ ] `docs/14-arquitectura-tecnica.md`: reescribir stack, estructura, entornos, seguridad (RLS con `set local`, tres caminos como dueño), respaldos (PITR activo: cerrar la pregunta abierta). `docs/15-roadmap.md`: Fase 0 real. `docs/README.md`: filas 16 y 17 y puntero a `docs/superpowers/`. `docs/04`: Face ID sigue siendo futuro; invitaciones por API propia.
- [ ] Merge a `main` (`finishing-a-development-branch`), push.
- [ ] Commit `docs: describe the fastapi architecture and close the backups question`.

---

## Verificación final (spec v2 §9)

```bash
npm run typecheck && npm test
cd api && uv run pytest -q
curl -s https://<api>/health
```

Y a mano: invitación → alta → login desde la web desplegada y desde el iPhone; operatore no ve precio; PITR `status` = archiving.
