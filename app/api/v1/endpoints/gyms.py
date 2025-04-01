"""
Gyms (Tenants) Module - API Endpoints

Este módulo proporciona endpoints para la gestión de gimnasios (tenants) en el sistema.
Permite crear, actualizar, listar y eliminar gimnasios, así como gestionar los usuarios
asociados a cada gimnasio. La mayoría de estos endpoints están restringidos a administradores
del sistema.
"""

from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Security, status, Path, Query
from sqlalchemy.orm import Session

from app.core.auth0_fastapi import auth, Auth0User
from app.db.session import get_db
from app.models.gym import Gym
from app.models.user_gym import GymRoleType, UserGym
from app.schemas.gym import (
    GymCreate, 
    GymUpdate, 
    Gym as GymSchema, 
    GymWithStats, 
    GymStatusUpdate
)
from app.services.gym import gym_service
from app.services.user import user_service

router = APIRouter()

@router.post("/", response_model=GymSchema, status_code=status.HTTP_201_CREATED)
async def create_gym(
    *,
    db: Session = Depends(get_db),
    gym_in: GymCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
) -> Any:
    """
    Crear un nuevo gimnasio (tenant) en el sistema.
    
    Este endpoint permite a los administradores del sistema crear nuevos gimnasios,
    que funcionan como tenants independientes. Puede opcionalmente incluir usuarios
    iniciales para el gimnasio.
    
    Permissions:
        - Requiere scope 'admin:gyms' (solo administradores del sistema)
        
    Args:
        db: Sesión de base de datos
        gym_in: Datos del gimnasio a crear
        current_user: Usuario administrador autenticado
        
    Returns:
        GymSchema: El gimnasio creado
    """
    # Verificar que el subdominio no exista ya
    existing_gym = db.query(Gym).filter(Gym.subdomain == gym_in.subdomain).first()
    if existing_gym:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un gimnasio con el subdominio '{gym_in.subdomain}'"
        )
    
    # Crear el gimnasio
    gym = gym_service.create_gym(db, gym_in=gym_in)
    
    # Si se proporcionaron usuarios iniciales, asignarlos al gimnasio
    if gym_in.initial_users:
        for user_data in gym_in.initial_users:
            user_id = user_data.get("user_id")
            role = user_data.get("role", GymRoleType.MEMBER)
            
            if user_id:
                gym_service.add_user_to_gym(db, gym_id=gym.id, user_id=user_id, role=role)
    
    return gym


@router.get("/", response_model=List[GymSchema])
async def read_gyms(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:gyms"])
) -> Any:
    """
    Obtener lista de gimnasios.
    
    Este endpoint permite a administradores del sistema obtener una lista de todos
    los gimnasios registrados, con opción de filtrar por estado.
    
    Permissions:
        - Requiere scope 'read:gyms' (administradores)
        
    Args:
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        is_active: Filtrar por estado activo/inactivo
        current_user: Usuario autenticado con permisos
        
    Returns:
        List[GymSchema]: Lista de gimnasios
    """
    gyms = gym_service.get_gyms(
        db, 
        skip=skip, 
        limit=limit, 
        is_active=is_active
    )
    return gyms


@router.get("/my", response_model=List[GymSchema])
async def read_my_gyms(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Depends(auth.get_user)
) -> Any:
    """
    Obtener gimnasios a los que pertenece el usuario actual.
    
    Este endpoint permite a cualquier usuario obtener la lista de gimnasios
    a los que tiene acceso, junto con su rol en cada uno.
    
    Args:
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario autenticado
        
    Returns:
        List[GymSchema]: Lista de gimnasios a los que pertenece el usuario
    """
    # Obtener usuario local
    auth0_id = current_user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado en la base de datos local"
        )
    
    # Obtener gimnasios del usuario
    user_gyms = gym_service.get_user_gyms(db, user_id=db_user.id, skip=skip, limit=limit)
    return user_gyms


@router.get("/{gym_id}", response_model=GymWithStats)
async def read_gym(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:gyms"])
) -> Any:
    """
    Obtener detalles de un gimnasio específico con estadísticas.
    
    Este endpoint devuelve información completa sobre un gimnasio, incluyendo
    estadísticas básicas como número de miembros, entrenadores, etc.
    
    Permissions:
        - Requiere scope 'read:gyms' (administradores)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio a consultar
        current_user: Usuario autenticado con permisos
        
    Returns:
        GymWithStats: Detalles del gimnasio con estadísticas
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    gym = gym_service.get_gym_with_stats(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    return gym


@router.put("/{gym_id}", response_model=GymSchema)
async def update_gym(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    gym_in: GymUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
) -> Any:
    """
    Actualizar un gimnasio existente.
    
    Este endpoint permite a los administradores del sistema actualizar la información
    de un gimnasio específico.
    
    Permissions:
        - Requiere scope 'admin:gyms' (solo administradores del sistema)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio a actualizar
        gym_in: Datos actualizados del gimnasio
        current_user: Usuario administrador autenticado
        
    Returns:
        GymSchema: El gimnasio actualizado
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    
    # Actualizar gimnasio
    updated_gym = gym_service.update_gym(db, gym=gym, gym_in=gym_in)
    return updated_gym


@router.patch("/{gym_id}/status", response_model=GymSchema)
async def update_gym_status(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    status_in: GymStatusUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
) -> Any:
    """
    Actualizar el estado de un gimnasio.
    
    Este endpoint permite a los administradores activar o desactivar un gimnasio.
    Un gimnasio desactivado no permite acceso a sus usuarios.
    
    Permissions:
        - Requiere scope 'admin:gyms' (solo administradores del sistema)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio a actualizar
        status_in: Nuevo estado del gimnasio
        current_user: Usuario administrador autenticado
        
    Returns:
        GymSchema: El gimnasio actualizado
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    
    # Actualizar estado del gimnasio
    updated_gym = gym_service.update_gym_status(db, gym_id=gym_id, is_active=status_in.is_active)
    return updated_gym


@router.post("/{gym_id}/users/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_user_to_gym(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    user_id: int = Path(..., title="ID del usuario"),
    role: GymRoleType = Query(GymRoleType.MEMBER, title="Rol del usuario en el gimnasio"),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
) -> Any:
    """
    Añadir un usuario a un gimnasio con un rol específico.
    
    Este endpoint permite a los administradores del sistema asignar usuarios a gimnasios
    con roles específicos (OWNER, ADMIN, TRAINER, MEMBER).
    
    Permissions:
        - Requiere scope 'admin:gyms' (solo administradores del sistema)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        user_id: ID del usuario a añadir
        role: Rol del usuario en el gimnasio
        current_user: Usuario administrador autenticado
        
    Returns:
        dict: Detalles de la asignación
        
    Raises:
        HTTPException: 404 si el gimnasio o usuario no existe
    """
    # Verificar que el gimnasio y el usuario existen
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    
    user = user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Añadir usuario al gimnasio
    try:
        user_gym = gym_service.add_user_to_gym(db, gym_id=gym_id, user_id=user_id, role=role)
        return {
            "message": "Usuario añadido al gimnasio correctamente",
            "user_id": user_id,
            "gym_id": gym_id,
            "role": role
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.delete("/{gym_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_gym(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    user_id: int = Path(..., title="ID del usuario"),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
) -> Any:
    """
    Eliminar un usuario de un gimnasio.
    
    Este endpoint permite a los administradores del sistema eliminar la asociación
    de un usuario con un gimnasio.
    
    Permissions:
        - Requiere scope 'admin:gyms' (solo administradores del sistema)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        user_id: ID del usuario a eliminar
        current_user: Usuario administrador autenticado
        
    Returns:
        dict: Mensaje de confirmación
        
    Raises:
        HTTPException: 404 si el gimnasio o la asociación no existe
    """
    # Verificar que el gimnasio existe
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    
    # Eliminar usuario del gimnasio
    try:
        gym_service.remove_user_from_gym(db, gym_id=gym_id, user_id=user_id)
        return {
            "message": "Usuario eliminado del gimnasio correctamente",
            "user_id": user_id,
            "gym_id": gym_id
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{gym_id}/users", response_model=List[dict])
async def read_gym_users(
    *,
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    role: Optional[GymRoleType] = None,
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:gym_users"])
) -> Any:
    """
    Obtener lista de usuarios de un gimnasio con sus roles.
    
    Este endpoint permite a los administradores obtener una lista de todos los usuarios
    asociados a un gimnasio específico, con opción de filtrar por rol.
    
    Permissions:
        - Requiere scope 'read:gym_users' (administradores del sistema y del gimnasio)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        role: Filtrar por rol específico
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario autenticado con permisos
        
    Returns:
        List[dict]: Lista de usuarios con sus roles en el gimnasio
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    # Verificar que el gimnasio existe
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    
    # Obtener usuarios del gimnasio
    users = gym_service.get_gym_users(
        db, 
        gym_id=gym_id, 
        role=role, 
        skip=skip, 
        limit=limit
    )
    return users 