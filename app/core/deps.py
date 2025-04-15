"""
Dependencias centrales para la aplicación.

Este módulo proporciona funciones helpers para obtener información del usuario y gimnasio
desde el estado de la solicitud, establecido previamente por el middleware TenantAuthMiddleware.
"""

from fastapi import Request, HTTPException, status, Depends
from typing import Optional, Dict, Any

from app.schemas.gym import GymSchema
from app.schemas.user import User as UserSchema
from app.models.user_gym import GymRoleType

async def get_request_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Obtiene el usuario desde el estado de la solicitud.
    
    Args:
        request: Solicitud HTTP
        
    Returns:
        Datos del usuario o None si no está autenticado
    """
    return request.state.user

async def get_request_gym(request: Request) -> Optional[Dict[str, Any]]:
    """
    Obtiene el gimnasio desde el estado de la solicitud.
    
    Args:
        request: Solicitud HTTP
        
    Returns:
        Datos del gimnasio o None si no se especificó gimnasio
    """
    return request.state.gym

async def get_user_role_in_gym(request: Request) -> Optional[str]:
    """
    Obtiene el rol del usuario en el gimnasio desde el estado de la solicitud.
    
    Args:
        request: Solicitud HTTP
        
    Returns:
        Rol del usuario en el gimnasio o None si no está autenticado o no pertenece al gimnasio
    """
    return request.state.user_role_in_gym

async def verify_admin_access(request: Request) -> bool:
    """
    Verifica si el usuario tiene acceso de administrador al gimnasio.
    
    Args:
        request: Solicitud HTTP
        
    Returns:
        True si el usuario es administrador del gimnasio, False en caso contrario
        
    Raises:
        HTTPException: Si el usuario no es administrador
    """
    role = request.state.user_role_in_gym
    if role not in [GymRoleType.ADMIN.value, GymRoleType.OWNER.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes para acceder a esta funcionalidad"
        )
    return True

async def verify_trainer_access(request: Request) -> bool:
    """
    Verifica si el usuario tiene acceso de entrenador al gimnasio.
    
    Args:
        request: Solicitud HTTP
        
    Returns:
        True si el usuario es entrenador o administrador del gimnasio, False en caso contrario
        
    Raises:
        HTTPException: Si el usuario no es entrenador ni administrador
    """
    role = request.state.user_role_in_gym
    if role not in [GymRoleType.TRAINER.value, GymRoleType.ADMIN.value, GymRoleType.OWNER.value]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permisos insuficientes para acceder a esta funcionalidad"
        )
    return True 