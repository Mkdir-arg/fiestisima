# Documentación funcional — Fiestisima

Especificación de qué hace el sistema y cómo debe comportarse. Es la fuente de verdad para el desarrollo: si el código y este documento no coinciden, se corrige uno de los dos, pero se decide acá.

| Nº | Documento | Contenido |
|----|-----------|-----------|
| 01 | [Contexto y alcance](01-contexto-y-alcance.md) | Para quién es, qué problema resuelve, qué queda afuera |
| 02 | [Roles y permisos](02-roles-y-permisos.md) | Titolare / Responsabile / Operatore y matriz de permisos |
| 03 | [Modelo de datos](03-modelo-de-datos.md) | Entidades, relaciones, reglas de integridad |
| 04 | [Autenticación y usuarios](04-autenticacion-y-usuarios.md) | Login, Face ID, invitaciones, ABM de usuarios |
| 05 | [Productos](05-productos.md) | Catálogo, alta rápida por código de barras, códigos internos |
| 06 | [Escaneo y OCR](06-escaneo-y-ocr.md) | Lector de código de barras, lectura de etiqueta, foto de DDT |
| 07 | [Lotes, carico y scarico](07-lotes-carico-scarico.md) | Ciclo de vida de un lote, movimientos, FEFO |
| 08 | [Scadenze y notificaciones](08-scadenze-y-notificaciones.md) | Alertas de vencimiento, push, resumen diario |
| 09 | [Stock y compras](09-stock-y-compras.md) | Cálculo de stock, mínimos, lista de compra, WhatsApp |
| 10 | [Fornitori](10-fornitori.md) | ABM de proveedores e historial |
| 11 | [Registro y reportes](11-registro-y-reportes.md) | Registro de trazabilidad, PDF para inspección, Excel |
| 12 | [Web](12-web.md) | Dashboard y diferencias con la app |
| 13 | [Offline y sincronización](13-offline-y-sincronizacion.md) | Funcionamiento sin señal |
| 14 | [Arquitectura técnica](14-arquitectura-tecnica.md) | Stack, estructura del repo, convenciones |
| 15 | [Roadmap](15-roadmap.md) | Qué va en cada fase |

## Convenciones de esta documentación
- La documentación está en español. Los textos de la interfaz (botones, etiquetas, mensajes) están en **italiano**, porque es el idioma de quien usa la app, y se escriben así: `Registra carico`.
- Cada funcionalidad tiene: **Objetivo**, **Flujo**, **Reglas**, **Casos borde** y **Criterios de aceptación**. Un criterio de aceptación es una frase verificable: si se cumple, la funcionalidad está terminada.
- "Debe" = obligatorio en el MVP. "Puede" = deseable, se decide en desarrollo. "Fase 2" = no va en el MVP.
