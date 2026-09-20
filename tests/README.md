# Pruebas de integración de permisos

No hay Docker, así que no hay base local: estas pruebas corren contra un
proyecto Supabase real. A diferencia de la primera versión de este plan, la
suite no depende de usuarios creados a mano desde el panel: se aprovisiona a
sí misma con la service role key en `beforeAll` y se desmonta en `afterAll`,
así que puede correrse una y otra vez contra el mismo proyecto sin dejar
basura ni requerir pasos manuales entre corridas.

## Qué crea la suite y qué necesita de vos

En `beforeAll` se crean, con la service role key:

- Dos negocios efímeros ("business A" y "business B"). Business A es donde
  vive la mayoría de las pruebas (título, catálogo, lotes, movimientos);
  business B existe únicamente para probar el límite entre inquilinos y
  nunca se usa con sesión propia, siempre se lee y escribe con la service
  role key.
- Un usuario titolare y un usuario operatore de business A (vía
  `auth.admin.createUser` con `email_confirm: true`, sin pasar por el panel
  ni por un email real).
- Un usuario titolare de business B, sólo para satisfacer `created_by` en
  sus lotes.
- Catálogo base de business A (proveedor, producto, un lote con precio y
  documento, un lote sin ningún movimiento) y un lote de business B.

En `afterAll` se borran los dos negocios (el `on delete cascade` en cada
`business_id` de 0001 se lleva puesto perfiles, catálogo, lotes y
movimientos en una sola sentencia) y después se borran los usuarios de
`auth.users` que la suite creó, que no desaparecen solos con el borrado del
negocio.

Las pruebas 11, 12 y 13 (acciones de borrado sobre foreign keys) crean sus
propios usuarios/lotes/eventos/movimientos descartables dentro de cada test
y los limpian en su propio `finally`, en vez de tocar el catálogo
compartido - son las únicas que de verdad borran filas, y borrar es
exactamente lo que están probando.

## Variables de entorno

Crear `.env.test` en la raíz (está en `.gitignore`, nunca se commitea):

    EXPO_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
    EXPO_PUBLIC_SUPABASE_ANON_KEY=<anon key>
    SUPABASE_SERVICE_ROLE_KEY=<service role key>
    SUPABASE_DB_URL=postgresql://postgres:<password>@<host>:5432/postgres

La service role key aparece en Project Settings → API. `SUPABASE_DB_URL` es
la cadena de conexión directa (o el connection pooler) de Project Settings →
Database: la necesita únicamente la prueba de `security_barrier` ("un
predicado que sólo falla contra la fila de business B no debe filtrar su
existencia"), porque ese ataque se arma con un WHERE arbitrario que la
gramática de filtros de PostgREST no permite expresar - hay que hablarle a
Postgres directo, autenticado como si fuera PostgREST (`set local role
authenticated` + `request.jwt.claims`), para replicar el escenario real.

Ninguna de estas claves va en un archivo commiteado. `SUPABASE_SERVICE_ROLE_KEY`
y `SUPABASE_DB_URL` en particular tienen acceso total a la base: tratarlas
como se trataría cualquier credencial de administrador.

Correr con: `npm run test:rls`

No van en CI mientras las credenciales vivan sólo en la máquina.

## Por qué no hacen falta más variables

La primera versión de este plan pedía `TEST_TITOLARE_EMAIL`,
`TEST_OPERATORE_EMAIL` y sus contraseñas, para usuarios creados a mano desde
el panel. Con la service role key alcanza para crear usuarios confirmados
por API (`auth.admin.createUser`), así que esas cuatro variables ya no
existen: la suite no depende de que alguien haya seguido un paso manual
antes de correrla, y arranca en un proyecto Supabase recién creado sin
seed de ningún tipo.

## Advertencia sobre `lots_view`, `lot_stock` y `product_stock` con la service role key

Las tres vistas filtran por `auth_business_id()`, que resuelve a través de
`auth.uid()`. La service role key no lleva claim `sub`, así que
`auth.uid()` (y por lo tanto `auth_business_id()`) también da `null` para
ella - consultar esas vistas con la service role key devuelve siempre cero
filas, por el mismo mecanismo que bloquea a un caller sin sesión. Por eso
en la suite la service role key sólo se usa contra las tablas base (`lots`,
`movements`, `profiles`, ...), donde sí tiene bypass de RLS; para leer stock
o precios "como los vería un usuario", las pruebas siempre usan los
clientes `titolare`/`operatore` autenticados.
