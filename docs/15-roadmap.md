# 15 · Roadmap

## Bloque 0 — Fundaciones (terminado)

Lo que hay hoy en el repo y en Railway, no un plan. El backend cambió de Supabase a una API propia en FastAPI a mitad de este bloque (ver [`docs/superpowers/specs/2026-09-20-backend-fastapi-design.md`](superpowers/specs/2026-09-20-backend-fastapi-design.md)); lo que sigue es el resultado final.

- [x] Esquema completo (`api/migrations/0001_init.sql`): negocios, perfiles, productos, lotes, movimientos, proveedores, invitaciones, vistas de stock — multi-negocio desde el día uno
- [x] Permisos por Row Level Security (`0002_rls.sql`): las 19 políticas del diseño original, con `unit_price`/`document_url` de `lots` ocultos a `operatore` por privilegio de columna, no por la interfaz (ver doc 14)
- [x] API en FastAPI: auth (login, refresh, logout, `/me`, reset de contraseña), invitaciones, usuarios, negocio, catálogo de productos
- [x] JWT propio (access 15 min, refresh opaco rotativo de 30 días), argon2id, bloqueo de 5 intentos / 15 minutos
- [x] Sin registro público: el primer titolare de un negocio se crea fuera de banda con `api/scripts/bootstrap.py` (modo dueño, imprime una contraseña generada una sola vez)
- [x] Capa de datos del cliente: `src/lib/api.ts` (fetch tipado desde `openapi-typescript`, reintento de refresh ante 401), `tokenStorage`, `useSession`
- [x] Pantallas: `Accedi`, aceptar invitación, shell con tabs, catálogo de productos (lista, alta, edición)
- [x] Deploy en Railway: `fiestisima-db` (Postgres 18), `fiestisima-api` (Docker), `fiestisima-web` (Expo export servido por `serve`, instalable como PWA)
- [x] CI en GitHub Actions: typecheck + Jest del cliente, pytest de la API contra Postgres real con migraciones aplicadas dos veces
- [x] PITR activo y verificado en `fiestisima-db` — cierra la pregunta de respaldos que quedaba abierta con Supabase

Pendiente de este bloque, sin bloquear el siguiente: enlazar la cuenta de GitHub de la dueña con Railway para que el deploy sea automático en cada push (hoy es manual, `railway up`).

## Bloque A — Mercadería (siguiente)
- [ ] Escaneo de código de barras + alta rápida con Open Food Facts
- [ ] Lotes: registrar carico completo (lote, scadenza, fornitore, cantidad, precio, foto DDT)
- [ ] Scarico y scarto con FEFO
- [ ] Scadenze con agrupación y umbral configurable, push de resumen diario y alertas
- [ ] Stock, mínimos, `Sotto scorta`
- [ ] Fornitori: ABM e historial
- [ ] Registro de trazabilidad con filtros + PDF

## Bloque B — Eventos
- [ ] Modelo y flujo de eventos (ver doc 16)
- [ ] Vínculo entre eventos y movimientos de mercadería

Al final de A y B: TestFlight / instalación real con la dueña. **Meta: una semana de uso real registrando todo lo que entra, en lugar del cuaderno.**

## Más adelante
Sin fecha ni orden fijado; se prioriza cuando termine el Bloque B.
- [ ] Dashboard web (ver doc 12)
- [ ] OCR de lote y fecha (requiere dev build, ver doc 06)
- [ ] Foto de fattura/DDT → carico múltiple
- [ ] QR interno imprimible para preparaciones propias y productos sfusi
- [ ] Modo escaneo continuo
- [ ] Lista de compra con WhatsApp Business API (confirmaciones automáticas)
- [ ] Registro de temperaturas HACCP (frigos y freezers, dos veces al día)
- [ ] Alérgenos por producto y por preparación
- [ ] Offline parcial con cola, después offline completo (ver doc 13)
- [ ] Excel
- [ ] Multi-negocio (misma app para otra attività)

## Criterio para pasar de bloque
La dueña usa la app en lugar del cuaderno durante una semana completa sin volver al papel. Si vuelve al papel, el bloque no terminó.
