# 10 · Fornitori

## Objetivo
Saber de quién vino cada lote (obligación legal) y tener a mano el contacto para pedir.

## Ficha
| Campo | Obligatorio |
|---|:-:|
| Nombre | ✓ |
| Teléfono (para WhatsApp) | — |
| Email | — |
| Partita IVA | — |
| Dirección | — |
| Notas (días de entrega, condiciones) | — |

## Alta
- Desde `Fornitori → Nuovo`, o inline desde `Registra carico → Fornitore → Nuovo fornitore…` (solo nombre; el resto se completa después).
- Nombre único por negocio. Si se escribe uno parecido a uno existente (`Metro` vs `Metro Pescara`) se sugiere el existente.

## Lista
Nombre, cantidad de productos comprados, último carico, botón WhatsApp si hay teléfono.

## Detalle
- Datos de contacto con acciones (llamar, WhatsApp, email).
- `Prodotti forniti`: qué productos se le compraron, cuántas veces, último precio (según rol).
- `Ultimi carichi`: cronológico con lote y cantidad.
- `Ordini`: listas de compra enviadas a ese fornitore.

## Baja
`Disattiva`. No aparece en el selector de carico, pero los lotes históricos siguen mostrándolo. Un fornitore con lotes no puede borrarse.

## Fusión (fase 2)
Si se crearon dos fornitori que son el mismo, `Unisci` mueve todos los lotes al que queda y desactiva el otro.

## Criterios de aceptación
- Crear un fornitore inline durante un carico no interrumpe el flujo más de una pantalla.
- Desde la ficha del fornitore se responde en un vistazo "¿qué le compré el último mes?".
