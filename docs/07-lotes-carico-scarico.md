# 07 · Lotes, carico y scarico

## Conceptos
- **Lote**: una partida de un producto que entró junta, del mismo fornitore, con el mismo código de lote y vencimiento.
- **Carico**: entrada. Crea un lote (o suma a uno existente idéntico) y un movimiento `+`.
- **Scarico**: salida por uso o venta. Movimiento `−` sobre un lote.
- **Scarto**: salida por descarte. Movimiento `−` con motivo obligatorio.

## Registra carico
**Flujo**
1. Se llega desde el escaneo (producto ya cargado) o desde la ficha del producto.
2. Formulario:
   - `Lotto` (texto, obligatorio, con icono OCR)
   - `Scadenza` (fecha, obligatoria si el producto tiene vencimiento, con icono OCR)
   - `Fornitore` (selector; preseleccionado el último usado para ese producto; opción `Nuovo fornitore…` inline)
   - `Quantità` (stepper ±, obligatoria, en la unidad del producto; para kg/l acepta decimales)
   - `Prezzo unitario` (opcional; oculto para operatore)
   - `Documento` (opcional; foto del DDT/fattura, se guarda en Storage y se linkea al lote)
   - `Note` (opcional)
3. Botón principal `Registra e scansiona il prossimo` → guarda y vuelve a la cámara. Secundario `Registra e chiudi`.

**Reglas**
- Si ya existe un lote del mismo producto + mismo `lot_code` + misma `expires_on` + mismo fornitore, **no se crea otro**: se agrega el movimiento al existente.
- Fecha de vencimiento anterior a hoy → advertencia, pero se permite (puede ser un registro tardío). Queda marcado en Scadenze como vencido.
- Cantidad 0 → no se puede guardar.
- El último fornitore y el último precio se recuerdan por producto para preseleccionar la próxima vez.
- Feedback al guardar: vibración + toast `Carico registrato · +24 pz` durante 2 s. Sin pantalla de confirmación que frene el ritmo.

## Scarico
**Flujo**
1. Desde ficha de producto (`Scarico`) o desde el escaneo.
2. La app propone el lote según **FEFO** (First Expired, First Out): el que vence primero con stock > 0. Se muestra `Lotto 0817B · scade tra 6 giorni · 4 pz` y se puede cambiar de lote tocando.
3. Cantidad (por defecto 1, o toda la existencia del lote con `Tutto`).
4. Tipo: `Uso` (cocina/producción) o `Vendita`. Se recuerda el último elegido.
5. `Conferma`.

**Reglas**
- No se puede descargar más de lo que tiene el lote. Si la cantidad supera el lote propuesto, la app ofrece repartir en los siguientes lotes FEFO (`Prendi 4 dal lotto 0817B e 2 dal lotto L2311C`).
- Si el lote está vencido, se advierte en rojo: `Questo lotto è scaduto` con la opción de pasar a `Scarto`.

## Scarto
Igual que scarico pero:
- `Motivo` obligatorio, selector: `Scaduto`, `Danneggiato`, `Non conforme`, `Errore di carico`, `Altro` (con texto).
- Opcional: foto de evidencia.
- Aparece en el registro con etiqueta propia y en el reporte mensual de scarti (doc 11). La ley pide poder demostrar qué pasó con lo que no se usó.

## Anulación
- Todo movimiento puede anularse dentro de las 24 h por quien lo hizo, y en cualquier momento por titolare/responsabile.
- Anular crea el movimiento inverso con `reason = annullamento` y referencia al original. Ambos quedan visibles en el historial, el original tachado.

## Ficha del lote
Se abre tocando un lote en la ficha del producto: código, scadenza, fornitore, fecha de recepción, quién lo cargó, documento adjunto, stock actual, línea de tiempo de movimientos.

## Estados de un lote (derivados, no guardados)
| Estado | Condición | Color |
|---|---|---|
| `OK` | stock > 0 y vence en más de 7 días | verde |
| `In scadenza` | stock > 0 y vence en ≤ 7 días | ámbar |
| `Scaduto` | stock > 0 y `expires_on < hoy` | rojo |
| `Esaurito` | stock = 0 | gris; se oculta de la lista por defecto |

Los 7 días son configurables por negocio (`Impostazioni → Soglia di avviso`), con presets 3 / 7 / 14.

## Criterios de aceptación
- Carico completo con OCR exitoso: menos de 30 segundos por producto.
- Dos caricos idénticos consecutivos no generan dos lotes.
- Un scarico mayor al stock del lote propuesto ofrece el reparto FEFO y nunca deja un lote en negativo.
- Un scarto sin motivo no se puede guardar.
