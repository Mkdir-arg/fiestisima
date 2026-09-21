# 12 · Web

## Objetivo
Que la dueña pueda trabajar desde la computadora del negocio y que cualquier dispositivo con navegador pueda consultar. Mismo código que la app (Expo Web), misma base.

## Qué tiene la web
- Login (sin Face ID; el navegador recuerda la sesión).
- Dashboard: cuatro indicadores (productos a catálogo, caricos de la semana, in scadenza, sotto scorta), registro reciente, `Da usare per primi`, `Ordine suggerito`.
- Prodotti, Lotti e movimenti, Scadenze, Fornitori, Registro e report, Utenti, Impostazioni.
- Todo el ABM con tablas más amplias que en el teléfono (más columnas, ordenamiento por columna, paginación).

## Diferencias con la app
| | App iOS | Web |
|---|---|---|
| Escaneo con cámara | ✓ | Solo lector USB / entrada manual |
| OCR | ✓ | — |
| Push | ✓ | Badge en el menú + resumen en dashboard |
| Face ID | ✓ | — |
| Exportes | ✓ (share sheet) | ✓ (descarga) |
| Tablas amplias y reportes | básico | ✓ |

## Responsive
- Ancho ≥ 1024 px: barra lateral fija + contenido.
- Entre 768 y 1024: barra lateral colapsable.
- < 768 (móvil en navegador): mismo layout que la app, con pestañas abajo. Sirve como fallback para Android sin instalar nada.

## Roles en web
Operatore ve solo Prodotti y Scadenze; el resto del menú no aparece.

## Criterios de aceptación
- Un lector USB conectado a la computadora dispara la búsqueda de producto sin tocar el teclado.
- El dashboard carga en menos de 2 segundos con 500 productos y 5.000 movimientos.
- La web funciona en Safari, Chrome y Edge de los últimos dos años.
