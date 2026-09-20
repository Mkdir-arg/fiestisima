# Fiestisima · Backend propio en FastAPI

**Fecha**: 2026-09-20 · **Estado**: decidido por el controlador bajo mandato de "desarrollar todo"; cada decisión es reversible y está marcada.

Sustituye a la parte de infraestructura y permisos de [2026-09-20-fundaciones-design.md](2026-09-20-fundaciones-design.md). Todo lo que ese documento dice sobre el negocio, el alcance, el cliente Expo, el modelo de datos y el sistema visual **sigue vigente**. Lo que cambia es dónde vive la identidad del usuario y quién sirve la API.

---

## 1. Qué cambió y por qué

La dueña decidió sacar Supabase y construir Fiestisima como su otro sistema (`cauce`): una API propia, un backoffice web y un Postgres en Railway, todo en el proyecto `faithful-commitment`. Eligió Python con FastAPI. La razón que dio: tener todo junto, con un solo patrón de despliegue y de respaldo.

Consecuencia: `auth.uid()`, `auth.users`, los roles `authenticated`/`anon` y PostgREST desaparecen. Todo lo que dependía de ellos se reescribe. Todo lo demás se conserva.

## 2. Qué se conserva sin tocar

- El cliente Expo entero: andamiaje, `src/ui/`, `src/i18n/it.ts`, `src/lib/lotStatus.ts`, tests.
- El **diseño** del esquema de `0001_init.sql`: tablas, vistas de stock, claves compuestas por negocio, expresión de signo de anulaciones, `occurred_at`, fecha de Roma, `check` constraints. Cambia una sola cosa: `profiles.id` deja de referenciar `auth.users` y pasa a referenciar una tabla `users` nuestra.
- La **lógica** de `0002_rls.sql`: las 19 políticas se conservan con dos sustituciones mecánicas (sección 4). El disparador de roles se conserva. Los permisos por columna se conservan cambiando el nombre del rol.
- La documentación funcional, salvo `docs/14`.

## 3. Autenticación

**Decisión**: JWT propio, emitido por la API.

| Pieza | Decisión | Reversible |
|---|---|---|
| Tabla de usuarios | `users(id uuid pk, email citext unique, password_hash text, created_at)`. `profiles.id → users.id`. | Sí |
| Hash de contraseña | argon2id vía `pwdlib`. | Sí |
| Token de acceso | JWT HS256, 15 minutos, claims `sub` (user id), `bid` (business id), `role`. Secreto en `JWT_SECRET`. | Sí |
| Token de refresco | Opaco, 30 días, guardado hasheado en `refresh_tokens(id, user_id, token_hash, expires_at, revoked_at)`. Rotación en cada uso. | Sí |
| Almacenamiento en cliente | El `secureStorage` ya construido guarda el par de tokens. En web, `localStorage`; en iPhone, llavero troceado. Sin cambios. | — |
| Bloqueo por intentos | 5 fallos → 15 minutos, por email, en tabla `login_attempts`. Lo pedía `docs/04`. | Sí |
| Reset de contraseña | Token de un solo uso por email, 1 hora. | Sí |
| Invitaciones | La tabla `invitations` existente. La API crea el invito, manda el email con `SITE_URL/invito/<token>`; el invitado fija contraseña y la API crea `users` + `profiles` en una transacción. Ya no hace falta la política especial de la migración 0003 del plan viejo. | — |
| Envío de email | Interfaz `Mailer` con dos implementaciones: `ConsoleMailer` (imprime el enlace en el log; default) y `ResendMailer` (activa si existe `RESEND_API_KEY`). Las invitaciones funcionan en desarrollo sin proveedor. | Sí |

**Ruling**: sin registro público, como decía la spec original. Nadie crea cuenta sin invitación.

## 4. Permisos: la RLS sobrevive

**Decisión**: los permisos siguen viviendo en Postgres. La regla de la spec original —ningún permiso vive sólo en el cliente— se mantiene, y además ahora **tampoco vive sólo en la API**.

Mecanismo, el estándar fuera de Supabase:

1. La API se conecta como `fiestisima`, dueño de las tablas.
2. Existe un rol `app_user` (`NOLOGIN`) que reemplaza a `authenticated`. `fiestisima` es miembro de `app_user`.
3. Por cada request autenticado, la API abre una transacción y ejecuta:
   ```sql
   set local role app_user;
   set local app.user_id = '<uuid del sub>';
   ```
4. Las funciones `app_user_id()`, `app_business_id()` y `app_role()` reemplazan a `auth.uid()`, `auth_business_id()` y `auth_role()`. Leen `current_setting('app.user_id', true)`. Siguen siendo `security definer` por la misma razón de siempre: se llaman desde las políticas de `profiles`.
5. Al terminar la transacción, `set local` se deshace solo. No hay estado entre requests.

Porque `fiestisima` es dueño, **fuera** de `set local role` la RLS no aplica: ése es el equivalente del `service_role`. La API lo usa sólo en tres sitios, nombrados y comentados: aceptar una invitación (crear `users` + `profiles`), el login (leer `users.password_hash`), y el runner de migraciones. Nada más corre como dueño.

`anon` desaparece: un request sin token válido lo rechaza la API con 401 antes de tocar la base.

Sustituciones mecánicas sobre `0002_rls.sql`:
- `to authenticated` → `to app_user`
- `auth.uid()` → `app_user_id()`
- `auth_business_id()` / `auth_role()` → `app_business_id()` / `app_role()`
- Todo lo que hablaba de `anon` se elimina.
- El disparador: `auth.uid() is not null` → `app_user_id() is not null`. Misma semántica: como dueño (migraciones, aceptar invito) la variable no está y el disparador no se activa.

## 5. La API

**Stack**: Python 3.12 (Railway's default; 3.14 local funciona pero se fija 3.12 para producción), FastAPI, pydantic v2, **psycopg 3 asíncrono con `psycopg_pool`**, SQL a mano. Sin ORM: el esquema es SQL-first, las vistas y la RLS viven en la base, y un ORM pelearía con eso.

**Ruling**: sin ORM. Reversible pero caro de revertir después.

Estructura, un módulo por dominio como en el cliente:

```
api/
├── pyproject.toml            uv; deps fijadas
├── Dockerfile                python:3.12-slim
├── railway.json              pre-deploy: migrate; healthcheck /health
├── migrations/               los .sql, numerados; el runner los aplica en orden
│   ├── 0001_init.sql         del actual, con users en vez de auth.users
│   └── 0002_rls.sql          del actual, con las sustituciones de la sección 4
├── scripts/migrate.py        aplica pendientes, registra en schema_migrations
└── app/
    ├── main.py               FastAPI, routers, CORS, /health
    ├── config.py             settings desde env
    ├── db.py                 pool; `as_user(user_id)` abre la tx con set local
    ├── security.py           argon2, JWT, dependencias `current_user`
    ├── mail.py               Mailer, ConsoleMailer, ResendMailer
    └── routers/
        ├── auth.py           login, refresh, logout, me, password reset
        ├── invitations.py    crear, aceptar
        ├── users.py          listar, cambiar rol, activar/desactivar
        ├── businesses.py     ver, editar
        └── products.py       CRUD del catálogo
```

Endpoints del Bloque 0 (los lotes y movimientos son del Bloque A; las tablas ya existen):

| Método | Ruta | Quién |
|---|---|---|
| POST | `/auth/login` | público |
| POST | `/auth/refresh` | público con refresh token |
| POST | `/auth/logout` | autenticado |
| GET | `/auth/me` | autenticado → perfil + negocio |
| POST | `/auth/password/forgot`, `/auth/password/reset` | público |
| POST | `/invitations` | titolare |
| GET | `/invitations/{token}` | público → nombre y negocio, para la pantalla |
| POST | `/invitations/{token}/accept` | público |
| GET | `/users` · PATCH `/users/{id}` | titolare |
| GET, PATCH | `/businesses/me` | autenticado / titolare |
| GET, POST | `/products` · GET, PATCH `/products/{id}` | todos leen; titolare y responsabile escriben |
| GET | `/health` | público; comprueba la base |

La autorización fina la hace la RLS. La API sólo traduce el error de Postgres (42501, RLS violation) a 403, y las violaciones de unicidad (23505) a 409 con el mensaje italiano que ya existe en `src/i18n/it.ts` para el código de barras duplicado.

**Tipos para el cliente**: `openapi-typescript` genera `src/types/api.ts` desde `/openapi.json`. Reemplaza al `supabase gen types`. Misma regla: prohibido tipar a mano lo que la API ya define.

## 6. El cliente

- Se elimina `@supabase/supabase-js`. Entra `src/lib/api.ts`: un `fetch` tipado con los tipos generados, que adjunta el token de acceso y, ante 401, intenta un refresh una vez y reintenta.
- `src/features/auth/` habla con `/auth/*`. `useSession` conserva su forma pública (`session`, `profile`, `isLoading`) para que las pantallas ya planificadas no cambien.
- TanStack Query se conserva.
- Las pantallas del plan viejo (login, invito, tabs, catálogo) se construyen igual; sólo cambia la capa de datos debajo.

## 7. Despliegue

Tres servicios en `faithful-commitment`, junto a cauce:

| Servicio | Fuente | Detalle |
|---|---|---|
| `fiestisima-db` | imagen `postgres-ssl:18` de Railway | **Ya existe.** Volumen 50 GB, ams, PITR disponible. Proxy TCP abierto para migrar y testear desde fuera durante el Bloque 0; se cierra al final. |
| `fiestisima-api` | GitHub `Mkdir-arg/fiestisima`, rootDirectory `api` | Dockerfile. Pre-deploy `python scripts/migrate.py`. Healthcheck `/health`. Variables: `DATABASE_URL` (referencia a `fiestisima-db`), `JWT_SECRET`, `SITE_URL`, `CORS_ORIGINS`, `RESEND_API_KEY` opcional. |
| `fiestisima-web` | GitHub, rootDirectory `.` | `npx expo export -p web` → `dist/`, servido por `serve` con fallback a `index.html`. Variable `EXPO_PUBLIC_API_URL`. |

El repo local se empuja a `origin` (existe y está vacío). Rama `main`.

**Respaldos**: activar PITR en `fiestisima-db` desde la pestaña Backups. Es la respuesta definitiva a la pregunta abierta de `docs/14`. Se hace en la última tarea del bloque y se documenta.

## 8. Qué se prueba

- **pytest** contra `fiestisima-db` por el proxy (`DATABASE_URL` en `.env.test`, nunca commiteado). Cada test crea su negocio y sus usuarios y los borra.
- La suite de permisos de `tests/rls.integration.test.ts` se **traduce** a pytest, no se reinventa: las 45 invariantes son las mismas. Se ejercitan por dos vías: a través de la API con tokens de cada rol, y directo en la base con `as_user()` para la matriz de privilegios por columna.
- Los tests de Jest del cliente siguen. `useSession.test.tsx` se escribe contra `src/lib/api.ts` mockeado.
- CI: GitHub Actions corre `npm test`, `npm run typecheck`, `pytest` (con la base real vía secreto) en cada push.

## 9. Bloque 0 v2: cuándo está terminado

1. Un invitado por email completa el alta y entra, en web y en el iPhone.
2. Los tres roles se aplican en la base: un operatore que llame a la API directamente no recibe `unit_price`; un operatore no puede cambiar su propio rol.
3. El esquema completo está migrado por el pre-deploy de la API; las vistas de stock devuelven números correctos.
4. `fiestisima-api` y `fiestisima-web` viven en Railway con URL estable; la web se instala en el iPhone desde Safari.
5. El catálogo se lista, crea y edita desde los dos dispositivos.
6. PITR activo en `fiestisima-db`.
7. `docs/14` describe esta arquitectura y no la anterior.
