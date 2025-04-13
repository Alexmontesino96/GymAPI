"""
Endpoints para la gestión de gimnasios.

Este módulo proporciona todas las rutas relacionadas con la gestión de gimnasios,
incluyendo creación, lectura, actualización y eliminación de gimnasios, así como
la gestión de miembros asociados a cada gimnasio.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Security, Path, status, Request
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.services.gym import gym_service
from app.services.user import user_service
from app.schemas.gym import Gym as GymSchema, GymCreate, GymUpdate, GymStatusUpdate, GymWithStats, UserGymMembershipSchema, UserGymRoleUpdate, UserGymSchema
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.core.tenant import verify_gym_access, verify_admin_role
from app.db.session import get_db
from app.db.redis_client import get_redis_client, redis
from app.services.cache_service import cache_service
import logging

router = APIRouter()

# ======================================================================
# RUTAS ESPECÍFICAS (sin parámetros de ruta variables)
# ======================================================================

@router.post("/", response_model=GymSchema, status_code=status.HTTP_201_CREATED)
async def create_gym(
    *,
    db: Session = Depends(get_db),
    gym_in: GymCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
) -> Any:
    """
    [ADMIN] Crear un nuevo gimnasio.
    
    Este endpoint permite a administradores crear un nuevo gimnasio en el sistema.
    El usuario que crea el gimnasio automáticamente se convierte en administrador del mismo.
    
    Permissions:
        - Requiere scope "admin:gyms"
        
    Args:
        db: Sesión de base de datos
        gym_in: Datos del gimnasio a crear
        current_user: Usuario administrador autenticado
        
    Returns:
        Gym: El nuevo gimnasio creado
        
    Raises:
        HTTPException: 400 si ya existe un gimnasio con el mismo subdominio,
                      404 si el usuario no se encuentra en la base de datos
    """
    # Verificar que el subdominio es único
    db_gym = gym_service.get_gym_by_subdomain(db, subdomain=gym_in.subdomain)
    if db_gym:
        raise HTTPException(
            status_code=400,
            detail=f"Ya existe un gimnasio con el subdominio '{gym_in.subdomain}'"
        )
    
    # Obtener el usuario local de Auth0
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado en la base de datos local"
        )
    
    # Crear el gimnasio
    new_gym = gym_service.create_gym(db, gym_in=gym_in)
    
    # Añadir al creador como administrador del gimnasio
    gym_service.add_user_to_gym(
        db, 
        gym_id=new_gym.id, 
        user_id=db_user.id, 
        role=GymRoleType.OWNER  # El creador es el OWNER
    )
    
    return new_gym


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
    [ADMIN or TRAINER] Obtener todos los gimnasios.
    
    Este endpoint permite a administradores y entrenadores ver todos los gimnasios
    registrados en el sistema. Se puede filtrar por estado (activo/inactivo).
    
    Permissions:
        - Requiere scope "read:gyms"
        
    Args:
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        is_active: Filtrar por estado activo/inactivo
        current_user: Usuario administrador o entrenador autenticado
        
    Returns:
        List[Gym]: Lista de gimnasios
    """
    gyms = gym_service.get_gyms(db, skip=skip, limit=limit, is_active=is_active)
    return gyms


@router.get("/my", response_model=List[UserGymMembershipSchema])
async def read_my_gyms(
    *,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    user_id: int = Path(..., title="ID del usuario a añadir"),
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
    
    # Añadir usuario al gimnasio
    user_gym = gym_service.add_user_to_gym(db, gym_id=gym_id, user_id=user_id)
    
    # Invalidar caché de miembros
    redis_client = get_redis_client()
    if redis_client:
        await user_service.invalidate_role_cache(redis_client, role=target_user.role, gym_id=gym_id)
    
    return {
        "message": "Usuario añadido al gimnasio correctamente",
        "user_id": user_id,
        "gym_id": gym_id,
        "role": user_gym.role.value,
        "joined_at": user_gym.created_at
    }


@router.delete("/users/{user_id}", status_code=status.HTTP_200_OK)
async def remove_user_from_current_gym(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., title="ID del usuario a eliminar"),
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
        
        # Invalidar cachés relevantes
        redis_client = get_redis_client()
        if redis_client and target_role:
            # Invalidar caché del usuario específico
            await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
            # Invalidar caché del rol para este gimnasio
            await user_service.invalidate_role_cache(redis_client, role=target_role, gym_id=gym_id)
            
        return {
            "message": "Usuario eliminado del gimnasio correctamente",
            "user_id": user_id,
            "gym_id": gym_id
        }
    except HTTPException as http_exc:
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
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:gyms"])
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
    db: Session = Depends(get_db),
    gym_id: int = Path(..., title="ID del gimnasio"),
    gym_in: GymUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:gyms"])
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
    
    # Si se intenta cambiar el subdominio, verificar que no exista otro con ese subdominio
    if gym_in.subdomain and gym_in.subdomain != gym.subdomain:
        existing_gym = gym_service.get_gym_by_subdomain(db, subdomain=gym_in.subdomain)
        if existing_gym and existing_gym.id != gym_id:
            raise HTTPException(
                status_code=400,
                detail=f"Ya existe un gimnasio con el subdominio '{gym_in.subdomain}'"
            )
    
    # Actualizar el gimnasio
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
    db: Session = Depends(get_db),
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
        return {
            "message": "Usuario eliminado del gimnasio correctamente por SUPER_ADMIN",
            "user_id": user_id,
            "gym_id": gym_id
        }
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al eliminar usuario del gimnasio: {e}"
        )


@router.get("/{gym_id}/users", response_model=List[dict])
async def read_gym_users_by_superadmin(
    *,
    db: Session = Depends(get_db),
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
    db: Session = Depends(get_db),
    user_id: int = Path(..., title="ID del usuario a modificar"),
    role_in: UserGymRoleUpdate,
    # Verificar que el llamante es ADMIN del gym actual o SUPER_ADMIN
    current_gym_verified: Gym = Depends(verify_admin_role), 
) -> Any:
    """
    [ADMIN ONLY] Actualizar el rol de un usuario DENTRO del gimnasio actual.
    
    Permite cambiar el rol específico (MEMBER, TRAINER, ADMIN) de un usuario 
    dentro del gimnasio identificado por X-Gym-ID.
    
    Restricciones:
    - No se puede asignar/modificar el rol OWNER aquí.
    - No se puede modificar el rol de un SUPER_ADMIN global.
    - Un admin no puede modificar el rol de otro admin/owner.
    
    Permissions:
        - Requiere ser ADMIN/OWNER del gimnasio actual (X-Gym-ID) o SUPER_ADMIN.
    """
    gym_id = current_gym_verified.id
    logger = logging.getLogger("gym_endpoint")
    logger.info(f"Intentando actualizar rol de gym para user {user_id} a {role_in.role.name} en gym {gym_id}")

    # La dependencia verify_admin_role ya verifica los permisos del llamante
    
    # Validar el rol solicitado
    if role_in.role == GymRoleType.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="No se puede asignar el rol OWNER a través de este endpoint."
        )
        
    # Obtener usuario llamante para verificar si es SUPER_ADMIN (ya que verify_admin_role lo permite)
    current_auth_user = await get_current_user() # Necesitamos al usuario autenticado
    caller = user_service.get_user_by_auth0_id(db, auth0_id=current_auth_user.id)
    is_super_admin = caller and caller.role == UserRole.SUPER_ADMIN

    # Obtener la membresía actual del usuario objetivo en el gimnasio
    target_user_membership = gym_service.check_user_in_gym(db, user_id=user_id, gym_id=gym_id)
    if not target_user_membership:
        raise HTTPException(status_code=404, detail="El usuario no pertenece a este gimnasio")

    # Impedir que un ADMIN modifique a otro ADMIN/OWNER
    if not is_super_admin and target_user_membership.role in [GymRoleType.ADMIN, GymRoleType.OWNER]:
        raise HTTPException(status_code=403, detail="Los administradores no pueden modificar el rol de otros administradores u owners.")

    try:
        # Llamar al servicio para actualizar el rol específico del gym
        updated_membership = gym_service.update_user_role_in_gym(
            db=db, 
            gym_id=gym_id, 
            user_id=user_id, 
            role=role_in.role
        )
        db.commit()
        db.refresh(updated_membership)
        logger.info(f"Rol de gym actualizado para user {user_id} en gym {gym_id} a {updated_membership.role.name}")
        
        # Invalidar caché (relacionado con la lista de usuarios del gym)
        redis_client = get_redis_client()
        if redis_client:
            # Invalidar caché general de usuarios del gym
            # Podría ser más específico si tuviéramos caché por rol de gym
            await cache_service.delete_pattern(redis_client, f"gym:{gym_id}:users:*") 
            # También invalidar caché de roles globales si el rol global del usuario podría verse afectado
            target_user = user_service.get_user(db, user_id=user_id)
            if target_user:
                 await user_service.invalidate_role_cache(redis_client, role=target_user.role, gym_id=gym_id)
            
        return updated_membership
        
    except HTTPException as http_exc:
        db.rollback()
        raise http_exc
    except Exception as e:
        db.rollback()
        logger.error(f"Error actualizando rol de gym para user {user_id} en gym {gym_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar rol en gimnasio.") 