# 11 · Registro y reportes

## Registro de trazabilidad
Es la vista de todos los movimientos, la que se muestra a un inspector.

**Columnas**: fecha y hora · producto · lote · scadenza · fornitore · tipo (Carico / Uso / Vendita / Scarto) · evento (si el movimiento se imputó a uno) · cantidad · usuario · documento adjunto (icono si hay foto de DDT).

**Filtros**: rango de fechas (presets: oggi, settimana, mese, anno) · producto · lote · fornitore · tipo · usuario.

**Búsqueda inversa** (la que pide la ASL): "¿dónde está el lote X?" → se escribe el código de lote y se ve todo: cuándo entró, de quién, cuánto queda, qué se usó y cuándo. Un producto se puede rastrear desde el fornitore hasta el último scarico.

## Exportar PDF
**Objetivo**: entregar el registro en menos de 10 segundos ante una inspección.

- Botón `Esporta registro PDF` en web y en la app (`Altro → Registro`).
- Se aplica el filtro actual. Por defecto: último mes.
- Cabecera: nombre del negocio, dirección, P. IVA, período, fecha de generación, generado por.
- Cuerpo: tabla del registro en orden cronológico. Los scarti en una sección aparte al final con sus motivos.
- Pie: `Documento generato da Fiestisima · pagina N di M`.
- Formato A4, apto para imprimir. Se genera en el servidor (Supabase Edge Function) para que quede idéntico desde app y web, y se comparte con el share sheet de iOS (email, AirDrop, imprimir).

## Exportar Excel
Mismo filtro, archivo `.xlsx` con una hoja `Movimenti` y otra `Stock attuale`. Para el contador o para análisis propio.

## Reportes en el dashboard (web)
- Scarti del mes: cantidad y valor, por motivo y por producto. Sirve para ver qué se compra de más.
- Compras por fornitore: cantidad de caricos y valor (según rol).
- Rotación: productos sin movimientos en 60 días.

## Reglas
- Los exportes registran quién los generó y cuándo (tabla `exports`, fase 1.1).
- El PDF no incluye precios salvo que el usuario marque `Includi prezzi` (solo titolare).

## Criterios de aceptación
- Con 5.000 movimientos, el PDF del último mes se genera en menos de 10 segundos.
- Buscar un código de lote muestra su historia completa en una pantalla.
- El PDF abierto en un iPhone es legible sin hacer zoom (mínimo 10 pt).
