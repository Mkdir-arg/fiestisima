# 14 · Arquitectura técnica

## Stack
| Capa | Elección | Por qué |
|---|---|---|
| App + web | **Expo (React Native)** con `react-native-web` | Un solo código para iPhone y navegador. EAS Build genera el `.ipa` sin Mac. |
| Navegación | **Expo Router**, no React Navigation | Da URLs reales en web (`/prodotti/123`), botón atrás del navegador y enlaces que se pueden compartir o guardar. Con React Navigation la web queda con una sola URL para todo — correcto para una app sólo nativa, no para ésta. |
| Backend | **Supabase** (Postgres + Auth + Storage + Edge Functions + Realtime) | Base relacional real, RLS para permisos, auth y storage resueltos, plan gratuito suficiente para un negocio. |
| Cámara / barcode | `expo-camera` | Lee EAN/QR nativo en iOS. |
| OCR | ML Kit Text Recognition (`react-native-mlkit-ocr` o `@react-native-ml-kit/text-recognition`) | On-device, gratis, sin enviar fotos a terceros. Requiere dev build (no Expo Go) y por tanto cuenta de Apple Developer — no entra en la primera entrega (ver doc 06). |
| Biometría | `expo-local-authentication` + `expo-secure-store` | Face ID. |
| Push | Expo Push + cron en Supabase | Sin Firebase propio. |
| PDF | Edge Function con `pdf-lib` o Puppeteer | Mismo PDF desde app y web. |
| Offline (MVP) | `expo-sqlite` para la cola | Ver doc 13. |
| Estado / datos | TanStack Query + Supabase client | Cache, reintentos, invalidación. |

## Estructura del repo
Una sola app en la raíz, no un monorepo con `apps/mobile/`: con un único paquete el monorepo es ceremonia sin beneficio, y el nombre "mobile" mentiría ahora que la web es la entrega principal.

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
│   ├── ui/               sistema de diseño, sin conocimiento del dominio (ver doc 17)
│   ├── lib/              supabase · openfoodfacts · ocr · queue · format
│   ├── i18n/it.ts        todos los textos, desde el día 1
│   └── types/database.ts generado por Supabase, nunca a mano
├── supabase/migrations/  SQL versionado. Nunca se edita una migración aplicada.
└── docs/                 Esta documentación
```

No hay carpeta `screens/`: con Expo Router las rutas ya son archivos, y sería el mismo concepto dos veces. Tampoco `navigation/`: la navegación la resuelve el árbol de `app/`. Tres capas y una regla que no se rompe: `app/` sólo compone (lee la URL, arma la pantalla, cero lógica de negocio); `src/features/<dominio>/` tiene consultas, mutaciones, validación y componentes propios, y una feature nunca importa de otra (lo compartido sube a `lib/` o `ui/`); `src/ui/` no sabe que existen los lotes, sólo recibe props y dibuja.

**Estado real al momento de escribir esto**: sólo existen `app/_layout.tsx`, `app/index.tsx`, `src/i18n/it.ts`, `src/lib/lotStatus.ts` y los seis componentes de `src/ui/` (doc 17). El resto del árbol de arriba es el destino, no el inventario — se completa a medida que avanzan las tareas bloqueadas por la cuenta de Supabase.

## Convenciones
- **Idiomas**: código y commits en inglés; documentación en español; textos de UI en italiano, centralizados en `src/i18n/it.ts` desde el día 1 (aunque solo haya un idioma).
- **Tipos de la base** generados con `supabase gen types typescript` tras cada migración. Prohibido tipar a mano lo que la base ya define.
- **Nada de lógica de permisos solo en el cliente**: toda regla de acceso tiene su política RLS.
- **Migraciones** numeradas `NNNN_descripcion.sql`. Cambios de esquema = nueva migración.
- **Commits**: Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`).
- **Ramas**: `main` siempre desplegable; features en `feat/<nombre>`; PR con CI verde.

## Entornos
Estado real de las cuentas: hay Vercel. **No hay** cuenta de Supabase, ni Docker, ni Apple Developer.

| | Decisión |
|---|---|
| Base de datos | Un proyecto Supabase gratuito. Sin Docker: se desarrolla contra la nube, no con `supabase start`. |
| Web | Vercel. |
| iPhone | Safari con "Añadir a pantalla de inicio", más Expo Go para probar funciones nativas durante el desarrollo. |
| Staging | No, todavía. No tiene sentido mantener dos entornos antes de que exista un usuario. |
| Apple Developer | No existe todavía. Se crea cuando la web esté probada y se quiera nativo — el mismo código compila, no se tira nada. |

## Distribución iOS (bloqueada hasta que exista la cuenta)
1. Cuenta Apple Developer (99 €/año) a nombre de la dueña o del desarrollador.
2. `eas build --platform ios --profile preview` → TestFlight para probar con ella.
3. `eas submit` → App Store (puede ser "no listada" para que solo se instale con link).

## Seguridad y datos
- Fotos de DDT en bucket privado; se sirven con URL firmada de 1 h.
- Backups diarios de Supabase (incluidos en el plan).
- Datos en la UE (región Frankfurt), relevante por GDPR.
