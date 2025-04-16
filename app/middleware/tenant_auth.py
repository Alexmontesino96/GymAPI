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
from app.core.auth0_fastapi import get_current_user


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
        
        # Inicializar state para esta request (más limpio)
        request.state.gym = None
        request.state.user = None
        request.state.role_in_gym = None
        
        # 1. Verificar si la ruta requiere comprobación de gimnasio
        requires_gym = not any(path.startswith(exempt) for exempt in GYM_EXEMPT_PATHS)
        
        # 2. Obtener ID de gimnasio del header si es necesario
        gym_id: Optional[int] = None
        if requires_gym:
            try:
                gym_id_header = request.headers.get("X-Gym-ID")
                if gym_id_header:
                    gym_id = int(gym_id_header)
                else:
                    # Gimnasio requerido pero no proporcionado
                    logger.warning(f"Acceso a {path} denegado: Falta X-Gym-ID")
                    return Response(
                        content=json.dumps({"detail": "Se requiere el header X-Gym-ID"}),
                        status_code=status.HTTP_400_BAD_REQUEST, 
                        media_type="application/json"
                    )
            except (ValueError, TypeError):
                logger.warning(f"Acceso a {path} denegado: X-Gym-ID inválido - {request.headers.get('X-Gym-ID')}")
                return Response(
                    content=json.dumps({"detail": f"Formato inválido para X-Gym-ID: {request.headers.get('X-Gym-ID')}"}),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    media_type="application/json"
                )
        
        # 3. Verificar si la ruta requiere autenticación
        requires_auth = not any(path.startswith(exempt) for exempt in AUTH_EXEMPT_PATHS)
        
        # 4. Si se requiere autenticación, obtener usuario y rol (si aplica gym)
        if requires_auth:
            auth0_id = None
            try:
                # Obtener payload del token (sin validación de scopes aquí, solo existencia)
                token_payload = await get_current_user(request)
                auth0_id = token_payload.get("sub") if token_payload else None
                if not auth0_id:
                     raise HTTPException(status.HTTP_401_UNAUTHORIZED, "No se pudo obtener el ID de usuario del token")
            except HTTPException as auth_exc:
                 # Si get_current_user falla (token inválido, expirado, etc.)
                 logger.warning(f"Autenticación fallida para {path}: {auth_exc.detail}")
                 # Devolver la respuesta de error de la excepción original
                 return Response(
                    content=json.dumps({"detail": auth_exc.detail}),
                    status_code=auth_exc.status_code,
                    headers=auth_exc.headers or {},
                    media_type="application/json"
                 )
                 
            # Si tenemos auth0_id y se requiere gimnasio, obtener datos combinados
            if auth0_id and requires_gym and gym_id is not None:
                # Necesitamos DB y Redis para obtener/guardar datos combinados
                # Obtenerlos aquí en lugar de depender de llamadas posteriores
                db = next(get_db()) # Obtener sesión de DB síncrona
                redis_client = await get_redis_client() # Obtener cliente Redis
                
                if not redis_client:
                    logger.error("Redis no disponible en middleware, no se pueden verificar/cachear datos de acceso")
                    # Fallback a no hacer nada o error 503? Por seguridad, mejor fallar
                    return Response(
                        content=json.dumps({"detail": "Servicio de caché no disponible"}),
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        media_type="application/json"
                    )
                    
                # Intentar obtener datos combinados
                combined_data = await self.get_combined_auth_data(auth0_id, gym_id, db, redis_client)
                
                if combined_data and combined_data.get("access", True): # Verificar acceso (puede ser negativo) 
                    # Poblar request.state para uso posterior
                    request.state.user = UserSchema(**combined_data.get("user", {}))
                    request.state.gym = GymSchema(**combined_data.get("gym", {}))
                    request.state.role_in_gym = combined_data.get("role_in_gym")
                    logger.debug(f"Datos combinados cargados en state para user {auth0_id}, gym {gym_id}")
                else:
                    # Si no hay datos combinados o acceso es False (cache negativo)
                    logger.warning(f"Acceso denegado para user {auth0_id} a gym {gym_id} (middleware)")
                    return Response(
                        content=json.dumps({"detail": f"Acceso denegado al gimnasio"}),
                        status_code=status.HTTP_403_FORBIDDEN,
                        media_type="application/json"
                    )
            elif auth0_id: # Se requiere auth pero no gym, obtener solo usuario
                 db = next(get_db())
                 redis_client = await get_redis_client()
                 user = await user_service.get_user_by_auth0_id_cached(db, auth0_id, redis_client)
                 if user:
                     request.state.user = user
                 else:
                     logger.warning(f"Usuario autenticado {auth0_id} no encontrado en DB local")
                     # Permitir continuar o devolver error? Depende del caso de uso.
                     # Por ahora, permitimos continuar pero sin usuario en state.
                     pass
                     
        # 5. Ejecutar el resto de la request
        try:
            response = await call_next(request)
        finally:
            # Limpiar el estado de la request al finalizar (buena práctica)
            if hasattr(request, 'state'):
                del request.state
            # Cerrar sesión de DB si se abrió aquí (si db fue obtenido)
            # Nota: Esto puede ser complejo si la sesión se usa más adelante.
            # Considerar usar dependencias en endpoints para manejar sesiones. 
            pass

        # 6. Medir tiempo total de procesamiento
        process_time = (time.time() - start_time) * 1000
        logger.debug(f"TenantAuthMiddleware: {request.method} {path} procesado en {process_time:.2f}ms")
        
        # 7. Devolver la respuesta
        return response
    
    async def get_combined_auth_data(self, auth0_id: str, gym_id: int, db: Session, redis_client: redis.Redis) -> Optional[Dict[str, Any]]:
        """
        Obtiene o crea los datos combinados de autenticación y acceso al gimnasio.
        """
        combined_key = f"tenant_auth:{auth0_id}:{gym_id}"
        settings = get_settings() # Obtener settings para TTLs
        
        try:
            @time_redis_operation
            async def _redis_get(key):
                return await redis_client.get(key)
            
            cached_data = await _redis_get(combined_key)
            
            if cached_data:
                register_cache_hit(combined_key)
                loaded_data = json.loads(cached_data)
                # Devolver directamente si es entrada negativa
                if not loaded_data.get("access", True):
                    return {"access": False} 
                return loaded_data
            
            register_cache_miss(combined_key)
            
            user = await user_service.get_user_by_auth0_id_cached(db, auth0_id, redis_client)
            if not user:
                await self.store_negative_auth_data(auth0_id, gym_id, redis_client) # Cache negativo si user no existe
                return {"access": False}
                
            @time_db_query
            def _get_gym(): return db.query(Gym).filter(Gym.id == gym_id).first()
            gym_db = _get_gym()
            if not gym_db:
                await self.store_negative_auth_data(auth0_id, gym_id, redis_client) # Cache negativo si gym no existe
                return {"access": False}
            gym = GymSchema.model_validate(gym_db)
            
            @time_db_query
            def _check_membership(): return db.query(UserGym).filter(UserGym.user_id == user.id, UserGym.gym_id == gym_id).first()
            membership = _check_membership()
            if not membership:
                await self.store_negative_auth_data(auth0_id, gym_id, redis_client)
                return {"access": False}
                
            auth_data = {
                "user_id": user.id,
                "user": user.model_dump(),
                "gym_id": gym_id,
                "gym": gym.model_dump(),
                "role_in_gym": membership.role.value,
                "timestamp": time.time(),
                "access": True # Indicar acceso positivo
            }
            
            await self.store_auth_data(auth_data, redis_client)
            return auth_data
            
        except Exception as e:
            logger.error(f"Error en get_combined_auth_data: {e}", exc_info=True)
            # En caso de error, no sabemos si tiene acceso, así que devolvemos None
            return None

    async def store_auth_data(self, auth_data: Dict[str, Any], redis_client: redis.Redis) -> None:
        """
        Almacena los datos combinados de autenticación en caché.
        """
        try:
            settings = get_settings()
            auth0_id = auth_data["user"]["auth0_id"]
            gym_id = auth_data["gym_id"]
            combined_key = f"tenant_auth:{auth0_id}:{gym_id}"
            
            @time_redis_operation
            async def _redis_set(key, value, ex):
                await redis_client.set(key, value, ex=ex)
                
            await _redis_set(
                combined_key,
                json.dumps(auth_data), 
                ex=settings.CACHE_TTL_USER_MEMBERSHIP
            )
            logger.debug(f"Datos de autenticación guardados en caché: {combined_key}")
        except Exception as e:
            logger.error(f"Error guardando datos de autenticación en caché: {e}", exc_info=True)
    
    async def store_negative_auth_data(self, auth0_id: str, gym_id: int, redis_client: redis.Redis) -> None:
        """
        Almacena una entrada negativa en caché para evitar consultas repetidas para usuarios sin acceso.
        """
        try:
            settings = get_settings()
            combined_key = f"tenant_auth:{auth0_id}:{gym_id}"
            negative_data = {"access": False, "timestamp": time.time()}
            
            @time_redis_operation
            async def _redis_set(key, value, ex):
                await redis_client.set(key, value, ex=ex)
                
            await _redis_set(
                combined_key,
                json.dumps(negative_data),
                ex=settings.CACHE_TTL_NEGATIVE
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