"""
AsyncAuth0SyncService - Servicio async para sincronización de roles con Auth0.

Este módulo proporciona funcionalidades para sincronizar roles de usuarios
entre la base de datos local y Auth0 Management API.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import List, Optional
import logging
from types import SimpleNamespace
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.services.auth0_mgmt import auth0_mgmt_service
from app.core.config import get_settings

logger = logging.getLogger("async_auth0_sync_service")

# Mapeo de nombres de roles internos a nombres de roles en Auth0
ROLE_NAME_MAPPING = {
    "SUPER_ADMIN": "SuperAdmin",
    "ADMIN": "Admin",
    "OWNER": "Owner",
    "TRAINER": "Trainer",
    "MEMBER": "Member"
}

# Mapeo de roles de usuario global a nivel de prioridad (mayor número = mayor prioridad)
USER_ROLE_PRIORITY = {
    UserRole.SUPER_ADMIN: 100,
    UserRole.ADMIN: 80,
    UserRole.TRAINER: 60,
    UserRole.MEMBER: 40,
    None: 0
}

# Mapeo de roles de gimnasio a nivel de prioridad
GYM_ROLE_PRIORITY = {
    GymRoleType.OWNER: 90,
    GymRoleType.ADMIN: 70,
    GymRoleType.TRAINER: 50,
    GymRoleType.MEMBER: 30,
    None: 0
}

# Permisos asignados a cada rol
# Nota: Esto es solo documentación/referencia.
# Los permisos reales se asignan en la Action de Auth0.
ROLE_PERMISSIONS = {
    "SUPER_ADMIN": [
      "tenant:admin", "tenant:read",
      "user:admin", "user:write", "user:read",
      "resource:admin", "resource:write", "resource:read"
    ],
    "ADMIN": [
      "tenant:read",
      "user:write", "user:read",
      "resource:admin", "resource:write", "resource:read"
    ],
    "OWNER": [
      "tenant:admin", "tenant:read",
      "user:write", "user:read",
      "resource:admin", "resource:write", "resource:read"
    ],
    "TRAINER": [
      "tenant:read",
      "user:read",
      "resource:write", "resource:read"
    ],
    "MEMBER": [
      "tenant:read",
      "user:read",
      "resource:write", "resource:read"
    ]
}


def determine_highest_role(global_role: UserRole, gym_roles: List[GymRoleType]) -> str:
    """
    Determina el rol más alto de un usuario basado en su rol global y roles de gimnasio.

    Args:
        global_role: Rol global del usuario
        gym_roles: Lista de roles del usuario en diferentes gimnasios

    Returns:
        str: Nombre del rol más alto

    Note:
        Función pura sin acceso a BD - no requiere async.
        Compara prioridades entre rol global y roles de gimnasio.
    """
    # Determinar la prioridad del rol global
    global_priority = USER_ROLE_PRIORITY.get(global_role, 0)

    # Determinar la prioridad más alta entre los roles de gimnasio
    gym_priority = 0
    highest_gym_role = None

    for role in gym_roles:
        role_priority = GYM_ROLE_PRIORITY.get(role, 0)
        if role_priority > gym_priority:
            gym_priority = role_priority
            highest_gym_role = role

    # Determinar el rol más alto entre global y gimnasio
    if global_priority >= gym_priority:
        return global_role.value if global_role else "MEMBER"
    else:
        return highest_gym_role.value if highest_gym_role else "MEMBER"


async def update_highest_role_in_auth0(db: AsyncSession, user_id: int) -> Optional[str]:
    """
    Determina el rol más alto del usuario y lo actualiza en Auth0.

    Args:
        db: Sesión async de base de datos
        user_id: ID del usuario

    Returns:
        str: El rol más alto asignado, o None si hubo error

    Raises:
        Exception: Si ocurre un error en la sincronización con Auth0

    Note:
        - Consulta rol global del usuario
        - Consulta roles en todos los gimnasios
        - Determina el rol más alto por prioridad
        - Sincroniza con Auth0 usando Management API
    """
    try:
        # Obtener el usuario y su rol global
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user or not user.auth0_id:
            logger.error(f"Usuario {user_id} no encontrado o sin auth0_id")
            return None

        global_role = user.role

        # Obtener roles en todos los gimnasios
        result = await db.execute(
            select(UserGym.role).where(UserGym.user_id == user_id)
        )
        gym_roles_raw = result.scalars().all()
        gym_roles = list(gym_roles_raw)

        # Determinar el rol más alto
        highest_role = determine_highest_role(global_role, gym_roles)
        logger.info(f"Rol más alto para usuario {user_id}: {highest_role}")

        # Convertir el nombre del rol interno al formato de Auth0
        auth0_role_name = ROLE_NAME_MAPPING.get(highest_role)
        if not auth0_role_name:
            logger.error(f"No se encontró mapeo para el rol '{highest_role}'")
            return highest_role  # Devolver rol original para compatibilidad

        logger.info(f"Rol mapeado para Auth0: {highest_role} -> {auth0_role_name}")

        # Asignar rol en Auth0 en lugar de actualizar metadata
        try:
            # Actualizar el rol directamente en Auth0
            success = await auth0_mgmt_service.assign_roles_to_user(user.auth0_id, [auth0_role_name])
            if success:
                logger.info(f"Rol {auth0_role_name} asignado a usuario {user.auth0_id} en Auth0")
            else:
                logger.error(f"Error asignando rol {auth0_role_name} a usuario {user.auth0_id} en Auth0")

            return highest_role

        except Exception as e:
            logger.error(f"Error actualizando rol en Auth0: {str(e)}", exc_info=True)
            raise

    except Exception as e:
        logger.error(f"Error actualizando rol más alto en Auth0 para usuario {user_id}: {str(e)}", exc_info=True)
        raise


async def run_initial_migration(db: AsyncSession):
    """
    Migración inicial para actualizar el rol más alto de todos los usuarios en Auth0.

    Args:
        db: Sesión async de base de datos

    Returns:
        Dict con estadísticas de la migración:
        - success: Número de usuarios actualizados correctamente
        - errors: Número de errores
        - total: Total de usuarios procesados

    Note:
        Útil para migración masiva o sincronización inicial.
        Procesa todos los usuarios uno por uno.
    """
    logger.info("Iniciando migración de roles más altos para todos los usuarios")

    # Obtener todos los usuarios
    result = await db.execute(select(User))
    users = result.scalars().all()
    total = len(users)
    success = 0
    errors = 0

    for i, user in enumerate(users):
        try:
            logger.info(f"Procesando usuario {i+1}/{total}: {user.id}")
            await update_highest_role_in_auth0(db, user.id)
            success += 1
        except Exception as e:
            logger.error(f"Error procesando usuario {user.id}: {str(e)}")
            errors += 1

    logger.info(f"Migración completada. Éxito: {success}, Errores: {errors}, Total: {total}")
    return {"success": success, "errors": errors, "total": total}


# Exportar el servicio como singleton
async_auth0_sync_service = SimpleNamespace(
    determine_highest_role=determine_highest_role,
    update_highest_role_in_auth0=update_highest_role_in_auth0,
    run_initial_migration=run_initial_migration,
    # Constantes exportadas
    ROLE_NAME_MAPPING=ROLE_NAME_MAPPING,
    USER_ROLE_PRIORITY=USER_ROLE_PRIORITY,
    GYM_ROLE_PRIORITY=GYM_ROLE_PRIORITY,
    ROLE_PERMISSIONS=ROLE_PERMISSIONS
)
