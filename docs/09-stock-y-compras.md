# 09 · Stock y compras

## Cálculo de stock
- Stock de un lote = Σ movimientos `carico` − Σ movimientos `scarico_*` y `scarto`.
- Stock de un producto = Σ stock de sus lotes.
- Se calcula con las vistas `lot_stock` y `product_stock`. La app nunca escribe un número de stock.
- Valor del stock (solo titolare/responsabile) = Σ (stock del lote × precio unitario del lote). Lotes sin precio se excluyen y se indica `(2 lotti senza prezzo)`.

## Stock mínimo
- Por producto, en su unidad. 0 = sin control.
- Cuando `stock < min_stock` el producto pasa a `Sotto scorta`: aparece en el filtro, en el dashboard y dispara la notificación (doc 08).
- Se vuelve a evaluar en cada movimiento.

## Inventario físico (`Inventario`)
Para corregir la realidad cuando el cuaderno y el estante no coinciden.

**Flujo**
1. `Prodotti → Inventario` (titolare/responsabile).
2. Se recorre el catálogo (o una categoría / conservación) contando. Para cada producto se escanea o se busca y se ingresa la cantidad real por lote.
3. Al confirmar, la app genera los movimientos de ajuste necesarios: `carico` con `reason = rettifica inventario` si sobra, `scarto` con motivo `Rettifica inventario` si falta.
4. Reporte de diferencias al final.

## Lista de compra (`Ordine suggerito`)
**Objetivo**: convertir los `Sotto scorta` en un pedido listo para mandar.

**Flujo**
1. Dashboard o `Prodotti → Sotto scorta → Crea ordine`.
2. La app agrupa los productos bajo mínimo **por fornitore** (el último usado para cada producto) y propone cantidad = `min_stock × 2 − stock`, redondeada hacia arriba a la unidad. Editable.
3. Se pueden agregar productos que no están bajo mínimo.
4. Por fornitore, botón `Invia su WhatsApp`: abre WhatsApp con el mensaje prearmado:
   ```
   Buongiorno, ordine per [NOME ATTIVITÀ]:
   • Farina 00 25 kg × 2
   • Olio EVO 5 L × 2
   Grazie!
   ```
   También `Copia` y `Email`.
5. La lista se guarda con estado `Inviato`. Cuando llega la mercadería y se hace el carico, los productos se marcan como recibidos; la lista pasa a `Ricevuto` cuando todos lo están.

**Reglas**
- En el MVP el envío es por el WhatsApp del teléfono (`wa.me/<telefono>?text=…`), no por la API de WhatsApp Business. La API queda para fase 2 si se quiere automatizar confirmaciones.
- Un fornitore sin teléfono → solo `Copia` y `Email`.

## Criterios de aceptación
- El stock mostrado coincide siempre con la suma de movimientos (test automático sobre la vista).
- Un inventario de 50 productos se completa en menos de 15 minutos y deja el registro cuadrado.
- La lista de compra agrupa correctamente por último fornitore y abre WhatsApp con el texto completo.
