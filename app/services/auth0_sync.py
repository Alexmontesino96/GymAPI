from typing import List, Optional
import logging
from types import SimpleNamespace
from fastapi import Depends
from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.services.auth0_mgmt import auth0_mgmt_service
from app.core.config import get_settings

logger = logging.getLogger("auth0_sync_service")

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

async def update_highest_role_in_auth0(db: Session, user_id: int):
    """
    Determina el rol más alto del usuario y lo actualiza en Auth0.
    
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario
        
    Returns:
        str: El rol más alto asignado
    """
    try:
        # Obtener el usuario y su rol global
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.auth0_id:
            logger.error(f"Usuario {user_id} no encontrado o sin auth0_id")
            return None
            
        global_role = user.role
        
        # Obtener roles en todos los gimnasios
        gym_roles_query = db.query(UserGym.role).filter(UserGym.user_id == user_id).all()
        gym_roles = [r[0] for r in gym_roles_query]
        
        # Determinar el rol más alto
        highest_role = determine_highest_role(global_role, gym_roles)
        logger.info(f"Rol más alto para usuario {user_id}: {highest_role}")
        
        # Actualizar en Auth0
        metadata = {"app_metadata": {"highest_role": highest_role}}
        await auth0_mgmt_service.update_user_metadata(user.auth0_id, metadata)
        logger.info(f"Metadata actualizada para usuario Auth0 {user.auth0_id}")
        
        return highest_role
        
    except Exception as e:
        logger.error(f"Error actualizando rol más alto en Auth0 para usuario {user_id}: {str(e)}", exc_info=True)
        raise

async def run_initial_migration(db: Session):
    """
    Migración inicial para actualizar el rol más alto de todos los usuarios en Auth0.
    """
    logger.info("Iniciando migración de roles más altos para todos los usuarios")
    
    # Obtener todos los usuarios
    users = db.query(User).all()
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
auth0_sync_service = SimpleNamespace(
    determine_highest_role=determine_highest_role,
    update_highest_role_in_auth0=update_highest_role_in_auth0,
    run_initial_migration=run_initial_migration
) 