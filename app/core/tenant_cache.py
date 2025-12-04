"""
Verificación de acceso a gimnasio con soporte para caché de usuario.

Este módulo proporciona dependencias optimizadas para verificar el acceso
de un usuario a un gimnasio específico, evitando duplicar consultas al
mismo usuario en una solicitud.
"""

from fastapi import Depends, Request, HTTPException, status, Security
from fastapi.security import SecurityScopes
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.db.session import get_async_db
from app.db.redis_client import get_redis_client, redis
from app.core.user_cache import get_current_user_cached
from app.core.auth0_fastapi import Auth0User
from app.schemas.gym import GymSchema
from app.core.tenant import get_current_gym, _verify_user_role_in_gym
from app.models.user_gym import GymRoleType


async def verify_gym_access_cached(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Security(get_current_user_cached, scopes=["resource:read"]),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """
    Dependencia optimizada: Verifica acceso al gimnasio usando caché de usuario.

    Args:
        request: La solicitud HTTP actual
        db: Sesión de base de datos
        current_gym_schema: Esquema del gimnasio actual
        current_user: Usuario autenticado (cacheado)
        redis_client: Cliente Redis

    Returns:
        GymSchema: Esquema del gimnasio verificado
    """
    return await _verify_user_role_in_gym(request, None, db, current_gym_schema, current_user, redis_client)


async def verify_gym_admin_access_cached(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Security(get_current_user_cached, scopes=["resource:admin"]),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """Dependencia optimizada: Verifica rol ADMIN u OWNER en el gimnasio."""
    return await _verify_user_role_in_gym(
        request, {GymRoleType.ADMIN, GymRoleType.OWNER}, db, current_gym_schema, current_user, redis_client
    )


async def verify_gym_trainer_access_cached(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
    current_gym_schema: Optional[GymSchema] = Depends(get_current_gym),
    current_user: Auth0User = Security(get_current_user_cached, scopes=["resource:write"]),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> GymSchema:
    """Dependencia optimizada: Verifica rol TRAINER, ADMIN u OWNER en el gimnasio."""
    return await _verify_user_role_in_gym(
        request, {GymRoleType.TRAINER, GymRoleType.ADMIN, GymRoleType.OWNER}, db, current_gym_schema, current_user, redis_client
    ) 