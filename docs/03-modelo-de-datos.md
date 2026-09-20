# 03 · Modelo de datos

Implementado en `supabase/migrations/0001_init.sql` y `0002_rls.sql`. Este documento explica el **porqué**.

## Entidades
```
businesses ──< profiles (rol)
    │      ──< invitations
    │      ──< suppliers
    │      ──< categories
    │      ──< events
    └──────< products ──< lots ──< movements >──── events
```

| Entidad | Qué representa | Campos clave |
|---|---|---|
| `businesses` | El negocio (attività). Multi-tenant desde el día 1 para poder dar la app a otro negocio después. | `name` |
| `profiles` | Usuario del sistema, 1:1 con `auth.users` de Supabase. | `role`, `active`, `business_id` |
| `invitations` | Invitación pendiente por email. | `email`, `role`, `accepted_at` |
| `suppliers` | Fornitore. | `name`, `phone`, `email` |
| `categories` | Categoría libre (Conserve, Latticini, Ortofrutta…). | `name` |
| `events` | El evento (boda, cumpleaños…) al que se imputa el consumo — el "paso adelante" de la trazabilidad en un salón que hace catering. Ver doc 16. | `name`, `event_date`, `guests`, `with_kitchen`, `status` |
| `products` | Producto del catálogo. **No tiene stock**: el stock se calcula. | `barcode`, `unit`, `storage`, `min_stock`, `image_url` |
| `lots` | Una partida física de un producto que entró en una fecha con un lote y un vencimiento. | `lot_code`, `expires_on`, `supplier_id`, `unit_price`, `document_url`, `received_on` |
| `movements` | Cada entrada o salida de un lote. Es el **registro de trazabilidad**. | `type`, `quantity`, `reason`, `created_by`, `occurred_at`, `event_id` |

## Decisiones
1. **El stock no se guarda, se calcula.** `stock del lote = Σ carico − Σ scarico`. Vistas `lot_stock` y `product_stock`. Así el stock nunca se desincroniza del registro y cualquier número se puede auditar.
2. **Un lote pertenece a un producto y a un fornitore.** Si el mismo producto viene de dos fornitori con el mismo código de lote, son dos filas en `lots`. La trazabilidad es por fornitore, no por código.
3. **Los movimientos son inmutables.** No hay `update` ni `delete` en `movements` (la política RLS solo permite `insert` y `select`). Anular no inserta un tipo opuesto: inserta OTRO movimiento del **mismo `type`** que el original, con `reverses_id` apuntando a él. La vista `lot_stock` decide el signo comparando el tipo con si el movimiento es una reversión (`(type = 'carico') <> (reverses_id is not null)`), así el stock queda bien y los informes pueden netear el original contra su anulación — ver doc 07.
4. **`products.barcode` es único por negocio**, no global: dos negocios pueden tener el mismo EAN. Puede ser `null` para productos sin código (se les genera uno interno con prefijo `INT-`, ver doc 05).
5. **`unit`** es texto libre acotado a `pz | kg | l | g | ml`. La cantidad es `numeric`, no entero, porque el basilico se pesa.
6. **`expires_on` puede ser null** para productos sin vencimiento (sal, vinagre, artículos no alimentarios). Un lote sin fecha nunca aparece en Scadenze.
7. **`storage`** (frigo / freezer / dispensa) vive en el producto, no en el lote. Si un día hace falta por lote se mueve.
8. **`movements.event_id`** conecta un `scarico_uso` o `scarico_vendita` con el evento que consumió la mercadería. Es nullable: mientras el Bloque B (agenda de eventos) no exista, queda vacío y no molesta. La tabla `events` entra completa desde la primera migración aunque su pantalla se construya mucho después — migrar una tabla con datos reales es caro, crearla vacía es gratis.
9. **`movements.occurred_at`**, separado de `created_at`, es cuándo pasó en el piso; `created_at` es cuándo se sincronizó. Los movimientos se encolan sin conexión (`client_id` es la idempotencia de esa cola) y pueden sincronizarse horas o días después: sin esta separación, un scarico hecho el martes y sincronizado el viernes figuraría como viernes en el registro legal.
10. **`lots.received_on`** usa la fecha calendario de Roma, no UTC (`(now() at time zone 'Europe/Rome')::date`). El negocio está en Italia; con UTC, un carico cargado de madrugada quedaría fechado el día anterior en un registro que se contrasta contra papel.
11. **Las referencias entre tablas del mismo negocio son claves foráneas compuestas** contra `(id, business_id)` del padre (con `unique (id, business_id)` en cada padre), no sólo contra `id`. Así la base misma impide, y no sólo la política RLS, que un movimiento o un lote queden cosidos a una fila de otro negocio aunque alguien conozca su UUID.

## Tipos de movimiento
| `type` | Signo | Cuándo |
|---|:-:|---|
| `carico` | + | Entra mercadería |
| `scarico_uso` | − | Se usa en producción / cocina |
| `scarico_vendita` | − | Se vende tal cual |
| `scarto` | − | Se descarta (vencido, roto, no conforme). `reason` obligatorio |

## Reglas de integridad
- `quantity > 0` siempre; el signo lo da el tipo.
- No se puede descargar más de lo que hay en el lote. Se valida en el cliente y con un trigger en el backend (fase 1.1; en el MVP solo cliente).
- Un producto con lotes no se borra: se marca `active = false` y desaparece del catálogo, no del historial.
