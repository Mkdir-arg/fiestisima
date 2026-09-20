# 04 · Autenticación y usuarios

## Objetivo
Que cada movimiento quede firmado por quien lo hizo, y que entrar a la app sea rápido en un ambiente de trabajo (manos ocupadas, apuro).

## Login
**Flujo**
1. Pantalla `Accedi`: email + password. Botón `Entra`.
2. Alternativa: `Accedi con Face ID`. Disponible solo si el usuario ya entró una vez con password en ese dispositivo y activó la opción.
3. `Password dimenticata?` → Supabase envía email con link de reset.
4. Tras entrar, la sesión persiste hasta que el usuario cierre sesión o pasen 30 días sin uso.

**Reglas**
- No hay registro público. Nadie puede crear cuenta sin invitación.
- Face ID usa `expo-local-authentication`; el refresh token se guarda en `expo-secure-store`, nunca en AsyncStorage.
- 5 intentos fallidos → bloqueo de 15 minutos (lo maneja Supabase Auth).

**Casos borde**
- Usuario desactivado intenta entrar → `Il tuo account è stato disattivato. Contatta il titolare.`
- Sin conexión → se permite entrar con Face ID a la sesión cacheada para consultar; las escrituras se encolan (ver doc 13).

## Invitaciones
**Flujo**
1. Titolare, en `Utenti`, toca `Invita`: ingresa email, nombre y rol.
2. El sistema crea la fila en `invitations` y envía un email con link (`fiestisima://invite/<token>` en app, URL web como fallback).
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
- Después del primer login con password, el segundo ingreso con Face ID tarda menos de 2 segundos.
- Un usuario desactivado ve el mensaje correcto y no puede leer ningún dato.
