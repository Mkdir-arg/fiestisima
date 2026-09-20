# 02 · Roles y permisos

## Roles
| Rol (en la app) | Quién es | Resumen |
|---|---|---|
| `Titolare` | Dueña del negocio | Acceso total. Único que gestiona usuarios y ve costos. |
| `Responsabile` | Encargado | Todo lo operativo + catálogo + reportes. No gestiona usuarios. |
| `Operatore` | Empleado | Solo carico, scarico y consulta. No ve precios. |

Hay exactamente un `Titolare` por negocio en el MVP. El rol se asigna al invitar y solo el titolare puede cambiarlo.

## Matriz de permisos
| Acción | Titolare | Responsabile | Operatore |
|---|:-:|:-:|:-:|
| Escanear y consultar productos, lotes, stock | ✓ | ✓ | ✓ |
| Registrar carico | ✓ | ✓ | ✓ |
| Registrar scarico (uso / vendita) | ✓ | ✓ | ✓ |
| Registrar scarto | ✓ | ✓ | ✓ (con motivo obligatorio) |
| Ver precio unitario y valor del stock | ✓ | ✓ | — |
| Crear / editar / desactivar productos | ✓ | ✓ | — |
| Crear / editar fornitori | ✓ | ✓ | — |
| Anular un movimiento (últimas 24 h) | ✓ | ✓ | solo los propios |
| Exportar registro PDF / Excel | ✓ | ✓ | — |
| Ver dashboard web completo | ✓ | ✓ | — (ve solo Scadenze y Prodotti) |
| Invitar usuarios, cambiar roles, desactivar | ✓ | — | — |
| Editar datos del negocio | ✓ | — | — |

## Reglas
- Los permisos se aplican **en el backend** (Row Level Security de Postgres), no solo escondiendo botones. Un operatore que llame a la API directamente tampoco puede ver `unit_price`.
- Todo movimiento guarda `created_by`. No existe el "usuario anónimo": para registrar algo hay que estar logueado.
- Nunca se borra un movimiento: se **anula** con un movimiento inverso que referencia al original. El registro de trazabilidad tiene que ser inmutable.
- Un usuario desactivado no puede entrar, pero sus movimientos históricos siguen apareciendo con su nombre.

## Criterios de aceptación
- Un operatore no ve el campo precio en ninguna pantalla ni lo recibe en ninguna respuesta de la API.
- Un responsabile que intenta abrir `Utenti` recibe un mensaje `Solo il titolare può gestire gli utenti`.
- Al desactivar a un usuario, su sesión activa se cierra en menos de 1 minuto.
