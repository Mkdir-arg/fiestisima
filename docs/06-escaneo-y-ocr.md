# 06 · Escaneo y OCR

Es la funcionalidad central. Todo lo demás existe para que esto sea rápido.

## Pantalla `Scansiona`
Pantalla completa con la cámara. Tres modos en un selector superior:
1. `Codice a barre` (por defecto)
2. `Etichetta (OCR)`
3. `Fattura` (fase 2, se muestra deshabilitado con `Presto disponibile`)

Controles: cerrar, linterna, y en la parte inferior una hoja (bottom sheet) que muestra el resultado.

## Modo 1 — Código de barras
**Flujo**
1. La cámara detecta EAN-13, EAN-8, UPC-A, Code128 y QR (para códigos internos `INT-`).
2. Al leer, vibración corta + sonido, y la hoja inferior muestra el producto: imagen, nombre, conservación, stock actual, último fornitore.
3. Botones: `Carico` (va a Registra carico con el producto cargado), `Scarico`, `Vedi scheda e lotti`.
4. Si el código no existe → alta rápida (doc 05).

**Reglas**
- Se lee un código a la vez. Después de leer, la cámara pausa hasta que la usuaria toque `Scansiona un altro` o termine el carico. Evita lecturas dobles.
- Debounce de 1,5 s para el mismo código.
- Modo continuo (fase 2): escanear varios productos seguidos y cargar todos con el mismo fornitore y DDT.

**Casos borde**
- Código de peso variable (empieza con `2`, típico de carnicería/frutería): se reconoce el producto por los primeros 7 dígitos y se propone la cantidad en kg leída del código. Si no hay coincidencia, alta normal.
- Sin permiso de cámara → pantalla que explica y botón que abre Ajustes de iOS.
- Código parcialmente ilegible → nada pasa; no se inventa. Botón `Inserisci a mano` siempre visible.

## Modo 2 — Etiqueta (OCR)
**Objetivo**: no tipear lote ni fecha. Se enfoca la etiqueta y la app los lee.

**Flujo**
1. Desde `Registra carico`, el icono de cámara junto a `Lotto` o `Scadenza` abre la cámara en modo OCR.
2. Se enfoca la zona de la etiqueta con "L: 2409A / Da consumarsi entro 12/03/2027".
3. El texto reconocido se procesa en el dispositivo (ML Kit, sin enviar la foto a ningún servidor).
4. La app propone: `Lotto: L2409A` · `Scadenza: 12/03/2027`, cada uno con `Usa` o `Ripeti`.
5. Los valores aceptados se completan en el formulario, marcados con una nota `Letti dall'etichetta — controlla e conferma`.

**Reglas de extracción**
- Fechas: se aceptan `dd/mm/yyyy`, `dd.mm.yyyy`, `dd-mm-yy`, `mm/yyyy` (→ último día del mes), `dd MMM yyyy` en italiano e inglés. Si hay varias fechas, se toma la más lejana en el futuro (la más cercana suele ser la de producción o envasado).
- Lote: se busca después de `L`, `L:`, `LOT`, `LOTTO`, `Lot.`, `BATCH`. Si no hay etiqueta, se toma la cadena alfanumérica de 4-12 caracteres más cercana a la fecha.
- Nunca se guarda un valor OCR sin que la usuaria lo vea. **Siempre confirma.**
- Si la confianza es baja, el campo queda vacío y no se muestra propuesta.

**Casos borde**
- Etiqueta en relieve o troquelada (latas): el OCR falla seguido. Se avisa `Prova con più luce o inclina la lattina` y se ofrece teclado.
- Fecha ya pasada → advertencia amarilla `Questa data è già passata. Confermi?`

## Modo 3 — Fattura / DDT (fase 2)
Foto del documento de transporte → se detectan las líneas (descripción, cantidad, a veces lote) y se propone un carico múltiple para revisar. En el MVP solo se **adjunta la foto** al lote como evidencia (doc 07).

## Web
En web no hay cámara nativa. Se soporta lector USB: el campo de búsqueda recibe el código como texto + Enter y dispara el mismo flujo.

## Criterios de aceptación
- Escanear un EAN conocido y llegar a `Registra carico` con el producto cargado: menos de 3 segundos.
- OCR de una etiqueta impresa nítida: lote y fecha correctos en al menos 8 de 10 intentos con buena luz.
- Ningún valor OCR entra a la base sin confirmación explícita.
