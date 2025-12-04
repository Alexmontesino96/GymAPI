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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt
from app.models.user import User, UserRole
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.services.user import user_service
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate, UserRoleUpdate, UserProfileUpdate, UserSearchParams, EmailAvailabilityCheck, UserPublicProfile, Auth0EmailChangeRequest, UserSyncFromAuth0, GymUserSummary, UserProfile, UserBasicInfo
from app.services.auth0_mgmt import auth0_mgmt_service
from app.core.tenant import verify_gym_access, verify_gym_admin_access, verify_gym_trainer_access, get_current_gym, GymSchema
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.db.session import get_async_db, get_async_db
from app.core.config import get_settings
from app.db.redis_client import get_redis_client, redis
from app.services.cache_service import cache_service
from app.services.gym import gym_service
from app.services.user_stats import user_stats_service
from app.core.security import verify_auth0_webhook_secret
from app.middleware.rate_limit import limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/profile", response_model=UserSchema, tags=["Profile"])
async def get_user_profile(
    request: Request,
    db: AsyncSession = Depends(get_async_db),  # ✅ MIGRADO A ASYNC
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Obtiene el perfil del usuario autenticado.

    ✅ ASYNC: Migrado a AsyncSession para mejor performance.
    """
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(status_code=400, detail="Token inválido")

    # ✅ ASYNC: Obtener o crear usuario
    user_data = {"sub": auth0_id, "email": getattr(user, "email", None)}

    # Por ahora usar método sync en executor hasta migrar create_or_update_auth0_user
    # TODO: Crear versión completamente async de create_or_update_auth0_user
    from app.core.async_utils import run_sync_in_async

    @run_sync_in_async
    def _create_or_update(data):
        from app.db.session import SessionLocal
        sync_db = SessionLocal()
        try:
            # Importar el método sync temporalmente
            import asyncio
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(
                user_service.create_or_update_auth0_user_async(sync_db, data)
            )
            loop.close()
            return result
        finally:
            sync_db.close()

    db_user = await _create_or_update(user_data)

    # Consistencia: si viene X-Gym-ID y el middleware pobló el rol del gym,
    # incluirlo en la respuesta como gym_role.
    try:
        user_schema = UserSchema.model_validate(db_user)
        role_in_gym = getattr(request.state, 'role_in_gym', None)
        if role_in_gym:
            from app.models.user_gym import GymRoleType
            user_schema.gym_role = GymRoleType(role_in_gym)
        logger.debug(f"Perfil async obtenido para usuario auth0_id={auth0_id}")
        return user_schema
    except Exception as e:
        logger.error(f"Error procesando perfil: {e}")
        # Fallback: devolver el modelo original si algo falla en la conversión
        return db_user

@router.put("/profile", response_model=UserSchema, tags=["Profile"])
async def update_user_profile(
    profile_update: UserProfileUpdate,
    db: AsyncSession = Depends(get_async_db),
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
    file: Optional[UploadFile] = File(None),
    image: Optional[UploadFile] = File(None),
    photo: Optional[UploadFile] = File(None),
    picture: Optional[UploadFile] = File(None),
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Sube o actualiza la imagen de perfil del usuario autenticado.

    Acepta el archivo en cualquiera de estos nombres de campo:
    - file
    - image
    - photo
    - picture
    """
    # Obtener el primer archivo disponible
    upload_file = file or image or photo or picture

    if not upload_file:
        raise HTTPException(
            status_code=400,
            detail="Debe proporcionar un archivo de imagen (campo: file, image, photo o picture)"
        )

    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(status_code=400, detail="Token inválido")
    content_type = upload_file.content_type or ""
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="El archivo debe ser una imagen")
    updated_user = await user_service.update_user_profile_image(db, auth0_id, upload_file)
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

@router.post("/profile/data", response_model=UserSchema, tags=["Profile"])
async def create_or_update_user_profile_data(
    profile_data: UserProfileUpdate, # Usamos el esquema existente que excluye email/teléfono
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["user:read"]), # Asegurar autenticación
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """
    Crea o actualiza datos específicos del perfil del usuario autenticado.
    Este endpoint permite establecer nombre, apellido, fecha de nacimiento, altura, peso, etc.,
    pero NO modifica el email ni el número de teléfono.
    """
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")

    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario local no encontrado")

    logger = logging.getLogger("user_endpoint")
    logger.info(f"Usuario {db_user.id} ({auth0_id}) actualizando datos de perfil.")

    try:
        updated_user = user_service.update_user_profile(db, user_id=db_user.id, profile_in=profile_data)

        if redis_client:
            logger.info(f"Invalidando cachés para usuario {db_user.id} tras actualizar datos de perfil.")
            await cache_service.invalidate_user_caches(redis_client, user_id=db_user.id)
            public_profile_cache_key = f"user_public_profile:{db_user.id}"
            await redis_client.delete(public_profile_cache_key)
            logger.debug(f"Invalidada caché de perfil público: {public_profile_cache_key}")

        return updated_user
    except Exception as e:
        logger.error(f"Error actualizando datos de perfil para usuario {db_user.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al actualizar los datos del perfil."
        )

@router.get("/profile/me", response_model=UserProfile, tags=["Profile"])
async def get_my_profile(
    db: AsyncSession = Depends(get_async_db),  # ✅ MIGRADO A ASYNC
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtiene el perfil detallado del usuario autenticado sin incluir información sensible.

    Este endpoint devuelve información detallada del perfil del usuario actual,
    pero excluye datos sensibles como email y número de teléfono. Incluye información
    como nombre, foto de perfil, biografía, metas, altura, peso y fecha de nacimiento.

    ✅ ASYNC: Migrado a AsyncSession para mejor performance.
    """
    logger_local = logging.getLogger("user_endpoint")

    # Obtener ID de Auth0
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")

    try:
        # ✅ ASYNC: Obtener usuario con método async
        db_user = await user_service.get_user_by_auth0_id_async_direct(
            db,
            auth0_id=auth0_id,
            eager_load=False  # No necesitamos relaciones para este endpoint
        )

        if not db_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        # Crear y devolver objeto UserProfile
        user_profile = UserProfile(
            id=db_user.id,
            first_name=db_user.first_name,
            last_name=db_user.last_name,
            picture=db_user.picture,
            role=db_user.role,
            bio=db_user.bio,
            goals=db_user.goals,
            height=db_user.height,
            weight=db_user.weight,
            birth_date=db_user.birth_date,
            is_active=db_user.is_active,
            created_at=db_user.created_at
        )

        logger_local.debug(f"Perfil async obtenido para usuario {db_user.id}")
        return user_profile

    except HTTPException as e:
        # Re-lanzar excepciones HTTP
        raise e
    except Exception as e:
        logger_local.error(f"Error obteniendo perfil propio (async): {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener perfil de usuario"
        )

@router.get("/last-attendance", response_model=Dict[str, Any], tags=["Profile"])
async def get_last_attendance(
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    current_gym: GymSchema = Depends(verify_gym_access),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtiene la fecha de la última asistencia del usuario autenticado.

    Este endpoint devuelve la fecha y hora de la última vez que el usuario
    hizo check-in en el gimnasio actual.

    **Características:**
    - ⚡ Optimizado con caché (TTL: 10 minutos)
    - 🔒 Multi-tenant: Solo asistencias del gimnasio actual
    - 📊 Datos desde ClassParticipation con status ATTENDED

    **Permissions:**
    - Requiere scope 'resource:read' (usuarios autenticados)
    - Requiere pertenecer al gimnasio actual

    **Returns:**
    - JSON con last_attendance_date, user_id, gym_id
    - last_attendance_date será null si no hay asistencias previas
    """
    logger_endpoint = logging.getLogger("user_endpoint")

    # Obtener ID de Auth0
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")

    try:
        # Obtener usuario desde la BD
        db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
        if not db_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        # Obtener última fecha de asistencia
        last_attendance_date = await user_stats_service.get_last_attendance_date(
            db=db,
            user_id=db_user.id,
            gym_id=current_gym.id,
            redis_client=redis_client
        )

        logger_endpoint.info(f"Last attendance retrieved for user {db_user.id}, gym {current_gym.id}")

        return {
            "user_id": db_user.id,
            "gym_id": current_gym.id,
            "last_attendance_date": last_attendance_date.isoformat() if last_attendance_date else None,
            "has_attendance": last_attendance_date is not None
        }

    except HTTPException as e:
        # Re-lanzar excepciones HTTP
        raise e
    except Exception as e:
        logger_endpoint.error(f"Error obteniendo última asistencia: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener última asistencia"
        )

@router.get("/profile/{user_id}", response_model=UserProfile, tags=["Profile"])
async def get_user_profile_by_id(
    user_id: int = Path(..., title="ID del usuario", ge=1),
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: GymSchema = Depends(verify_gym_access),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """
    Obtiene el perfil detallado de un usuario si ambos pertenecen al mismo gimnasio.
    
    Este endpoint permite ver el perfil de otro usuario, pero solo si el usuario actual
    y el usuario objetivo pertenecen al mismo gimnasio. Devuelve información de perfil
    sin incluir datos sensibles como email o número de teléfono.
    """
    logger = logging.getLogger("user_endpoint")
    gym_id = current_gym.id # ID del gimnasio actual
    
    # Obtener ID del usuario actual
    auth0_id = current_user.id
    if not auth0_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token inválido")
    
    # Obtener ID interno del usuario actual
    current_db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not current_db_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario actual no encontrado")
    
    try:
        # Verificar que el usuario objetivo pertenece al mismo gimnasio
        target_belongs_to_gym = False
        
        if redis_client:
            # Verificar usando caché
            membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
            cached_role = await redis_client.get(membership_cache_key)
            
            if cached_role is not None:
                if cached_role == "__NONE__":
                    target_belongs_to_gym = False
                else:
                    target_belongs_to_gym = True
            else:
                # Cache miss, verificar en BD
                result = await db.execute(select(UserGym).where(
                    UserGym.user_id == user_id,
                    UserGym.gym_id == gym_id
                ))
    user_gym = result.scalar_one_or_none()
                
                if user_gym:
                    target_belongs_to_gym = True
                    # Actualizar caché
                    await redis_client.set(
                        membership_cache_key, 
                        user_gym.role.value, 
                        ex=get_settings().CACHE_TTL_USER_MEMBERSHIP
                    )
                else:
                    # Guardar resultado negativo en caché
                    await redis_client.set(
                        membership_cache_key, 
                        "__NONE__", 
                        ex=get_settings().CACHE_TTL_NEGATIVE
                    )
        else:
            # Sin Redis, verificar directamente en BD
            result = await db.execute(select(UserGym).where(
                UserGym.user_id == user_id,
                UserGym.gym_id == gym_id
            ))
    user_gym = result.scalar_one_or_none()
            target_belongs_to_gym = user_gym is not None
        
        if not target_belongs_to_gym:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado o no pertenece al mismo gimnasio"
            )
        
        # Obtener usuario objetivo
        target_user = user_service.get_user(db, user_id=user_id)
        if not target_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
        # Crear y devolver objeto UserProfile
        user_profile = UserProfile(
            id=target_user.id,
            first_name=target_user.first_name,
            last_name=target_user.last_name,
            picture=target_user.picture,
            role=target_user.role,
            bio=target_user.bio,
            goals=target_user.goals,
            height=target_user.height,
            weight=target_user.weight,
            birth_date=target_user.birth_date,
            is_active=target_user.is_active,
            created_at=target_user.created_at
        )
        
        return user_profile
        
    except HTTPException as e:
        # Re-lanzar excepciones HTTP
        raise e
    except Exception as e:
        logger.error(f"Error obteniendo perfil de usuario {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al obtener perfil de usuario"
        )

@router.post("/check-email-availability", response_model=dict, tags=["Email Management"])
@limiter.limit("10 per minute")
async def check_email_availability(
    *,
    db: AsyncSession = Depends(get_async_db),
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
@limiter.limit("3 per minute")
async def initiate_auth0_email_change(
    *,
    db: AsyncSession = Depends(get_async_db),
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
    db: AsyncSession = Depends(get_async_db),
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
    request: Request,
    role: Optional[UserRole] = Query(None, description="Filtrar por rol (MEMBER o TRAINER). Omitir para ambos."),
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["user:read"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Any:
    """
    [ADMIN ONLY] Obtiene miembros y/o entrenadores del gimnasio actual.
    
    Este endpoint permite a administradores, propietarios y super administradores ver 
    todos los miembros y/o entrenadores registrados en el gimnasio actual.
    
    Permissions:
        - Requiere scope "user:read"
        - Requiere ser ADMIN u OWNER del gimnasio actual, o SUPER_ADMIN
        
    Args:
        request: Objeto de solicitud
        role: Filtrar por rol (MEMBER o TRAINER). Omitir para ambos
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario administrador autenticado
        redis_client: Cliente de Redis
        current_gym: Gimnasio actual verificado
        
    Returns:
        List[UserSchema]: Lista de usuarios con el rol especificado
    """
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
    request: Request,
    role: Optional[UserRole] = Query(None, description="Filtrar por rol (MEMBER o TRAINER). Omitir para ambos."),
    name_contains: Optional[str] = Query(None, description="Filtrar por nombre/apellido (parcial)"),
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: GymSchema = Depends(verify_gym_access)
) -> Any:
    """
    Obtiene perfiles públicos de miembros y/o entrenadores del gimnasio actual.
    
    Este endpoint permite a cualquier miembro del gimnasio ver los perfiles
    públicos de otros miembros del mismo gimnasio.
    
    Permissions:
        - Requiere scope "resource:read"
        - Requiere pertenecer al gimnasio actual
        
    Args:
        request: Objeto de solicitud
        role: Filtrar por rol (MEMBER o TRAINER). Omitir para ambos
        name_contains: Filtrar por nombre/apellido (búsqueda parcial)
        db: Sesión de base de datos
        skip: Número de registros a omitir (paginación)
        limit: Número máximo de registros a devolver
        current_user: Usuario autenticado
        redis_client: Cliente de Redis
        current_gym: Gimnasio actual verificado
        
    Returns:
        List[UserPublicProfile]: Lista de perfiles públicos de usuarios
    """
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

@router.get("/p/gym-participants/{user_id}", response_model=UserPublicProfile, tags=["Gym Participants (Public)"])
async def read_public_gym_participant_by_id(
    request: Request,
    user_id: int = Path(..., title="ID interno del usuario", ge=1),
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    current_gym: GymSchema = Depends(verify_gym_access),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Obtiene el perfil público de un miembro/entrenador del gimnasio actual por **ID interno**.

    • Visibilidad idéntica al listado público: cualquier miembro del gimnasio puede consultar
      a otro miembro del mismo gym.
    • Devuelve los mismos campos que el listado (`UserPublicProfile`).
    """
    logger = logging.getLogger("user_endpoint")
    gym_id = current_gym.id

    # Verificar pertenencia del usuario objetivo al gimnasio actual (con caché)
    membership_cache_key = f"user_gym_membership:{user_id}:{gym_id}"
    try:
        belongs = None
        if redis_client:
            cached = await redis_client.get(membership_cache_key)
            if cached is not None:
                belongs = cached != "__NONE__"
        if belongs is None:
            # Cache miss o redis no disponible ⇒ consultar BD
            from app.models.user_gym import UserGym
            result = await db.execute(select(UserGym).where(UserGym.user_id == user_id, UserGym.gym_id == gym_id))
    membership = result.scalar_one_or_none()
            belongs = membership is not None
            # Guardar en caché si es posible
            if redis_client:
                ttl = get_settings().CACHE_TTL_USER_MEMBERSHIP if belongs else get_settings().CACHE_TTL_NEGATIVE
                await redis_client.set(membership_cache_key, membership.role.value if belongs else "__NONE__", ex=ttl)

        if not belongs:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verificando membresía en gym ({membership_cache_key}): {e}", exc_info=True)
        # Fallback BD sin caché
        from app.models.user_gym import UserGym
        result = await db.execute(select(UserGym).where(UserGym.user_id == user_id, UserGym.gym_id == gym_id))
    membership = result.scalar_one_or_none()
        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio (BD Fallback)")

    # Obtener perfil público (con caché)
    try:
        public_profile = await user_service.get_public_profile_cached(user_id, db, redis_client)
        if not public_profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        return public_profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo perfil público para user {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al obtener perfil")

@router.get("/p/public-profile/{user_id}", response_model=UserPublicProfile, tags=["Gym Participants (Public)"])
async def read_public_user_profile(
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    current_gym: GymSchema = Depends(verify_gym_access),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Mantiene compatibilidad con la ruta histórica `/p/public-profile/{user_id}`.

    Internamente reutiliza la lógica del nuevo endpoint basado en la ruta
    `/p/gym-participants/{user_id}`.
    """
    return await read_public_gym_participant_by_id(
        request=request,
        user_id=user_id,
        db=db,
        current_user=current_user,
        current_gym=current_gym,
        redis_client=redis_client,
    )


# === Endpoints de Gestión de Gimnasio (Admins de Gym / SuperAdmins) === #

@router.get("/search-by-email", response_model=UserBasicInfo, tags=["Gym Management"])
async def search_user_by_email(
    email: EmailStr = Query(..., description="Email del usuario a buscar"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["user:read"]),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Any:
    """
    [ADMIN ONLY] Busca un usuario por email que NO pertenezca al gimnasio actual.
    
    Este endpoint permite a administradores buscar usuarios por email 
    que existan en la plataforma pero que NO pertenezcan al gimnasio actual,
    para poder añadirlos posteriormente usando su ID.
    
    Permissions:
        - Requiere scope "user:read"
        - Requiere ser ADMIN u OWNER del gimnasio actual, o SUPER_ADMIN
        
    Args:
        email: Email del usuario a buscar
        db: Sesión de base de datos
        current_user: Usuario administrador autenticado
        current_gym: Gimnasio actual verificado
        
    Returns:
        UserBasicInfo: Información básica del usuario encontrado que NO está en el gimnasio
        
    Raises:
        HTTPException: 404 si el usuario no existe o ya está en el gimnasio
    """
    logger = logging.getLogger("user_endpoint")
    logger.info(f"🔍 search-by-email endpoint llamado con email: {email}")
    
    try:
        # Buscar usuario por email
        target_user = user_service.get_user_by_email(db, email=email)
        if not target_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Usuario no encontrado en la plataforma"
            )
        
        # Verificar que el usuario NO pertenece al gimnasio actual
        from app.models.user_gym import UserGym
        result = await db.execute(select(UserGym).where(
            UserGym.user_id == target_user.id,
            UserGym.gym_id == current_gym.id
        ))
    membership = result.scalar_one_or_none()
        
        if membership:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Usuario ya pertenece a este gimnasio"
            )
        
        logger.info(f"Admin {current_user.id} búsqueda por email {email} en gym {current_gym.id} - Usuario disponible para añadir: {target_user.id}")
        
        # Crear respuesta con información básica
        return UserBasicInfo(
            id=target_user.id,
            email=target_user.email,
            first_name=target_user.first_name,
            last_name=target_user.last_name
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error buscando usuario por email {email} para gym {current_gym.id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al buscar usuario por email"
        )

@router.get("/gym-users", response_model=List[GymUserSummary], tags=["Gym Management"])
async def read_gym_users(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    role: Optional[UserRole] = Query(None, description="Filtrar por rol de usuario global"),
    current_user: Auth0User = Security(auth.get_user, scopes=["user:read"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: GymSchema = Depends(verify_gym_admin_access)
) -> Any:
    """[ADMIN] Obtiene todos los usuarios asociados al gimnasio actual."""
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
    if not local_caller:
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
    request: Request,
    user_id: int = Path(..., title="ID del usuario a eliminar del gimnasio"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> None:
    """[ADMIN] Elimina a un usuario (TRAINER o MEMBER) del gimnasio actual."""
    logger = logging.getLogger("user_endpoint")
    logger.info(f"Intento de eliminar user {user_id} del gym {current_gym.id} por usuario {current_user.id}")

    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
    if not local_caller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario llamante no encontrado")

    is_super_admin = local_caller.role == UserRole.SUPER_ADMIN
    is_gym_admin = False
    if not is_super_admin:
        result = await db.execute(select(UserGym).where(UserGym.user_id == local_caller.id, UserGym.gym_id == current_gym.id, UserGym.role == GymRoleType.ADMIN))
    caller_gym_membership = result.scalar_one_or_none()
        if not caller_gym_membership:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permisos insuficientes para eliminar usuarios de este gimnasio")
        is_gym_admin = True

    result = await db.execute(select(UserGym).where(UserGym.user_id == user_id, UserGym.gym_id == current_gym.id))
    target_user_membership = result.scalar_one_or_none()
    if not target_user_membership:
        result = await db.execute(select(User.id).where(User.id == user_id))
 target_user_exists = result.scalar() is not None
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
        await db.commit()
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
        await db.rollback()
        logger.error(f"Error al eliminar user {user_id} del gym {current_gym.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error interno al eliminar usuario del gimnasio.")


# === Endpoints de Búsqueda y Lookup (Roles Específicos) === #

@router.get("/search", response_model=List[UserSchema], tags=["User Search"])
async def search_users(
    search_params: UserSearchParams = Depends(),
    db: AsyncSession = Depends(get_async_db),
    current_auth_user: Auth0User = Depends(get_current_user),
    current_gym: Optional[GymSchema] = Depends(get_current_gym),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Búsqueda avanzada de usuarios. Admins buscan dentro de su gym, SuperAdmins globalmente."""
    
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_auth_user.id, redis_client)
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
    request: Request,
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_auth_user: Auth0User = Depends(get_current_user),
    current_gym: Optional[GymSchema] = Depends(get_current_gym),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """Obtiene un usuario específico por ID local (Admin/SuperAdmin). 
       Admins solo pueden ver usuarios dentro del gym actual (X-Gym-ID)."""
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_auth_user.id, redis_client)
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
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["user:read"]),
) -> Any:
    """Obtiene un usuario específico por su ID de Auth0."""
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return db_user


# === Endpoints de Administración de Plataforma (SuperAdmins) === #

@router.get("/", response_model=List[UserSchema], tags=["Platform Admin"])
async def read_users(
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["user:read"]),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Obtiene todos los usuarios de la plataforma."""
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_user = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
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
    db: AsyncSession = Depends(get_async_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    gym_id: Optional[int] = Query(None, description="Filtrar por gimnasio específico (opcional)"),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Obtiene usuarios filtrados por rol global."""
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
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
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Actualiza el perfil de cualquier usuario."""
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
    if not local_caller or local_caller.role != UserRole.SUPER_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requiere rol SUPER_ADMIN.")
    target_user = user_service.get_user(db, user_id=user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario a actualizar no encontrado")
    old_role = target_user.role
    
    # Actualizar usuario
    updated_user = user_service.update_user(db, db_obj=target_user, obj_in=user_in)
    
    # Si el rol cambió, actualizar en Auth0
    if old_role != updated_user.role:
        from app.services.auth0_sync import auth0_sync_service
        try:
            await auth0_sync_service.update_highest_role_in_auth0(db, user_id)
            logger.info(f"Rol más alto de usuario {user_id} actualizado en Auth0 después de cambio de rol global")
        except Exception as e:
            logger.error(f"Error actualizando rol en Auth0 para usuario {user_id}: {str(e)}")
            # No falla la operación principal si la sincronización falla

    # Invalidar caché del usuario
    if redis_client:
        await cache_service.invalidate_user_caches(redis_client, user_id=user_id, auth0_id=target_user.auth0_id)
    
    return updated_user

@router.delete("/admin/users/{user_id}", response_model=UserSchema, tags=["Platform Admin"])
async def admin_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_async_db),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Any:
    """[SUPER_ADMIN] Elimina un usuario completamente del sistema (BD y Auth0)."""
    # Usar la versión cacheada para evitar consulta a BD innecesaria
    local_caller = await user_service.get_user_by_auth0_id_cached(db, current_user.id, redis_client)
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
    db: AsyncSession = Depends(get_async_db),
    user: Auth0User = Security(auth.get_user, scopes=["user:write"]),
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
    db: AsyncSession = Depends(get_async_db),
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

# === Nuevo endpoint público para un participante específico por ID === #

@router.get(
    "/gym-participants/{user_id}",
    response_model=UserSchema,
    tags=["Gym Participants"],
)
async def read_gym_participant_by_id(
    request: Request,
    user_id: int = Path(..., ge=1, title="ID interno del usuario"),
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 1,
    current_user: Auth0User = Security(auth.get_user, scopes=["user:read"]),
    redis_client: redis.Redis = Depends(get_redis_client),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
) -> Any:
    """[ADMIN ONLY] Obtiene un usuario del gimnasio actual por ID.

    Permite ver cualquier usuario que pertenezca al gimnasio actual, 
    independientemente de su rol (MEMBER, TRAINER, ADMIN, OWNER).
    """
    logger = logging.getLogger("user_endpoint")

    from app.models.user_gym import UserGym, GymRoleType

    # Verificar que el usuario pertenezca al gimnasio actual
    result = await db.execute(
        select(UserGym).where(UserGym.user_id == user_id, UserGym.gym_id == current_gym.id)
    )
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado en este gimnasio")

    # Obtener usuario (podemos utilizar servicio con caché)
    try:
        user_data = await user_service.get_user_cached(db, user_id, redis_client)
    except AttributeError:
        # Fallback si get_user_cached no existe aún
        user_data = user_service.get_user(db, user_id=user_id)

    if not user_data:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    # --- NUEVO: establecer el rol dentro del gimnasio en la respuesta ---
    try:
        # Mutar el modelo Pydantic con el rol específico del gym
        user_data.gym_role = membership.role  # type: ignore[attr-defined]
        
        # Mapeo seguro entre GymRoleType y UserRole
        gym_to_user_role_mapping = {
            GymRoleType.MEMBER: UserRole.MEMBER,
            GymRoleType.TRAINER: UserRole.TRAINER,
            GymRoleType.ADMIN: UserRole.ADMIN,
            GymRoleType.OWNER: UserRole.ADMIN  # OWNER se mapea a ADMIN en el contexto de UserRole
        }
        
        # Solo sobrescribir si existe mapeo directo
        if membership.role in gym_to_user_role_mapping:
            user_data.role = gym_to_user_role_mapping[membership.role]  # type: ignore[attr-defined]
        else:
            logger.debug(f"No se encontró mapeo para rol de gimnasio {membership.role}, manteniendo rol original del usuario")
            
    except Exception as e:
        logger.warning(f"No se pudo asignar gym_role/role en la respuesta de usuario {user_id}: {e}")

    return user_data

