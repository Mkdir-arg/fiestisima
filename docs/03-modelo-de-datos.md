# 03 · Modelo de datos

Implementado en `supabase/migrations/0001_init.sql`. Este documento explica el **porqué**.

## Entidades
```
businesses ──< profiles (rol)
    │      ──< invitations
    │      ──< suppliers
    │      ──< categories
    └──────< products ──< lots ──< movements
```

| Entidad | Qué representa | Campos clave |
|---|---|---|
| `businesses` | El negocio (attività). Multi-tenant desde el día 1 para poder dar la app a otro negocio después. | `name` |
| `profiles` | Usuario del sistema, 1:1 con `auth.users` de Supabase. | `role`, `active`, `business_id` |
| `invitations` | Invitación pendiente por email. | `email`, `role`, `accepted_at` |
| `suppliers` | Fornitore. | `name`, `phone`, `email` |
| `categories` | Categoría libre (Conserve, Latticini, Ortofrutta…). | `name` |
| `products` | Producto del catálogo. **No tiene stock**: el stock se calcula. | `barcode`, `unit`, `storage`, `min_stock`, `image_url` |
| `lots` | Una partida física de un producto que entró en una fecha con un lote y un vencimiento. | `lot_code`, `expires_on`, `supplier_id`, `unit_price`, `document_url` |
| `movements` | Cada entrada o salida de un lote. Es el **registro de trazabilidad**. | `type`, `quantity`, `reason`, `created_by` |

## Decisiones
1. **El stock no se guarda, se calcula.** `stock del lote = Σ carico − Σ scarico`. Vistas `lot_stock` y `product_stock`. Así el stock nunca se desincroniza del registro y cualquier número se puede auditar.
2. **Un lote pertenece a un producto y a un fornitore.** Si el mismo producto viene de dos fornitori con el mismo código de lote, son dos filas en `lots`. La trazabilidad es por fornitore, no por código.
3. **Los movimientos son inmutables.** No hay `update` ni `delete` en `movements` (la política RLS solo permite `insert` y `select`). Anular = insertar el inverso con `reason = 'annullamento di <id>'`.
4. **`products.barcode` es único por negocio**, no global: dos negocios pueden tener el mismo EAN. Puede ser `null` para productos sin código (se les genera uno interno con prefijo `INT-`, ver doc 05).
5. **`unit`** es texto libre acotado a `pz | kg | l | g | ml`. La cantidad es `numeric`, no entero, porque el basilico se pesa.
6. **`expires_on` puede ser null** para productos sin vencimiento (sal, vinagre, artículos no alimentarios). Un lote sin fecha nunca aparece en Scadenze.
7. **`storage`** (frigo / freezer / dispensa) vive en el producto, no en el lote. Si un día hace falta por lote se mueve.

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
