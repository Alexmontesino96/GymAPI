# Permisos de la API de GymAPI

Este documento describe los permisos (scopes) utilizados en la API del sistema de gestión de gimnasios, organizados por módulo y rol de usuario.

## Roles de Usuario

El sistema define tres roles principales de usuario:

- **ADMIN**: Administradores del gimnasio con acceso completo a todas las funcionalidades.
- **TRAINER**: Entrenadores que gestionan clases, eventos y miembros asignados.
- **MEMBER**: Miembros del gimnasio que participan en clases y eventos.

## Permisos por Módulo

### Autenticación (Auth)

| Scope | Descripción | Roles |
|-------|-------------|-------|
| `read:auth_logs` | Acceso a logs de autenticación | ADMIN |
| `read:user_sessions` | Ver sesiones de usuario activas | ADMIN, TRAINER (solo propias) |
| `delete:user_sessions` | Eliminar sesiones de usuario | ADMIN, TRAINER (solo propias) |

### Usuarios (Users)

| Scope | Descripción | Roles |
|-------|-------------|-------|
| `create:users` | Crear usuarios en la base de datos local | ADMIN |
| `create:own_user` | Registrar el propio perfil | Todos los usuarios autenticados |
| `read:users` | Ver perfiles de usuarios | ADMIN, TRAINER |
| `read:own_user` | Ver el propio perfil | Todos los usuarios autenticados |
| `update:users` | Modificar cualquier perfil de usuario | ADMIN |
| `update:own_user` | Modificar el propio perfil | Todos los usuarios autenticados |
| `delete:users` | Eliminar usuarios de la base de datos | ADMIN |

### Relaciones Entrenador-Miembro (Trainer-Member)

| Scope | Descripción | Roles |
|-------|-------------|-------|
| `create:relationships` | Crear relaciones entrenador-miembro | ADMIN, TRAINER |
| `read:relationships` | Ver relaciones entrenador-miembro | ADMIN, TRAINER, MEMBER (solo propias) |
| `read:own_relationships` | Ver las propias relaciones | Todos los usuarios autenticados |
| `update:relationships` | Actualizar relaciones entrenador-miembro | ADMIN, TRAINER (solo propias) |
| `delete:relationships` | Eliminar relaciones entrenador-miembro | ADMIN, TRAINER, MEMBER (solo propias) |
| `admin:relationships` | Administrar todas las relaciones | ADMIN |

### Programación (Schedule)

| Scope | Descripción | Roles |
|-------|-------------|-------|
| `read:schedules` | Ver horarios del gimnasio | Todos los usuarios autenticados |
| `create:schedules` | Crear y modificar horarios generales | ADMIN |
| `read:class_types` | Ver tipos de clases | Todos los usuarios autenticados |
| `create:class_types` | Crear y modificar tipos de clases | ADMIN |
| `read:classes` | Ver sesiones de clases programadas | Todos los usuarios autenticados |
| `create:classes` | Crear sesiones de clases | ADMIN, TRAINER |
| `update:classes` | Modificar sesiones de clases | ADMIN, TRAINER (solo propias) |
| `delete:classes` | Eliminar sesiones de clases | ADMIN, TRAINER (solo propias) |
| `read:class_registrations` | Ver registros a clases | ADMIN, TRAINER |
| `manage:class_registrations` | Gestionar registros a clases (añadir/eliminar participantes) | ADMIN, TRAINER |
| `register:classes` | Registrarse a clases | MEMBER |

### Eventos (Events)

| Scope | Descripción | Roles |
|-------|-------------|-------|
| `read:events` | Ver eventos | Todos los usuarios autenticados |
| `create:events` | Crear eventos | ADMIN, TRAINER |
| `update:events` | Modificar eventos | ADMIN, TRAINER (solo propios) |
| `delete:events` | Eliminar eventos | ADMIN, TRAINER (solo propios) |
| `register:events` | Registrarse a eventos | MEMBER |
| `admin:events` | Administrar todos los eventos (incluye eliminación) | ADMIN |

### Chat

| Scope | Descripción | Roles |
|-------|-------------|-------|
| `use:chat` | Utilizar el sistema de chat | Todos los usuarios autenticados |
| `create:chat_rooms` | Crear salas de chat | ADMIN, TRAINER |
| `manage:chat_rooms` | Gestionar miembros de salas de chat | ADMIN, TRAINER |

## Asignación de Permisos

La asignación de permisos se realiza a través de Auth0 y se incluye en los tokens JWT cuando un usuario se autentica. Estos permisos determinan a qué endpoints tiene acceso el usuario y qué operaciones puede realizar.

## Validación de Permisos

La validación de permisos se realiza en dos niveles:

1. **Nivel de endpoint**: FastAPI verifica los scopes requeridos en la definición del endpoint.
2. **Nivel de lógica de negocio**: Dentro de cada endpoint, se realizan verificaciones adicionales como:
   - ¿El usuario es propietario del recurso?
   - ¿El usuario tiene el rol adecuado?
   - ¿El recurso existe y está disponible?

## Ejemplo de Uso

```python
@router.post("/events/", response_model=EventSchema)
async def create_event(
    event_in: EventCreate,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["create:events"]),
):
    # Código del endpoint...
```

En este ejemplo, solo los usuarios con el scope `create:events` (ADMIN y TRAINER) pueden acceder al endpoint para crear eventos. 