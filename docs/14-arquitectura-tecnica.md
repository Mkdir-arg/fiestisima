# 14 · Arquitectura técnica

Supabase se descartó durante el Bloque 0 (ver [`docs/superpowers/specs/2026-09-20-backend-fastapi-design.md`](superpowers/specs/2026-09-20-backend-fastapi-design.md)). Lo que sigue es lo que existe hoy en el repo y en Railway, no un plan.

## Stack

| Capa | Elección | Por qué |
|---|---|---|
| App + web | **Expo SDK 57** (React Native + `react-native-web`), universal: mismo código para iPhone y navegador | Expo Router da URLs reales en web y un único árbol de pantallas |
| Lenguaje del cliente | TypeScript en modo estricto | El tipado de la API se genera, no se escribe a mano (ver más abajo) |
| Backend | **FastAPI** propia (Python 3.12) | Reemplaza a Supabase; corre en Railway junto al resto de la infraestructura de la dueña |
| Validación / esquemas | **pydantic v2** | Modelos de entrada y salida de cada router |
| Acceso a la base | **psycopg 3, asíncrono**, con `psycopg_pool`, **SQL escrito a mano** | Sin ORM: el esquema es SQL-first, las vistas de stock y las políticas de RLS viven en la base, y un ORM pelearía con eso. Decisión reversible pero cara de revertir |
| Base de datos | **Postgres 18** | Imagen oficial de Railway (`postgres-ssl:18`) |
| Gestor de paquetes Python | **uv** | Lockfile (`uv.lock`), entorno reproducible en Docker y en local |
| Infraestructura | **Railway**, proyecto `faithful-commitment` | El mismo proyecto donde vive `cauce`, el otro sistema de la dueña; un solo patrón de despliegue y de respaldo para los dos |

## Estructura del repo

```
fiestisima/
├── app/                  Rutas (Expo Router: el archivo ES la URL)
│   ├── (auth)/           accedi, invito/[token]
│   └── (app)/            área autenticada
│       └── (tabs)/       prodotti · scadenze · altro
├── src/
│   ├── features/         auth · products (más dominios a medida que avanza el roadmap)
│   ├── ui/                sistema de diseño, sin conocimiento del dominio (ver doc 17)
│   ├── lib/               api.ts (fetch tipado), tokenStorage, lotStatus
│   ├── i18n/it.ts         todos los textos, desde el día 1
│   └── types/api.ts       generado con openapi-typescript desde /openapi.json, nunca a mano
├── api/
│   ├── app/               main.py, config.py, db.py, security.py, mail.py, routers/
│   ├── migrations/        SQL numerado (0001…0006 al momento de escribir esto)
│   ├── scripts/           migrate.py (runner), bootstrap.py (primer titolare)
│   └── tests/             pytest, contra una base Postgres real
└── docs/                  Esta documentación
```

Misma regla de capas que antes: `app/` sólo compone (lee la ruta, arma la pantalla, cero lógica de negocio); `src/features/<dominio>/` tiene consultas, mutaciones y validación propias; `src/ui/` no sabe que existen los lotes.

## Los tres servicios en Railway

| Servicio | Qué es | Detalle |
|---|---|---|
| `fiestisima-db` | Postgres 18 | Volumen de 50 GB, región `ams`. PITR activo y verificado (ver Backups). |
| `fiestisima-api` | Docker, `python:3.12-slim` | Build con el `Dockerfile` del repo (`api/Dockerfile`). Pre-deploy corre `uv run python scripts/migrate.py` (aplica migraciones pendientes antes de que el contenedor nuevo reciba tráfico). Healthcheck en `/health`. |
| `fiestisima-web` | Expo exportado para web | `npx expo export -p web` genera `dist/`; se sirve con `serve -s dist`, con fallback a `index.html` para que las rutas de Expo Router funcionen al refrescar. Instalable como PWA desde Safari/Chrome ("Añadir a pantalla de inicio"). |

URLs en vivo: API `https://fiestisima-api-production.up.railway.app`, web `https://fiestisima-web-production.up.railway.app`.

## Seguridad: los permisos viven en Postgres, no en el cliente ni sólo en la API

Regla central, sin excepciones: ninguna decisión de acceso se toma en el cliente, y tampoco se toma exclusivamente en la API. La autorización fina la hace **Row Level Security** en la base, igual que en el diseño original con Supabase — sólo cambia el mecanismo que hace de puente porque ya no existe `auth.uid()` ni `PostgREST`.

**Cómo funciona:**
1. La API se conecta a Postgres como `fiestisima`, dueño de las tablas.
2. Existe un rol `app_user` (`NOLOGIN`), del que `fiestisima` es miembro.
3. En cada request autenticado, la API abre una transacción y ejecuta `set local role app_user` y `select set_config('app.user_id', '<uuid>', true)` con el `sub` del JWT. Al terminar la transacción, ese `set local` se deshace solo: no queda estado entre requests.
4. Las políticas de RLS llaman a tres funciones — `app_user_id()`, `app_business_id()`, `app_role()` — que leen `current_setting('app.user_id', true)` y resuelven el resto contra `profiles`. Son `security definer` porque las políticas de `profiles` las necesitan para resolverse a sí mismas.

**La API nunca decide autorización mirando el claim `role` del JWT.** Ese claim existe sólo para que la interfaz muestre u oculte botones; la palabra final siempre es de la política SQL evaluada con `app_role()` en el momento del request, no con lo que decía el token cuando se emitió (un token de 15 minutos puede sobrevivir a un cambio de rol o a una desactivación).

**Modo dueño (sin RLS)**: existen exactamente cinco sitios donde la API opera como `fiestisima` sin pasar por `app_user`, y ninguno más:
- login (necesita leer `users.password_hash`, tabla a la que `app_user` no tiene acceso);
- la vista previa y la aceptación de una invitación (crear `users` + `profiles` en una transacción, antes de que exista una identidad que asumir);
- la revocación de refresh tokens tras desactivar a un usuario (`PATCH /users/{id}`, en un bloque separado, después de que el cambio de rol/estado ya se aplicó como `app_user`);
- el runner de migraciones;
- `/health` (no hay identidad de llamador que fijar).

Cada uno está comentado en el código como `-- runs as owner:` con la razón. Función auxiliar: `as_owner()` en `api/app/db.py`, junto a `as_user(user_id)` para el camino normal.

**Columnas ocultas por privilegio, no por la interfaz.** `lots.unit_price` y `lots.document_url` no son legibles ni escribibles por `operatore`: la migración `0002_rls.sql` revoca `SELECT`/`UPDATE` sobre `lots` a nivel de tabla para `app_user` y los vuelve a conceder columna por columna, dejando esas dos afuera del `GRANT`. Un `operatore` que llame a la API directamente (sin pasar por la pantalla) recibe esas columnas en `null`, no un error — es el mismo comportamiento para cualquier cliente, no una regla de presentación.

**Un detalle no obvio: algunos rechazos dan 404 en vez de 403.** Cuando una fila está protegida sólo por una cláusula `USING` de RLS (sin `WITH CHECK` ni disparador) — por ejemplo, reenviar o cancelar una invitación ajena, o que alguien sin `titolare` intente `PATCH /businesses/me` — el `UPDATE`/`DELETE` simplemente no encuentra la fila: Postgres la filtra en el `USING` antes de que exista algo que modificar, `rowcount` da 0 y el router devuelve 404. Es deliberado: producir un 403 ahí exigiría que la API leyera `current_user.role` en Python para inferir "por qué" no hubo fila, y eso es justo lo que la regla de arriba prohíbe. Los casos donde sí falla con un error explícito (`INSERT` con `WITH CHECK`, o el disparador de cambio de rol) sí dan 403 porque Postgres los rechaza con una excepción (`42501`, mapeada por `main.py`), no con cero filas.

## Autenticación

| Pieza | Decisión |
|---|---|
| Identidad | Tabla `users` propia (`id`, `email citext`, `password_hash`). Reemplaza a `auth.users` de Supabase. |
| Hash de contraseña | argon2id, vía `pwdlib` |
| Token de acceso | JWT HS256, 15 minutos, claims `sub` (user id), `bid` (business id), `role`. Secreto en la variable `JWT_SECRET` (mínimo 32 caracteres, exigido al arrancar) |
| Token de refresco | Opaco, 30 días, guardado **hasheado** (SHA-256) en `refresh_tokens`; se rota en cada uso (el token usado queda revocado y se emite un sucesor) |
| Registro público | No existe. Nadie crea cuenta sin invitación (ver doc 04) |
| Bloqueo por intentos | 5 fallos de login → 15 minutos de bloqueo, por email, registrado en `login_attempts` |
| Envío de invitaciones y reset | Interfaz `Mailer` con dos implementaciones: `ConsoleMailer` (imprime el link en el log; default) y `ResendMailer` (se activa si existe `RESEND_API_KEY`) |

## Backups

**PITR (Point-in-Time Recovery) está activo y verificado en `fiestisima-db`.** Esto cierra la pregunta que dejaba abierta la versión anterior de este documento: el plan gratuito de Supabase no incluía backups automáticos y nunca se llegó a decidir una alternativa; en Railway, PITR se activó como parte del cierre del Bloque 0 y se comprobó en vivo (archivador de WAL saludable, primer backup base tomado, cobertura confirmada).

- **Cómo funciona**: Postgres archiva cada segmento de WAL de forma continua a un bucket de Railway, más un backup completo semanal y uno diferencial cada día.
- **Retención**: se conservan los últimos 4 backups completos (uno por semana, con sus diferenciales diarios), lo que da una ventana de restauración de aproximadamente 4 semanas. No se puede restaurar a un momento anterior a cuando se activó PITR.
- **Cómo restaurar**: desde la pestaña **Backups** del servicio en el dashboard de Railway, eligiendo una fecha/hora en el selector de PITR; o por CLI con `railway postgres pitr restore --service fiestisima-db --at <timestamp>`. En ambos casos Railway crea un servicio nuevo (`fiestisima-db-restored-...`) con los datos al momento elegido; el servicio original sigue sirviendo tráfico sin tocarse. El cambio de conexión (apuntar la API al restaurado) es un paso manual posterior.
- `railway postgres pitr status --service fiestisima-db` muestra la salud del archivador y la ventana de cobertura disponible en cualquier momento.

## Entornos y secretos

| Entorno | Dónde vive la config |
|---|---|
| Cliente en desarrollo | `.env.local` en la raíz (gitignored). Variable clave: `EXPO_PUBLIC_API_URL`. |
| API en tests | `api/.env.test` (gitignored). `DATABASE_URL` apunta a una base real (ver CI más abajo), nunca mockeada. |
| API y web en producción | Variables de Railway por servicio: `DATABASE_URL` (referencia a `fiestisima-db`), `JWT_SECRET`, `SITE_URL`, `CORS_ORIGINS`, `RESEND_API_KEY` (opcional) en la API; `EXPO_PUBLIC_API_URL` en la web. |

Nada secreto se commitea: contraseñas, `JWT_SECRET` y cualquier cadena de conexión con credenciales quedan fuera del repo y de esta documentación.

## CI

`.github/workflows/ci.yml` corre en cada push, dos jobs independientes:

- **`client`**: `npm ci`, `npm run typecheck`, `npm test` (Jest, con `EXPO_PUBLIC_API_URL` fijo para que `src/lib/api.ts` no falle al importarse).
- **`api`**: levanta un contenedor `postgres:18` como servicio de GitHub Actions (misma versión mayor que `fiestisima-db`, necesaria porque la suite usa `citext`), corre `uv sync --frozen`, aplica las migraciones **dos veces seguidas** (para probar que son idempotentes) y corre `pytest`. La suite se conecta como dueño de las tablas, igual que la API en producción; cada test dentro crea su propio negocio y usuarios y los borra.

## Cómo se despliega

La API y la web se construyen desde este mismo repo en Railway (`fiestisima-api` con `rootDirectory: api`, `fiestisima-web` con `rootDirectory: .`). El despliegue automático al hacer push a GitHub requiere enlazar la cuenta de GitHub de la dueña con el workspace de Railway (Icore) — **todavía pendiente**: hoy los pushes no disparan un deploy solos. Mientras tanto, un despliegue se hace a mano con `railway up --service <servicio>` desde el repo.
