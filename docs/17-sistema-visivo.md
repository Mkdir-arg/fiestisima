# 17 · Sistema visivo

Implementado en `src/ui/`. Este documento describe lo que existe: los valores vienen de `src/ui/tokens.ts`, no de la maqueta ni de la spec de diseño — si algún día difieren, manda el código y hay que corregir este documento, no al revés.

**Lenguaje**: convenciones nativas de iOS. Título grande, listas agrupadas sobre fondo gris, separadores finos, hojas que suben desde abajo. En la PC (web), la misma base con más espacio horizontal.

## Tokens (`src/ui/tokens.ts`)

**Color** — blanco, gris y un solo azul. El rojo y el ámbar aparecen sólo cuando algo vence o falta.

| Token | Valor | Uso |
|---|---|---|
| `background` | `#F2F2F7` | fondo agrupado |
| `surface` | `#FFFFFF` | superficie (tarjetas, filas) |
| `separator` | `#E5E5EA` | líneas finas entre filas |
| `fill` | `#EFEFF4` | relleno neutro — el fondo del estado `OK` de un lote y de los botones secundarios |
| `text` | `#000000` | texto principal |
| `textSecondary` | `#6C6C70` | subtítulos, texto secundario |
| `textTertiary` | `#8E8E93` | placeholders, notas al pie |
| `blue` | `#0066E0` | acciones, enlaces, tab activo |
| `blueTint` | `#EAF2FE` | fondo suave para contenido en azul |
| `chevron` | `#C4C4C6` | flecha de fila navegable en `ListRow` |
| `redText` / `redTint` | `#C9251B` / `#FFE5E3` | `Scaduto` |
| `amberText` / `amberTint` | `#9A5400` / `#FFF0D9` | `In scadenza` |

**Espaciado** (`space`): `xs` 4 · `sm` 8 · `md` 12 · `lg` 16 · `xl` 24 · `xxl` 32.

**Radios** (`radius`): `small` 8 · `control` 10 · `card` 12 · `pill` 100.

**Táctil**: `HIT_SIZE` = 44 px, altura mínima de todo lo que se toca. Se usa con las manos mojadas.

**Tipografía** (`type`): una sola familia (San Francisco en iPhone y Mac; Geist como sustituto en Windows, resuelto por la plataforma, no por este archivo). Escala: `largeTitle` 34/700 · `title` 22/700 · `headline` 17/600 · `body` 17/400 · `subhead` 14/400 · `footnote` 13/400 · `caption` 12/500.

## Componentes (`src/ui/`)

Seis piezas, sin conocimiento del dominio: reciben props y dibujan, nunca importan de `src/features/`.

- **`Text`** — envoltorio de `Text` de React Native. Toma `variant` (una de las siete escalas de arriba) y `tone` (`primary` · `secondary` · `tertiary` · `blue` · `red` · `amber`), y resuelve el color desde los tokens.
- **`Button`** — `title`, `onPress`, `variant` (`primary` · `secondary` · `destructive`), `disabled`, `loading`. Altura mínima `HIT_SIZE`. El primario es azul con texto blanco; el secundario usa `fill`; el destructivo usa `redTint` con texto rojo.
- **`Field`** — campo de formulario con etiqueta a la izquierda y `TextInput` a la derecha (recibe cualquier prop de `TextInputProps`). No tiene una prop `error`; el error de un campo se muestra hoy como texto aparte, cuando hace falta.
- **`ListGroup`** — agrupa filas sobre una superficie blanca con separadores finos entre ellas, más `header` y `footer` opcionales. Es la lista agrupada del lenguaje iOS.
- **`ListRow`** — una fila dentro de un `ListGroup`: `title`, `subtitle` opcional, contenido `right` libre, y una flecha (`chevron`) cuando la fila tiene `onPress`.
- **`StatusPill`** — la pastilla de vencimiento. Recibe `daysLeft` ya calculado (no importa `lotStatus`, que vive en `src/lib/`) y un `thresholdDays`. Vencido: rojo. Por vencer dentro del umbral: ámbar. En orden: `fill`, sin color propio.

Lo que falta para cubrir toda la maqueta — control segmentado, barra lateral, barra de pestañas — no está construido todavía: entra con las tareas de navegación y catálogo, hoy bloqueadas por la falta de un proyecto Supabase.

## Dos decisiones con razón, no de gusto

1. **Ningún estado correcto lleva verde.** El doc 07 definía el estado `OK` de un lote como verde; se cambió a gris (`colors.fill`, sin tono propio — ver `StatusPill`). Si todo lo que está bien es verde, el verde deja de significar algo y le compite al ámbar de `In scadenza`. Una pantalla sin color de estado quiere decir "no te necesita nada"; el color se reserva para lo que sí lo necesita.
2. **El azul es `#0066E0`, no el `#007AFF` de Apple.** El azul de sistema de Apple no alcanza 4.5:1 de contraste sobre blanco para texto chico. Sobre superficies grandes la diferencia no se nota; en un enlace o en el texto de un botón secundario, sí — y ahí es donde vive `colors.blue` en este sistema.
