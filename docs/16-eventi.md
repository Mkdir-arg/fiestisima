# 16 · Eventi (Bloque B)

Este documento es distinto de los demás: en vez de especificar una funcionalidad, dice honestamente qué se sabe del Bloque B y qué falta decidir. Escribir esto con preguntas abiertas vale más que inventar respuestas que después haya que deshacer.

## Qué es un evento

El negocio es un salón de fiestas con cocina, en Italia (ver doc 01). El salón se alquila con cocina o sin cocina; cuando va con cocina, el catering lo da el negocio. Un evento es una fiesta reservada en el salón — una boda, un cumpleaños, una comunión — con una fecha, una cantidad de cubiertos y, si lleva catering, el consumo de mercadería que genera.

El evento es el "paso adelante" de la trazabilidad: la Reg. CE 178/2002 pide poder decir, hacia atrás, de qué fornitore vino cada lote (eso ya lo resuelve el modelo del Bloque A), y hacia adelante, qué se hizo con él. En un negocio de mostrador el paso adelante es difuso — un cliente cualquiera, un día cualquiera. En un salón que hace catering, el paso adelante tiene nombre y fecha: si hay una intoxicación en la boda del 12 de marzo, la pregunta de la ASL es qué lotes se usaron ese día, y el evento es la única respuesta posible.

## El puente con la mercadería

Una sola conexión conecta los dos subsistemas: un `scarico_uso` o `scarico_vendita` puede apuntar a un evento (`movements.event_id`). Con eso alcanza para cerrar la trazabilidad hacia adelante y, de paso, para saber cuánto costó en mercadería cada fiesta. No hay más acoplamiento que ése — el Bloque A no necesita saber nada de agenda, presupuestos ni clientes para funcionar.

## Qué existe hoy

La tabla `events` entra completa desde la primera migración (`supabase/migrations/0001_init.sql`), aunque la pantalla que la llena se construya mucho después: migrar una tabla con datos reales es caro, crearla vacía es gratis. Hoy tiene estos campos:

| Campo | Tipo | Nota |
|---|---|---|
| `id` | uuid | |
| `business_id` | uuid | multi-tenant, como el resto del esquema |
| `name` | text | por ejemplo `Matrimonio Rossi` |
| `event_date` | date | |
| `guests` | int | cubiertos; si se informa, tiene que ser mayor a 0 |
| `with_kitchen` | bool | con cocina (catering propio) o sólo alquiler de sala |
| `status` | text | hoy sólo acepta `previsto` y `concluso` — una restricción `check`, no una lista abierta |
| `client_name` | text | nullable |
| `notes` | text | nullable |

Nada de esto tiene todavía una pantalla en `app/` ni un `src/features/events/`. RLS ya cubre la tabla igual que al resto del esquema (doc 02): cualquiera con sesión la lee, sólo titolare y responsabile la escriben (ver `supabase/migrations/0002_rls.sql`).

## Preguntas abiertas

El riesgo del Bloque B es más alto que el del Bloque A precisamente porque estas preguntas no están cerradas. Ninguna tiene todavía una respuesta que valga la pena documentar como regla:

- **Disponibilidad y doble reserva.** ¿Un salón, una fecha? ¿Se permite más de un evento el mismo día si son turnos distintos (mediodía / noche)? ¿Cómo se ve el calendario y quién lo edita.
- **Presupuesto.** Cómo se arma, si tiene ítems editables o es un monto libre, si depende de los cubiertos y de si lleva cocina, y si convive con precios de mercadería (`unit_price` en `lots`) o es un número aparte.
- **Seña y saldo.** Si hay seña obligatoria, cómo se registra el pago, y qué pasa con el saldo cuando el evento se concluye o se cancela.
- **Estados del evento.** Hoy sólo existen `previsto` y `concluso`, lo mínimo para no bloquear nada. Falta decidir toda la lista real: ¿hay `confirmado` entre "previsto" y "concluso"? ¿Existe `cancelado`? ¿Qué pasa con los movimientos que ya apuntan a un evento si éste se cancela — se quedan huérfanos de sentido pero no de referencia, porque `movements.event_id` tiene `on delete restrict` justamente para que un evento con movimientos encima no se pueda borrar?

## Qué no es todavía

Este documento no define Objetivo, Flujo, Reglas, Casos borde ni Criterios de aceptación como el resto de la documentación funcional (ver `docs/README.md`) porque el Bloque B no está especificado — eso es trabajo de diseño futuro, no de esta tarea. Cuando se aborde, la especificación completa reemplaza este documento o lo convierte en uno con esa estructura.
