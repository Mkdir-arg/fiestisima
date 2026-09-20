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

Crear `.env.test` en la raíz (está en `.gitignore`, nunca se commitea).

**Para que la suite corra:**

    EXPO_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
    EXPO_PUBLIC_SUPABASE_ANON_KEY=<anon key>
    SUPABASE_SERVICE_ROLE_KEY=<service role key>

La service role key aparece en Project Settings → API. Con estas tres alcanza
para correr toda la suite salvo una prueba (ver abajo).

**Extra, opcional, para una sola prueba:**

    SUPABASE_DB_URL=postgresql://postgres:<password>@<host>:5432/postgres

`SUPABASE_DB_URL` es la cadena de conexión directa (o el connection pooler) de
Project Settings → Database. La necesita únicamente la prueba de
`security_barrier` en "tenant isolation cannot be bypassed" ("un predicado
que sólo falla contra la fila de business B no debe filtrar su existencia"),
porque ese ataque se arma con un WHERE arbitrario ("1 / (expires_on - fecha)"
sobre una fila concreta) que la gramática de filtros de PostgREST no permite
expresar en absoluto - sólo acepta operadores fijos contra literales, nunca
una expresión arbitraria provista por el caller. Para reproducir el ataque de
verdad hay que hablarle a Postgres directo, autenticado como si fuera
PostgREST (`set local role authenticated` + `request.jwt.claims`).

Sin `SUPABASE_DB_URL` esa prueba se salta sola (`it.skip`) y la suite avisa
por consola al arrancar con el nombre exacto de la variable que falta; el
resto de la suite corre igual. No hace falta esa credencial para nada más, y
no vale la pena que una prueba opcional le exija a quien corre `test:rls`
una credencial bastante más sensible que el resto (una conexión directa a
Postgres, no una API key con alcance acotado).

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
ella. A diferencia de `anon` (que en 0002 no tiene ningún `grant select`
sobre estas vistas, y por lo tanto recibe un error de permiso), la service
role key sí conserva el `select` que Supabase le otorga por defecto: la
consulta no falla, simplemente el filtro interno de la vista
(`business_id = auth_business_id()`) no matchea ninguna fila, y el resultado
es siempre un array vacío. Mismo destino final (nada de datos reales), por
dos caminos distintos. Por eso en la suite la service role key sólo se usa
contra las tablas base (`lots`, `movements`, `profiles`, ...), donde sí tiene
bypass de RLS; para leer stock o precios "como los vería un usuario", las
pruebas siempre usan los clientes `titolare`/`operatore` autenticados.
