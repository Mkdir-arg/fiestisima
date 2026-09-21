# 04 · Autenticación y usuarios

## Objetivo
Que cada movimiento quede firmado por quien lo hizo, y que entrar a la app sea rápido en un ambiente de trabajo (manos ocupadas, apuro).

## Login
**Flujo**
1. Pantalla `Accedi`: email + password. Botón `Entra`.
2. `Password dimenticata?` → la API envía un email con un link de reset de un solo uso, válido 1 hora.
3. Tras entrar, la sesión persiste hasta que el usuario cierre sesión o pasen 30 días sin uso (duración del refresh token, ver doc 14).

**Reglas**
- No hay registro público. Nadie puede crear cuenta sin invitación. El primer titolare de un negocio no tiene invitación posible (nadie existe todavía para invitarlo): se crea fuera de banda con un script de bootstrap que corre quien administra la infraestructura, no desde la app.
- Face ID (`expo-local-authentication` + `expo-secure-store`) es un ítem futuro, todavía no implementado. Hoy el refresh token se guarda con el mismo mecanismo (`expo-secure-store` en iPhone, `localStorage` en web), pero el segundo ingreso siempre pide password.
- 5 intentos fallidos → bloqueo de 15 minutos, por email. Lo aplica la API (no reinicia el conteo con cada intento adicional durante el bloqueo, para que un tercero no pueda mantener bloqueada a la dueña indefinidamente repitiendo intentos).

**Casos borde**
- Usuario desactivado intenta entrar → `Il tuo account è stato disattivato. Contatta il titolare.` Si ya tenía sesión abierta, la API revoca sus refresh tokens al desactivarlo: el próximo `/auth/refresh` falla y lo saca.
- Sin conexión → ver doc 13 (offline y sincronización).

## Invitaciones
**Flujo**
1. Titolare, en `Utenti`, toca `Invita`: ingresa email, nombre y rol.
2. La API crea la fila en `invitations` y envía un email con un link a `SITE_URL/invito/<token>` (la web; se abre igual desde el navegador del iPhone).
3. El invitado abre el link, define su password y queda vinculado al negocio con el rol asignado. `accepted_at` se completa.
4. La invitación caduca a los 7 días. Se puede reenviar (`Reinvia`) o cancelar.

**Reglas**
- Un email solo puede tener una invitación pendiente por negocio.
- Si el email ya pertenece a un usuario activo del negocio → `Questo utente fa già parte dell'attività.`

## ABM de usuarios (`Utenti`)
Solo titolare.

**Lista**: nombre, rol (pill), último acceso, estado. Sección separada `Inviti in attesa`.

**Acciones por usuario**
- Cambiar rol (selector Titolare / Responsabile / Operatore). Cambiar el titolare pide confirmación doble porque transfiere la propiedad.
- Desactivar / reactivar. Desactivar no borra nada.
- Ver actividad: últimos 50 movimientos de ese usuario.

**Reglas**
- El titolare no puede desactivarse a sí mismo ni bajarse de rol si es el único titolare.
- Tabla de permisos visible en la misma pantalla (solo lectura), para que la dueña entienda qué puede hacer cada rol antes de asignarlo.

## Criterios de aceptación
- Un invitado completa el alta en menos de 2 minutos desde que recibe el email.
- Un usuario desactivado ve el mensaje correcto y no puede leer ningún dato.
