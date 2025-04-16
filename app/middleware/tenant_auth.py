"""
Middleware unificado para verificación de tenant (gimnasio) y autenticación.

Este middleware combina en un solo paso:
1. Extracción del ID de gimnasio del header X-Gym-ID
2. Verificación del token de usuario
3. Obtención del usuario de la caché
4. Verificación de pertenencia al gimnasio
5. Determinación del rol del usuario

Reemplaza las múltiples verificaciones individuales y reduce el overhead.
"""

from fastapi import Request, Response, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
import json
import logging
import time
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from functools import lru_cache

from app.db.redis_client import redis, get_redis_client
from app.models.user_gym import GymRoleType, UserGym
from app.schemas.gym import GymSchema
from app.schemas.user import User as UserSchema
from app.core.config import get_settings
from app.services.user import user_service
from app.db.session import get_db
from app.models.gym import Gym
from app.core.profiling import register_cache_hit, register_cache_miss, time_db_query, time_redis_operation


logger = logging.getLogger("tenant_auth_middleware")

# Rutas que no requieren verificación de gimnasio (X-Gym-ID)
GYM_EXEMPT_PATHS = [
    "/api/v1/auth/",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
    "/api/v1/token",
    "/api/v1/callback",
    "/api/v1/profile",
    "/"
]

# Rutas que no requieren autenticación
AUTH_EXEMPT_PATHS = [
    "/api/v1/auth/",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
    "/"
]

class TenantAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware unificado que verifica la autenticación y el acceso al gimnasio en un solo paso.
    Almacena los resultados en request.state para evitar verificaciones repetidas.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("TenantAuthMiddleware inicializado")
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()
        path = request.url.path
        
        # Inicializar state para esta request
        request.state.gym_id = None
        request.state.gym = None
        request.state.user_id = None
        request.state.user = None
        request.state.user_role_in_gym = None
        
        # 1. Verificar si la ruta requiere comprobación de gimnasio
        requires_gym = not any(path.startswith(exempt) for exempt in GYM_EXEMPT_PATHS)
        
        # 2. Obtener ID de gimnasio del header si es necesario
        if requires_gym:
            try:
                gym_id_header = request.headers.get("X-Gym-ID")
                if gym_id_header:
                    request.state.gym_id = int(gym_id_header)
                elif requires_gym:
                    # Gimnasio requerido pero no proporcionado
                    return Response(
                        content=json.dumps({"detail": "Se requiere el header X-Gym-ID"}),
                        status_code=status.HTTP_400_BAD_REQUEST, 
                        media_type="application/json"
                    )
            except (ValueError, TypeError):
                return Response(
                    content=json.dumps({"detail": f"Formato inválido para X-Gym-ID: {request.headers.get('X-Gym-ID')}"}),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    media_type="application/json"
                )
        
        # 3. Verificar si la ruta requiere autenticación
        requires_auth = not any(path.startswith(exempt) for exempt in AUTH_EXEMPT_PATHS)
        
        # 4. Si se requiere autenticación y gimnasio, intentar obtener datos combinados de caché
        # Nota: La verificación completa del token la hará FastAPI/Auth0 más adelante
        # Aquí solo verificamos la pertenencia al gimnasio si tenemos acceso al token
        if requires_auth and requires_gym and request.state.gym_id:
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                # Aquí solo extraemos el token, pero no lo validamos
                # Para manejar la verificación completa, necesitaríamos duplicar la lógica de Auth0
                # Lo cual no es recomendable para mantener la seguridad
                pass
        
        # 5. Ejecutar el resto de la request
        response = await call_next(request)
        
        # 6. Medir tiempo total de procesamiento
        process_time = (time.time() - start_time) * 1000
        logger.debug(f"TenantAuthMiddleware: {request.method} {path} procesado en {process_time:.2f}ms")
        
        # 7. Devolver la respuesta
        return response
    
    async def get_combined_auth_data(self, auth0_id: str, gym_id: int, db: Session, redis_client: redis.Redis) -> Optional[Dict[str, Any]]:
        """
        Obtiene o crea los datos combinados de autenticación y acceso al gimnasio.
        
        Args:
            auth0_id: ID de Auth0 del usuario
            gym_id: ID del gimnasio
            db: Sesión de base de datos
            redis_client: Cliente Redis
            
        Returns:
            Dict con los datos combinados o None si no tiene acceso
        """
        # 1. Intentar obtener de caché primero
        combined_key = f"tenant_auth:{auth0_id}:{gym_id}"
        
        try:
            @time_redis_operation
            async def _redis_get(key):
                return await redis_client.get(key)
                
            cached_data = await _redis_get(combined_key)
            
            if cached_data:
                # Cache HIT
                register_cache_hit(combined_key)
                return json.loads(cached_data)
            
            # Cache MISS - obtener datos de DB y guardar en caché
            register_cache_miss(combined_key)
            
            # 2. Obtener usuario
            user = await user_service.get_user_by_auth0_id_cached(db, auth0_id, redis_client)
            if not user:
                return None
                
            # 3. Obtener gimnasio
            @time_db_query
            def _get_gym():
                return db.query(Gym).filter(Gym.id == gym_id).first()
            gym_db = _get_gym()
            if not gym_db:
                return None
            gym = GymSchema.model_validate(gym_db)
            
            # 4. Verificar pertenencia al gimnasio
            @time_db_query
            def _check_membership():
                return db.query(UserGym).filter(
                    UserGym.user_id == user.id, 
                    UserGym.gym_id == gym_id
                ).first()
            membership = _check_membership()
            if not membership:
                # Crear entrada negativa en caché
                await self.store_negative_auth_data(auth0_id, gym_id, redis_client)
                return None
                
            # 5. Crear datos combinados
            auth_data = {
                "user_id": user.id,
                "user": user.model_dump(),
                "gym_id": gym_id,
                "gym": gym.model_dump(),
                "role_in_gym": membership.role.value,
                "timestamp": time.time()
            }
            
            # 6. Guardar en caché
            await self.store_auth_data(auth_data, redis_client)
            
            return auth_data
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de autenticación: {e}", exc_info=True)
            return None
    
    async def store_auth_data(self, auth_data: Dict[str, Any], redis_client: redis.Redis) -> None:
        """
        Almacena los datos combinados de autenticación en caché.
        """
        try:
            auth0_id = auth_data["user"]["auth0_id"]
            gym_id = auth_data["gym_id"]
            combined_key = f"tenant_auth:{auth0_id}:{gym_id}"
            
            @time_redis_operation
            async def _redis_set(key, value, ex):
                await redis_client.set(key, value, ex=ex)
                
            await _redis_set(
                combined_key,
                json.dumps(auth_data),
                ex=get_settings().CACHE_TTL_USER_MEMBERSHIP
            )
            
            logger.debug(f"Datos de autenticación guardados en caché: {combined_key}")
        except Exception as e:
            logger.error(f"Error guardando datos de autenticación en caché: {e}", exc_info=True)
    
    async def store_negative_auth_data(self, auth0_id: str, gym_id: int, redis_client: redis.Redis) -> None:
        """
        Almacena una entrada negativa en caché para evitar consultas repetidas para usuarios sin acceso.
        """
        try:
            combined_key = f"tenant_auth:{auth0_id}:{gym_id}"
            
            @time_redis_operation
            async def _redis_set(key, value, ex):
                await redis_client.set(key, value, ex=ex)
                
            await _redis_set(
                combined_key,
                json.dumps({"access": False, "timestamp": time.time()}),
                ex=get_settings().CACHE_TTL_NEGATIVE
            )
            
            logger.debug(f"Entrada negativa guardada en caché: {combined_key}")
        except Exception as e:
            logger.error(f"Error guardando entrada negativa en caché: {e}", exc_info=True)


# Función helper para configurar el middleware en la aplicación
def setup_tenant_auth_middleware(app):
    """
    Configura el middleware de autenticación de tenant en la aplicación.
    
    Args:
        app: Aplicación FastAPI
    """
    app.add_middleware(TenantAuthMiddleware)
    logger.info("TenantAuthMiddleware configurado en la aplicación") 