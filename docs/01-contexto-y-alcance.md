# 01 · Contexto y alcance

## El problema
Un negocio en Italia tiene la obligación de saber, para cada producto que entra, **de quién lo compró, con qué lote, cuándo vence y qué se hizo con él**. Hoy la titular lo lleva a mano en un cuaderno. Eso es lento, se olvida, y cuando llega una inspección hay que buscar entre páginas.

Marco legal (para entender por qué existen ciertas reglas, no para reproducirlo en el código):
- **Reg. CE 178/2002, art. 18** — rintracciabilità: el operador debe poder identificar de quién recibió cada producto y ponerlo a disposición de la autoridad "sin demora".
- **HACCP (Reg. CE 852/2004)** — autocontrol: registros de recepción de mercadería, control de vencimientos, gestión de productos no conformes (scarti).
- Autoridades que controlan: ASL (servicio sanitario local) y NAS (Carabinieri). Piden ver el registro **en el momento**.
- La trazabilidad es "un paso atrás, un paso adelante". Los cuatro puntos de arriba resuelven el paso atrás: de qué fornitore vino cada lote. El paso adelante, en un salón que hace catering, es el evento: si hay una intoxicación en la boda del 12 de marzo, la ASL pregunta qué lotes se usaron ese día, y sin el evento en el modelo esa pregunta no tiene respuesta. Por eso `events` y `movements.event_id` existen desde la primera migración (ver doc 03 y doc 16).

El rubro ya no es una pregunta abierta: **salón de fiestas con cocina, en Italia**. El salón se alquila con cocina o sin cocina; cuando se alquila con cocina, el catering lo da el negocio. Eso cambia una premisa de fondo de esta documentación, escrita en su origen para un negocio de mostrador con consumo difuso: un salón consume **por evento** — un sábado de 120 cubiertos gasta en una tarde lo que estos documentos modelan como goteo diario.

## Objetivo del sistema
Que registrar una entrada de mercadería tome **menos de 30 segundos** por producto (escanear → confirmar lote y fecha → guardar) y que el registro de trazabilidad se pueda mostrar en **menos de 10 segundos** ante una inspección.

## Usuarios
- **Titolare**: la dueña. Usa la app en iPhone y la web en la computadora. Ve todo, incluidos precios.
- **Responsabile**: encargado de cocina/depósito. Carga y descarga, mantiene el catálogo.
- **Operatore**: empleado. Solo carga y descarga. No ve precios ni reportes.

## Dispositivos
- Web responsive (Expo Router), para cualquier dispositivo con navegador. Es la entrega principal por ahora: instalada desde Safari con "Añadir a pantalla de inicio" se comporta como una app, y el escaneo de código de barras funciona en el navegador con una librería JS.
- App nativa iOS, mismo código, distribuida por TestFlight → App Store — pendiente de que exista una cuenta de Apple Developer (ver doc 14). Sin ella no hay OCR de etiqueta, que necesita un build nativo (ver doc 06).

## Qué está dentro del MVP
Login e invitaciones · catálogo de productos · escaneo de código de barras · OCR de lote y fecha (Fase 2 mientras no haya cuenta de Apple, ver doc 06) · carico y scarico de lotes · scadenze con push · stock y mínimos · lista de compra · fornitori · registro de trazabilidad en PDF · web con dashboard · ABM de usuarios y roles.

## Qué queda fuera del MVP (ver Roadmap)
Escaneo de fattura completa · QR interno para preparaciones propias · offline completo · registro de temperaturas · alérgenos · facturación o ventas · integración con caja (POS).
