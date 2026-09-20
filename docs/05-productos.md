# 05 · Productos (catálogo)

## Objetivo
Tener un catálogo que se arma solo a medida que se escanea, sin que la dueña tenga que cargar 150 productos a mano.

## Ficha de producto
| Campo | Obligatorio | Notas |
|---|:-:|---|
| Nombre | ✓ | Ej. `Pomodori pelati 400 g` |
| Código de barras | — | EAN-13 / EAN-8 / QR interno. Único por negocio |
| Marca | — | |
| Categoría | — | Lista editable |
| Unidad | ✓ | `pz` por defecto; `kg`, `l`, `g`, `ml` |
| Conservación | ✓ | `Frigo` / `Freezer` / `Dispensa` |
| Stock mínimo | ✓ | 0 por defecto. Debajo de este valor aparece en `Sotto scorta` |
| Tiene vencimiento | ✓ | Sí por defecto. Si no, el carico no pide fecha |
| Imagen | — | Foto propia o la que trae Open Food Facts |
| Precio de referencia | — | Se actualiza con el último carico. Oculto para operatore |

## Alta rápida desde el escaneo
**Flujo**
1. Se escanea un código que no existe en el catálogo.
2. La app consulta **Open Food Facts** (`/api/v2/product/<ean>.json`).
3. Si hay resultado: pantalla `Nuovo prodotto` prellenada con nombre, marca e imagen. La usuaria ajusta y confirma → sigue directo al carico.
4. Si no hay resultado o no hay internet: misma pantalla vacía con el código ya cargado.

**Reglas**
- Open Food Facts es una ayuda, no una fuente de verdad: todo lo que trae es editable y se guarda en nuestra base. Nunca se vuelve a consultar para un producto ya creado.
- La imagen de OFF se descarga y se guarda en Supabase Storage (no se linkea a OFF).
- Timeout de la consulta: 3 segundos. Si falla, se sigue sin bloquear.

## Productos sin código de barras
Preparaciones propias (ragù, salsas), productos a granel (basilico, carne del carnicero) y algunos artículos de fornitori pequeños no tienen EAN.

- Al crear un producto sin código, la app genera uno interno: `INT-` + 8 caracteres. Se marca `is_internal_code = true`.
- Se puede imprimir como etiqueta QR (fase 2). En el MVP se busca por nombre.

## Lista de productos (`Prodotti`)
- Búsqueda por nombre o código (búsqueda incremental, también con lector USB en web).
- Filtros: `Tutti`, `Sotto scorta`, `Frigo`, `Freezer`, `Dispensa`, por categoría.
- Cada fila: imagen, nombre, categoría, cantidad de lotes activos, próxima scadenza, stock actual vs mínimo (en rojo si está debajo).
- Orden por defecto: alfabético. Alternativas: por stock, por próxima scadenza.

## Detalle de producto (`Prodotto`)
- Cabecera: imagen, nombre, categoría, conservación, código.
- Tres números: stock, mínimo, lotes activos.
- Pestañas: `Lotti` (ordenados FEFO, ver doc 07) · `Movimenti` (cronológico) · `Fornitori` (de quién se compró, cuántas veces, último precio si el rol lo permite).
- Botones fijos abajo: `Carico`, `Scarico`, `Scarto`.

## Edición y baja
- Editar: cualquier campo salvo el código de barras si ya tiene lotes (para no romper la trazabilidad). Si el código estaba mal, se crea un producto nuevo y se desactiva el viejo.
- Baja: `Disattiva`. El producto desaparece de listas y del escaneo, pero sus lotes y movimientos siguen en el registro. Se puede reactivar.
- Duplicados: si se intenta crear un producto con un código existente → `Questo codice è già associato a "<nombre>"` con link al producto.

## Criterios de aceptación
- Escanear un producto nuevo que existe en OFF y confirmarlo toma menos de 15 segundos.
- Un producto con movimientos no puede borrarse, solo desactivarse.
- La búsqueda devuelve resultados mientras se escribe, con menos de 300 ms de demora en un catálogo de 500 productos.
