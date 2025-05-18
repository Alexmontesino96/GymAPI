# Sistema Simplificado de Scopes para GymAPI

Este documento describe el nuevo sistema simplificado de scopes para la autenticación y autorización en GymAPI.

## Beneficios del Nuevo Sistema

- **Simplicidad**: Reduce de más de 30 scopes a solo 7 scopes fundamentales
- **Consistencia**: Nomenclatura estandarizada y coherente
- **Mantenimiento**: Facilita la gestión de permisos en Auth0
- **Flexibilidad**: Mejor adaptación a un sistema multi-tenant

## Scopes Simplificados

| Scope | Descripción | Reemplaza a |
|-------|-------------|------------|
| `user:read` | Permite leer información de usuarios y perfiles | `read:profile`, `read:users`, `read:members` |
| `user:write` | Permite crear o modificar usuarios | `admin:users`, `update:users` |
| `user:admin` | Permite operaciones administrativas sobre usuarios | `delete:users` |
| `resource:read` | Permite leer recursos (eventos, clases, participaciones, etc.) | `read:events`, `read:own_events`, `read:schedules`, `read:own_schedules`, `read:relationships`, `read:own_relationships`, `read:participations`, `read:own_participations` |
| `resource:write` | Permite crear o modificar recursos | `create:events`, `create:participations`, `create:relationships`, `create:schedules`, `update:events`, `update:participations`, `update:relationships`, `update:schedules` |
| `resource:admin` | Permite operaciones administrativas sobre recursos | `delete:events`, `delete:schedules`, `admin:events`, `admin:relationships`, `delete:relationships` |
| `tenant:read` | Permite acceso a información de gimnasios | `read:gyms`, `read:gym_users` |
| `tenant:admin` | Permite administración de gimnasios | `admin:gyms` |

## Modelo de Autorización

El nuevo modelo de autorización opera en dos niveles:

1. **Nivel Global (Auth0)**
   - Auth0 verifica que el usuario tiene los scopes necesarios para la operación general
   - Estos scopes son asignados según el rol global del usuario (MEMBER, TRAINER, ADMIN, SUPER_ADMIN)

2. **Nivel Contextual (Aplicación)**
   - La aplicación verifica el rol específico del usuario en el gimnasio actual
   - Estos roles se almacenan en la tabla `UserGym` (MEMBER, TRAINER, ADMIN, OWNER)
   - Las funciones como `verify_gym_access` y `verify_gym_admin_access` verifican estos roles

## Asignación de Scopes por Rol Global

### MEMBER
- `user:read`
- `resource:read`
- `resource:write` (limitado)
- `tenant:read`

### TRAINER
- `user:read`
- `resource:read`
- `resource:write`
- `tenant:read`

### ADMIN
- `user:read`
- `user:write`
- `resource:read`
- `resource:write`
- `resource:admin`
- `tenant:read`

### SUPER_ADMIN
- Todos los scopes

## Notas de Implementación

1. Esta simplificación delega más lógica de autorización al código de la aplicación
2. La verificación de permisos específicos debe hacerse considerando:
   - El scope global del usuario (de Auth0)
   - El rol del usuario en el gimnasio específico (de UserGym)
   - El contexto de la operación (propio vs. otros usuarios) 