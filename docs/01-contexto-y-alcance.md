# 01 · Contexto y alcance

## El problema
Un negocio en Italia tiene la obligación de saber, para cada producto que entra, **de quién lo compró, con qué lote, cuándo vence y qué se hizo con él**. Hoy la titular lo lleva a mano en un cuaderno. Eso es lento, se olvida, y cuando llega una inspección hay que buscar entre páginas.

Marco legal (para entender por qué existen ciertas reglas, no para reproducirlo en el código):
- **Reg. CE 178/2002, art. 18** — rintracciabilità: el operador debe poder identificar de quién recibió cada producto y ponerlo a disposición de la autoridad "sin demora".
- **HACCP (Reg. CE 852/2004)** — autocontrol: registros de recepción de mercadería, control de vencimientos, gestión de productos no conformes (scarti).
- Autoridades que controlan: ASL (servicio sanitario local) y NAS (Carabinieri). Piden ver el registro **en el momento**.

Pregunta abierta con la cliente: confirmar el rubro exacto del negocio. La especificación asume alimentario; si es otro rubro, los vencimientos pierden peso pero lotes y proveedores siguen siendo el eje.

## Objetivo del sistema
Que registrar una entrada de mercadería tome **menos de 30 segundos** por producto (escanear → confirmar lote y fecha → guardar) y que el registro de trazabilidad se pueda mostrar en **menos de 10 segundos** ante una inspección.

## Usuarios
- **Titolare**: la dueña. Usa la app en iPhone y la web en la computadora. Ve todo, incluidos precios.
- **Responsabile**: encargado de cocina/depósito. Carga y descarga, mantiene el catálogo.
- **Operatore**: empleado. Solo carga y descarga. No ve precios ni reportes.

## Dispositivos
- App nativa iOS (React Native / Expo), distribuida por TestFlight → App Store.
- Web responsive con el mismo código, para cualquier dispositivo con navegador. Sin cámara nativa en web: el escaneo es funcionalidad de la app; en web se busca por texto o se usa un lector USB (que escribe el código como si fuera teclado).

## Qué está dentro del MVP
Login e invitaciones · catálogo de productos · escaneo de código de barras · OCR de lote y fecha · carico y scarico de lotes · scadenze con push · stock y mínimos · lista de compra · fornitori · registro de trazabilidad en PDF · web con dashboard · ABM de usuarios y roles.

## Qué queda fuera del MVP (ver Roadmap)
Escaneo de fattura completa · QR interno para preparaciones propias · offline completo · registro de temperaturas · alérgenos · facturación o ventas · integración con caja (POS).
