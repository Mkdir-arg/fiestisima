# Bloque 0 · Fundaciones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar en pie la base compartida del sistema: una app Expo universal (web + iPhone) con autenticación por invitación, tres roles aplicados en la base de datos, el esquema completo migrado, el sistema de diseño en código y el catálogo de productos funcionando, desplegada en una URL estable.

**Architecture:** Una sola app Expo con Expo Router en la raíz del repositorio; las rutas son archivos y la web obtiene URLs reales. La lógica vive en `src/features/<dominio>/`, los componentes sin dominio en `src/ui/`. Supabase provee Postgres, auth y storage; todos los permisos se aplican con Row Level Security, nunca sólo en el cliente. El stock no se guarda: se calcula con vistas.

**Tech Stack:** Expo SDK 57 · expo-router 57 · React Native Web 0.21 · TypeScript strict · @supabase/supabase-js 2.116 · @tanstack/react-query 5.103 · Zod 4 · jest-expo 57 + @testing-library/react-native 14 · Supabase CLI 2.117 · Vercel (web estática)

**Spec:** [docs/superpowers/specs/2026-09-20-fundaciones-design.md](../specs/2026-09-20-fundaciones-design.md)

## Global Constraints

- **Idiomas**: código y commits en inglés; documentación en español; textos de interfaz en italiano, centralizados en `src/i18n/it.ts` desde el primer día. Ningún string italiano hardcodeado en un componente.
  - "Código en inglés" **incluye los comentarios**, también los de los archivos `.sql`. Varios bloques de código de este plan traen comentarios en español: son explicaciones para vos, no texto a copiar. Quien implemente los traduce al inglés al escribir el archivo, conservando lo que dicen.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- **Migraciones**: numeradas `NNNN_descripcion.sql`. **Nunca se edita una migración ya aplicada**; los cambios van en una migración nueva.
- **Tipos de la base**: generados con `npx supabase gen types typescript --linked`. Prohibido escribir a mano un tipo que la base ya define.
- **Permisos**: toda regla de acceso tiene su política RLS. Esconder un botón no es un permiso.
- **Multi-tenant**: toda tabla de negocio lleva `business_id`.
- **Colores** (exactos, de la sección 5 de la spec): fondo `#F2F2F7` · superficie `#FFFFFF` · separador `#E5E5EA` · texto `#000000` · texto secundario `#6C6C70` · azul `#0066E0` · scaduto fondo `#FFE5E3` texto `#C9251B` · in scadenza fondo `#FFF0D9` texto `#9A5400`.
- **Táctil**: altura mínima 44 px en todo elemento interactivo.
- **Nada de verde para estados correctos.** Un lote en orden es gris.
- **Los tests de componentes se escriben `async`.** En `@testing-library/react-native` 14, `render` y `fireEvent` son asíncronos por dentro: esperan a `act()` para vaciar los efectos. Llamarlos sin `await` hace fallar todas las aserciones con `render function has not been called`, un mensaje que no apunta a la causa. El callback de cada `it()` que renderice va marcado `async` y cada `render` y `fireEvent` va precedido de `await`. Esto vale también para `renderHook`, que envuelve a `render`: verificar y esperar igual. Las aserciones no cambian.
- **Node**: Expo 57 recomienda Node 20 o 22 LTS. La máquina tiene Node 24. Si un comando de Expo falla de forma inexplicable, ése es el primer sospechoso; la solución es instalar Node 22 LTS, no pelearse con el error.
- **Sin Docker**: no hay Supabase local. Las migraciones se aplican al proyecto en la nube con `supabase db push` y las pruebas de RLS son de integración contra ese proyecto.

---

## Estructura de archivos

Qué se crea y de qué es responsable cada cosa. Las decisiones de descomposición se cierran acá.

| Ruta | Responsabilidad |
|---|---|
| `app/_layout.tsx` | Raíz: providers (React Query, sesión) y decisión de qué grupo de rutas mostrar. |
| `app/(auth)/accedi.tsx` | Pantalla de login. |
| `app/(auth)/invito/[token].tsx` | Aceptar invitación y definir contraseña. |
| `app/(app)/_layout.tsx` | Guardia de sesión y layout responsive: pestañas abajo en pantalla angosta, barra lateral en ancha. |
| `app/(app)/(tabs)/prodotti.tsx` | Lista del catálogo. |
| `app/(app)/prodotti/[id].tsx` | Ficha de producto. |
| `app/(app)/prodotti/nuovo.tsx` | Alta de producto. |
| `app/+html.tsx` | Envoltorio HTML de la web: manifest PWA y metadatos de iOS. |
| `src/ui/tokens.ts` | Colores, espaciado, radios, escala tipográfica. Sin componentes. |
| `src/ui/Text.tsx` | Texto con variantes de la escala. |
| `src/ui/StatusPill.tsx` | Pastilla de estado. Recibe días, decide variante. |
| `src/ui/ListGroup.tsx` | Grupo de lista agrupada (tarjeta blanca con separadores). |
| `src/ui/ListRow.tsx` | Fila de lista: título, subtítulo, accesorio derecho. |
| `src/ui/Button.tsx` | Botón primario, secundario y destructivo. |
| `src/ui/Field.tsx` | Campo de formulario con etiqueta. |
| `src/lib/supabase.ts` | Única instancia del cliente. Nadie más llama a `createClient`. |
| `src/lib/secureStorage.ts` | Adaptador de almacenamiento de sesión, con troceado para SecureStore. |
| `src/lib/lotStatus.ts` | Días hasta vencer → estado derivado. Lógica pura. |
| `src/features/auth/useSession.ts` | Sesión y perfil del usuario actual. |
| `src/features/auth/api.ts` | `signIn`, `signOut`, `acceptInvitation`. |
| `src/features/products/queries.ts` | Hooks de lectura del catálogo. |
| `src/features/products/mutations.ts` | Alta y edición de producto. |
| `src/features/products/schema.ts` | Validación Zod del formulario de producto. |
| `src/i18n/it.ts` | Todos los textos de interfaz. |
| `src/types/database.ts` | Generado. No se edita. |
| `supabase/migrations/0001_init.sql` | Esquema, vistas, funciones y RLS. |
| `supabase/functions/invite-user/index.ts` | Edge Function que crea la invitación y manda el email. |
| `tests/rls.integration.test.ts` | Pruebas de permisos contra el proyecto real. |

**Regla de dependencia**: `app/` sólo compone. `src/features/<dominio>/` no importa de otra feature. `src/ui/` no conoce el dominio.

---

## Task 1: Andamiaje de la app y arnés de pruebas

**Files:**
- Create: `package.json`, `app.json`, `tsconfig.json`, `jest.config.js`, `jest.setup.js`, `.env.example`
- Create: `app/_layout.tsx`, `app/index.tsx`
- Create: `src/lib/lotStatus.ts`, `src/lib/lotStatus.test.ts`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nada.
- Produces: proyecto Expo ejecutable en web y en Expo Go; `npm test` funcionando; `lotStatus(expiresOn, today, thresholdDays): LotStatus` donde `LotStatus = 'scaduto' | 'in_scadenza' | 'ok' | 'senza_scadenza'`.

- [ ] **Step 1: Crear el proyecto Expo en la raíz del repositorio**

El repositorio ya tiene `docs/` y `.git`. `create-expo-app` no escribe en un directorio no vacío, así que se genera al lado y se mueve el contenido.

```bash
cd /c/Users/mkdir/Proyectos
npx create-expo-app@latest fiestisima-tmp --template default --no-install
cp -r fiestisima-tmp/. fiestisima/
rm -rf fiestisima-tmp fiestisima/.gitignore.orig
cd fiestisima
npm install
```

Si `create-expo-app` trajo su propio `.gitignore`, combinalo con el existente en vez de pisarlo: tienen que quedar `node_modules/`, `.expo/`, `dist/`, `.env`, `.env.local`.

- [ ] **Step 2: Verificar que arranca en web**

Run: `npx expo start --web`
Expected: abre el navegador y muestra la pantalla de ejemplo de Expo Router sin errores en consola. Cerrar con Ctrl+C.

Si falla con un error de Node, instalar Node 22 LTS y repetir.

- [ ] **Step 3: Configurar TypeScript estricto y la salida web**

En `tsconfig.json`, dentro de `compilerOptions`, asegurar:

```json
{
  "extends": "expo/tsconfig.base",
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "paths": { "@/*": ["./*"] }
  },
  "include": ["**/*.ts", "**/*.tsx", ".expo/types/**/*.ts", "expo-env.d.ts"]
}
```

En `app.json`, dentro de `expo`, fijar la salida web como página única (hace falta para que Vercel sirva las rutas de Expo Router) y el esquema de enlaces profundos:

```json
{
  "scheme": "fiestisima",
  "web": { "bundler": "metro", "output": "single" }
}
```

- [ ] **Step 4: Instalar y configurar el arnés de pruebas**

```bash
npx expo install jest-expo jest @types/jest @testing-library/react-native --dev
```

Crear `jest.config.js`:

```js
module.exports = {
  preset: 'jest-expo',
  setupFilesAfterEnv: ['<rootDir>/jest.setup.js'],
  transformIgnorePatterns: [
    'node_modules/(?!((jest-)?react-native|@react-native(-community)?)|expo(nent)?|@expo(nent)?/.*|@expo-google-fonts/.*|react-navigation|@react-navigation/.*|@sentry/react-native|native-base|react-native-svg)',
  ],
  collectCoverageFrom: ['src/**/*.{ts,tsx}', '!src/types/**'],
};
```

Crear `jest.setup.js`:

```js
require('@testing-library/react-native/extend-expect');
```

En `package.json`, agregar a `scripts`:

```json
{
  "test": "jest",
  "test:watch": "jest --watch",
  "typecheck": "tsc --noEmit"
}
```

- [ ] **Step 5: Escribir el test que falla**

Crear `src/lib/lotStatus.test.ts`:

```ts
import { lotStatus } from './lotStatus';

const today = new Date('2026-09-20T10:00:00Z');

describe('lotStatus', () => {
  it('marca senza_scadenza cuando el lote no tiene fecha', () => {
    expect(lotStatus(null, today, 7)).toBe('senza_scadenza');
  });

  it('marca scaduto cuando la fecha ya pasó', () => {
    expect(lotStatus('2026-09-19', today, 7)).toBe('scaduto');
  });

  it('marca scaduto el día anterior, no el mismo día', () => {
    expect(lotStatus('2026-09-20', today, 7)).toBe('in_scadenza');
  });

  it('incluye el umbral exacto en in_scadenza', () => {
    expect(lotStatus('2026-09-27', today, 7)).toBe('in_scadenza');
  });

  it('deja fuera el día siguiente al umbral', () => {
    expect(lotStatus('2026-09-28', today, 7)).toBe('ok');
  });

  it('respeta un umbral distinto de 7', () => {
    expect(lotStatus('2026-10-01', today, 14)).toBe('in_scadenza');
    expect(lotStatus('2026-10-01', today, 3)).toBe('ok');
  });
});

describe('daysUntil', () => {
  it('devuelve negativo para una fecha pasada', () => {
    const { daysUntil } = require('./lotStatus');
    expect(daysUntil('2026-09-17', today)).toBe(-3);
  });

  it('devuelve cero el mismo día', () => {
    const { daysUntil } = require('./lotStatus');
    expect(daysUntil('2026-09-20', today)).toBe(0);
  });
});
```

- [ ] **Step 6: Correr el test y verificar que falla**

Run: `npx jest src/lib/lotStatus.test.ts`
Expected: FAIL — `Cannot find module './lotStatus'`

- [ ] **Step 7: Implementar lo mínimo**

Crear `src/lib/lotStatus.ts`:

```ts
export type LotStatus = 'scaduto' | 'in_scadenza' | 'ok' | 'senza_scadenza';

const MS_PER_DAY = 86_400_000;

/** Días calendario desde `from` hasta `isoDate`. Negativo si ya pasó. */
export function daysUntil(isoDate: string, from: Date): number {
  const [y, m, d] = isoDate.split('-').map(Number) as [number, number, number];
  const target = Date.UTC(y, m - 1, d);
  const start = Date.UTC(from.getUTCFullYear(), from.getUTCMonth(), from.getUTCDate());
  return Math.round((target - start) / MS_PER_DAY);
}

export function lotStatus(
  expiresOn: string | null,
  today: Date,
  thresholdDays: number,
): LotStatus {
  if (expiresOn === null) return 'senza_scadenza';
  const days = daysUntil(expiresOn, today);
  if (days < 0) return 'scaduto';
  if (days <= thresholdDays) return 'in_scadenza';
  return 'ok';
}
```

- [ ] **Step 8: Correr el test y verificar que pasa**

Run: `npx jest src/lib/lotStatus.test.ts`
Expected: PASS, 8 tests.

- [ ] **Step 9: Verificar tipos**

Run: `npm run typecheck`
Expected: sin errores.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: scaffold expo universal app with test harness"
```

---

## Task 2: Tokens de diseño y primitivas de interfaz

**Files:**
- Create: `src/ui/tokens.ts`, `src/ui/Text.tsx`, `src/ui/StatusPill.tsx`, `src/ui/ListGroup.tsx`, `src/ui/ListRow.tsx`, `src/ui/Button.tsx`, `src/ui/Field.tsx`
- Create: `src/ui/StatusPill.test.tsx`, `src/ui/Button.test.tsx`
- Create: `src/i18n/it.ts`

**Interfaces:**
- Consumes: nada de tareas anteriores. `StatusPill` recibe los días ya calculados; quien los calcula usa `daysUntil` de `src/lib/lotStatus.ts` (Task 1).
- Produces: `colors`, `space`, `radius`, `HIT_SIZE`, `type` de `tokens.ts`; `<Text variant>`, `<StatusPill daysLeft>`, `<ListGroup>`, `<ListRow title subtitle right onPress>`, `<Button variant title onPress>`, `<Field label value onChangeText>`; `t` de `src/i18n/it.ts`.

- [ ] **Step 1: Crear los tokens**

Crear `src/ui/tokens.ts`. Los valores son los de la spec, sin reinterpretar:

```ts
export const colors = {
  background: '#F2F2F7',
  surface: '#FFFFFF',
  separator: '#E5E5EA',
  fill: '#EFEFF4',
  text: '#000000',
  textSecondary: '#6C6C70',
  textTertiary: '#8E8E93',
  blue: '#0066E0',
  blueTint: '#EAF2FE',
  redText: '#C9251B',
  redTint: '#FFE5E3',
  amberText: '#9A5400',
  amberTint: '#FFF0D9',
  chevron: '#C4C4C6',
} as const;

export const space = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 } as const;

export const radius = { pill: 100, card: 12, control: 10, small: 8 } as const;

/** Altura mínima de cualquier elemento que se toque. Se usa con las manos mojadas. */
export const HIT_SIZE = 44;

export const type = {
  largeTitle: { fontSize: 34, fontWeight: '700', letterSpacing: -0.8 },
  title: { fontSize: 22, fontWeight: '700', letterSpacing: -0.5 },
  headline: { fontSize: 17, fontWeight: '600', letterSpacing: -0.3 },
  body: { fontSize: 17, fontWeight: '400' },
  subhead: { fontSize: 14, fontWeight: '400' },
  footnote: { fontSize: 13, fontWeight: '400' },
  caption: { fontSize: 12, fontWeight: '500' },
} as const;

export type TypeVariant = keyof typeof type;
```

- [ ] **Step 2: Crear los textos italianos**

Crear `src/i18n/it.ts`. Sólo lo que se usa en el Bloque 0; crece con cada tarea.

```ts
export const t = {
  common: {
    save: 'Salva',
    cancel: 'Annulla',
    edit: 'Modifica',
    retry: 'Riprova',
    search: 'Cerca',
    days: 'giorni',
    daysAgo: 'gg fa',
    loading: 'Caricamento…',
  },
  auth: {
    signInTitle: 'Accedi',
    email: 'Email',
    password: 'Password',
    submit: 'Entra',
    forgot: 'Password dimenticata?',
    invalidCredentials: 'Email o password non corretti.',
    deactivated: 'Il tuo account è stato disattivato. Contatta il titolare.',
    offline: 'Nessuna connessione. Riprova quando torni online.',
  },
  invite: {
    title: 'Completa la registrazione',
    fullName: 'Nome e cognome',
    choosePassword: 'Scegli una password',
    submit: 'Entra in Fiestisima',
    expired: 'Questo invito è scaduto. Chiedine uno nuovo al titolare.',
  },
  products: {
    title: 'Prodotti',
    empty: 'Nessun prodotto. Aggiungi il primo.',
    add: 'Nuovo prodotto',
    name: 'Nome',
    barcode: 'Codice a barre',
    brand: 'Marca',
    unit: 'Unità',
    storage: 'Conservazione',
    minStock: 'Scorta minima',
    hasExpiry: 'Ha una scadenza',
    inStock: 'in magazzino',
    activeLots: 'lotti attivi',
    duplicateBarcode: (name: string) => `Questo codice è già associato a "${name}".`,
  },
  errors: {
    generic: 'Qualcosa non ha funzionato. Riprova.',
    onlyTitolare: 'Solo il titolare può gestire gli utenti.',
  },
} as const;
```

- [ ] **Step 3: Escribir el test que falla de StatusPill**

`StatusPill` es la única primitiva con lógica propia: traduce días restantes a variante y etiqueta. Por eso se testea.

Crear `src/ui/StatusPill.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react-native';
import { StatusPill } from './StatusPill';
import { colors } from './tokens';

describe('StatusPill', () => {
  it('muestra los días restantes en plural', async () => {
    await render(<StatusPill daysLeft={5} />);
    expect(screen.getByText('5 giorni')).toBeOnTheScreen();
  });

  it('muestra el singular con un día', async () => {
    await render(<StatusPill daysLeft={1} />);
    expect(screen.getByText('1 giorno')).toBeOnTheScreen();
  });

  it('dice oggi cuando vence hoy', async () => {
    await render(<StatusPill daysLeft={0} />);
    expect(screen.getByText('oggi')).toBeOnTheScreen();
  });

  it('cuenta hacia atrás cuando ya venció', async () => {
    await render(<StatusPill daysLeft={-3} />);
    expect(screen.getByText('3 gg fa')).toBeOnTheScreen();
  });

  it('usa el rojo cuando está vencido', async () => {
    await render(<StatusPill daysLeft={-1} />);
    expect(screen.getByTestId('status-pill')).toHaveStyle({ backgroundColor: colors.redTint });
  });

  it('usa el ámbar dentro del umbral', async () => {
    await render(<StatusPill daysLeft={4} thresholdDays={7} />);
    expect(screen.getByTestId('status-pill')).toHaveStyle({ backgroundColor: colors.amberTint });
  });

  it('usa el gris fuera del umbral: lo que está bien no lleva color', async () => {
    await render(<StatusPill daysLeft={30} thresholdDays={7} />);
    expect(screen.getByTestId('status-pill')).toHaveStyle({ backgroundColor: colors.fill });
  });
});
```

- [ ] **Step 4: Correr el test y verificar que falla**

Run: `npx jest src/ui/StatusPill.test.tsx`
Expected: FAIL — `Cannot find module './StatusPill'`

- [ ] **Step 5: Implementar Text y StatusPill**

Crear `src/ui/Text.tsx`:

```tsx
import { Text as RNText, type TextProps as RNTextProps } from 'react-native';
import { colors, type, type TypeVariant } from './tokens';

type Props = RNTextProps & {
  variant?: TypeVariant;
  tone?: 'primary' | 'secondary' | 'tertiary' | 'blue' | 'red' | 'amber';
};

const tones = {
  primary: colors.text,
  secondary: colors.textSecondary,
  tertiary: colors.textTertiary,
  blue: colors.blue,
  red: colors.redText,
  amber: colors.amberText,
} as const;

export function Text({ variant = 'body', tone = 'primary', style, ...rest }: Props) {
  return <RNText {...rest} style={[type[variant], { color: tones[tone] }, style]} />;
}
```

Crear `src/ui/StatusPill.tsx`:

```tsx
import { View } from 'react-native';
import { Text } from './Text';
import { colors, radius } from './tokens';

type Props = { daysLeft: number; thresholdDays?: number };

function label(daysLeft: number): string {
  if (daysLeft < 0) return `${Math.abs(daysLeft)} gg fa`;
  if (daysLeft === 0) return 'oggi';
  if (daysLeft === 1) return '1 giorno';
  return `${daysLeft} giorni`;
}

export function StatusPill({ daysLeft, thresholdDays = 7 }: Props) {
  const variant =
    daysLeft < 0 ? 'red' : daysLeft <= thresholdDays ? 'amber' : 'neutral';

  const background =
    variant === 'red' ? colors.redTint : variant === 'amber' ? colors.amberTint : colors.fill;
  const tone = variant === 'red' ? 'red' : variant === 'amber' ? 'amber' : 'secondary';

  return (
    <View
      testID="status-pill"
      style={{
        backgroundColor: background,
        borderRadius: radius.pill,
        paddingHorizontal: 9,
        paddingVertical: 4,
      }}
    >
      <Text variant="footnote" tone={tone} style={{ fontWeight: '600' }}>
        {label(daysLeft)}
      </Text>
    </View>
  );
}
```

- [ ] **Step 6: Correr el test y verificar que pasa**

Run: `npx jest src/ui/StatusPill.test.tsx`
Expected: PASS, 7 tests.

- [ ] **Step 7: Escribir el test que falla de Button**

Crear `src/ui/Button.test.tsx`:

```tsx
import { render, screen, fireEvent } from '@testing-library/react-native';
import { Button } from './Button';
import { HIT_SIZE } from './tokens';

describe('Button', () => {
  it('llama a onPress al tocarlo', async () => {
    const onPress = jest.fn();
    await render(<Button title="Salva" onPress={onPress} />);
    await fireEvent.press(screen.getByRole('button', { name: 'Salva' }));
    expect(onPress).toHaveBeenCalledTimes(1);
  });

  it('no llama a onPress cuando está deshabilitado', async () => {
    const onPress = jest.fn();
    await render(<Button title="Salva" onPress={onPress} disabled />);
    await fireEvent.press(screen.getByRole('button', { name: 'Salva' }));
    expect(onPress).not.toHaveBeenCalled();
  });

  it('respeta la altura mínima táctil', async () => {
    await render(<Button title="Salva" onPress={() => {}} />);
    expect(screen.getByRole('button', { name: 'Salva' })).toHaveStyle({ minHeight: HIT_SIZE });
  });
});
```

- [ ] **Step 8: Correr el test y verificar que falla**

Run: `npx jest src/ui/Button.test.tsx`
Expected: FAIL — `Cannot find module './Button'`

- [ ] **Step 9: Implementar Button, ListGroup, ListRow y Field**

Crear `src/ui/Button.tsx`:

```tsx
import { Pressable, ActivityIndicator, View } from 'react-native';
import { Text } from './Text';
import { colors, radius, HIT_SIZE } from './tokens';

type Props = {
  title: string;
  onPress: () => void;
  variant?: 'primary' | 'secondary' | 'destructive';
  disabled?: boolean;
  loading?: boolean;
};

export function Button({
  title,
  onPress,
  variant = 'primary',
  disabled = false,
  loading = false,
}: Props) {
  const background =
    variant === 'primary' ? colors.blue : variant === 'destructive' ? colors.redTint : colors.fill;
  const tone = variant === 'primary' ? 'primary' : variant === 'destructive' ? 'red' : 'blue';
  const textColor = variant === 'primary' ? colors.surface : undefined;

  return (
    <Pressable
      role="button"
      accessibilityLabel={title}
      accessibilityState={{ disabled: disabled || loading }}
      disabled={disabled || loading}
      onPress={onPress}
      style={{
        minHeight: HIT_SIZE,
        paddingHorizontal: 22,
        borderRadius: radius.card,
        backgroundColor: background,
        opacity: disabled ? 0.4 : 1,
        alignItems: 'center',
        justifyContent: 'center',
      }}
    >
      {loading ? (
        <ActivityIndicator color={variant === 'primary' ? colors.surface : colors.blue} />
      ) : (
        <Text variant="headline" tone={tone} style={textColor ? { color: textColor } : undefined}>
          {title}
        </Text>
      )}
    </Pressable>
  );
}
```

Crear `src/ui/ListGroup.tsx`:

```tsx
import { Children, Fragment, type ReactNode } from 'react';
import { View } from 'react-native';
import { Text } from './Text';
import { colors, radius, space } from './tokens';

type Props = { header?: string; footer?: string; children: ReactNode };

export function ListGroup({ header, footer, children }: Props) {
  const rows = Children.toArray(children);
  return (
    <View style={{ marginBottom: space.xl }}>
      {header ? (
        <Text variant="headline" style={{ marginBottom: space.sm, marginLeft: space.xs }}>
          {header}
        </Text>
      ) : null}
      <View
        style={{
          backgroundColor: colors.surface,
          borderRadius: radius.card,
          overflow: 'hidden',
        }}
      >
        {rows.map((row, i) => (
          <Fragment key={i}>
            {i > 0 ? (
              <View
                style={{ height: 1, backgroundColor: colors.separator, marginLeft: space.lg }}
              />
            ) : null}
            {row}
          </Fragment>
        ))}
      </View>
      {footer ? (
        <Text
          variant="footnote"
          tone="secondary"
          style={{ marginTop: space.sm, marginHorizontal: space.xs }}
        >
          {footer}
        </Text>
      ) : null}
    </View>
  );
}
```

Crear `src/ui/ListRow.tsx`:

```tsx
import type { ReactNode } from 'react';
import { Pressable, View } from 'react-native';
import { Text } from './Text';
import { colors, space, HIT_SIZE } from './tokens';

type Props = {
  title: string;
  subtitle?: string;
  right?: ReactNode;
  onPress?: () => void;
};

export function ListRow({ title, subtitle, right, onPress }: Props) {
  const content = (
    <View
      style={{
        minHeight: HIT_SIZE + 10,
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.md,
        paddingHorizontal: space.lg,
        paddingVertical: 11,
      }}
    >
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text variant="body" style={{ fontWeight: '500' }}>
          {title}
        </Text>
        {subtitle ? (
          <Text variant="subhead" tone="secondary" style={{ marginTop: 2 }}>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {right}
      {onPress ? <Chevron /> : null}
    </View>
  );

  if (!onPress) return content;
  return (
    <Pressable role="button" accessibilityLabel={title} onPress={onPress}>
      {content}
    </Pressable>
  );
}

function Chevron() {
  return (
    <View
      style={{
        width: 8,
        height: 13,
        borderRightWidth: 2,
        borderTopWidth: 2,
        borderColor: colors.chevron,
        transform: [{ rotate: '45deg' }],
      }}
    />
  );
}
```

Crear `src/ui/Field.tsx`:

```tsx
import { TextInput, View, type TextInputProps } from 'react-native';
import { Text } from './Text';
import { colors, space, HIT_SIZE } from './tokens';

type Props = TextInputProps & { label: string };

export function Field({ label, style, ...rest }: Props) {
  return (
    <View
      style={{
        flexDirection: 'row',
        alignItems: 'center',
        gap: space.md,
        paddingHorizontal: space.lg,
        minHeight: HIT_SIZE + 8,
      }}
    >
      <Text variant="body" style={{ width: 110 }} nativeID={`label-${label}`}>
        {label}
      </Text>
      <TextInput
        accessibilityLabel={label}
        aria-labelledby={`label-${label}`}
        placeholderTextColor={colors.textTertiary}
        {...rest}
        style={[
          { flex: 1, fontSize: 17, color: colors.text, paddingVertical: 12 },
          style,
        ]}
      />
    </View>
  );
}
```

- [ ] **Step 10: Correr todos los tests**

Run: `npm test`
Expected: PASS, 18 tests en 3 suites.

- [ ] **Step 11: Verificar tipos**

Run: `npm run typecheck`
Expected: sin errores.

- [ ] **Step 12: Commit**

```bash
git add -A
git commit -m "feat: add design tokens, ui primitives and italian strings"
```

---

## Task 3: Esquema de la base de datos y vistas de stock

**Files:**
- Create: `supabase/config.toml` (lo genera `supabase init`)
- Create: `supabase/migrations/0001_init.sql`
- Modify: `.gitignore` (añadir `supabase/.temp/`)

**Interfaces:**
- Consumes: nada del código.
- Produces: tablas `businesses`, `profiles`, `invitations`, `suppliers`, `categories`, `products`, `lots`, `events`, `movements`; vistas `lots_view`, `lot_stock`, `product_stock`; funciones `auth_business_id()`, `auth_role()`; tipos enum `user_role`, `storage_place`, `unit_kind`, `movement_type`.

**Prerequisito humano:** la cuenta y el proyecto Supabase tienen que existir. Proyecto `fiestisima`, región Frankfurt. Hacen falta el *project ref* (está en la URL del panel) y la contraseña de la base.

- [ ] **Step 1: Inicializar y enlazar Supabase**

```bash
cd /c/Users/mkdir/Proyectos/fiestisima
npx supabase init
npx supabase link --project-ref <PROJECT_REF>
```

`link` pide la contraseña de la base. Añadir `supabase/.temp/` al `.gitignore`.

- [ ] **Step 2: Escribir la migración inicial**

Crear `supabase/migrations/0001_init.sql`:

```sql
-- Fiestisima · esquema inicial
-- Multi-tenant desde el día 1. Toda tabla de negocio lleva business_id.

create extension if not exists pgcrypto;
create extension if not exists citext;

-- ---------------------------------------------------------------- tipos

create type user_role as enum ('titolare', 'responsabile', 'operatore');
create type storage_place as enum ('frigo', 'freezer', 'dispensa');
create type unit_kind as enum ('pz', 'kg', 'l', 'g', 'ml');
create type movement_type as enum ('carico', 'scarico_uso', 'scarico_vendita', 'scarto');

-- ---------------------------------------------------------------- tablas

create table businesses (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  address text,
  vat_number text,
  expiry_threshold_days int not null default 7 check (expiry_threshold_days > 0),
  created_at timestamptz not null default now()
);

create table profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  business_id uuid not null references businesses (id) on delete cascade,
  full_name text not null,
  role user_role not null default 'operatore',
  active boolean not null default true,
  last_seen_at timestamptz,
  created_at timestamptz not null default now()
);
create index profiles_business_idx on profiles (business_id);

create table invitations (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  email citext not null,
  full_name text not null,
  role user_role not null default 'operatore',
  token uuid not null default gen_random_uuid(),
  invited_by uuid references profiles (id) on delete set null,
  expires_at timestamptz not null default now() + interval '7 days',
  accepted_at timestamptz,
  created_at timestamptz not null default now()
);
-- Un solo invito pendiente por email y negocio.
create unique index invitations_pending_idx
  on invitations (business_id, email) where accepted_at is null;
create unique index invitations_token_idx on invitations (token);

create table suppliers (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null,
  phone text,
  email text,
  vat_number text,
  address text,
  notes text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (business_id, name)
);

create table categories (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null,
  unique (business_id, name)
);

create table products (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null check (length(trim(name)) > 0),
  barcode text,
  is_internal_code boolean not null default false,
  brand text,
  category_id uuid references categories (id) on delete set null,
  unit unit_kind not null default 'pz',
  storage storage_place not null default 'dispensa',
  min_stock numeric not null default 0 check (min_stock >= 0),
  has_expiry boolean not null default true,
  image_url text,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  updated_by uuid references profiles (id) on delete set null,
  -- El código es único por negocio, no global: dos negocios pueden tener el
  -- mismo EAN. Varios productos sin código conviven porque NULL no colisiona.
  unique (business_id, barcode)
);
create index products_business_active_idx on products (business_id, active);

create table events (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  name text not null,
  event_date date not null,
  guests int check (guests > 0),
  with_kitchen boolean not null default true,
  status text not null default 'previsto' check (status in ('previsto', 'concluso')),
  client_name text,
  notes text,
  created_at timestamptz not null default now()
);
create index events_business_date_idx on events (business_id, event_date);

create table lots (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  product_id uuid not null references products (id) on delete restrict,
  supplier_id uuid references suppliers (id) on delete restrict,
  lot_code text not null,
  expires_on date,
  unit_price numeric check (unit_price >= 0),
  document_url text,
  received_on date not null default current_date,
  created_by uuid references profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  -- Dos caricos idénticos no crean dos lotes. NULLS NOT DISTINCT hace que
  -- un lote sin fecha o sin fornitore también colisione consigo mismo.
  unique nulls not distinct (business_id, product_id, lot_code, expires_on, supplier_id)
);
create index lots_product_idx on lots (product_id);
create index lots_expiry_idx on lots (business_id, expires_on);

create table movements (
  id uuid primary key default gen_random_uuid(),
  business_id uuid not null references businesses (id) on delete cascade,
  lot_id uuid not null references lots (id) on delete restrict,
  event_id uuid references events (id) on delete set null,
  type movement_type not null,
  quantity numeric not null check (quantity > 0),
  reason text,
  reverses_id uuid references movements (id) on delete set null,
  -- Idempotencia de la cola offline: un reintento no duplica el movimiento.
  client_id uuid unique,
  created_by uuid references profiles (id) on delete set null,
  created_at timestamptz not null default now(),
  constraint scarto_needs_reason check (type <> 'scarto' or reason is not null)
);
create index movements_lot_idx on movements (lot_id);
create index movements_business_date_idx on movements (business_id, created_at desc);
create index movements_event_idx on movements (event_id) where event_id is not null;

-- ---------------------------------------------------------------- funciones
-- SECURITY DEFINER a propósito: estas funciones se usan DENTRO de las
-- políticas RLS de profiles. Si respetaran RLS, consultar profiles para
-- decidir si se puede consultar profiles sería recursión infinita.

create or replace function auth_business_id()
returns uuid
language sql
stable
security definer
set search_path = public
as $$
  select business_id from profiles where id = auth.uid() and active
$$;

create or replace function auth_role()
returns user_role
language sql
stable
security definer
set search_path = public
as $$
  select role from profiles where id = auth.uid() and active
$$;

-- ---------------------------------------------------------------- vistas
-- El stock no se guarda: se calcula. Así nunca se desincroniza del registro.

create view lot_stock as
select
  l.id as lot_id,
  l.business_id,
  l.product_id,
  coalesce(
    sum(case when m.type = 'carico' then m.quantity else -m.quantity end),
    0
  ) as stock
from lots l
left join movements m on m.lot_id = l.id
where l.business_id = auth_business_id()
group by l.id, l.business_id, l.product_id;

create view product_stock as
select business_id, product_id, sum(stock) as stock
from lot_stock
group by business_id, product_id;

-- El precio no se esconde en el cliente: no sale de la base para un
-- operatore. Por eso se revoca el acceso directo a lots y se lee por vista.
create view lots_view as
select
  l.id,
  l.business_id,
  l.product_id,
  l.supplier_id,
  l.lot_code,
  l.expires_on,
  l.document_url,
  l.received_on,
  l.created_by,
  l.created_at,
  case when auth_role() in ('titolare', 'responsabile') then l.unit_price end as unit_price
from lots l
where l.business_id = auth_business_id();
```

- [ ] **Step 3: Aplicar la migración**

Run: `npx supabase db push`
Expected: `Applying migration 0001_init.sql...` y `Finished supabase db push.`

- [ ] **Step 4: Verificar el esquema en la base real**

```bash
npx supabase inspect db table-sizes --linked
```

Expected: aparecen `businesses`, `profiles`, `invitations`, `suppliers`, `categories`, `products`, `events`, `lots`, `movements`.

- [ ] **Step 5: Verificar a mano las dos reglas que más importan**

En el editor SQL del panel de Supabase, ejecutar:

```sql
-- Un scarto sin motivo tiene que fallar.
insert into businesses (name) values ('Prova') returning id;
-- Copiar el id devuelto y usarlo abajo; luego:
-- Se espera: ERROR ... viola la restricción «scarto_needs_reason»
```

Expected: la restricción `scarto_needs_reason` rechaza la fila. Después, borrar el negocio de prueba:

```sql
delete from businesses where name = 'Prova';
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: add initial database schema with stock views"
```

---

## Task 4: Row Level Security y prueba de permisos por rol

**Files:**
- Create: `supabase/migrations/0002_rls.sql`
- Create: `tests/rls.integration.test.ts`
- Create: `tests/README.md`
- Modify: `package.json` (script `test:rls`)

**Interfaces:**
- Consumes: todas las tablas y funciones de la Task 3.
- Produces: RLS activa en todas las tablas; el cliente lee lotes por `lots_view`, nunca por `lots`.

- [ ] **Step 1: Escribir la migración de RLS**

Crear `supabase/migrations/0002_rls.sql`:

```sql
-- Toda regla de acceso vive acá. Esconder un botón no es un permiso.

alter table businesses  enable row level security;
alter table profiles    enable row level security;
alter table invitations enable row level security;
alter table suppliers   enable row level security;
alter table categories  enable row level security;
alter table products    enable row level security;
alter table events      enable row level security;
alter table lots        enable row level security;
alter table movements   enable row level security;

-- businesses: se ve el propio; sólo el titolare lo edita.
create policy businesses_select on businesses for select to authenticated
  using (id = auth_business_id());
create policy businesses_update on businesses for update to authenticated
  using (id = auth_business_id() and auth_role() = 'titolare')
  with check (id = auth_business_id());

-- profiles: todos ven a sus compañeros; sólo el titolare los modifica.
create policy profiles_select on profiles for select to authenticated
  using (business_id = auth_business_id());
create policy profiles_update_self on profiles for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid() and business_id = auth_business_id());
create policy profiles_update_titolare on profiles for update to authenticated
  using (business_id = auth_business_id() and auth_role() = 'titolare')
  with check (business_id = auth_business_id());

-- invitations: sólo el titolare.
create policy invitations_all on invitations for all to authenticated
  using (business_id = auth_business_id() and auth_role() = 'titolare')
  with check (business_id = auth_business_id() and auth_role() = 'titolare');

-- suppliers y categories: todos leen; titolare y responsabile escriben.
create policy suppliers_select on suppliers for select to authenticated
  using (business_id = auth_business_id());
create policy suppliers_write on suppliers for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

create policy categories_select on categories for select to authenticated
  using (business_id = auth_business_id());
create policy categories_write on categories for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

-- products: todos leen; titolare y responsabile escriben.
create policy products_select on products for select to authenticated
  using (business_id = auth_business_id());
create policy products_write on products for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

-- events: todos leen; titolare y responsabile escriben.
create policy events_select on events for select to authenticated
  using (business_id = auth_business_id());
create policy events_write on events for all to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'));

-- lots: cualquiera con sesión puede registrar un carico.
create policy lots_insert on lots for insert to authenticated
  with check (business_id = auth_business_id());
create policy lots_update on lots for update to authenticated
  using (business_id = auth_business_id() and auth_role() in ('titolare', 'responsabile'))
  with check (business_id = auth_business_id());

-- movements: sólo insert y select. Nunca update ni delete: el registro de
-- trazabilidad es inmutable. Anular es insertar el inverso.
create policy movements_select on movements for select to authenticated
  using (business_id = auth_business_id());
create policy movements_insert on movements for insert to authenticated
  with check (business_id = auth_business_id() and created_by = auth.uid());

-- El precio no sale de la base para un operatore. Se revoca el acceso
-- directo a la tabla y se lee por la vista, que lo anula según el rol.
revoke select on lots from authenticated;
grant select on lots_view to authenticated;
grant select on lot_stock to authenticated;
grant select on product_stock to authenticated;
```

- [ ] **Step 2: Aplicar la migración**

Run: `npx supabase db push`
Expected: `Applying migration 0002_rls.sql...` sin errores.

- [ ] **Step 3: Preparar los datos de prueba**

En el editor SQL del panel, crear el negocio y tres usuarios. Los usuarios se crean desde Authentication → Users → Add user (con email confirmado), y luego se les asigna perfil:

```sql
insert into businesses (name, address, vat_number)
values ('Sala Fiestisima', 'Pescara', 'IT00000000000')
returning id;
-- Copiar el id; abajo se llama :bid

insert into profiles (id, business_id, full_name, role) values
  ('<uuid del usuario titolare>',     '<bid>', 'Anna Ricci',  'titolare'),
  ('<uuid del usuario responsabile>', '<bid>', 'Luca Neri',   'responsabile'),
  ('<uuid del usuario operatore>',    '<bid>', 'Sofia Greco', 'operatore');

insert into suppliers (business_id, name) values ('<bid>', 'Metro Pescara') returning id;
insert into products (business_id, name, barcode, unit, storage)
values ('<bid>', 'Pomodori pelati 400 g', '8001234567890', 'pz', 'dispensa')
returning id;

insert into lots (business_id, product_id, supplier_id, lot_code, expires_on, unit_price)
values ('<bid>', '<product id>', '<supplier id>', 'L2409A', '2027-03-12', 0.89);
```

- [ ] **Step 4: Escribir las credenciales de prueba**

Crear `tests/README.md`:

```markdown
# Pruebas de integración de permisos

No hay Docker, así que no hay base local: estas pruebas corren contra el
proyecto Supabase real y necesitan tres usuarios de prueba ya creados.

Crear `.env.test` en la raíz (está en .gitignore, nunca se commitea):

    EXPO_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
    EXPO_PUBLIC_SUPABASE_ANON_KEY=<anon key>
    TEST_TITOLARE_EMAIL=...
    TEST_TITOLARE_PASSWORD=...
    TEST_OPERATORE_EMAIL=...
    TEST_OPERATORE_PASSWORD=...

Correr con: npm run test:rls

No van en CI mientras las credenciales vivan sólo en la máquina.
```

Añadir `.env.test` al `.gitignore`.

- [ ] **Step 5: Escribir el test que falla**

Crear `tests/rls.integration.test.ts`:

```ts
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL!;
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!;

async function signIn(email: string, password: string): Promise<SupabaseClient> {
  const client = createClient(url, anonKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { error } = await client.auth.signInWithPassword({ email, password });
  if (error) throw new Error(`No se pudo entrar como ${email}: ${error.message}`);
  return client;
}

let titolare: SupabaseClient;
let operatore: SupabaseClient;

beforeAll(async () => {
  titolare = await signIn(
    process.env.TEST_TITOLARE_EMAIL!,
    process.env.TEST_TITOLARE_PASSWORD!,
  );
  operatore = await signIn(
    process.env.TEST_OPERATORE_EMAIL!,
    process.env.TEST_OPERATORE_PASSWORD!,
  );
}, 30_000);

describe('el precio no sale de la base para un operatore', () => {
  it('el titolare recibe unit_price', async () => {
    const { data, error } = await titolare.from('lots_view').select('lot_code, unit_price');
    expect(error).toBeNull();
    expect(data?.[0]?.unit_price).not.toBeNull();
  });

  it('el operatore recibe unit_price en null', async () => {
    const { data, error } = await operatore.from('lots_view').select('lot_code, unit_price');
    expect(error).toBeNull();
    expect(data?.length).toBeGreaterThan(0);
    expect(data?.every((row) => row.unit_price === null)).toBe(true);
  });

  it('el operatore no puede leer la tabla lots directamente', async () => {
    const { error } = await operatore.from('lots').select('unit_price');
    expect(error).not.toBeNull();
  });
});

describe('el operatore no administra el catálogo', () => {
  it('puede leer productos', async () => {
    const { data, error } = await operatore.from('products').select('id, name');
    expect(error).toBeNull();
    expect(data?.length).toBeGreaterThan(0);
  });

  it('no puede crear un producto', async () => {
    const { data: profile } = await operatore.from('profiles').select('business_id').single();
    const { error } = await operatore
      .from('products')
      .insert({ business_id: profile!.business_id, name: 'Contrabando' });
    expect(error).not.toBeNull();
  });

  it('no puede invitar usuarios', async () => {
    const { data: profile } = await operatore.from('profiles').select('business_id').single();
    const { error } = await operatore.from('invitations').insert({
      business_id: profile!.business_id,
      email: 'nadie@example.com',
      full_name: 'Nadie',
      role: 'operatore',
    });
    expect(error).not.toBeNull();
  });
});

describe('el registro de trazabilidad es inmutable', () => {
  it('nadie puede borrar un movimiento', async () => {
    const { error } = await titolare.from('movements').delete().neq('id', crypto.randomUUID());
    expect(error).not.toBeNull();
  });

  it('nadie puede modificar un movimiento', async () => {
    const { error } = await titolare.from('movements').update({ quantity: 1 }).neq('id', crypto.randomUUID());
    expect(error).not.toBeNull();
  });
});

describe('el stock se calcula', () => {
  it('product_stock devuelve una fila por producto', async () => {
    const { data, error } = await titolare.from('product_stock').select('product_id, stock');
    expect(error).toBeNull();
    expect(Array.isArray(data)).toBe(true);
  });
});
```

- [ ] **Step 6: Añadir el script y correr el test**

En `package.json`, agregar a `scripts`:

```json
{
  "test:rls": "node --env-file=.env.test node_modules/jest/bin/jest.js --config jest.rls.config.js --runInBand"
}
```

Crear `jest.rls.config.js`:

```js
module.exports = {
  testEnvironment: 'node',
  testMatch: ['<rootDir>/tests/**/*.integration.test.ts'],
  transform: { '^.+\\.tsx?$': ['babel-jest', { presets: ['babel-preset-expo'] }] },
};
```

Excluir `tests/` del jest principal añadiendo a `jest.config.js`:

```js
  testPathIgnorePatterns: ['/node_modules/', '/tests/'],
```

Run: `npm run test:rls`
Expected: 9 tests en verde. Si alguno falla, la política correspondiente está mal: **se corrige la política, no el test.**

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: enforce role permissions with row level security"
```

---

## Task 5: Cliente de Supabase, tipos generados y sesión persistente

**Files:**
- Create: `src/lib/secureStorage.ts`, `src/lib/secureStorage.test.ts`, `src/lib/supabase.ts`
- Create: `src/types/database.ts` (generado)
- Create: `.env.example`, `.env.local` (no se commitea)
- Modify: `.gitignore`

**Interfaces:**
- Consumes: el esquema de las Tasks 3 y 4.
- Produces: `supabase` (instancia única) de `src/lib/supabase.ts`; tipo `Database` de `src/types/database.ts`; `sessionStorage` de `src/lib/secureStorage.ts`.

- [ ] **Step 1: Instalar dependencias**

```bash
npx expo install @supabase/supabase-js expo-secure-store react-native-url-polyfill @tanstack/react-query zod
```

- [ ] **Step 2: Escribir las variables de entorno**

Crear `.env.example`:

```
EXPO_PUBLIC_SUPABASE_URL=https://xxxxxxxx.supabase.co
EXPO_PUBLIC_SUPABASE_ANON_KEY=eyJ...
```

Crear `.env.local` con los valores reales. Añadir `.env.local` al `.gitignore`. **La clave `service_role` nunca entra en el repositorio ni en una variable `EXPO_PUBLIC_`**: esas viajan al navegador.

- [ ] **Step 3: Generar los tipos de la base**

```bash
npx supabase gen types typescript --linked > src/types/database.ts
```

Añadir a `scripts` de `package.json`:

```json
{ "types": "supabase gen types typescript --linked > src/types/database.ts" }
```

- [ ] **Step 4: Escribir el test que falla del almacenamiento**

SecureStore de iOS rechaza valores de más de 2048 bytes y el token de sesión de Supabase los pasa. Hay que trocearlo. Esto tiene lógica propia, así que se testea.

Crear `src/lib/secureStorage.test.ts`:

```ts
import { chunk, unchunk, CHUNK_SIZE } from './secureStorage';

describe('chunk', () => {
  it('deja intacto un valor corto', () => {
    expect(chunk('hola')).toEqual(['hola']);
  });

  it('parte un valor largo en trozos del tamaño máximo', () => {
    const value = 'x'.repeat(CHUNK_SIZE * 2 + 10);
    const parts = chunk(value);
    expect(parts).toHaveLength(3);
    expect(parts[0]).toHaveLength(CHUNK_SIZE);
    expect(parts[2]).toHaveLength(10);
  });

  it('unchunk revierte chunk sin perder nada', () => {
    const value = JSON.stringify({ token: 'y'.repeat(5000) });
    expect(unchunk(chunk(value))).toBe(value);
  });
});
```

- [ ] **Step 5: Correr el test y verificar que falla**

Run: `npx jest src/lib/secureStorage.test.ts`
Expected: FAIL — `Cannot find module './secureStorage'`

- [ ] **Step 6: Implementar el almacenamiento**

Crear `src/lib/secureStorage.ts`:

```ts
import { Platform } from 'react-native';
import * as SecureStore from 'expo-secure-store';

/** SecureStore de iOS avisa por encima de 2048 bytes. Se trocea por debajo. */
export const CHUNK_SIZE = 1800;

export function chunk(value: string): string[] {
  if (value.length <= CHUNK_SIZE) return [value];
  const parts: string[] = [];
  for (let i = 0; i < value.length; i += CHUNK_SIZE) {
    parts.push(value.slice(i, i + CHUNK_SIZE));
  }
  return parts;
}

export function unchunk(parts: string[]): string {
  return parts.join('');
}

const countKey = (key: string) => `${key}__count`;
const partKey = (key: string, i: number) => `${key}__${i}`;

/**
 * En el navegador la sesión vive en localStorage, que es lo único que hay.
 * En el teléfono vive en el llavero del sistema, troceada. Nunca en
 * AsyncStorage: ahí el refresh token quedaría en texto plano.
 */
export const sessionStorage = {
  async getItem(key: string): Promise<string | null> {
    if (Platform.OS === 'web') {
      try {
        return globalThis.localStorage?.getItem(key) ?? null;
      } catch {
        return null;
      }
    }
    const raw = await SecureStore.getItemAsync(countKey(key));
    if (raw === null) return null;
    const count = Number(raw);
    const parts: string[] = [];
    for (let i = 0; i < count; i++) {
      const part = await SecureStore.getItemAsync(partKey(key, i));
      if (part === null) return null;
      parts.push(part);
    }
    return unchunk(parts);
  },

  async setItem(key: string, value: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        globalThis.localStorage?.setItem(key, value);
      } catch {
        /* modo privado o almacenamiento bloqueado: la sesión dura lo que la pestaña */
      }
      return;
    }
    await this.removeItem(key);
    const parts = chunk(value);
    await SecureStore.setItemAsync(countKey(key), String(parts.length));
    for (let i = 0; i < parts.length; i++) {
      await SecureStore.setItemAsync(partKey(key, i), parts[i]!);
    }
  },

  async removeItem(key: string): Promise<void> {
    if (Platform.OS === 'web') {
      try {
        globalThis.localStorage?.removeItem(key);
      } catch {
        /* nada que borrar */
      }
      return;
    }
    const raw = await SecureStore.getItemAsync(countKey(key));
    if (raw === null) return;
    const count = Number(raw);
    for (let i = 0; i < count; i++) {
      await SecureStore.deleteItemAsync(partKey(key, i));
    }
    await SecureStore.deleteItemAsync(countKey(key));
  },
};
```

- [ ] **Step 7: Correr el test y verificar que pasa**

Run: `npx jest src/lib/secureStorage.test.ts`
Expected: PASS, 3 tests.

- [ ] **Step 8: Crear el cliente**

Crear `src/lib/supabase.ts`:

```ts
import 'react-native-url-polyfill/auto';
import { createClient } from '@supabase/supabase-js';
import { sessionStorage } from './secureStorage';
import type { Database } from '@/src/types/database';

const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  throw new Error(
    'Faltan EXPO_PUBLIC_SUPABASE_URL o EXPO_PUBLIC_SUPABASE_ANON_KEY. Copiá .env.example a .env.local.',
  );
}

/** Única instancia del cliente. Nadie más llama a createClient. */
export const supabase = createClient<Database>(url, anonKey, {
  auth: {
    storage: sessionStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: false,
  },
});
```

- [ ] **Step 9: Verificar tipos y tests**

Run: `npm run typecheck && npm test`
Expected: sin errores; 21 tests en verde.

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: add supabase client with secure session storage"
```

---

## Task 6: Login, sesión y protección de rutas

**Files:**
- Create: `src/features/auth/api.ts`, `src/features/auth/useSession.ts`, `src/features/auth/useSession.test.tsx`
- Create: `app/(auth)/accedi.tsx`, `app/(auth)/_layout.tsx`, `app/(app)/_layout.tsx`
- Modify: `app/_layout.tsx`, `app/index.tsx`

**Interfaces:**
- Consumes: `supabase`, `t`, primitivas de `src/ui/`.
- Produces: `useSession(): { session, profile, isLoading }` donde `profile` es `{ id, business_id, full_name, role, active }`; `signIn(email, password)`, `signOut()` de `src/features/auth/api.ts`.

- [ ] **Step 1: Escribir el test que falla de la sesión**

Crear `src/features/auth/useSession.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { useSession } from './useSession';
import { supabase } from '@/src/lib/supabase';

jest.mock('@/src/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: jest.fn(),
      onAuthStateChange: jest.fn(() => ({ data: { subscription: { unsubscribe: jest.fn() } } })),
    },
    from: jest.fn(),
  },
}));

function wrapper({ children }: { children: ReactNode }) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

const profileRow = {
  id: 'u1',
  business_id: 'b1',
  full_name: 'Anna Ricci',
  role: 'titolare',
  active: true,
};

describe('useSession', () => {
  beforeEach(() => jest.clearAllMocks());

  it('devuelve sesión nula cuando nadie entró', async () => {
    (supabase.auth.getSession as jest.Mock).mockResolvedValue({ data: { session: null } });
    const { result } = renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.session).toBeNull();
    expect(result.current.profile).toBeNull();
  });

  it('carga el perfil cuando hay sesión', async () => {
    (supabase.auth.getSession as jest.Mock).mockResolvedValue({
      data: { session: { user: { id: 'u1' } } },
    });
    (supabase.from as jest.Mock).mockReturnValue({
      select: () => ({ eq: () => ({ single: () => Promise.resolve({ data: profileRow, error: null }) }) }),
    });
    const { result } = renderHook(() => useSession(), { wrapper });
    await waitFor(() => expect(result.current.profile).not.toBeNull());
    expect(result.current.profile?.role).toBe('titolare');
  });
});
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `npx jest src/features/auth/useSession.test.tsx`
Expected: FAIL — `Cannot find module './useSession'`

- [ ] **Step 3: Implementar la capa de autenticación**

Crear `src/features/auth/api.ts`:

```ts
import { supabase } from '@/src/lib/supabase';
import { t } from '@/src/i18n/it';

export type SignInResult = { ok: true } | { ok: false; message: string };

export async function signIn(email: string, password: string): Promise<SignInResult> {
  const { data, error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) {
    return { ok: false, message: t.auth.invalidCredentials };
  }
  // Un usuario desactivado no entra, aunque la contraseña sea correcta.
  const { data: profile } = await supabase
    .from('profiles')
    .select('active')
    .eq('id', data.user.id)
    .single();
  if (!profile?.active) {
    await supabase.auth.signOut();
    return { ok: false, message: t.auth.deactivated };
  }
  return { ok: true };
}

export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}
```

Crear `src/features/auth/useSession.ts`:

```ts
import { useEffect, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import type { Session } from '@supabase/supabase-js';
import { supabase } from '@/src/lib/supabase';
import type { Database } from '@/src/types/database';

export type Profile = Pick<
  Database['public']['Tables']['profiles']['Row'],
  'id' | 'business_id' | 'full_name' | 'role' | 'active'
>;

export function useSession() {
  const [session, setSession] = useState<Session | null>(null);
  const [checked, setChecked] = useState(false);
  const queryClient = useQueryClient();

  useEffect(() => {
    let active = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!active) return;
      setSession(data.session ?? null);
      setChecked(true);
    });
    const { data } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      queryClient.invalidateQueries({ queryKey: ['profile'] });
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, [queryClient]);

  const profileQuery = useQuery({
    queryKey: ['profile', session?.user.id],
    enabled: Boolean(session?.user.id),
    queryFn: async (): Promise<Profile> => {
      const { data, error } = await supabase
        .from('profiles')
        .select('id, business_id, full_name, role, active')
        .eq('id', session!.user.id)
        .single();
      if (error) throw error;
      return data;
    },
  });

  return {
    session,
    profile: profileQuery.data ?? null,
    isLoading: !checked || (Boolean(session) && profileQuery.isLoading),
  };
}
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `npx jest src/features/auth/useSession.test.tsx`
Expected: PASS, 2 tests.

- [ ] **Step 5: Construir la pantalla de login y la guardia**

Crear `app/(auth)/_layout.tsx`:

```tsx
import { Stack } from 'expo-router';
export default function AuthLayout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
```

Crear `app/(auth)/accedi.tsx`:

```tsx
import { useState } from 'react';
import { View, ScrollView } from 'react-native';
import { router } from 'expo-router';
import { Text } from '@/src/ui/Text';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { ListGroup } from '@/src/ui/ListGroup';
import { colors, space } from '@/src/ui/tokens';
import { signIn } from '@/src/features/auth/api';
import { t } from '@/src/i18n/it';

export default function AccediScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    const result = await signIn(email.trim(), password);
    setBusy(false);
    if (result.ok) {
      router.replace('/(app)/(tabs)/prodotti');
    } else {
      setError(result.message);
    }
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={{ padding: space.lg, paddingTop: 72, maxWidth: 480, width: '100%', alignSelf: 'center' }}
    >
      <Text variant="largeTitle" style={{ marginBottom: space.xl }}>
        {t.auth.signInTitle}
      </Text>

      <ListGroup>
        <Field
          label={t.auth.email}
          value={email}
          onChangeText={setEmail}
          autoCapitalize="none"
          keyboardType="email-address"
          textContentType="emailAddress"
        />
        <Field
          label={t.auth.password}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          textContentType="password"
        />
      </ListGroup>

      {error ? (
        <Text variant="footnote" tone="red" style={{ marginBottom: space.md, marginLeft: space.xs }}>
          {error}
        </Text>
      ) : null}

      <Button title={t.auth.submit} onPress={submit} loading={busy} disabled={!email || !password} />

      <View style={{ height: space.lg }} />
      <Text variant="footnote" tone="blue" style={{ textAlign: 'center' }}>
        {t.auth.forgot}
      </Text>
    </ScrollView>
  );
}
```

Crear `app/(app)/_layout.tsx`:

```tsx
import { Redirect, Stack } from 'expo-router';
import { View, ActivityIndicator } from 'react-native';
import { useSession } from '@/src/features/auth/useSession';
import { colors } from '@/src/ui/tokens';

export default function AppLayout() {
  const { session, isLoading } = useSession();

  if (isLoading) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background }}>
        <ActivityIndicator color={colors.blue} />
      </View>
    );
  }
  if (!session) return <Redirect href="/(auth)/accedi" />;

  return <Stack screenOptions={{ headerShown: false }} />;
}
```

Reemplazar `app/_layout.tsx`:

```tsx
import { Slot } from 'expo-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';

export default function RootLayout() {
  const [client] = useState(() => new QueryClient({
    defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
  }));
  return (
    <QueryClientProvider client={client}>
      <Slot />
    </QueryClientProvider>
  );
}
```

Reemplazar `app/index.tsx`:

```tsx
import { Redirect } from 'expo-router';
export default function Index() {
  return <Redirect href="/(app)/(tabs)/prodotti" />;
}
```

- [ ] **Step 6: Probar el login a mano en web**

Run: `npx expo start --web`
Expected: se abre `Accedi`. Entrando con el email y contraseña del titolare de prueba, redirige (todavía a una ruta inexistente: eso se resuelve en la Task 8). Entrando con credenciales falsas, aparece `Email o password non corretti.`

- [ ] **Step 7: Correr todos los tests y tipos**

Run: `npm run typecheck && npm test`
Expected: sin errores; 23 tests en verde.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: add email login with session persistence and route guard"
```

---

## Task 7: Invitaciones por email

**Files:**
- Create: `supabase/functions/invite-user/index.ts`
- Create: `app/(auth)/invito/[token].tsx`
- Modify: `src/features/auth/api.ts` (añadir `acceptInvitation`)

**Interfaces:**
- Consumes: tabla `invitations`, `supabase`, primitivas de `src/ui/`.
- Produces: Edge Function `invite-user` que recibe `{ email, fullName, role }` y devuelve `{ ok: true }`; `acceptInvitation(token, fullName, password)` en `src/features/auth/api.ts`.

- [ ] **Step 1: Escribir la Edge Function**

Sólo el servidor puede crear usuarios: hace falta la clave `service_role`, que nunca viaja al cliente.

Crear `supabase/functions/invite-user/index.ts`:

```ts
import { createClient } from 'jsr:@supabase/supabase-js@2';

const ALLOWED_ROLES = ['titolare', 'responsabile', 'operatore'] as const;

Deno.serve(async (req) => {
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405 });

  const authHeader = req.headers.get('Authorization');
  if (!authHeader) return new Response('Unauthorized', { status: 401 });

  const url = Deno.env.get('SUPABASE_URL')!;
  const anonKey = Deno.env.get('SUPABASE_ANON_KEY')!;
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!;

  // Cliente con el token de quien llama: sirve para saber QUIÉN es.
  const caller = createClient(url, anonKey, {
    global: { headers: { Authorization: authHeader } },
  });
  const { data: profile } = await caller
    .from('profiles')
    .select('business_id, role')
    .single();

  if (!profile || profile.role !== 'titolare') {
    return Response.json({ error: 'Solo il titolare può invitare utenti.' }, { status: 403 });
  }

  const body = await req.json();
  const email = String(body.email ?? '').trim().toLowerCase();
  const fullName = String(body.fullName ?? '').trim();
  const role = body.role;

  if (!email || !fullName || !ALLOWED_ROLES.includes(role)) {
    return Response.json({ error: 'Dati mancanti o non validi.' }, { status: 400 });
  }

  const admin = createClient(url, serviceKey);

  const { data: invitation, error: insertError } = await admin
    .from('invitations')
    .insert({ business_id: profile.business_id, email, full_name: fullName, role })
    .select('token')
    .single();

  if (insertError) {
    return Response.json({ error: 'Questo utente ha già un invito in attesa.' }, { status: 409 });
  }

  const redirect = `${Deno.env.get('SITE_URL')}/invito/${invitation.token}`;
  const { error: inviteError } = await admin.auth.admin.inviteUserByEmail(email, {
    redirectTo: redirect,
    data: { full_name: fullName, business_id: profile.business_id, role },
  });

  if (inviteError) {
    await admin.from('invitations').delete().eq('token', invitation.token);
    return Response.json({ error: 'Non è stato possibile inviare l\'email.' }, { status: 502 });
  }

  return Response.json({ ok: true });
});
```

- [ ] **Step 2: Desplegar la función y configurar su entorno**

```bash
npx supabase functions deploy invite-user
npx supabase secrets set SITE_URL=http://localhost:8081
```

`SUPABASE_URL`, `SUPABASE_ANON_KEY` y `SUPABASE_SERVICE_ROLE_KEY` las inyecta Supabase sola. `SITE_URL` se actualiza a la URL de Vercel en la Task 10.

- [ ] **Step 3: Añadir acceptInvitation**

Añadir al final de `src/features/auth/api.ts`:

```ts
export type AcceptResult = { ok: true } | { ok: false; message: string };

/**
 * El usuario llega desde el email ya autenticado por Supabase. Sólo falta
 * fijar su contraseña, crear el perfil con el rol del invito y marcarlo
 * aceptado.
 */
export async function acceptInvitation(
  token: string,
  fullName: string,
  password: string,
): Promise<AcceptResult> {
  const { data: invitation } = await supabase
    .from('invitations')
    .select('id, business_id, role, expires_at, accepted_at')
    .eq('token', token)
    .maybeSingle();

  if (!invitation || invitation.accepted_at || new Date(invitation.expires_at) < new Date()) {
    return { ok: false, message: t.invite.expired };
  }

  const { data: user, error: updateError } = await supabase.auth.updateUser({ password });
  if (updateError || !user.user) return { ok: false, message: t.errors.generic };

  const { error: profileError } = await supabase.from('profiles').insert({
    id: user.user.id,
    business_id: invitation.business_id,
    full_name: fullName,
    role: invitation.role,
  });
  if (profileError) return { ok: false, message: t.errors.generic };

  await supabase.from('invitations').update({ accepted_at: new Date().toISOString() }).eq('id', invitation.id);
  return { ok: true };
}
```

- [ ] **Step 4: Permitir que el invitado lea su propia invitación**

La política actual sólo deja ver invitaciones al titolare, y el invitado todavía no tiene perfil. Crear `supabase/migrations/0003_invitation_lookup.sql`:

```sql
-- El invitado llega autenticado pero sin perfil: auth_business_id() es null.
-- Necesita leer su propia invitación por token para poder aceptarla.
create policy invitations_select_own on invitations for select to authenticated
  using (
    accepted_at is null
    and expires_at > now()
    and email = (select email from auth.users where id = auth.uid())::citext
  );

-- Y crear su propio perfil una sola vez, con el rol que dice la invitación.
create policy profiles_insert_self on profiles for insert to authenticated
  with check (
    id = auth.uid()
    and exists (
      select 1 from invitations i
      where i.business_id = profiles.business_id
        and i.role = profiles.role
        and i.accepted_at is null
        and i.expires_at > now()
        and i.email = (select email from auth.users where id = auth.uid())::citext
    )
  );

create policy invitations_update_own on invitations for update to authenticated
  using (email = (select email from auth.users where id = auth.uid())::citext)
  with check (accepted_at is not null);
```

Run: `npx supabase db push`
Expected: `Applying migration 0003_invitation_lookup.sql...` sin errores.

- [ ] **Step 5: Crear la pantalla de aceptación**

Crear `app/(auth)/invito/[token].tsx`:

```tsx
import { useState } from 'react';
import { ScrollView } from 'react-native';
import { useLocalSearchParams, router } from 'expo-router';
import { Text } from '@/src/ui/Text';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { ListGroup } from '@/src/ui/ListGroup';
import { colors, space } from '@/src/ui/tokens';
import { acceptInvitation } from '@/src/features/auth/api';
import { t } from '@/src/i18n/it';

export default function InvitoScreen() {
  const { token } = useLocalSearchParams<{ token: string }>();
  const [fullName, setFullName] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setBusy(true);
    setError(null);
    const result = await acceptInvitation(token, fullName.trim(), password);
    setBusy(false);
    if (result.ok) router.replace('/(app)/(tabs)/prodotti');
    else setError(result.message);
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={{ padding: space.lg, paddingTop: 72, maxWidth: 480, width: '100%', alignSelf: 'center' }}
    >
      <Text variant="largeTitle" style={{ marginBottom: space.xl }}>
        {t.invite.title}
      </Text>
      <ListGroup>
        <Field label={t.invite.fullName} value={fullName} onChangeText={setFullName} />
        <Field
          label={t.invite.choosePassword}
          value={password}
          onChangeText={setPassword}
          secureTextEntry
          textContentType="newPassword"
        />
      </ListGroup>
      {error ? (
        <Text variant="footnote" tone="red" style={{ marginBottom: space.md, marginLeft: space.xs }}>
          {error}
        </Text>
      ) : null}
      <Button
        title={t.invite.submit}
        onPress={submit}
        loading={busy}
        disabled={fullName.length < 2 || password.length < 8}
      />
    </ScrollView>
  );
}
```

- [ ] **Step 6: Probar el ciclo completo a mano**

1. Autenticado como titolare, llamar a la función desde la consola del navegador con la app corriendo:

```js
const { data, error } = await window.__supabase.functions.invoke('invite-user', {
  body: { email: 'prueba@example.com', fullName: 'Marco Prova', role: 'operatore' },
});
console.log(data, error);
```

Para que `window.__supabase` exista durante la prueba, añadir temporalmente en `src/lib/supabase.ts`: `if (__DEV__) (globalThis as any).__supabase = supabase;`

2. Abrir el email recibido, seguir el enlace, completar nombre y contraseña.
3. Verificar en el panel de Supabase que la fila de `invitations` tiene `accepted_at` y que existe el perfil con rol `operatore`.

Expected: el alta se completa y el usuario nuevo entra.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: invite users by email with role assignment"
```

---

## Task 8: Cáscara de navegación responsive

**Files:**
- Create: `app/(app)/(tabs)/_layout.tsx`, `app/(app)/(tabs)/prodotti.tsx`, `app/(app)/(tabs)/scadenze.tsx`, `app/(app)/(tabs)/altro.tsx`
- Create: `src/ui/useLayout.ts`, `src/ui/Screen.tsx`
- Modify: `src/i18n/it.ts` (nombres de las secciones)

**Interfaces:**
- Consumes: `useSession`, tokens, `Text`.
- Produces: `useLayout(): { isWide: boolean }` (ancho ≥ 1024); `<Screen title children>` que aplica fondo, padding y título grande.

- [ ] **Step 1: Añadir los textos de navegación**

Añadir a `src/i18n/it.ts` dentro del objeto `t`:

```ts
  nav: {
    prodotti: 'Prodotti',
    scadenze: 'Scadenze',
    scansiona: 'Scansiona',
    altro: 'Altro',
    registro: 'Registro',
    fornitori: 'Fornitori',
    utenti: 'Utenti',
    impostazioni: 'Impostazioni',
    signOut: 'Esci',
  },
```

- [ ] **Step 2: Crear el detector de ancho**

Crear `src/ui/useLayout.ts`:

```ts
import { useWindowDimensions } from 'react-native';

/** 1024 px: por encima hay barra lateral, por debajo pestañas abajo. */
export const WIDE_BREAKPOINT = 1024;

export function useLayout() {
  const { width } = useWindowDimensions();
  return { isWide: width >= WIDE_BREAKPOINT };
}
```

- [ ] **Step 3: Crear el contenedor de pantalla**

Crear `src/ui/Screen.tsx`:

```tsx
import type { ReactNode } from 'react';
import { ScrollView, View } from 'react-native';
import { Text } from './Text';
import { colors, space } from './tokens';

type Props = { title: string; right?: ReactNode; children: ReactNode };

export function Screen({ title, right, children }: Props) {
  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={{ padding: space.lg, paddingTop: space.xl, maxWidth: 1100, width: '100%', alignSelf: 'center' }}
    >
      <View
        style={{
          flexDirection: 'row',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          marginBottom: space.lg,
        }}
      >
        <Text variant="largeTitle">{title}</Text>
        {right}
      </View>
      {children}
    </ScrollView>
  );
}
```

- [ ] **Step 4: Crear las pestañas**

Crear `app/(app)/(tabs)/_layout.tsx`:

```tsx
import { Tabs } from 'expo-router';
import { colors } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.blue,
        tabBarInactiveTintColor: colors.textTertiary,
        tabBarStyle: { backgroundColor: '#FBFBFD', borderTopColor: '#D8D8DC' },
        tabBarLabelStyle: { fontSize: 10, fontWeight: '500' },
      }}
    >
      <Tabs.Screen name="prodotti" options={{ title: t.nav.prodotti }} />
      <Tabs.Screen name="scadenze" options={{ title: t.nav.scadenze }} />
      <Tabs.Screen name="altro" options={{ title: t.nav.altro }} />
    </Tabs>
  );
}
```

Los iconos entran cuando exista el escáner; por ahora las pestañas van con etiqueta sola, que ya es navegable y accesible.

Crear `app/(app)/(tabs)/scadenze.tsx`:

```tsx
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { t } from '@/src/i18n/it';

export default function ScadenzeScreen() {
  return (
    <Screen title={t.nav.scadenze}>
      <Text tone="secondary">Nessun lotto in scadenza.</Text>
    </Screen>
  );
}
```

Crear `app/(app)/(tabs)/altro.tsx`:

```tsx
import { router } from 'expo-router';
import { Screen } from '@/src/ui/Screen';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { useSession } from '@/src/features/auth/useSession';
import { signOut } from '@/src/features/auth/api';
import { t } from '@/src/i18n/it';

export default function AltroScreen() {
  const { profile } = useSession();

  async function leave() {
    await signOut();
    router.replace('/(auth)/accedi');
  }

  return (
    <Screen title={t.nav.altro}>
      <ListGroup>
        <ListRow title={profile?.full_name ?? ''} subtitle={profile?.role ?? ''} />
      </ListGroup>
      <ListGroup>
        <ListRow title={t.nav.signOut} onPress={leave} />
      </ListGroup>
    </Screen>
  );
}
```

`app/(app)/(tabs)/prodotti.tsx` se escribe en la Task 9. Por ahora, un marcador mínimo para que la navegación arranque:

```tsx
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { t } from '@/src/i18n/it';

export default function ProdottiScreen() {
  return (
    <Screen title={t.products.title}>
      <Text tone="secondary">{t.common.loading}</Text>
    </Screen>
  );
}
```

- [ ] **Step 5: Probar la navegación**

Run: `npx expo start --web`
Expected: tras entrar, aparecen tres pestañas y se puede cerrar sesión desde `Altro`, volviendo a `Accedi`.

- [ ] **Step 6: Verificar tipos y tests**

Run: `npm run typecheck && npm test`
Expected: sin errores; 23 tests en verde.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add authenticated app shell with tab navigation"
```

---

## Task 9: Catálogo de productos

**Files:**
- Create: `src/features/products/schema.ts`, `src/features/products/schema.test.ts`
- Create: `src/features/products/queries.ts`, `src/features/products/mutations.ts`
- Modify: `app/(app)/(tabs)/prodotti.tsx`
- Create: `app/(app)/prodotti/nuovo.tsx`, `app/(app)/prodotti/[id].tsx`

**Interfaces:**
- Consumes: `supabase`, `useSession`, primitivas de `src/ui/`, `t`.
- Produces: `productSchema` (Zod) y `ProductInput`; `useProducts()`, `useProduct(id)`; `useCreateProduct()`, `useUpdateProduct()`.

- [ ] **Step 1: Escribir el test que falla de la validación**

Crear `src/features/products/schema.test.ts`:

```ts
import { productSchema } from './schema';

const valid = {
  name: 'Pomodori pelati 400 g',
  barcode: '8001234567890',
  unit: 'pz' as const,
  storage: 'dispensa' as const,
  min_stock: 24,
  has_expiry: true,
};

describe('productSchema', () => {
  it('acepta un producto completo', () => {
    expect(productSchema.safeParse(valid).success).toBe(true);
  });

  it('rechaza un nombre vacío', () => {
    const result = productSchema.safeParse({ ...valid, name: '   ' });
    expect(result.success).toBe(false);
  });

  it('recorta los espacios del nombre', () => {
    const result = productSchema.parse({ ...valid, name: '  Farina 00  ' });
    expect(result.name).toBe('Farina 00');
  });

  it('acepta un producto sin código de barras', () => {
    const result = productSchema.safeParse({ ...valid, barcode: '' });
    expect(result.success).toBe(true);
    if (result.success) expect(result.data.barcode).toBeNull();
  });

  it('rechaza una scorta minima negativa', () => {
    expect(productSchema.safeParse({ ...valid, min_stock: -1 }).success).toBe(false);
  });

  it('rechaza una unidad que no existe', () => {
    expect(productSchema.safeParse({ ...valid, unit: 'cajas' }).success).toBe(false);
  });
});
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `npx jest src/features/products/schema.test.ts`
Expected: FAIL — `Cannot find module './schema'`

- [ ] **Step 3: Implementar la validación**

Crear `src/features/products/schema.ts`:

```ts
import { z } from 'zod';

export const UNITS = ['pz', 'kg', 'l', 'g', 'ml'] as const;
export const STORAGES = ['frigo', 'freezer', 'dispensa'] as const;

export const productSchema = z.object({
  name: z.string().trim().min(1),
  // Un producto sin código guarda null, no cadena vacía: así el índice único
  // por negocio no considera iguales a dos productos sin código.
  barcode: z
    .string()
    .trim()
    .transform((value) => (value === '' ? null : value))
    .nullable(),
  brand: z.string().trim().nullable().optional(),
  unit: z.enum(UNITS),
  storage: z.enum(STORAGES),
  min_stock: z.number().min(0),
  has_expiry: z.boolean(),
});

export type ProductInput = z.infer<typeof productSchema>;
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `npx jest src/features/products/schema.test.ts`
Expected: PASS, 6 tests.

- [ ] **Step 5: Escribir las consultas y mutaciones**

Crear `src/features/products/queries.ts`:

```ts
import { useQuery } from '@tanstack/react-query';
import { supabase } from '@/src/lib/supabase';

export type ProductListItem = {
  id: string;
  name: string;
  unit: string;
  storage: string;
  min_stock: number;
  barcode: string | null;
};

export function useProducts(search = '') {
  return useQuery({
    queryKey: ['products', search],
    queryFn: async (): Promise<ProductListItem[]> => {
      let query = supabase
        .from('products')
        .select('id, name, unit, storage, min_stock, barcode')
        .eq('active', true)
        .order('name');
      if (search.trim()) {
        const term = `%${search.trim()}%`;
        query = query.or(`name.ilike.${term},barcode.ilike.${term}`);
      }
      const { data, error } = await query;
      if (error) throw error;
      return data;
    },
  });
}

export function useProduct(id: string) {
  return useQuery({
    queryKey: ['product', id],
    enabled: Boolean(id),
    queryFn: async () => {
      const { data, error } = await supabase
        .from('products')
        .select('id, name, barcode, brand, unit, storage, min_stock, has_expiry')
        .eq('id', id)
        .single();
      if (error) throw error;
      return data;
    },
  });
}
```

Crear `src/features/products/mutations.ts`:

```ts
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { supabase } from '@/src/lib/supabase';
import { t } from '@/src/i18n/it';
import type { ProductInput } from './schema';

/** Código 23505 de Postgres: violación de índice único. */
const UNIQUE_VIOLATION = '23505';

async function describeBarcodeClash(barcode: string): Promise<string> {
  const { data } = await supabase.from('products').select('name').eq('barcode', barcode).maybeSingle();
  return t.products.duplicateBarcode(data?.name ?? barcode);
}

export function useCreateProduct(businessId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProductInput) => {
      const { data, error } = await supabase
        .from('products')
        .insert({ ...input, business_id: businessId })
        .select('id')
        .single();
      if (error) {
        if (error.code === UNIQUE_VIOLATION && input.barcode) {
          throw new Error(await describeBarcodeClash(input.barcode));
        }
        throw new Error(t.errors.generic);
      }
      return data;
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['products'] }),
  });
}

export function useUpdateProduct(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (input: ProductInput) => {
      const { error } = await supabase
        .from('products')
        .update({ ...input, updated_at: new Date().toISOString() })
        .eq('id', id);
      if (error) {
        if (error.code === UNIQUE_VIOLATION && input.barcode) {
          throw new Error(await describeBarcodeClash(input.barcode));
        }
        throw new Error(t.errors.generic);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] });
      queryClient.invalidateQueries({ queryKey: ['product', id] });
    },
  });
}
```

- [ ] **Step 6: Construir la lista**

Reemplazar `app/(app)/(tabs)/prodotti.tsx`:

```tsx
import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { Field } from '@/src/ui/Field';
import { useProducts } from '@/src/features/products/queries';
import { useSession } from '@/src/features/auth/useSession';
import { space, HIT_SIZE } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

export default function ProdottiScreen() {
  const [search, setSearch] = useState('');
  const { data, isLoading, error } = useProducts(search);
  const { profile } = useSession();
  const canEdit = profile?.role === 'titolare' || profile?.role === 'responsabile';

  return (
    <Screen
      title={t.products.title}
      right={
        canEdit ? (
          <Pressable
            role="button"
            accessibilityLabel={t.products.add}
            onPress={() => router.push('/(app)/prodotti/nuovo')}
            style={{ minHeight: HIT_SIZE, justifyContent: 'center' }}
          >
            <Text variant="body" tone="blue">
              {t.products.add}
            </Text>
          </Pressable>
        ) : undefined
      }
    >
      <ListGroup>
        <Field label={t.common.search} value={search} onChangeText={setSearch} autoCapitalize="none" />
      </ListGroup>

      {error ? <Text tone="red">{t.errors.generic}</Text> : null}
      {isLoading ? <Text tone="secondary">{t.common.loading}</Text> : null}

      {data && data.length === 0 ? (
        <Text tone="secondary" style={{ marginTop: space.md }}>
          {t.products.empty}
        </Text>
      ) : null}

      {data && data.length > 0 ? (
        <ListGroup>
          {data.map((product) => (
            <ListRow
              key={product.id}
              title={product.name}
              subtitle={product.barcode ?? product.storage}
              onPress={() => router.push(`/(app)/prodotti/${product.id}`)}
            />
          ))}
        </ListGroup>
      ) : null}
    </Screen>
  );
}
```

- [ ] **Step 7: Construir el formulario de alta**

Crear `app/(app)/prodotti/nuovo.tsx`:

```tsx
import { useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { Field } from '@/src/ui/Field';
import { Button } from '@/src/ui/Button';
import { useSession } from '@/src/features/auth/useSession';
import { useCreateProduct } from '@/src/features/products/mutations';
import { productSchema, UNITS, STORAGES } from '@/src/features/products/schema';
import { space } from '@/src/ui/tokens';
import { t } from '@/src/i18n/it';

export default function NuovoProdottoScreen() {
  const { profile } = useSession();
  const create = useCreateProduct(profile?.business_id ?? '');

  const [name, setName] = useState('');
  const [barcode, setBarcode] = useState('');
  const [unit, setUnit] = useState<(typeof UNITS)[number]>('pz');
  const [storage, setStorage] = useState<(typeof STORAGES)[number]>('dispensa');
  const [minStock, setMinStock] = useState('0');
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    const parsed = productSchema.safeParse({
      name,
      barcode,
      unit,
      storage,
      min_stock: Number(minStock.replace(',', '.')) || 0,
      has_expiry: true,
    });
    if (!parsed.success) {
      setError(t.errors.generic);
      return;
    }
    try {
      await create.mutateAsync(parsed.data);
      router.back();
    } catch (e) {
      setError(e instanceof Error ? e.message : t.errors.generic);
    }
  }

  return (
    <Screen title={t.products.add}>
      <ListGroup>
        <Field label={t.products.name} value={name} onChangeText={setName} />
        <Field
          label={t.products.barcode}
          value={barcode}
          onChangeText={setBarcode}
          keyboardType="number-pad"
        />
        <Field
          label={t.products.minStock}
          value={minStock}
          onChangeText={setMinStock}
          keyboardType="decimal-pad"
        />
      </ListGroup>

      <ListGroup header={t.products.unit}>
        {UNITS.map((value) => (
          <Chooser key={value} label={value} selected={unit === value} onPress={() => setUnit(value)} />
        ))}
      </ListGroup>

      <ListGroup header={t.products.storage}>
        {STORAGES.map((value) => (
          <Chooser key={value} label={value} selected={storage === value} onPress={() => setStorage(value)} />
        ))}
      </ListGroup>

      {error ? (
        <Text tone="red" variant="footnote" style={{ marginBottom: space.md }}>
          {error}
        </Text>
      ) : null}

      <Button title={t.common.save} onPress={submit} loading={create.isPending} disabled={!name.trim()} />
      <View style={{ height: space.xxl }} />
    </Screen>
  );
}

function Chooser({ label, selected, onPress }: { label: string; selected: boolean; onPress: () => void }) {
  return (
    <ListRow
      title={label}
      onPress={onPress}
      right={
        selected ? (
          <Text tone="blue" variant="headline">
            ✓
          </Text>
        ) : undefined
      }
    />
  );
}
```

- [ ] **Step 8: Construir la ficha de producto**

Crear `app/(app)/prodotti/[id].tsx`:

```tsx
import { useLocalSearchParams } from 'expo-router';
import { Screen } from '@/src/ui/Screen';
import { Text } from '@/src/ui/Text';
import { ListGroup } from '@/src/ui/ListGroup';
import { ListRow } from '@/src/ui/ListRow';
import { useProduct } from '@/src/features/products/queries';
import { t } from '@/src/i18n/it';

export default function ProdottoScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { data, isLoading, error } = useProduct(id);

  if (isLoading) return <Screen title={t.common.loading}><Text tone="secondary">{t.common.loading}</Text></Screen>;
  if (error || !data) return <Screen title={t.errors.generic}><Text tone="red">{t.errors.generic}</Text></Screen>;

  return (
    <Screen title={data.name}>
      <ListGroup>
        <ListRow title={t.products.barcode} right={<Text tone="secondary">{data.barcode ?? '—'}</Text>} />
        <ListRow title={t.products.unit} right={<Text tone="secondary">{data.unit}</Text>} />
        <ListRow title={t.products.storage} right={<Text tone="secondary">{data.storage}</Text>} />
        <ListRow title={t.products.minStock} right={<Text tone="secondary">{String(data.min_stock)}</Text>} />
      </ListGroup>
    </Screen>
  );
}
```

- [ ] **Step 9: Probar el catálogo a mano**

Run: `npx expo start --web`

1. Como titolare: `Nuovo prodotto` está visible, se crea un producto y aparece en la lista.
2. Crear otro con el mismo código de barras: sale `Questo codice è già associato a "…"`.
3. Buscar por nombre parcial: la lista se filtra.
4. Cerrar sesión y entrar como operatore: `Nuovo prodotto` **no** aparece, y la lista sí.

Expected: los cuatro puntos se cumplen.

- [ ] **Step 10: Correr todos los tests y tipos**

Run: `npm run typecheck && npm test`
Expected: sin errores; 29 tests en verde.

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: add product catalogue with search and role-gated editing"
```

---

## Task 10: Despliegue web e instalación en el iPhone

**Files:**
- Create: `app/+html.tsx`, `public/manifest.json`, `vercel.json`
- Modify: `app.json` (nombre, icono, color de tema), `package.json` (script `build:web`)

**Interfaces:**
- Consumes: la app completa de las tareas anteriores.
- Produces: una URL de producción estable; la app instalable desde Safari.

- [ ] **Step 1: Escribir el manifiesto PWA**

Crear `public/manifest.json`:

```json
{
  "name": "Fiestisima",
  "short_name": "Fiestisima",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#F2F2F7",
  "theme_color": "#F2F2F7",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png" }
  ]
}
```

Generar `public/icon-192.png` y `public/icon-512.png` a partir del icono de `assets/`. Si todavía no hay icono propio, usar el que trae la plantilla de Expo: sirve para probar y se reemplaza después.

- [ ] **Step 2: Personalizar el envoltorio HTML**

Crear `app/+html.tsx`:

```tsx
import { ScrollViewStyleReset } from 'expo-router/html';
import type { PropsWithChildren } from 'react';

export default function Root({ children }: PropsWithChildren) {
  return (
    <html lang="it">
      <head>
        <meta charSet="utf-8" />
        <meta httpEquiv="X-UA-Compatible" content="IE=edge" />
        <meta
          name="viewport"
          content="width=device-width, initial-scale=1, viewport-fit=cover"
        />
        <meta name="theme-color" content="#F2F2F7" />
        {/* Sin esto, iOS no ofrece "Aggiungi alla schermata Home" como app. */}
        <meta name="apple-mobile-web-app-capable" content="yes" />
        <meta name="apple-mobile-web-app-status-bar-style" content="default" />
        <meta name="apple-mobile-web-app-title" content="Fiestisima" />
        <link rel="manifest" href="/manifest.json" />
        <link rel="apple-touch-icon" href="/icon-192.png" />
        <ScrollViewStyleReset />
        <style dangerouslySetInnerHTML={{ __html: `body { background-color: #F2F2F7; }` }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
```

- [ ] **Step 3: Configurar Vercel**

Crear `vercel.json`:

```json
{
  "buildCommand": "npx expo export --platform web",
  "outputDirectory": "dist",
  "rewrites": [{ "source": "/(.*)", "destination": "/index.html" }]
}
```

La reescritura es imprescindible: con `output: "single"` cualquier ruta de Expo Router se sirve desde `index.html`; sin ella, recargar en `/prodotti` da 404.

Añadir a `scripts` de `package.json`:

```json
{ "build:web": "expo export --platform web" }
```

- [ ] **Step 4: Verificar la compilación en local**

Run: `npm run build:web`
Expected: se genera `dist/` con `index.html` y los bundles, sin errores.

- [ ] **Step 5: Desplegar**

```bash
npx vercel login
npx vercel link
npx vercel env add EXPO_PUBLIC_SUPABASE_URL production
npx vercel env add EXPO_PUBLIC_SUPABASE_ANON_KEY production
npx vercel --prod
```

Expected: devuelve una URL de producción.

- [ ] **Step 6: Apuntar Supabase a la URL real**

En el panel de Supabase → Authentication → URL Configuration, poner la URL de Vercel como *Site URL* y añadir `https://<url>/invito/*` a *Redirect URLs*. Luego:

```bash
npx supabase secrets set SITE_URL=https://<url-de-vercel>
```

Sin esto, los enlaces de invitación siguen apuntando a localhost.

- [ ] **Step 7: Probar en el iPhone**

1. Abrir la URL en Safari del iPhone.
2. Compartir → `Aggiungi alla schermata Home`.
3. Abrir desde el icono: tiene que verse sin barra de Safari.
4. Entrar, ver el catálogo, crear un producto.
5. Cerrar la app y volver a abrirla: la sesión sigue abierta.

Expected: los cinco puntos se cumplen.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: deploy web build to vercel as installable pwa"
```

---

## Task 11: Poner la documentación al día

**Files:**
- Modify: `docs/01-contexto-y-alcance.md`, `docs/03-modelo-de-datos.md`, `docs/06-escaneo-y-ocr.md`, `docs/07-lotes-carico-scarico.md`, `docs/11-registro-y-reportes.md`, `docs/12-web.md`, `docs/14-arquitectura-tecnica.md`, `docs/15-roadmap.md`, `docs/README.md`
- Create: `docs/16-eventi.md`, `docs/17-sistema-visivo.md`

**Interfaces:**
- Consumes: la sección 8 de la spec, que lista exactamente qué corregir.
- Produces: documentación que describe el sistema que existe.

Esta tarea es la sección 8 de la spec, ejecutada. Va al final a propósito: hasta que el código existe, no se sabe con certeza qué quedó como estaba previsto.

- [ ] **Step 1: Corregir lo que es falso**

En `docs/03-modelo-de-datos.md`, primera línea: sustituir "Implementado en `supabase/migrations/0001_init.sql`. Este documento explica el **porqué**." por "Implementado en `supabase/migrations/0001_init.sql` y `0002_rls.sql`. Este documento explica el **porqué**." (ahora sí existen).

En `docs/15-roadmap.md`, reescribir la Fase 0 con lo realmente hecho, marcando cada casilla que este plan completó y desmarcando lo que no.

- [ ] **Step 2: Añadir los eventos al alcance**

En `docs/01-contexto-y-alcance.md`:
- Sustituir el párrafo "Pregunta abierta con la cliente…" por la descripción del negocio real: salón de fiestas con cocina, alquiler con o sin cocina, catering propio cuando va con cocina.
- Añadir al marco legal una frase sobre el paso adelante de la trazabilidad y por qué el evento lo resuelve.

En `docs/03-modelo-de-datos.md`, añadir `events` al diagrama de entidades y a la tabla, y `event_id` a `movements`.

- [ ] **Step 3: Corregir las expectativas de entrega**

En `docs/06-escaneo-y-ocr.md`, añadir al principio una nota: el OCR requiere build nativo y por tanto cuenta de Apple Developer; no entra en la primera entrega.

En `docs/12-web.md`, cambiar el objetivo: la web es la entrega principal, no la secundaria, mientras no haya cuenta de Apple.

En `docs/07-lotes-carico-scarico.md`, en la tabla de estados de un lote, cambiar el color de `OK` de verde a gris, con la razón: si todo lo correcto es verde, el verde deja de significar algo.

En `docs/11-registro-y-reportes.md`, añadir la columna de evento a la lista de columnas del registro.

- [ ] **Step 4: Corregir la arquitectura**

En `docs/14-arquitectura-tecnica.md`:
- Cambiar React Navigation por Expo Router en la tabla de stack, con la razón (URLs reales en web).
- Reemplazar el árbol del repositorio por el real.
- Reemplazar la tabla de entornos: sin staging, sin Docker, sin cuenta de Apple todavía.

- [ ] **Step 5: Escribir los dos documentos nuevos**

Crear `docs/17-sistema-visivo.md` con los tokens de la sección 5 de la spec, los componentes de `src/ui/` y las dos decisiones con su razón (ningún verde para estados correctos; azul `#0066E0` en vez del de Apple, por contraste).

Crear `docs/16-eventi.md` con lo que hoy se sabe del Bloque B: qué es un evento, los campos que ya existen en la tabla, y una lista explícita de las preguntas sin responder (disponibilidad, presupuestos, señas). Un documento que dice honestamente qué falta decidir vale más que uno que lo inventa.

- [ ] **Step 6: Actualizar el índice**

En `docs/README.md`, añadir las filas 16 y 17 a la tabla y una línea que apunte a `docs/superpowers/specs/` y `docs/superpowers/plans/` como el lugar donde viven las decisiones de diseño y los planes.

- [ ] **Step 7: Verificar que no queda nada falso**

Leer los once documentos de corrido buscando afirmaciones sobre el estado del sistema. Cada una tiene que ser verdad o estar marcada como futura.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "docs: align functional docs with the built system"
```

---

## Verificación final del Bloque 0

Los seis puntos de la sección 9 de la spec, comprobados uno por uno:

- [ ] Un usuario invitado por email completa el alta y entra, en la web y en el iPhone. *(Task 7 + Task 10, paso 7)*
- [ ] Los tres roles existen y sus permisos se aplican en la base: un operatore que llame a la API no recibe `unit_price`. *(Task 4: `npm run test:rls` en verde)*
- [ ] El esquema completo está migrado, con `events` y `movements.event_id`, y las vistas de stock devuelven números correctos. *(Tasks 3 y 4)*
- [ ] La web está desplegada en una URL estable y se instala en el iPhone desde Safari. *(Task 10)*
- [ ] El catálogo se puede listar, crear y editar desde los dos dispositivos. *(Task 9)*
- [ ] Los componentes de `src/ui/` cubren lo dibujado en la maqueta. *(Task 2)*

Comandos que tienen que pasar en limpio antes de dar el bloque por terminado:

```bash
npm run typecheck
npm test
npm run test:rls
npm run build:web
```
