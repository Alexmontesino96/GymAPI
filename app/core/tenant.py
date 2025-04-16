from fastapi import Header, HTTPException, Depends, Request, status, Query
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List, Dict, Tuple, Set
from functools import wraps
import time
import asyncio

from app.db.session import get_db
from app.models.gym import Gym
from app.models.user_gym import UserGym, GymRoleType
from app.models.user import User, UserRole
from app.core.auth0_fastapi import Auth0User, get_current_user
from app.repositories.gym import gym_repository
from app.db.redis_client import get_redis_client, redis
from app.core.config import get_settings
import logging
from app.services.user import user_service
from app.services.cache_service import cache_service
from app.schemas.gym import GymSchema
from app.core.profiling import time_redis_operation, time_db_query, register_cache_hit, register_cache_miss
from app.schemas.user import User as UserSchema

async def get_tenant_id(
    x_gym_id: Optional[str] = Header(None, alias="X-Gym-ID")
) -> Optional[int]:
    """
    Obtiene el ID del tenant (gimnasio) únicamente del header X-Gym-ID.
    """
    if x_gym_id:
        try:
            return int(x_gym_id)
        except (ValueError, TypeError):
            logger = logging.getLogger("tenant_verification")
            logger.warning(f"Formato inválido para X-Gym-ID: {x_gym_id}")
            return None
    return None

async def get_current_gym(
    db: Session = Depends(get_db),
    tenant_id: Optional[int] = Depends(get_tenant_id),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> Optional[GymSchema]:
    """
    Obtiene el GymSchema actual basado en el tenant ID, usando caché Redis.
    Devuelve None si no se proporciona tenant_id o si el gym no existe.
    """
    logger = logging.getLogger("tenant_verification")
    
    if not tenant_id:
        return None
        
    gym_schema: Optional[GymSchema] = None

    if not redis_client:
        logger.warning(f"Redis no disponible, obteniendo gym {tenant_id} desde BD")
        @time_db_query
        def _direct_db_fetch(): 
            return db.query(Gym).filter(Gym.id == tenant_id).first()
        gym_db = _direct_db_fetch()
        if gym_db:
            gym_schema = GymSchema.from_orm(gym_db)
    else:
        cache_key = f"gym_details:{tenant_id}"
        
        @time_db_query 
        async def db_fetch():
            # Registro del cache miss
            register_cache_miss(cache_key)
            
            logger.info(f"DB Fetch for gym details cache miss: key={cache_key}")
            gym_db = db.query(Gym).filter(Gym.id == tenant_id).first()
            return GymSchema.from_orm(gym_db) if gym_db else None
            
        try:
            # El registro de cache hit/miss se realiza dentro de la función get_or_set
            gym_schema = await cache_service.get_or_set(
                redis_client=redis_client,
                cache_key=cache_key,
                db_fetch_func=db_fetch, 
                model_class=GymSchema,
                expiry_seconds=get_settings().CACHE_TTL_GYM_DETAILS, 
                is_list=False
            )
        except Exception as e:
            logger.error(f"Error obteniendo gym {tenant_id} desde caché/DB: {e}", exc_info=True)
            @time_db_query
            def _fallback_db_fetch(): 
                return db.query(Gym).filter(Gym.id == tenant_id).first()
            gym_db_fallback = _fallback_db_fetch()
            gym_schema = GymSchema.from_orm(gym_db_fallback) if gym_db_fallback else None

    if not gym_schema:
         if tenant_id: 
             logger.warning(f"El gimnasio con ID {tenant_id} no existe o no está activo.")
         return None

    return gym_schema

async def _verify_user_role_in_gym(
    request: Request,
    required_roles: Optional[Set[GymRoleType]],
    db: Session,
    current_gym_schema: Optional[GymSchema],
    current_user: Auth0User,
    redis_client: redis.Redis
) -> GymSchema:
    """
    Verifica que el usuario pertenece al gimnasio y tiene el rol requerido.
    Permite acceso si el usuario es SUPER_ADMIN global.
    """
    if not current_gym_schema:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Se requiere un ID de gimnasio (X-Gym-ID)")
    
    gym_id = current_gym_schema.id
    gym_name = current_gym_schema.name
    logger = logging.getLogger("tenant_verification")
    
    # --- Obtener usuario local y verificar rol SUPER_ADMIN --- 
    local_user = await user_service.get_user_by_auth0_id_cached(
        db=db, auth0_id=current_user.id, redis_client=redis_client
    )
    if not local_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Usuario no encontrado en el sistema local"
        )
        
    # Si es SUPER_ADMIN, conceder acceso directamente a cualquier gimnasio
    if local_user.role == UserRole.SUPER_ADMIN:
        logger.debug(f"Acceso concedido a gym {gym_id} para SUPER_ADMIN (User ID: {local_user.id})")
        return current_gym_schema
    # --- Fin verificación SUPER_ADMIN --- 
    
    user_id = local_user.id # ID interno del usuario
    
    # --- Lógica existente para verificar rol específico del gimnasio --- 
    # --- (Incluyendo optimización fallida de request.state que podemos eliminar o ignorar) --- 
    user_role_in_gym = getattr(request.state, 'role_in_gym', None)
    user_from_state = getattr(request.state, 'user', None)
    gym_from_state = getattr(request.state, 'gym', None)
    
    if gym_from_state and gym_from_state.id != gym_id:
         user_role_in_gym = None
         user_from_state = None
    if user_from_state and user_from_state.auth0_id != current_user.id:
         user_role_in_gym = None
         user_from_state = None
         
    if user_role_in_gym is not None:
        logger.debug(f"Verificación de rol obtenida de request.state: Rol={user_role_in_gym}")
        cache_hit_status = "STATE_HIT"
    else:
        # Verificar membresía (lógica de caché/DB existente)
        cache_hit_status = "NO_REDIS"
        if redis_client:
            cache_key = f"user_gym_membership:{user_id}:{gym_id}"
            try:
                @time_redis_operation
                async def _redis_get(key): return await redis_client.get(key)
                cached_role_str = await _redis_get(cache_key)
                
                if cached_role_str is not None:
                    register_cache_hit(cache_key)
                    if cached_role_str == "__NONE__":
                        cache_hit_status = "HIT_NEGATIVE"
                        user_role_in_gym = None 
                    else:
                        cache_hit_status = "HIT_POSITIVE"
                        user_role_in_gym = cached_role_str
                else:
                    register_cache_miss(cache_key)
                    cache_hit_status = "MISS"
                    @time_db_query
                    def _fetch_membership(): 
                         return db.query(UserGym).filter(UserGym.user_id == user_id, UserGym.gym_id == gym_id).first()
                    user_gym_db = _fetch_membership()
                    
                    if user_gym_db:
                        user_role_in_gym = user_gym_db.role.value
                        @time_redis_operation
                        async def _redis_set(key, value, ex): await redis_client.set(key, value, ex=ex)
                        asyncio.create_task(_redis_set(cache_key, user_role_in_gym, get_settings().CACHE_TTL_USER_MEMBERSHIP))
                    else:
                        @time_redis_operation
                        async def _redis_set_neg(key, value, ex): await redis_client.set(key, value, ex=ex)
                        asyncio.create_task(_redis_set_neg(cache_key, "__NONE__", get_settings().CACHE_TTL_NEGATIVE))
                        user_role_in_gym = None
            except Exception as e:
                logger.error(f"Error durante verificación de rol en gym con Redis: {e}", exc_info=True)
                cache_hit_status = "REDIS_ERROR_FALLBACK"
                @time_db_query
                def _fallback_fetch(): 
                     return db.query(UserGym).filter(UserGym.user_id == user_id, UserGym.gym_id == gym_id).first()
                user_gym_db_fallback = _fallback_fetch()
                user_role_in_gym = user_gym_db_fallback.role.value if user_gym_db_fallback else None

    if user_role_in_gym is None:
        logger.warning(f"Acceso denegado a gym {gym_id} para user {current_user.id}. No pertenece. (Cache: {cache_hit_status})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Acceso denegado al gimnasio {gym_name}")

    required_role_values = {role.value for role in required_roles} if required_roles else None

    if required_role_values is not None and user_role_in_gym not in required_role_values:
        logger.warning(f"Acceso denegado a gym {gym_id} para user {current_user.id}. Rol '{user_role_in_gym}' insuficiente (Req: {required_role_values}). (Cache: {cache_hit_status})")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permisos insuficientes en el gimnasio {gym_name}")

    logger.debug(f"Acceso concedido a gym {gym_id} para user {current_user.id}. Rol: '{user_role_in_gym}' (Req: {required_roles or 'Any'}). (Cache: {cache_hit_status})")
    return current_gym_schema

async def verify_gym_access(
    request: Request,
    db: Session = Depends(get_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """Dependencia: Verifica que el usuario pertenece al gimnasio."""
    return await _verify_user_role_in_gym(request, None, db, current_gym_schema, current_user, redis_client)

async def verify_gym_admin_access(
    request: Request,
    db: Session = Depends(get_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """Dependencia: Verifica rol ADMIN u OWNER en el gimnasio."""
    return await _verify_user_role_in_gym(request, {GymRoleType.ADMIN, GymRoleType.OWNER}, db, current_gym_schema, current_user, redis_client)

async def verify_gym_trainer_access(
    request: Request,
    db: Session = Depends(get_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """Dependencia: Verifica rol TRAINER, ADMIN u OWNER en el gimnasio."""
    return await _verify_user_role_in_gym(request, {GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER}, db, current_gym_schema, current_user, redis_client)

async def verify_gym_ownership(
    request: Request,
    db: Session = Depends(get_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """Dependencia: Verifica rol OWNER en el gimnasio."""
    return await _verify_user_role_in_gym(request, {GymRoleType.OWNER}, db, current_gym_schema, current_user, redis_client)

async def verify_admin_role(request: Request, gym: GymSchema = Depends(verify_gym_admin_access)) -> GymSchema:
    return gym
async def verify_trainer_role(request: Request, gym: GymSchema = Depends(verify_gym_trainer_access)) -> GymSchema:
    return gym
async def verify_member_role(request: Request, gym: GymSchema = Depends(verify_gym_access)) -> GymSchema:
    return gym 