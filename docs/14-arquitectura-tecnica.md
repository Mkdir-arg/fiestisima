# 14 · Arquitectura técnica

## Stack
| Capa | Elección | Por qué |
|---|---|---|
| App + web | **Expo (React Native)** con `react-native-web` | Un solo código para iPhone y navegador. EAS Build genera el `.ipa` sin Mac. |
| Navegación | React Navigation (stack + tabs) | Estándar, tipado. |
| Backend | **Supabase** (Postgres + Auth + Storage + Edge Functions + Realtime) | Base relacional real, RLS para permisos, auth y storage resueltos, plan gratuito suficiente para un negocio. |
| Cámara / barcode | `expo-camera` | Lee EAN/QR nativo en iOS. |
| OCR | ML Kit Text Recognition (`react-native-mlkit-ocr` o `@react-native-ml-kit/text-recognition`) | On-device, gratis, sin enviar fotos a terceros. Requiere dev build (no Expo Go). |
| Biometría | `expo-local-authentication` + `expo-secure-store` | Face ID. |
| Push | Expo Push + cron en Supabase | Sin Firebase propio. |
| PDF | Edge Function con `pdf-lib` o Puppeteer | Mismo PDF desde app y web. |
| Offline (MVP) | `expo-sqlite` para la cola | Ver doc 13. |
| Estado / datos | TanStack Query + Supabase client | Cache, reintentos, invalidación. |

## Estructura del repo
```
fiestisima/
├── apps/mobile/            Expo (iOS + web)
│   ├── App.tsx
│   ├── app.json · eas.json
│   └── src/
│       ├── screens/        Una carpeta por pantalla cuando crezca
│       ├── components/     UI reutilizable
│       ├── navigation/     Stacks y tabs tipados
│       ├── lib/            supabase, openfoodfacts, ocr, queue
│       ├── features/       lógica por dominio (lots, products, users…)  ← a crear
│       └── types/          tipos generados de la base
├── supabase/
│   ├── migrations/         SQL versionado. Nunca se edita una migración aplicada.
│   └── functions/          Edge Functions (pdf, push)  ← a crear
├── docs/                   Esta documentación
└── .github/workflows/      CI
```

## Convenciones
- **Idiomas**: código y commits en inglés; documentación en español; textos de UI en italiano, centralizados en `src/i18n/it.ts` desde el día 1 (aunque solo haya un idioma).
- **Tipos de la base** generados con `supabase gen types typescript` tras cada migración. Prohibido tipar a mano lo que la base ya define.
- **Nada de lógica de permisos solo en el cliente**: toda regla de acceso tiene su política RLS.
- **Migraciones** numeradas `NNNN_descripcion.sql`. Cambios de esquema = nueva migración.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
- **Ramas**: `main` siempre desplegable; features en `feat/<nombre>`; PR con CI verde.

## Entornos
| | Local | Staging | Producción |
|---|---|---|---|
| Base | `supabase start` (Docker) | proyecto Supabase `fiestisima-staging` | proyecto `fiestisima` |
| App | Expo Go / dev build | EAS preview → TestFlight interno | App Store |
| Web | `expo start --web` | Vercel preview | Vercel producción |

## Distribución iOS
1. Cuenta Apple Developer (99 €/año) a nombre de la dueña o del desarrollador.
2. `eas build --platform ios --profile preview` → TestFlight para probar con ella.
3. `eas submit` → App Store (puede ser "no listada" para que solo se instale con link).

## Seguridad y datos
- Fotos de DDT en bucket privado; se sirven con URL firmada de 1 h.
- Backups diarios de Supabase (incluidos en el plan).
- Datos en la UE (región Frankfurt), relevante por GDPR.
