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
from datetime import datetime
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
from fastapi import Security


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
    "/api/v1/webhooks/",  # Webhooks externos (Stripe, Stream, etc.)
    "/"
]

# Rutas que no requieren autenticación
AUTH_EXEMPT_PATHS = [
    "/api/v1/auth/",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
    "/api/v1/webhooks/",  # Webhooks externos verifican autenticidad mediante firmas
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
        
        # 3. Autenticación: verificar token y obtener usuario
        auth0_id = None
        user = None
        
        if not any(path.startswith(exempt) for exempt in AUTH_EXEMPT_PATHS):
            try:
                # Usar la función de autenticación existente
                user = await get_current_user(
                    db=db,
                    user=Security(auth.get_user, scopes=[]),
                    redis_client=redis_client
                )
                
                # 🔍 LOGGING ESPECÍFICO PARA TOKENS EN TENANT MIDDLEWARE
                auth_header = request.headers.get("authorization", "")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]
                    logger.info(f"🏢 TENANT MIDDLEWARE - TOKEN LENGTH: {len(token)} caracteres")
                    logger.info(f"🏢 TOKEN PREVIEW: {token[:20]}***")
                    logger.info(f"🏢 USER ID: {user.id if user else 'None'}")
                    logger.info(f"🏢 GYM ID: {gym_id}")
                
                auth0_id = user.id if user else None
                
            except Exception as e:
                logger.error(f"Error de autenticación en middleware: {str(e)}")
                return Response(
                    content=json.dumps({"detail": "Token de autenticación inválido"}),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json"
                )
                 
            # Si tenemos auth0_id y se requiere gimnasio, obtener datos combinados
            if auth0_id:
                # Obtener el usuario desde caché/DB (solo una vez)
                db = next(get_db())
                redis_client = await get_redis_client()
                user = None
                
                if not redis_client:
                    logger.error("Redis no disponible en middleware, no se pueden verificar/cachear datos de acceso")
                    return Response(
                        content=json.dumps({"detail": "Servicio de caché no disponible"}),
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        media_type="application/json"
                    )
                
                # Precargamos el usuario en todos los casos para evitar llamadas duplicadas
                user = await user_service.get_user_by_auth0_id_cached(db, auth0_id, redis_client)
                
                if requires_gym and gym_id is not None:
                    # Necesitamos verificar acceso al gimnasio
                    # Intentar obtener datos combinados, pasando el usuario ya cacheado
                    combined_data = await self.get_combined_auth_data(auth0_id, gym_id, db, redis_client, user_cached=user)
                    
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
                else:
                    # Solo se necesita el usuario (sin gimnasio)
                    if user:
                        request.state.user = user
                    else:
                        logger.warning(f"Usuario autenticado {auth0_id} no encontrado en DB local")
                        # Permitir continuar o devolver error? Depende del caso de uso.
                        # Por ahora, permitimos continuar pero sin usuario en state.
                        pass
                
                # Trackear acceso a la app si tenemos usuario y gimnasio
                if request.state.user and request.state.gym:
                    try:
                        await self._track_app_access(
                            db, 
                            request.state.user.id, 
                            request.state.gym.id,
                            redis_client
                        )
                    except Exception as e:
                        # No fallar la request por error de tracking
                        logger.error(f"Error tracking app access: {e}")
                        
        # 5. Ejecutar el resto de la request
        try:
            response = await call_next(request)
        finally:
            # Limpiar el estado de la request al finalizar (buena práctica)
            if hasattr(request, 'state') and hasattr(request.state, 'clear'):
                request.state.clear()
            # Cerrar sesión de DB si se abrió aquí (si db fue obtenido)
            # Nota: Es mejor manejar la sesión con dependencias en endpoints.
            pass

        # 6. Medir tiempo total de procesamiento
        process_time = (time.time() - start_time) * 1000
        logger.debug(f"TenantAuthMiddleware: {request.method} {path} procesado en {process_time:.2f}ms")
        
        # 7. Devolver la respuesta
        return response
    
    async def _track_app_access(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int,
        redis_client: Optional[Any] = None
    ):
        """
        Trackear acceso del usuario a la app (rate limited).
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            redis_client: Cliente de Redis opcional
        """
        try:
            # Rate limiting con Redis - máx 1 registro cada 5 minutos
            cache_key = f"app_access:{gym_id}:{user_id}"
            
            if redis_client:
                try:
                    exists = await redis_client.exists(cache_key)
                    if exists:
                        return  # Ya registrado recientemente
                except Exception as e:
                    logger.debug(f"Redis not available for rate limiting: {e}")
            
            # Actualizar UserGym con tracking de acceso
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == user_id,
                UserGym.gym_id == gym_id
            ).first()
            
            if user_gym:
                now = datetime.utcnow()
                user_gym.last_app_access = now
                user_gym.total_app_opens = (user_gym.total_app_opens or 0) + 1
                
                # Reset mensual si cambió el mes
                if not user_gym.monthly_reset_date or \
                   user_gym.monthly_reset_date.month != now.month or \
                   user_gym.monthly_reset_date.year != now.year:
                    user_gym.monthly_app_opens = 1
                    user_gym.monthly_reset_date = now
                else:
                    user_gym.monthly_app_opens = (user_gym.monthly_app_opens or 0) + 1
                
                db.commit()
                logger.debug(f"App access tracked for user {user_id} in gym {gym_id}")
                
                # Cachear por 5 minutos para evitar spam
                if redis_client:
                    try:
                        await redis_client.setex(cache_key, 300, "1")
                    except Exception as e:
                        logger.debug(f"Could not set Redis cache for rate limiting: {e}")
                        
        except Exception as e:
            logger.error(f"Error tracking app access: {e}")
            # No propagar el error - el tracking no debe afectar la funcionalidad
    
    async def get_combined_auth_data(self, auth0_id: str, gym_id: int, db: Session, redis_client: redis.Redis, user_cached: Optional[UserSchema] = None) -> Optional[Dict[str, Any]]:
        """
        Obtiene o crea los datos combinados de autenticación y acceso al gimnasio.
        
        Args:
            auth0_id: ID de Auth0 del usuario
            gym_id: ID del gimnasio
            db: Sesión de base de datos
            redis_client: Cliente Redis
            user_cached: Usuario ya obtenido de caché/DB (opcional, para evitar operación Redis redundante)
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
            
            # Usar el usuario ya cacheado si se proporciona
            user = user_cached
            if user is None:
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