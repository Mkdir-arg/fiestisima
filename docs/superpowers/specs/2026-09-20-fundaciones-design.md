# Fiestisima · Diseño de las fundaciones

**Fecha**: 2026-09-20 · **Estado**: aprobado, listo para plan de implementación

Este documento cierra la etapa de diseño del arranque. Recoge las decisiones tomadas en conversación con la dueña del proyecto y corrige la documentación funcional donde quedó desactualizada. Ante una contradicción entre este documento y `docs/01` a `docs/15`, manda este, hasta que aquellos se actualicen.

---

## 1. Qué es el negocio

**Salón de fiestas con cocina, en Italia.** El salón se alquila con cocina o sin cocina. Cuando se alquila con cocina, el catering lo da el negocio.

Esto responde la pregunta que [01-contexto-y-alcance.md](../../01-contexto-y-alcance.md) dejaba abierta, y cambia una premisa de fondo de toda la documentación funcional: está escrita para un negocio de mostrador con consumo difuso, y un salón consume **por evento**. Un sábado de 120 cubiertos gasta en una tarde lo que esos documentos modelan como goteo diario.

La consecuencia no es sólo operativa. La trazabilidad del Reg. CE 178/2002 es "un paso atrás, un paso adelante". La documentación resuelve bien el paso atrás: de qué fornitore vino cada lote. El paso adelante, en catering, **es el evento**: si hay una intoxicación en la boda del 12 de marzo, la ASL pregunta qué lotes se usaron ese día. Sin el evento en el modelo, esa pregunta no tiene respuesta.

---

## 2. Alcance: dos subsistemas, no uno

El sistema completo son dos cosas con datos, usuarios y ritmos distintos. Se tratan como tales.

### Bloque 0 — Fundaciones
Sirve a los dos y no depende de cuál venga primero. Es lo que se construye ahora.

App universal Expo (iOS + web) · proyecto Supabase · esquema multi-tenant con RLS · autenticación con invitaciones · roles y permisos · navegación · sistema de diseño en código · despliegue web y prueba en iPhone.

### Bloque A — Mercadería
Ya especificado al detalle en `docs/05` a `docs/11` y `docs/13`. Riesgo bajo. **Va primero.**

Catálogo · escaneo de código de barras · lotes · carico, scarico y scarto con FEFO · scadenze y notificaciones · stock y mínimos · fornitori · registro de trazabilidad y PDF.

### Bloque B — Eventos
No existe en la documentación actual. Hay que especificarlo de cero antes de construirlo. Riesgo más alto: las reglas de disponibilidad, los presupuestos y las señas son donde estos sistemas se complican.

Calendario y disponibilidad del salón · ficha de cliente · con o sin cocina · cubiertos · presupuesto, seña y saldo · estados del evento.

### El puente
Una sola cosa: **un `scarico_uso` puede apuntar a un evento**. Con eso queda cerrada la trazabilidad hacia adelante y, de paso, se sabe cuánto costó en mercadería cada fiesta.

**Decisión**: la tabla `events` entra en la primera migración con lo mínimo, aunque la agenda se construya mucho después. Mientras tanto `movements.event_id` queda nulo y no molesta. Migrar una tabla con datos reales es caro; crearla vacía es gratis.

---

## 3. Arquitectura

### Enfoque

**Expo universal con Expo Router.** Un solo código para web e iPhone.

Esto se aparta de [14-arquitectura-tecnica.md](../../14-arquitectura-tecnica.md) en un punto: la documentación eligió React Navigation. Para una app sólo nativa sería correcto; para una web no lo es. Expo Router da URLs reales (`/prodotti/123`), botón atrás del navegador y enlaces que se pueden compartir o guardar. Con React Navigation la web queda con una sola URL para todo.

Se descartó un monorepo con Next.js para web y Expo para iPhone: la web quedaría mejor, pero son dos interfaces que mantener y con un solo desarrollador es cómo se llega tarde. La deuda que asume el camino elegido es la calidad de las tablas anchas en la PC, y es pagable: si molesta, se mueve sólo el dashboard sin tocar el resto.

### Estructura del repositorio

Una sola app en la raíz. La documentación proponía `apps/mobile/`, pero con un único paquete el monorepo es ceremonia sin beneficio, y el nombre "mobile" miente cuando la web es la entrega principal.

```
fiestisima/
├── app/                  Rutas (Expo Router: el archivo ES la URL)
│   ├── (auth)/           accedi, invito/[token]
│   └── (app)/            área autenticada
│       ├── (tabs)/       prodotti · scadenze · scansiona · altro
│       ├── prodotti/[id] · lotti/[id] · fornitori/[id]
│       └── registro · utenti · impostazioni
├── src/
│   ├── features/         products · lots · suppliers · events · auth · reports
│   ├── ui/               sistema de diseño, sin conocimiento del dominio
│   ├── lib/              supabase · openfoodfacts · ocr · queue · format
│   ├── i18n/it.ts        todos los textos, desde el día 1
│   └── types/database.ts generado por Supabase, nunca a mano
├── supabase/migrations/  SQL versionado
└── docs/
```

### Regla de dependencia

Tres capas, y la regla no se rompe:

- **`app/`** sólo compone: lee parámetros de la URL y arma la pantalla. Cero lógica de negocio.
- **`src/features/<dominio>/`** tiene consultas, mutaciones, validación y componentes propios. **Una feature nunca importa de otra.** Si dos necesitan lo mismo, eso sube a `lib/` o a `ui/`.
- **`src/ui/`** no sabe que existen los lotes: recibe props y dibuja.

Se descarta la carpeta `screens/` que proponía la documentación: con Expo Router las rutas ya son archivos, y `screens/` sería el mismo concepto dos veces. Organizar por dominio importa cuando entre el Bloque B: esa feature se agrega sin tocar las otras.

### Datos y seguridad

- TanStack Query sobre el cliente de Supabase.
- **El stock nunca se calcula en el cliente.** Viven las vistas `lot_stock` y `product_stock` en Postgres, como decidió [03-modelo-de-datos.md](../../03-modelo-de-datos.md). Esa decisión se sostiene entera.
- **RLS desde la migración 1**, no como paso posterior. Cada tabla lleva `business_id` y las políticas cuelgan de una función `auth_business_id()`. Ningún permiso vive sólo en el cliente.
- Los movimientos son inmutables: sólo `insert` y `select`. Anular es insertar el inverso.

---

## 4. Cambios al modelo de datos

Sobre lo que define `docs/03`:

**Nueva tabla `events`**

| Campo | Tipo | Nota |
|---|---|---|
| `id` | uuid | |
| `business_id` | uuid | multi-tenant |
| `name` | text | `Matrimonio Rossi` |
| `event_date` | date | |
| `guests` | int | cubiertos |
| `with_kitchen` | bool | con cocina (catering propio) o sólo sala |
| `status` | text | en Bloque 0 sólo `previsto` y `concluso`; el Bloque B amplía la lista |
| `client_name` | text | nullable |
| `notes` | text | nullable |

**Nueva columna `movements.event_id`** — uuid, nullable, referencia a `events`. Sólo tiene sentido en `scarico_uso` y `scarico_vendita`.

Todo lo demás del modelo queda como está.

---

## 5. Sistema visual

Aprobado sobre maqueta. Referencia viva: el lienzo de diseño (siete pantallas, incluida una hoja con los tokens). Lo que sigue es lo que hay que codificar en `src/ui/`.

**Lenguaje**: convenciones nativas de iOS. Título grande, buscador debajo, listas agrupadas sobre fondo gris, separadores finos, barra de pestañas con la activa en azul, hojas que suben desde abajo, control segmentado. En la PC, barra lateral clara con el ítem activo en azul.

**Color**: blanco, gris y un solo azul. El rojo y el ámbar aparecen **sólo** cuando algo vence o falta.

| Rol | Valor |
|---|---|
| Fondo agrupado | `#F2F2F7` |
| Superficie | `#FFFFFF` |
| Separador | `#E5E5EA` |
| Texto | `#000000` |
| Texto secundario | `#6C6C70` |
| Azul, acciones | `#0066E0` |
| Scaduto | fondo `#FFE5E3`, texto `#C9251B` |
| In scadenza | fondo `#FFF0D9`, texto `#9A5400` |

Dos decisiones con razón detrás, no de gusto:

1. **Un lote en orden no lleva color.** `docs/07` define el estado `OK` como verde. Se cambia a gris. Si todo lo que está bien es verde, el verde deja de significar algo y le compite al ámbar. Una pantalla sin color pasa a querer decir "no te necesita nada".
2. **El azul es `#0066E0`, no el `#007AFF` de Apple.** El de Apple no alcanza 4.5:1 sobre blanco para texto chico. Sobre superficies grandes la diferencia no se nota; en un enlace, sí.

**Tipografía**: San Francisco en iPhone y Mac, Geist como sustituto en Windows. Una sola familia. Escala: 34 bold para títulos grandes · 17 semibold para encabezados de fila · 17 para cuerpo · 14 para subtítulo secundario · 13 para notas al pie de un grupo.

**Táctil**: altura mínima 44 px en todo lo que se toque. Se usa con las manos mojadas.

---

## 6. Entrega y entornos

Estado real de las cuentas: hay Vercel o Railway. **No hay** cuenta de Supabase, ni Docker, ni Apple Developer.

**Web primero, nativo después.** Sin cuenta de Apple Developer no hay app nativa: ni TestFlight, ni Face ID, ni escáner nativo, ni OCR de etiquetas, que `docs/06` define como la funcionalidad central. La web resuelve más de lo que esa documentación supone: instalada desde Safari se comporta como app, desde iOS 16.4 acepta notificaciones push, y el escaneo por cámara funciona con una librería JS. Lo único imposible en web es el OCR de lote y fecha.

| | Decisión |
|---|---|
| Base de datos | Un proyecto Supabase gratuito. Sin Docker: se desarrolla contra la nube. |
| Web | Vercel. |
| iPhone | Safari con "Añadir a pantalla de inicio", más Expo Go para probar funciones nativas durante el desarrollo. |
| Staging | No, todavía. No tiene sentido mantener dos entornos antes de que exista un usuario. |
| Apple Developer | Cuando la web esté probada y se quiera nativo. El mismo código compila: no se tira nada. |

**Bloqueo conocido**: hay que crear la cuenta de Supabase. Es gratis, sin tarjeta, dos minutos. Nada de la base avanza hasta que exista.

**Nota menor**: hay Node 24 instalado y Expo recomienda 20 o 22 LTS. Si aparecen rarezas en el arranque, ése es el primer sospechoso.

---

## 7. Qué probar

Los criterios de aceptación de `docs/01` a `docs/13` son la lista de tests. Se dividen así:

- **Lógica pura, tests unitarios**: parser de fechas del OCR, reparto FEFO, cálculo de la sugerencia de compra, derivación del estado de un lote.
- **Base de datos, tests SQL**: políticas RLS por rol y vistas de stock. Ahí es donde un error se paga caro y en silencio: un operatore que recibe `unit_price` de la API no se ve en ninguna pantalla.
- **Flujo completo, manual sobre la web desplegada**: registrar un carico en menos de 30 segundos.

---

## 8. Documentación funcional a corregir

La documentación quedó desactualizada respecto de lo decidido acá. Corregirla es una tarea del plan de implementación, no un extra.

| Documento | Qué corregir |
|---|---|
| `01-contexto-y-alcance.md` | El rubro ya no es una pregunta abierta. Falta el eje de eventos. |
| `03-modelo-de-datos.md` | Dice "Implementado en `supabase/migrations/0001_init.sql`" y ese archivo no existe. Faltan `events` y `movements.event_id`. |
| `06-escaneo-y-ocr.md` | El OCR no entra en la primera entrega: requiere build nativo, que requiere cuenta de Apple. |
| `07-lotes-carico-scarico.md` | El estado `OK` pasa de verde a gris. El scarico puede imputarse a un evento. |
| `11-registro-y-reportes.md` | El registro suma la columna de evento. |
| `12-web.md` | La web pasa de secundaria a entrega principal. |
| `14-arquitectura-tecnica.md` | Expo Router en vez de React Navigation. Estructura del repo. Entornos reales. |
| `15-roadmap.md` | Marca como hecho un scaffold que no existe. Hay que reordenar para web primero. |
| Nuevo `16-eventi.md` | Bloque B, cuando se especifique. |
| Nuevo `17-sistema-visivo.md` | Los tokens de la sección 5, para que vivan en la documentación y no sólo en la maqueta. |

---

## 9. Cuándo está terminado el Bloque 0

- Un usuario invitado por email completa el alta y entra, en web y en el iPhone.
- Los tres roles existen y sus permisos se aplican en la base: un operatore que llame a la API directamente no recibe `unit_price`.
- El esquema completo está migrado, con `events` y `movements.event_id`, y las vistas de stock devuelven números correctos.
- La web está desplegada en una URL estable y se instala en el iPhone desde Safari.
- El catálogo se puede listar, crear y editar desde los dos dispositivos.
- Los componentes de `src/ui/` cubren lo dibujado en la maqueta: fila de lista agrupada, pastilla de estado, botones, control segmentado, campo de formulario.
