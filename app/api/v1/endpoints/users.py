"""
User Management Module - API Endpoints

This module provides comprehensive user management functionality for the gym application,
including:

- User registration and profile management
- Role-based access control
- User search and filtering capabilities
- Administrative user management functions

The user system integrates with Auth0 for authentication while maintaining local user
records for application-specific data and relationships. This dual approach provides
secure authentication while enabling customized user experiences and data management.

Each endpoint is protected with appropriate permission scopes to ensure data security
and proper access control based on user roles (Member, Trainer, Admin).
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import EmailStr, validator, Field
from datetime import datetime, timedelta, date
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Security, UploadFile, File, Path, BackgroundTasks, status, Request
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.models.user import User, UserRole
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.services.user import user_service
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate, UserRoleUpdate, UserProfileUpdate, UserSearchParams, EmailAvailabilityCheck, UserPublicProfile, Auth0EmailChangeRequest, UserSyncFromAuth0, GymUserSummary
from app.services.auth0_mgmt import auth0_mgmt_service
from app.core.tenant import verify_gym_access, verify_gym_admin_access, verify_gym_trainer_access, get_current_gym
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.db.session import get_db
from app.core.config import settings
from app.db.redis_client import get_redis_client, redis
from app.services.cache_service import cache_service
from app.services.gym import gym_service
from app.core.security import verify_auth0_webhook_secret

router = APIRouter()

# === Endpoints Públicos / Generales (Accesibles por Miembros/Entrenadores) === #

@router.get("/profile", response_model=UserSchema, tags=["Profile"])
async def get_user_profile(
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """Obtiene el perfil del usuario autenticado."""
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(status_code=400, detail="Token inválido")
    user_data = {"sub": auth0_id, "email": getattr(user, "email", None)}
    db_user = user_service.create_or_update_auth0_user(db, user_data)
    return db_user

@router.put("/profile", response_model=UserSchema, tags=["Profile"])
async def update_user_profile(
    profile_update: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Actualiza el perfil del usuario autenticado."""
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(status_code=400, detail="Token inválido")
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    updated_user = user_service.update_user_profile(db, user_id=db_user.id, profile_in=profile_update)
    if redis_client:
        await cache_service.invalidate_user_caches(redis_client, user_id=db_user.id)
        if updated_user.role:
            await user_service.invalidate_role_cache(redis_client, role=updated_user.role)
        # <<< Invalidar caché de perfil público específico >>>
        public_profile_cache_key = f"user_public_profile:{db_user.id}"
        await redis_client.delete(public_profile_cache_key)
        logger = logging.getLogger("user_endpoint")
        logger.info(f"Invalidada caché de perfil público: {public_profile_cache_key}")
    return updated_user

@router.post("/profile/image", response_model=UserSchema, tags=["Profile"])
async def upload_profile_image(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """Sube o actualiza la imagen de perfil del usuario autenticado."""
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(status_code=400, detail="Token inválido")
    content_type = file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    updated_user = await user_service.update_user_profile_image(db, auth0_id, file)
    # <<< Invalidar caché de perfil público >>>
    # Necesitamos el user_id local e inyectar redis_client
    if updated_user:
        redis_client = await get_redis_client() # Obtener cliente si no está inyectado
        if redis_client:
            public_profile_cache_key = f"user_public_profile:{updated_user.id}"
            await redis_client.delete(public_profile_cache_key)
            logger = logging.getLogger("user_endpoint")
            logger.info(f"Invalidada caché de perfil público tras subir imagen: {public_profile_cache_key}")
    return updated_user

@router.post("/check-email-availability", response_model=dict, tags=["Email Management"])
async def check_email_availability(
    *,
    db: Session = Depends(get_db),
    email_check: EmailAvailabilityCheck,
    request: Request,
    current_user: Auth0User = Security(auth.get_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Verifica si un email está disponible para ser utilizado por el usuario actual."""
    auth0_id = current_user.id
    if not auth0_id:
         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    email = email_check.email
    user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if user and user.email.lower() == email.lower():
        return {"status": "error", "message": "Este es tu email actual."}
    try:
        is_available = await user_service.check_full_email_availability(email=email, calling_user_auth0_id=auth0_id, redis_client=redis_client)
        if is_available:
            return {"status": "success", "message": "El email parece cumplir con nuestros criterios."}
        else:
            return {"status": "error", "message": "El email no cumple con nuestros criterios."}
    except HTTPException as e:
         raise e
    except Exception as e:
         logging.getLogger("user_service").error(f"Error al verificar disponibilidad de email {email}: {e}", exc_info=True)
         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno")

@router.post("/initiate-email-change", response_model=dict, tags=["Email Management"])
async def initiate_auth0_email_change(
    *,
    db: Session = Depends(get_db),
    email_change_request: Auth0EmailChangeRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    current_user: Auth0User = Security(auth.get_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Inicia el proceso de cambio de email para el usuario actual usando Auth0."""
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    
    new_email = email_change_request.new_email
    logger = logging.getLogger("user_endpoint")
    logger.info(f"User {auth0_id} initiating email change request to {new_email}")
    
    try:
        # Llamamos al servicio que interactúa con Auth0 y actualiza nuestra BD
        await user_service.initiate_auth0_email_change_flow(
            db=db,
            auth0_id=auth0_id,
            new_email=new_email,
            redis_client=redis_client,
        )
        logger.info(f"Auth0 email change process initiated for user {auth0_id} to {new_email}.")
        return {"message": "Proceso de cambio de email iniciado. Revisa tu nuevo email para confirmar."}

    except HTTPException as e:
        logger.error(f"HTTP error during initiate_auth0_email_change for user {auth0_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during initiate_auth0_email_change for user {auth0_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al iniciar el cambio de email: {str(e)}"
        )

@router.post("/me/resend-verification", response_model=dict, tags=["Email Management"])
async def resend_email_verification(
    *,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Reenvía el correo de verificación al email actual del usuario."""
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(status_code=400, detail="Token inválido")
    user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    auth0_user = auth0_mgmt_service.get_user(auth0_id)
    if auth0_user.get("email_verified"):
        return {"message": "El email ya está verificado", "email": user.email, "success": True}
    try:
        await auth0_mgmt_service.send_verification_email(user_id=auth0_id, redis_client=redis_client)
        return {"message": "Correo de verificación enviado", "email": user.email, "success": True}
    except Exception as e:
        logging.getLogger("user_service").error(f"Error al reenviar verificación: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error al enviar correo de verificación: {str(e)}")

@router.get("/gym-participants", response_model=List[UserSchema], tags=["Gym Participants"])
async def read_gym_participants(
    role: Optional[UserRole] = Query(None, description="Filtrar por rol (MEMBER o TRAINER). Omitir para ambos."),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:members"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: Gym = Depends(verify_gym_access)
) -> Any:
    """Obtiene miembros y/o entrenadores del gimnasio actual."""
    logger = logging.getLogger("user_endpoint")
    allowed_roles = [UserRole.MEMBER, UserRole.TRAINER]
    roles_to_fetch = [role] if role else allowed_roles

    try:
        logger.info(f"Fetching gym participants for gym {current_gym.id}, roles: {roles_to_fetch}")
        # Llamada única al servicio refactorizado
        participants = await user_service.get_gym_participants_cached(
            db=db,
            gym_id=current_gym.id,
            roles=roles_to_fetch,
            skip=skip,
            limit=limit,
            redis_client=redis_client
        )
        return participants
    except Exception as e:
        logger.error(f"Error fetching gym participants for gym {current_gym.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener participantes del gimnasio."
        )

@router.get("/p/gym-participants", response_model=List[UserPublicProfile], tags=["Gym Participants (Public)"])
async def read_public_gym_participants(
    role: Optional[UserRole] = Query(None, description="Filtrar por rol (MEMBER o TRAINER). Omitir para ambos."),
    name_contains: Optional[str] = Query(None, description="Filtrar por nombre/apellido (parcial)"),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:members"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: Gym = Depends(verify_gym_access)
) -> Any:
    """Obtiene perfiles públicos de miembros y/o entrenadores del gimnasio actual."""
    logger = logging.getLogger("user_endpoint")
    allowed_roles = [UserRole.MEMBER, UserRole.TRAINER]
    roles_to_fetch = [role] if role else allowed_roles
    if role and role not in allowed_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Rol debe ser {UserRole.MEMBER.name} o {UserRole.TRAINER.name}")

    try:
        logger.info(f"Fetching public participants: gym={current_gym.id}, roles={roles_to_fetch}, name={name_contains}, skip={skip}, limit={limit}")
        # Llamada única al servicio refactorizado
        participants = await user_service.get_public_gym_participants_combined(
            db=db,
            gym_id=current_gym.id,
            roles=roles_to_fetch,
            name_contains=name_contains,
            skip=skip,
            limit=limit,
            redis_client=redis_client
        )
        return participants
    except Exception as e:
        # Captura general por si algo falla en el servicio/repo
        logger.error(f"Error fetching public gym participants: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener participantes del gimnasio."
        )

@router.get("/p/public-profile/{user_id}", response_model=UserPublicProfile, tags=["Gym Participants (Public)"])
async def read_public_user_profile(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:members"]),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Obtiene el perfil público de un usuario específico del gimnasio actual."""
    logger = logging.getLogger("user_endpoint")
    gym_id = current_gym.id # ID del gimnasio actual

    # --- Parte A: Verificar si el USUARIO OBJETIVO pertenece al gimnasio (usando caché) ---
    if not redis_client:
        logger.warning(f"Redis no disponible, verificando pertenencia de user {user_id} a gym {gym_id} en BD")
        user_gym_db = db.query(UserGym).filter(UserGym.user_id == user_id, UserGym.gym_id == gym_id).first()
        if not user_gym_db:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio (BD Check)")
    else:
        membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
        try:
            cached_role_str = await redis_client.get(membership_cache_key)
            if cached_role_str is not None:
                # Cache Hit
                if cached_role_str == "__NONE__":
                    logger.debug(f"Cache HIT Negativo: Usuario {user_id} NO pertenece a gym {gym_id} (verificación perfil público)")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio (Cache Check)")
                # Si existe y no es NONE, pertenece. No necesitamos el rol aquí, solo saber que existe.
                logger.debug(f"Cache HIT Positivo: Usuario {user_id} pertenece a gym {gym_id} (verificación perfil público)")
            else:
                # Cache Miss
                logger.debug(f"Cache MISS para {membership_cache_key} (verificación perfil público), consultando BD...")
                user_gym_db = db.query(UserGym).filter(UserGym.user_id == user_id, UserGym.gym_id == gym_id).first()
                if user_gym_db:
                    role_str = user_gym_db.role.value
                    await redis_client.set(membership_cache_key, role_str, ex=settings.CACHE_TTL_USER_MEMBERSHIP)
                    logger.debug(f"Cache de membresía {membership_cache_key} establecida a {role_str}")
                else:
                    await redis_client.set(membership_cache_key, "__NONE__", ex=settings.CACHE_TTL_NEGATIVE)
                    logger.debug(f"Cache de membresía negativa establecida para {membership_cache_key}")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio (BD Check + Cache Write)")
        except Exception as e:
            logger.error(f"Error consultando caché de membresía ({membership_cache_key}) para perfil público: {e}", exc_info=True)
            # Fallback a BD en caso de error de Redis
            user_gym_db = db.query(UserGym).filter(UserGym.user_id == user_id, UserGym.gym_id == gym_id).first()
            if not user_gym_db:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio (BD Fallback)")
    # --- Fin Parte A ---

    # --- Parte B: Obtener perfil público (usando caché) --- 
    try:
        public_profile = await user_service.get_public_profile_cached(user_id, db, redis_client)
    except Exception as e:
        # Error inesperado al obtener el perfil (probablemente del servicio de caché)
        logger.error(f"Error inesperado obteniendo perfil público cacheado para user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener perfil")
    
    if not public_profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
    # Devuelve directamente el UserPublicProfile obtenido
    return public_profile


# === Endpoints de Gestión de Gimnasio (Admins de Gym / SuperAdmins) === #

@router.get("/gym-users", response_model=List[GymUserSummary], tags=["Gym Management"])
async def read_gym_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = Query(None, description="Filtrar por rol de usuario global"),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: Gym = Depends(verify_gym_admin_access)
) -> Any:
    """[ADMIN] Obtiene todos los usuarios asociados al gimnasio actual."""
    local_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not local_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    if role:
        # Cuando se filtra por rol global, usamos el servicio de usuario cacheado
        users = await user_service.get_gym_participants_cached(
            db=db, gym_id=current_gym.id, roles=[role], skip=skip, limit=limit, redis_client=redis_client
        )
    else:
        # Cuando NO se filtra por rol global, obtenemos todos los usuarios del gym
        try:
            from app.services.gym import gym_service
            # Llamar a la versión cacheada del servicio de gym
            users = await gym_service.get_gym_users_cached(db=db, gym_id=current_gym.id, skip=skip, limit=limit, redis_client=redis_client)
        except Exception as e:
            logger = logging.getLogger("user_endpoint")
            logger.error(f"Error buscando usuarios del gimnasio {current_gym.id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error al recuperar usuarios del gimnasio")
    return users

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Gym Management"])
async def remove_user_from_gym(
    user_id: int = Path(..., title="ID del usuario a eliminar del gimnasio"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> None:
    """[ADMIN] Elimina a un usuario (TRAINER o MEMBER) del gimnasio actual."""
    logger = logging.getLogger("user_endpoint")
    logger.info(f"Intento de eliminar user {user_id} del gym {current_gym.id} por usuario {current_user.id}")

    local_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not local_caller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario llamante no encontrado")

    is_super_admin = local_caller.role == UserRole.SUPER_ADMIN
    is_gym_admin = False
    if not is_super_admin:
        caller_gym_membership = db.query(UserGym).filter(UserGym.user_id == local_caller.id, UserGym.gym_id == current_gym.id, UserGym.role == GymRoleType.ADMIN).first()
        if not caller_gym_membership:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes para eliminar usuarios de este gimnasio")
        is_gym_admin = True

    target_user_membership = db.query(UserGym).filter(UserGym.user_id == user_id, UserGym.gym_id == current_gym.id).first()
    if not target_user_membership:
        target_user_exists = db.query(User.id).filter(User.id == user_id).scalar() is not None
        if not target_user_exists:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario {user_id} no encontrado")
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Usuario {user_id} no pertenece al gimnasio {current_gym.name}")

    target_gym_role = target_user_membership.role
    if target_gym_role not in [GymRoleType.TRAINER, GymRoleType.MEMBER]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No se pueden eliminar usuarios con rol {target_gym_role.name} del gimnasio.")

    if is_gym_admin and local_caller.id == user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins no pueden eliminarse a sí mismos del gimnasio.")

    target_user = user_service.get_user(db, user_id=user_id)
    target_role = target_user.role if target_user else None

    try:
        logger.info(f"Eliminando asociación UserGym para user {user_id} en gym {current_gym.id}")
        db.delete(target_user_membership)
        db.commit()
        if redis_client and target_role:
            # <<< Invalidar caché de membresía específica >>>
            membership_cache_key = f"user_gym_membership:{user_id}:{current_gym.id}"
            await redis_client.delete(membership_cache_key)
            logging.info(f"Cache de membresía {membership_cache_key} invalidada")
            
            await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
            await user_service.invalidate_role_cache(redis_client, role=target_role, gym_id=current_gym.id)
            # Invalidar caché de GymUserSummary (si existe)
            await cache_service.delete_pattern(redis_client, f"gym:{current_gym.id}:users:*")
        logger.info(f"Usuario {user_id} eliminado exitosamente del gym {current_gym.id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Error al eliminar user {user_id} del gym {current_gym.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar usuario del gimnasio.")


# === Endpoints de Búsqueda y Lookup (Roles Específicos) === #

@router.get("/search", response_model=List[UserSchema], tags=["User Search"])
async def search_users(
    search_params: UserSearchParams = Depends(),
    db: Session = Depends(get_db),
    current_auth_user: Auth0User = Depends(get_current_user),
    current_gym: Optional[Gym] = Depends(get_current_gym)
) -> Any:
    """Búsqueda avanzada de usuarios. Admins buscan dentro de su gym, SuperAdmins globalmente."""
    
    local_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_auth_user.id)
    if not local_caller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no autorizado")

    is_super_admin = local_caller.role == UserRole.SUPER_ADMIN
    is_admin = local_caller.role == UserRole.ADMIN

    gym_id_to_search: Optional[int] = None

    if is_super_admin:
        pass
    elif is_admin:
        if not current_gym:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere X-Gym-ID header para administradores."
            )
        gym_id_to_search = current_gym.id
    else:
        if not current_gym:
             raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere X-Gym-ID header para esta operación."
            )
        gym_id_to_search = current_gym.id

    return user_service.search_users(db, search_params=search_params, gym_id=gym_id_to_search)

@router.get("/{user_id}", response_model=UserSchema, tags=["User Lookup"])
async def read_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    current_auth_user: Auth0User = Depends(get_current_user),
    current_gym: Optional[Gym] = Depends(get_current_gym),
) -> Any:
    """Obtiene un usuario específico por ID local (Admin/SuperAdmin). 
       Admins solo pueden ver usuarios dentro del gym actual (X-Gym-ID)."""
    local_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_auth_user.id)
    if not local_caller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no autorizado")

    is_super_admin = local_caller.role == UserRole.SUPER_ADMIN
    is_admin = local_caller.role == UserRole.ADMIN

    if not is_super_admin and not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a administradores."
        )

    # Obtener el usuario solicitado
    target_user = user_service.get_user(db, user_id=user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Si el llamante es ADMIN (no SuperAdmin), verificar que el target user
    # pertenece al gimnasio actual especificado en X-Gym-ID.
    if is_admin:
        if not current_gym:
            # Un ADMIN necesita el contexto de un gimnasio para buscar usuarios
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Se requiere X-Gym-ID header para administradores."
            )
        # Verificar si el usuario objetivo pertenece al gimnasio actual
        target_membership = gym_service.check_user_in_gym(db, user_id=target_user.id, gym_id=current_gym.id)
        if not target_membership:
            # Ocultar la existencia del usuario si no está en el gimnasio del ADMIN
            raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # Si es SuperAdmin o si es Admin y el usuario pertenece al gym actual, devolverlo.
    return target_user

@router.get("/auth0/{auth0_id}", response_model=UserSchema, tags=["User Lookup"])
async def read_user_by_auth0_id(
    auth0_id: str,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """Obtiene un usuario específico por su ID de Auth0."""
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return db_user


# === Endpoints de Administración de Plataforma (SuperAdmins) === #

@router.get("/", response_model=List[UserSchema], tags=["Platform Admin"])
async def read_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Obtiene todos los usuarios de la plataforma."""
    local_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not local_user or local_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol SUPER_ADMIN.")
    try:
        # Llamar al método cacheado del servicio
        users = await user_service.get_users_cached(db=db, skip=skip, limit=limit, redis_client=redis_client)
        # Eliminar lógica de caché directa de aquí
        # cache_key = f"users:all:skip:{skip}:limit:{limit}"
        # async def db_fetch(): return user_service.get_users(db, skip=skip, limit=limit)
        # users = await cache_service.get_or_set(redis_client=redis_client, cache_key=cache_key, db_fetch_func=db_fetch, model_class=UserSchema, expiry_seconds=300, is_list=True)
        return users
    except Exception as e:
        # El fallback ya está en el método del servicio, pero podemos loguear aquí si queremos
        logging.getLogger("user_endpoint").error(f"Error en endpoint read_users: {str(e)}", exc_info=True)
        # Podríamos relanzar una HTTPException específica o dejar que el servicio devuelva los datos sin caché
        raise HTTPException(status_code=500, detail="Error interno al obtener usuarios") # Opcional: relanzar error
        # O simplemente devolver la llamada no cacheada si el servicio la devuelve en caso de error
        # users = user_service.get_users(db, skip=skip, limit=limit)
        # return users

@router.get("/by-role/{role}", response_model=List[UserSchema], tags=["Platform Admin"])
async def read_users_by_role(
    role: UserRole,
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    gym_id: Optional[int] = Query(None, description="Filtrar por gimnasio específico (opcional)"),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Obtiene usuarios filtrados por rol global."""
    local_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not local_caller or local_caller.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol SUPER_ADMIN.")
    valid_roles = [UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.TRAINER, UserRole.MEMBER]
    if role not in valid_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rol inválido")
    try:
        # Usar el nuevo método get_gym_participants_cached pasando el rol como lista
        # Necesitamos pasar gym_id si está presente, y la lista de roles
        users = await user_service.get_gym_participants_cached(
            db=db, gym_id=gym_id, roles=[role], skip=skip, limit=limit, redis_client=redis_client
        )
        return users
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logging.getLogger("user_endpoint").error(f"Error buscando usuarios por rol {role.name} (gym_id={gym_id}): {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno buscando por rol.")

@router.put("/{user_id}", response_model=UserSchema, tags=["Platform Admin"])
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Actualiza el perfil de cualquier usuario."""
    local_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not local_caller or local_caller.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol SUPER_ADMIN.")
    target_user = user_service.get_user(db, user_id=user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario a actualizar no encontrado")
    old_role = target_user.role
    try:
        updated_user = await user_service.update_user(db=db, user_id=user_id, user_in=user_in, redis_client=redis_client)
        if redis_client:
            await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
            if old_role != updated_user.role:
                await user_service.invalidate_role_cache(redis_client, role=old_role)
                await user_service.invalidate_role_cache(redis_client, role=updated_user.role)
            # <<< Invalidar caché de perfil público específico >>>
            public_profile_cache_key = f"user_public_profile:{user_id}"
            await redis_client.delete(public_profile_cache_key)
            logger = logging.getLogger("user_endpoint")
            logger.info(f"(Superadmin Update) Invalidada caché de perfil público: {public_profile_cache_key}")
        return updated_user
    except HTTPException as e:
         raise e
    except Exception as e:
        logging.getLogger("user_endpoint").error(f"Error inesperado al actualizar usuario {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al actualizar usuario.")

@router.delete("/admin/users/{user_id}", response_model=UserSchema, tags=["Platform Admin"])
async def admin_delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Elimina un usuario completamente del sistema (BD y Auth0)."""
    local_caller = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not local_caller or local_caller.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol SUPER_ADMIN.")
    target_user = user_service.get_user(db, user_id=user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario a eliminar no encontrado")
    target_role = target_user.role
    try:
        deleted_user = user_service.delete_user(db, user_id=user_id)
        if redis_client:
            # <<< Invalidar cachés de membresía del usuario eliminado >>>
            # Necesitamos obtener los gym_ids a los que pertenecía ANTES de eliminar
            # Esto podría requerir ajustar delete_user o hacer una consulta previa.
            # Por simplicidad ahora, invalidaremos con patrón (menos eficiente)
            membership_pattern = f"user_gym_membership:{user_id}:*"
            await cache_service.delete_pattern(redis_client, membership_pattern)
            logging.info(f"(Superadmin Delete) Caches de membresía invalidadas para user {user_id} con patrón {membership_pattern}")

            await user_service.invalidate_role_cache(redis_client, role=target_role)
            await cache_service.invalidate_user_caches(redis_client, user_id=user_id)
            # <<< Invalidar caché de perfil público específico >>>
            public_profile_cache_key = f"user_public_profile:{user_id}"
            await redis_client.delete(public_profile_cache_key)
            # <<< Invalidar caché de usuario por auth0_id >>>
            # Necesitamos el auth0_id que estaba en deleted_user
            auth0_id_to_invalidate = deleted_user.auth0_id
            if auth0_id_to_invalidate:
                auth0_cache_key = f"user_by_auth0_id:{auth0_id_to_invalidate}"
                await redis_client.delete(auth0_cache_key)
                logging.info(f"(Superadmin Delete) Invalidada caché {auth0_cache_key}")
            
            logging.info(f"(Superadmin Delete) Invalidada caché de perfil público: {public_profile_cache_key}")
        return UserSchema.from_orm(deleted_user)
    except HTTPException as e:
        raise e
    except Exception as e:
        logging.getLogger("user_endpoint").error(f"Error inesperado al eliminar usuario {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar usuario.")

@router.put("/auth0/{auth0_id}", response_model=UserSchema, tags=["Platform Admin"])
async def update_user_by_auth0_id(
    auth0_id: str,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:users"]),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Actualiza un usuario específico por su ID de Auth0."""
    # Get user by Auth0 ID
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return await user_service.update_user(db=db, user_id=db_user.id, user_in=user_in, redis_client=redis_client)


# === NUEVO ENDPOINT PARA SINCRONIZACIÓN DESDE AUTH0 ACTIONS === #

@router.post(
    "/sync/email-status", 
    status_code=status.HTTP_204_NO_CONTENT, 
    tags=["Internal Sync"],
    dependencies=[Depends(verify_auth0_webhook_secret)]
)
async def sync_email_status_from_auth0(
    *, 
    sync_data: UserSyncFromAuth0, 
    db: Session = Depends(get_db),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> None:
    """
    Endpoint interno para recibir actualizaciones de estado de email desde Auth0 Actions.
    Actualiza el email del usuario en la base de datos local si es diferente.
    Protegido por un token secreto (X-Auth0-Webhook-Secret).
    """
    logger = logging.getLogger("user_endpoint")
    logger.info(f"Recibida llamada de sincronización para Auth0 ID: {sync_data.auth0_id}")
    
    updated_user = await user_service.sync_user_email_from_auth0(
        db=db,
        sync_data=sync_data,
        redis_client=redis_client
    )
    
    if updated_user is None:
        # Podríamos devolver 404 si el usuario no se encontró, 
        # pero para un webhook es común simplemente aceptar la llamada
        # y loggear el aviso como ya hace el servicio.
        logger.info(f"Sincronización completada (sin cambios o usuario no encontrado) para Auth0 ID: {sync_data.auth0_id}")
    else:
        logger.info(f"Sincronización de email completada para Auth0 ID: {sync_data.auth0_id}, User ID: {updated_user.id}")
        
    # No se necesita devolver contenido, un 204 es suficiente.
    return None


