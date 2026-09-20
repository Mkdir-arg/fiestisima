# 08 · Scadenze y notificaciones

## Objetivo
Que nada venza en el estante sin que alguien lo sepa antes.

## Pantalla `Scadenze`
Lista de lotes con stock > 0 y fecha de vencimiento, agrupados:
1. `Scaduti` (rojo) — con botón `Scarta` directo en la fila.
2. `Entro N giorni` (ámbar) — N = umbral configurado (7 por defecto).
3. `Entro 30 giorni` (gris).
4. Más allá no se muestra; hay un filtro `Tutti` si hace falta.

Cada fila: imagen, nombre, lote, fecha, cantidad, pill con días restantes. Tocar → ficha del lote.

Acciones rápidas por swipe: `Scarico`, `Scarta`.

## Notificaciones push
| Cuándo | A quién | Texto (ejemplo) |
|---|---|---|
| Resumen diario, 8:00 hora local | Titolare y Responsabile | `Buongiorno. 3 lotti scadono questa settimana, 1 è già scaduto.` |
| Un lote entra en `In scadenza` | Titolare y Responsabile | `Mozzarella fior di latte (lotto 0918) scade tra 7 giorni · 6 pz` |
| Un lote vence hoy | Todos los roles activos | `Oggi scade: Basilico fresco (lotto 0919)` |
| Producto pasa a `Sotto scorta` | Titolare y Responsabile | `Farina 00 sotto scorta: 1 su minimo 2` |

**Reglas**
- Las notificaciones se agrupan: si 5 lotes entran en scadenza el mismo día, es **una** notificación, no cinco.
- Cada usuario puede activar/desactivar cada tipo en `Impostazioni → Notifiche`. El resumen diario está activado por defecto.
- Se envían con Expo Push desde una función programada en Supabase (cron diario a las 7:55 y evaluación en cada carico).
- Tocar la notificación abre `Scadenze` (o el producto, si es una sola).
- Web: sin push; muestra el mismo resumen en el dashboard y un badge en el menú.

## Casos borde
- Producto sin vencimiento: nunca aparece ni notifica.
- Lote vencido con stock 0: no aparece (ya se consumió o descartó).
- Cambio de umbral: recalcula la lista al instante.

## Criterios de aceptación
- El resumen diario llega entre las 8:00 y 8:05 hora de Italia con las cifras correctas al momento del envío.
- Un lote que vence en 7 días exactos aparece en `Entro 7 giorni`, no en `Entro 30`.
- Desde `Scaduti`, descartar un lote toma dos toques (`Scarta` → motivo `Scaduto` ya seleccionado → `Conferma`).
