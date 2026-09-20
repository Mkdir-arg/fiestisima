# 13 · Offline y sincronización

## Realidad
Depósitos, cámaras frigoríficas y sótanos sin señal. El carico tiene que funcionar igual.

## MVP: offline parcial
- **Lectura**: la app cachea el catálogo completo (productos, fornitori, categorías) y los lotes activos. Sin señal se escanea y se ve el producto normalmente.
- **Escritura**: los caricos, scarichi y scarti se guardan en una cola local (SQLite via `expo-sqlite`) y se muestran con un icono de reloj `In attesa di sincronizzazione`.
- **Sincronización**: al recuperar conexión, la cola se envía en orden. Cada operación lleva un `client_id` (UUID) para que reintentos no dupliquen.
- Indicador discreto en la cabecera: `Offline · 3 operazioni in attesa`.

## Qué no funciona sin señal
- Alta de producto con Open Food Facts (se puede crear igual, sin autocompletar).
- Subir fotos (se encolan y suben después).
- Exportes, dashboard con cifras del servidor, invitaciones.

## Conflictos
- Los movimientos no conflictúan: son inserciones. Dos personas descargando el mismo lote sin señal pueden dejarlo negativo; al sincronizar, el servidor acepta ambos y marca el lote con `Verifica stock` para que alguien lo inventaríe. Preferimos un negativo visible a perder un registro.
- Edición de producto: última escritura gana; se guarda `updated_at` y `updated_by`.

## Fase 2: offline completo
Réplica local de toda la base con sincronización bidireccional (PowerSync o WatermelonDB). Se decide cuando haya datos de cuánto tiempo real pasan sin señal.

## Criterios de aceptación
- Con el teléfono en modo avión: escanear un producto conocido, registrar un carico y ver el reloj en el movimiento.
- Al desactivar modo avión, el movimiento aparece en la web en menos de 10 segundos y el reloj desaparece.
- Cerrar la app con operaciones en cola no las pierde.
