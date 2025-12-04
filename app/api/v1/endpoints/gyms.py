"""
Endpoints para la gestión de gimnasios.

Este módulo proporciona todas las rutas relacionadas con la gestión de gimnasios,
incluyendo creación, lectura, actualización y eliminación de gimnasios, así como
la gestión de miembros asociados a cada gimnasio.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Security, Path, status, Request, Body
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User, UserRole
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.services.gym import gym_service
from app.services.user import user_service
from app.schemas.gym import Gym as GymSchema, GymCreate, GymUpdate, GymStatusUpdate, GymWithStats, UserGymMembershipSchema, UserGymRoleUpdate, UserGymSchema, GymPublicSchema, GymDetailedPublicSchema
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.core.tenant import verify_gym_access, verify_admin_role
from app.db.session import get_async_db
from app.db.redis_client import get_redis_client, redis
from app.services.cache_service import cache_service
import logging
from app.core.config import get_settings

# Definir logger para este módulo
logger = logging.getLogger("gym_endpoint")

router = APIRouter()

# ======================================================================
# RUTAS ESPECÍFICAS (sin parámetros de ruta variables)
# ======================================================================

@router.post("/", response_model=GymSchema, status_code=status.HTTP_201_CREATED)
async def create_gym(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_in: GymCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["tenant:admin"])
) -> Any:
    """
    [ADMIN] Crear un nuevo gimnasio.
    
    Este endpoint permite a administradores crear un nuevo gimnasio en el sistema.
    El gimnasio se crea sin usuarios asignados inicialmente.
    
    Permissions:
        - Requiere scope "admin:gyms"
        
    Args:
        db: Sesión de base de datos
        gym_in: Datos del gimnasio a crear
        current_user: Usuario administrador autenticado
        
    Returns:
        Gym: El nuevo gimnasio creado
        
    Raises:
        HTTPException: 400 si ya existe un gimnasio con el mismo subdominio
    """
    # Verificar que el subdominio es único
    db_gym = gym_service.get_gym_by_subdomain(db, subdomain=gym_in.subdomain)
    if db_gym:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un gimnasio con el subdominio '{gym_in.subdomain}'"
        )
    
    # Crear el gimnasio
    new_gym = gym_service.create_gym(db, gym_in=gym_in)
    
    return new_gym


@router.get("/", response_model=List[GymPublicSchema])
async def read_gyms_public(
    *,
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = True  # Por defecto solo gimnasios activos para público
) -> Any:
    """
    Obtener todos los gimnasios (PÚBLICO - sin autenticación).
    
    Este endpoint permite a cualquier usuario (incluso sin autenticar) ver todos los 
    gimnasios activos registrados en el sistema para discovery público.
    
    Permissions:
        - Sin autenticación requerida (público)
        
    Args:
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        is_active: Filtrar por estado activo/inactivo (default: True para público)
        
    Returns:
        List[GymPublicSchema]: Lista de gimnasios públicos
    """
    gyms = gym_service.get_gyms(db, skip=skip, limit=limit, is_active=is_active)
    return gyms


@router.get("/{gym_id}/details", response_model=GymDetailedPublicSchema)
async def get_gym_details_public(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio")
) -> Any:
    """
    Obtener detalles completos de un gimnasio (PÚBLICO - sin autenticación).
    
    Este endpoint permite a cualquier usuario (incluso sin autenticar) ver los 
    detalles completos de un gimnasio específico, incluyendo horarios, planes 
    de membresía y módulos disponibles para discovery público.
    
    Permissions:
        - Sin autenticación requerida (público)
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        
    Returns:
        GymDetailedPublicSchema: Detalles completos del gimnasio
        
    Raises:
        HTTPException 404: Si el gimnasio no existe o está inactivo
    """
    gym = gym_service.get_gym_details_public(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado o inactivo"
        )
    return gym


@router.get("/my", response_model=List[UserGymMembershipSchema])
async def read_my_gyms(
    *,
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Depends(auth.get_user)
) -> Any:
    """
    Obtener todos los gimnasios a los que pertenece el usuario autenticado.
    
    Este endpoint permite a cualquier usuario autenticado ver todos los gimnasios
    a los que está asociado, junto con su rol en cada uno.
    
    Permissions:
        - Requiere autenticación
        
    Args:
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario autenticado
        
    Returns:
        List[UserGymMembership]: Lista de membresías del usuario
        
    Raises:
        HTTPException: 404 si el usuario no se encuentra en la base de datos local
    """
    # Obtener el usuario local de Auth0
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local"
        )
    
    # Obtener gimnasios del usuario
    user_gyms = gym_service.get_user_gyms(db, user_id=db_user.id, skip=skip, limit=limit)
    return user_gyms


@router.get("/users", response_model=List[dict])
async def read_current_gym_users(
    *,
    db: AsyncSession = Depends(get_async_db),
    role: Optional[GymRoleType] = Query(None, title="Filtrar por rol específico"),
    skip: int = 0,
    limit: int = 100,
    # Verificar que el llamante pertenece al gimnasio actual (X-Gym-ID)
    current_gym_verified: Gym = Depends(verify_gym_access), 
) -> Any:
    """
    Obtener lista de usuarios del gimnasio actual (identificado por X-Gym-ID).
    
    Este endpoint permite a CUALQUIER miembro del gimnasio actual
    obtener una lista de todos los usuarios asociados al mismo gimnasio,
    con opción de filtrar por rol.
    
    Permissions:
        - Requiere pertenecer al gimnasio actual (identificado por X-Gym-ID).
        
    Args:
        db: Sesión de base de datos
        role: Filtrar por rol específico (opcional)
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_gym_verified: Gimnasio actual verificado.
        
    Returns:
        List[dict]: Lista de usuarios con sus roles en el gimnasio
        
    Raises:
        HTTPException: 403 si el usuario no pertenece al gimnasio.
    """
    gym_id = current_gym_verified.id
    
    # La dependencia verify_gym_access ya verificó que el usuario pertenece al gym.
    
    # Obtener usuarios del gimnasio
    users = gym_service.get_gym_users(
        db, 
        gym_id=gym_id, 
        role=role, 
        skip=skip, 
        limit=limit
    )
    return users


@router.post("/users/{user_id}", status_code=status.HTTP_201_CREATED)
async def add_user_to_current_gym(
    *,
    db: AsyncSession = Depends(get_async_db),
    user_id: int = Path(..., title="ID del usuario a añadir"),
    # Inyectar redis_client
    redis_client: redis.Redis = Depends(get_redis_client), 
    # Permite ADMIN/OWNER del gym actual (obtenido de X-Gym-ID) o SUPER_ADMIN
    current_gym_verified: Gym = Depends(verify_admin_role), 
) -> Any:
    """
    [ADMIN ONLY] Añadir un usuario al gimnasio actual.
    
    Este endpoint permite a administradores de un gimnasio añadir nuevos usuarios
    al mismo. Por defecto, los usuarios añadidos son asignados como MEMBER.
    
    Permissions:
        - Requiere ser ADMIN/OWNER del gimnasio actual (X-Gym-ID) o SUPER_ADMIN.
        
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a añadir
        redis_client: Cliente de Redis inyectado
        current_gym_verified: Gimnasio actual verificado.
        
    Returns:
        dict: Información sobre la asociación
        
    Raises:
        HTTPException: 403 si quien llama no es ADMIN/OWNER, 
                       404 si el usuario no existe,
                       400 si el usuario ya pertenece al gimnasio.
    """
    gym_id = current_gym_verified.id
    
    # La dependencia verify_admin_role ya verificó que el usuario tiene rol de admin en este gym.
    
    # Verificar que el usuario a añadir existe
    target_user = user_service.get_user(db, user_id=user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar si ya pertenece al gimnasio
    existing_membership = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
    if existing_membership:
        raise HTTPException(
            status_code=400,
            detail=f"El usuario ya pertenece al gimnasio con rol {existing_membership.role.value}"
        )
    
    # Añadir usuario al gimnasio (ahora síncrono)
    user_gym = gym_service.add_user_to_gym(db, gym_id=gym_id, user_id=user_id)
    
    # Actualizar el rol más alto en Auth0
    from app.services.auth0_sync import auth0_sync_service
    try:
        await auth0_sync_service.update_highest_role_in_auth0(db, user_id)
        logger.info(f"Rol más alto de usuario {user_id} actualizado en Auth0 después de añadirlo al gimnasio {gym_id}")
    except Exception as e:
        logger.error(f"Error actualizando rol en Auth0 para usuario {user_id}: {str(e)}")
        # No falla la operación principal si la sincronización falla
    
    # Invalidar/Actualizar caché de membresía y roles (usando el redis_client inyectado)
    if redis_client:
        # Actualizar caché de membresía específica
        membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
        try:
            await redis_client.set(membership_cache_key, user_gym.role.value, ex=get_settings().CACHE_TTL_USER_MEMBERSHIP)
            logging.info(f"Cache de membresía {membership_cache_key} actualizada a {user_gym.role.value}")
        except Exception as e:
            logging.error(f"Error al actualizar cache de membresía {membership_cache_key}: {e}")
        
        # Invalidar cachés de listados de participantes (rol global)
        await user_service.invalidate_role_cache(redis_client, role=target_user.role, gym_id=gym_id)
        # Invalidar caché de GymUserSummary (si existe)
        await cache_service.delete_pattern(redis_client, f"gym:{gym_id}:users:*")
    
    return {
        "message": "Usuario añadido al gimnasio correctamente",
        "user_id": user_id,
        "gym_id": gym_id,
        "role": user_gym.role.value,
        "joined_at": user_gym.created_at
    }


@router.post("/users/by-email", status_code=status.HTTP_201_CREATED)
async def add_user_to_current_gym_by_email(
    *,
    db: AsyncSession = Depends(get_async_db),
    email: EmailStr = Body(..., title="Email del usuario a añadir"),
    # Inyectar redis_client
    redis_client: redis.Redis = Depends(get_redis_client), 
    # Permite ADMIN/OWNER del gym actual (obtenido de X-Gym-ID) o SUPER_ADMIN
    current_gym_verified: Gym = Depends(verify_admin_role), 
) -> Any:
    """
    [ADMIN ONLY] Añadir un usuario al gimnasio actual por email.
    
    Este endpoint permite a administradores de un gimnasio añadir nuevos usuarios
    al mismo utilizando su email. Por defecto, los usuarios añadidos son asignados como MEMBER.
    
    Permissions:
        - Requiere ser ADMIN/OWNER del gimnasio actual (X-Gym-ID) o SUPER_ADMIN.
        
    Args:
        db: Sesión de base de datos
        email: Email del usuario a añadir
        redis_client: Cliente de Redis inyectado
        current_gym_verified: Gimnasio actual verificado.
        
    Returns:
        dict: Información sobre la asociación
        
    Raises:
        HTTPException: 403 si quien llama no es ADMIN/OWNER, 
                       404 si el usuario no existe,
                       400 si el usuario ya pertenece al gimnasio.
    """
    gym_id = current_gym_verified.id
    
    # La dependencia verify_admin_role ya verificó que el usuario tiene rol de admin en este gym.
    
    # Verificar que el usuario a añadir existe
    target_user = user_service.get_user_by_email(db, email=email)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado con ese email")
    
    user_id = target_user.id
    
    # Verificar si ya pertenece al gimnasio
    existing_membership = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
    if existing_membership:
        raise HTTPException(
            status_code=400,
            detail=f"El usuario ya pertenece al gimnasio con rol {existing_membership.role.value}"
        )
    
    # Añadir usuario al gimnasio (ahora síncrono)
    user_gym = gym_service.add_user_to_gym(db, gym_id=gym_id, user_id=user_id)
    
    # Actualizar el rol más alto en Auth0
    from app.services.auth0_sync import auth0_sync_service
    try:
        await auth0_sync_service.update_highest_role_in_auth0(db, user_id)
        logger.info(f"Rol más alto de usuario {user_id} actualizado en Auth0 después de añadirlo al gimnasio {gym_id}")
    except Exception as e:
        logger.error(f"Error actualizando rol en Auth0 para usuario {user_id}: {str(e)}")
        # No falla la operación principal si la sincronización falla
    
    # Invalidar/Actualizar caché de membresía y roles (usando el redis_client inyectado)
    if redis_client:
        # Actualizar caché de membresía específica
        membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
        try:
            await redis_client.set(membership_cache_key, user_gym.role.value, ex=get_settings().CACHE_TTL_USER_MEMBERSHIP)
            logging.info(f"Cache de membresía {membership_cache_key} actualizada a {user_gym.role.value}")
        except Exception as e:
            logging.error(f"Error al actualizar cache de membresía {membership_cache_key}: {e}")
        
        # Invalidar cachés de listados de participantes (rol global)
        await user_service.invalidate_role_cache(redis_client, role=target_user.role, gym_id=gym_id)
        # Invalidar caché de GymUserSummary (si existe)
        await cache_service.delete_pattern(redis_client, f"gym:{gym_id}:users:*")
    
    return {
        "message": "Usuario añadido al gimnasio correctamente",
        "user_id": user_id,
        "user_email": email,
        "gym_id": gym_id,
        "role": user_gym.role.value,
        "joined_at": user_gym.created_at
    }


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_current_gym(
    *,
    db: AsyncSession = Depends(get_async_db),
    user_id: int = Path(..., title="ID del usuario a eliminar"),
    # Inyectar redis_client
    redis_client: redis.Redis = Depends(get_redis_client),
    # Verificar que el llamante pertenece al gimnasio actual (X-Gym-ID)
    current_gym_verified: Gym = Depends(verify_gym_access), 
    # Verificar que el usuario actual NO es el que se intenta eliminar (auto-eliminación)
    current_auth_user: Auth0User = Depends(auth.get_user)
) -> Any:
    """
    Eliminar un usuario del gimnasio actual.
    
    Este endpoint permite a un usuario eliminar a otro usuario de un gimnasio, 
    o a un usuario eliminarse a sí mismo de un gimnasio.
    
    Restricciones:
    - Un usuario miembro solo puede eliminarse a sí mismo.
    - Un administrador puede eliminar a cualquier miembro o entrenador, pero no a otro administrador.
    - Un administrador no puede eliminarse a sí mismo (para esto, habría que cambiar su rol antes).
    
    Permissions:
        - Requiere pertenencia al gimnasio actual (X-Gym-ID).
        - La capacidad de eliminar depende de roles (ADMIN puede eliminar MEMBERS/TRAINERS).
        
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a eliminar
        redis_client: Cliente de Redis inyectado
        current_gym_verified: Gimnasio actual verificado.
        current_auth_user: Usuario autenticado actual.
        
    Returns:
        dict: Mensaje de confirmación
        
    Raises:
        HTTPException: 403 si quien llama no tiene permisos para eliminar,
                      404 si el usuario a eliminar no pertenece al gimnasio.
    """
    gym_id = current_gym_verified.id
    
    # La dependencia verify_gym_access ya verificó que el usuario autenticado
    # pertenece al gimnasio actual.
    
    # Obtener el usuario autenticado desde la BD
    auth_user = user_service.get_user_by_auth0_id(db, auth0_id=current_auth_user.id)
    if not auth_user:
        raise HTTPException(status_code=403, detail="Usuario no encontrado en la BD local")
    
    # Verificar si el usuario autenticado es el mismo que se intenta eliminar
    is_self_removal = auth_user.id == user_id
    
    # Verificar el rol del usuario autenticado en este gimnasio
    auth_user_gym = gym_service.check_user_in_gym(db, user_id=auth_user.id, gym_id=gym_id)
    if not auth_user_gym:
        raise HTTPException(status_code=403, detail="Usuario no pertenece al gimnasio")
    
    auth_user_role = auth_user_gym.role
    
    # Si NO es un administrador, solo puede eliminarse a sí mismo
    if auth_user_role not in [GymRoleType.ADMIN, GymRoleType.OWNER] and not is_self_removal:
        raise HTTPException(
            status_code=403,
            detail="No tienes permisos para eliminar otros usuarios del gimnasio"
        )
    
    # Si es ADMIN pero intenta eliminarse a sí mismo, no permitirlo
    if auth_user_role in [GymRoleType.ADMIN, GymRoleType.OWNER] and is_self_removal:
        raise HTTPException(
            status_code=403,
            detail="Los administradores no pueden eliminarse a sí mismos del gimnasio"
        )
    
    # Verificar que el usuario a eliminar pertenece al gimnasio
    target_user_gym = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
    if not target_user_gym:
        raise HTTPException(
            status_code=404, 
            detail="El usuario no pertenece al gimnasio"
        )
    
    # Si es admin, verificar que no intente eliminar a otro admin
    if auth_user_role in [GymRoleType.ADMIN, GymRoleType.OWNER]:
        if target_user_gym.role in [GymRoleType.ADMIN, GymRoleType.OWNER]:
            raise HTTPException(
                status_code=403,
                detail="No puedes eliminar a otro administrador del gimnasio"
            )
    
    # Obtener información del usuario a eliminar para invalidar caché
    target_user = user_service.get_user(db, user_id=user_id)
    target_role = target_user.role if target_user else None

    # Eliminar usuario del gimnasio
    try:
        gym_service.remove_user_from_gym(db, gym_id=gym_id, user_id=user_id)
        await db.commit()
        
        # Invalidar cachés relevantes (usando el redis_client inyectado)
        if redis_client and target_role:
            # Invalidar caché de membresía específica
            membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
            await redis_client.delete(membership_cache_key)
            logging.info(f"Cache de membresía {membership_cache_key} invalidada")
            
            # Invalidar caché del usuario específico
            await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
            # Invalidar caché del rol para este gimnasio
            await user_service.invalidate_role_cache(redis_client, role=target_role, gym_id=gym_id)
            
            # Invalidar caché de GymUserSummary (si existe)
            await cache_service.delete_pattern(redis_client, f"gym:{gym_id}:users:*")
            
        return {
            "message": "Usuario eliminado del gimnasio correctamente",
            "user_id": user_id,
            "gym_id": gym_id
        }
    except HTTPException as http_exc:
        await db.rollback()
        raise http_exc
    except Exception as e:
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al eliminar usuario del gimnasio: {e}"
        )

# ======================================================================
# RUTAS CON PARÁMETROS DE RUTA VARIABLES
# ======================================================================

@router.get("/{gym_id}", response_model=GymWithStats)
async def read_gym(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    current_user: Auth0User = Security(auth.get_user, scopes=["tenant:read"])
) -> Any:
    """
    [ADMIN or TRAINER] Obtener detalles de un gimnasio específico.
    
    Este endpoint permite a administradores y entrenadores ver los detalles
    de un gimnasio específico, incluyendo estadísticas básicas como el número
    de miembros, entrenadores, eventos, etc.
    
    Permissions:
        - Requiere scope "read:gyms"
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        current_user: Usuario administrador o entrenador autenticado
        
    Returns:
        GymWithStats: Detalles y estadísticas del gimnasio
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    gym_with_stats = gym_service.get_gym_with_stats(db, gym_id=gym_id)
    if not gym_with_stats:
        raise HTTPException(
            status_code=404,
            detail="Gimnasio no encontrado"
        )
        
    return gym_with_stats


@router.put("/{gym_id}", response_model=GymSchema)
async def update_gym(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    gym_in: GymUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["tenant:admin"])
) -> Any:
    """
    [ADMIN] Actualizar la información de un gimnasio.
    
    Este endpoint permite a administradores actualizar la información de un gimnasio,
    como su nombre, descripción, dirección, logo, etc.
    
    Permissions:
        - Requiere scope "admin:gyms"
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        gym_in: Datos actualizados del gimnasio
        current_user: Usuario administrador autenticado
        
    Returns:
        Gym: El gimnasio actualizado
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    # Verificar que el gimnasio existe
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=404,
            detail="Gimnasio no encontrado"
        )
    
    # Nota: El subdominio no se puede cambiar una vez creado el gimnasio
    # ya que es un identificador único y podría romper URLs existentes
    
    # Actualizar el gimnasio
    updated_gym = gym_service.update_gym(db, gym=gym, gym_in=gym_in)
    return updated_gym


@router.patch("/{gym_id}/status", response_model=GymSchema)
async def update_gym_status(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    status_in: GymStatusUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["tenant:admin"])
) -> Any:
    """
    [ADMIN] Activar o desactivar un gimnasio.
    
    Este endpoint permite a administradores cambiar el estado de un gimnasio
    (activo o inactivo). Un gimnasio inactivo no será visible para nuevos usuarios.
    
    Permissions:
        - Requiere scope "admin:gyms"
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        status_in: Nuevo estado del gimnasio
        current_user: Usuario administrador autenticado
        
    Returns:
        Gym: El gimnasio actualizado
        
    Raises:
        HTTPException: 404 si el gimnasio no existe
    """
    # Verificar que el gimnasio existe
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=404,
            detail="Gimnasio no encontrado"
        )
    
    # Actualizar el estado del gimnasio
    updated_gym = gym_service.update_gym_status(db, gym_id=gym_id, is_active=status_in.is_active)
    return updated_gym


@router.delete("/{gym_id}/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_gym_by_superadmin(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    user_id: int = Path(..., title="ID del usuario a eliminar"),
    # Verificar que quien llama es SUPER_ADMIN
    current_user: Auth0User = Security(auth.get_user) 
) -> Any:
    """
    [SUPER_ADMIN ONLY] Eliminar un usuario de un gimnasio.
    
    Este endpoint permite a los SUPER_ADMIN eliminar la asociación
    de cualquier usuario (excepto otros SUPER_ADMIN) con cualquier gimnasio.
    
    Permissions:
        - Requiere rol global SUPER_ADMIN.
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        user_id: ID del usuario a eliminar
        current_user: Usuario SUPER_ADMIN autenticado.
        
    Returns:
        dict: Mensaje de confirmación
        
    Raises:
        HTTPException: 403 si quien llama no es SUPER_ADMIN, 
                       404 si el usuario o la asociación no existe, 
                       403 si se intenta eliminar un SUPER_ADMIN.
    """
    # Verificar permiso SUPER_ADMIN
    db_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_caller or db_caller.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acción restringida a administradores de plataforma."
        )
        
    # Verificar que el gimnasio existe (opcional, el servicio podría manejarlo)
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado")

    # Eliminar usuario del gimnasio (el servicio maneja la lógica de no eliminar SUPER_ADMIN)
    try:
        gym_service.remove_user_from_gym(db, gym_id=gym_id, user_id=user_id)
        await db.commit()
        
        # Obtener redis_client para poder invalidar
        redis_client = await get_redis_client()
        if redis_client:
            membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
            await redis_client.delete(membership_cache_key)
            logging.info(f"(Superadmin) Cache de membresía {membership_cache_key} invalidada")
        
        return {
            "message": "Usuario eliminado del gimnasio correctamente por SUPER_ADMIN",
            "user_id": user_id,
            "gym_id": gym_id
        }
    except HTTPException as http_exc:
        await db.rollback()
        raise http_exc
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al eliminar usuario del gimnasio: {e}"
        )


@router.get("/{gym_id}/users", response_model=List[dict])
async def read_gym_users_by_superadmin(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    role: Optional[GymRoleType] = Query(None, title="Filtrar por rol específico"),
    skip: int = 0,
    limit: int = 100,
    # Verificar que quien llama es SUPER_ADMIN
    current_user: Auth0User = Security(auth.get_user) 
) -> Any:
    """
    [SUPER_ADMIN ONLY] Obtener lista de usuarios de un gimnasio específico.
    
    Este endpoint permite a los SUPER_ADMIN obtener la lista de usuarios
    de cualquier gimnasio.
    
    Permissions:
        - Requiere rol global SUPER_ADMIN.
        
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        role: Filtrar por rol específico (opcional)
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario SUPER_ADMIN autenticado.
        
    Returns:
        List[dict]: Lista de usuarios con sus roles en el gimnasio
        
    Raises:
        HTTPException: 403 si quien llama no es SUPER_ADMIN, 404 si el gym no existe.
    """
    # Verificar permiso SUPER_ADMIN
    db_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_caller or db_caller.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acción restringida a administradores de plataforma."
        )
        
    # Verificar que el gimnasio existe
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(status_code=404, detail="Gimnasio no encontrado")

    # Obtener usuarios del gimnasio
    users = gym_service.get_gym_users(
        db, 
        gym_id=gym_id, 
        role=role, 
        skip=skip, 
        limit=limit
    )
    return users 

@router.put("/users/{user_id}/role", response_model=UserGymSchema)
async def update_user_gym_role(
    *,
    db: AsyncSession = Depends(get_async_db),
    user_id: int = Path(..., title="ID del usuario a modificar"),
    role_in: UserGymRoleUpdate,
    # Inyectar redis_client
    redis_client: redis.Redis = Depends(get_redis_client),
    # Verificar que el llamante es ADMIN del gym actual o SUPER_ADMIN
    current_gym_verified: Gym = Depends(verify_admin_role), 
    # Añadir la dependencia para obtener el usuario actual
    current_user: Auth0User = Depends(auth.get_user)
) -> Any:
    """
    [ADMIN ONLY] Actualizar el rol de un usuario DENTRO DEL GIMNASIO ACTUAL.
    
    Este endpoint permite a los administradores cambiar el rol de un usuario
    dentro del gimnasio actual (identificado por X-Gym-ID).
    
    Restrictions:
    - Un usuario no puede actualizar su propio rol.
    - Solo se pueden actualizar usuarios que ya pertenecen al gimnasio.
    
    Permissions:
        - Requiere ser ADMIN/OWNER del gimnasio actual (identificado por X-Gym-ID) o SUPER_ADMIN.
        
    Args:
        db: Sesión de base de datos
        user_id: ID del usuario a modificar
        role_in: Nuevo rol
        redis_client: Cliente de Redis inyectado
        current_gym_verified: Gimnasio actual verificado
        
    Returns:
        UserGymSchema: El usuario con su rol actualizado
        
    Raises:
        HTTPException: 404 si el usuario no existe o no pertenece al gimnasio,
                      400 si se intenta cambiar al rol OWNER y ya hay un OWNER,
                      403 si se intenta modificar el propio rol.
    """
    gym_id = current_gym_verified.id
    
    # Verificar que el ID del autenticado está en la BD
    auth_user = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
    if not auth_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Usuario autenticado no encontrado en la BD"
        )
    
    # Verificar que no está intentando cambiar su propio rol
    if auth_user.id == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cambiar tu propio rol en el gimnasio"
        )
    
    # Verificar que el usuario objetivo existe en el gimnasio
    target_user_gym = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
    if not target_user_gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no pertenece al gimnasio actual"
        )
    
    old_role = target_user_gym.role
    
    # Si se intenta cambiar a OWNER, verificar que no haya un OWNER ya
    if role_in.role == GymRoleType.OWNER and old_role != GymRoleType.OWNER:
        existing_owner = gym_service.check_gym_has_owner(db, gym_id=gym_id)
        if existing_owner:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El gimnasio ya tiene un propietario (User ID: {existing_owner.user_id})"
            )
    
    # Actualizar el rol
    updated_user_gym = gym_service.update_user_role_in_gym(
        db, user_id=user_id, gym_id=gym_id, role=role_in.role
    )

    # Commit del cambio de rol en la base de datos
    await db.commit()
    await db.refresh(updated_user_gym)

    # Si el rol cambió, actualizar en Auth0
    if old_role != role_in.role:
        from app.services.auth0_sync import auth0_sync_service
        try:
            await auth0_sync_service.update_highest_role_in_auth0(db, user_id)
            logger.info(f"Rol más alto de usuario {user_id} actualizado en Auth0 después de cambio de rol en gimnasio {gym_id}")
        except Exception as e:
            logger.error(f"Error actualizando rol en Auth0 para usuario {user_id}: {str(e)}")
            # No falla la operación principal si la sincronización falla
    
    # Invalidar cachés relevantes
    if redis_client:
        # Actualizar caché de membresía específica
        membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
        try:
            await redis_client.set(
                membership_cache_key, 
                role_in.role.value, 
                ex=get_settings().CACHE_TTL_USER_MEMBERSHIP
            )
            logging.info(f"Cache de membresía {membership_cache_key} actualizada a {role_in.role.value}")
        except Exception as e:
            logging.error(f"Error al actualizar cache de membresía {membership_cache_key}: {e}")
        
        # Si cambió el rol, invalidar cachés adicionales
        if old_role != role_in.role:
            # Obtener usuario para invalidar la caché de su rol global
            result = await db.execute(select(User).where(User.id == user_id))
    target_user = result.scalar_one_or_none()
            if target_user:
                # Invalidar caché del usuario individual
                await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
                # Invalidar cachés de listados por rol
                await user_service.invalidate_role_cache(redis_client, role=target_user.role, gym_id=gym_id)
                # Invalidar caché de GymUserSummary (si existe)
                await cache_service.delete_pattern(redis_client, f"gym:{gym_id}:users:*")
    
    return updated_user_gym

@router.put("/{gym_id}/owner", response_model=UserGymSchema)
async def assign_gym_owner(
    *,
    db: AsyncSession = Depends(get_async_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    user_id: int = Query(..., title="ID del usuario a asignar como OWNER"),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_user: Auth0User = Security(auth.get_user)
) -> Any:
    """
    [SUPER_ADMIN ONLY] Asignar un usuario como OWNER de un gimnasio.
    
    Este endpoint permite a los SUPER_ADMIN asignar un usuario como OWNER de un gimnasio.
    Si el usuario no pertenece al gimnasio, se le añade automáticamente.
    Si ya pertenece, se actualiza su rol a OWNER.
    
    Args:
        db: Sesión de base de datos
        gym_id: ID del gimnasio
        user_id: ID del usuario a asignar como OWNER
        redis_client: Cliente de Redis inyectado
        current_user: Usuario autenticado (debe ser SUPER_ADMIN)
        
    Returns:
        UserGymSchema: La relación usuario-gimnasio actualizada
        
    Raises:
        HTTPException: 403 si quien llama no es SUPER_ADMIN,
                       404 si el gimnasio o usuario no existen
    """
    # Verificar que quien llama es SUPER_ADMIN
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token no contiene información de usuario (sub)"
        )
    
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user or db_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo los SUPER_ADMIN pueden asignar OWNERS"
        )
    
    # Verificar que el gimnasio existe
    gym = gym_service.get_gym(db, gym_id=gym_id)
    if not gym:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Gimnasio no encontrado"
        )
    
    # Verificar que el usuario existe
    user = user_service.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    
    # Comprobar si el usuario ya pertenece al gimnasio
    user_gym = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
    
    try:
        if user_gym:
            # Si ya existe, actualizar el rol a OWNER
            user_gym.role = GymRoleType.OWNER
            db.add(user_gym)
            logger.info(f"Actualizando rol de usuario {user_id} a OWNER en gimnasio {gym_id}")
        else:
            # Si no existe, crear nueva relación
            user_gym = UserGym(
                user_id=user_id,
                gym_id=gym_id,
                role=GymRoleType.OWNER
            )
            db.add(user_gym)
            logger.info(f"Añadiendo usuario {user_id} como OWNER al gimnasio {gym_id}")
        
        await db.commit()
        await db.refresh(user_gym)
        
        # Actualizar caché
        if redis_client:
            # Actualizar caché de membresía específica
            membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
            await redis_client.set(membership_cache_key, user_gym.role.value, ex=get_settings().CACHE_TTL_USER_MEMBERSHIP)
            logger.info(f"Cache de membresía {membership_cache_key} actualizada a {user_gym.role.value}")
            
            # Invalidar cachés relacionadas
            await cache_service.delete_pattern(redis_client, f"gym:{gym_id}:users:*")
            await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
            
        return user_gym
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error al asignar OWNER: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al asignar OWNER: {str(e)}"
        ) 