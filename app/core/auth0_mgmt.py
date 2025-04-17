from fastapi import HTTPException, Depends, status
import requests
import os
import json
import time
from typing import Dict, Any, Optional
from app.core.config import get_settings
from redis.asyncio import Redis
from app.db.redis_client import get_redis_client
import logging

logger_rl = logging.getLogger("rate_limiter")

class RateLimiter:
    """
    Clase para limitar la tasa de operaciones por clave (usuario o IP)
    usando Redis para almacenamiento centralizado.
    """
    # Mapa de operaciones con su configuración de límites (TTL en segundos)
    RATE_LIMITS = {
        "change_email": {"max_attempts": 3, "ttl_seconds": 3600},  # 3 intentos por hora
        "verify_email": {"max_attempts": 5, "ttl_seconds": 3600},  # 5 intentos por hora
        "reset_password": {"max_attempts": 3, "ttl_seconds": 3600},  # 3 intentos por hora
        "check_email": {"max_attempts": 10, "ttl_seconds": 600},  # 10 intentos por 10 minutos
    }

    # No necesitamos __init__ si no hay estado en memoria
    # def __init__(self):
    #     pass 

    async def _get_redis_key(self, operation: str, key_identifier: str) -> str:
        """Genera la clave única para Redis."""
        return f"rate_limit:{operation}:{key_identifier}"

    async def can_perform_operation(
        self,
        operation: str,
        key_identifier: str,
        redis_client: Redis
    ) -> bool:
        """
        Verifica si una operación puede ser realizada por una clave específica usando Redis.
        
        Args:
            operation: Tipo de operación (debe estar en RATE_LIMITS)
            key_identifier: Identificador único para la clave (ej. user_id, IP)
            redis_client: Cliente Redis asíncrono.
            
        Returns:
            bool: True si la operación está permitida, False si excede el límite.
        """
        if not redis_client:
            logger_rl.error("Cliente Redis no disponible para rate limiting.")
            return False # O True si prefieres fallar abierto en caso de no haber Redis
            
        if operation not in self.RATE_LIMITS:
            logger_rl.warning(f"Operación '{operation}' no encontrada en RATE_LIMITS. Permitida por defecto.")
            return True
        
        limit_config = self.RATE_LIMITS[operation]
        max_attempts = limit_config["max_attempts"]
        ttl = limit_config["ttl_seconds"]
        
        redis_key = await self._get_redis_key(operation, key_identifier)
        
        try:
            # Usar pipeline para eficiencia (ejecutar múltiples comandos atómicamente)
            async with redis_client.pipeline(transaction=True) as pipe:
                # Incrementar el contador. Si no existe, se crea con 1.
                pipe.incr(redis_key)
                # Establecer el tiempo de expiración (TTL) la primera vez o refrescarlo.
                # ttl() devuelve -1 si existe sin TTL, -2 si no existe.
                pipe.ttl(redis_key)
                results = await pipe.execute()
            
            current_count = results[0]
            key_ttl = results[1]
            
            # Si la clave es nueva (TTL era -2 o -1), establecer la expiración
            if key_ttl == -2 or key_ttl == -1:
                await redis_client.expire(redis_key, ttl)
                logger_rl.debug(f"Set TTL for {redis_key} to {ttl}s")
                
            # Verificar si se excede el límite
            if current_count > max_attempts:
                logger_rl.warning(f"Rate limit excedido para '{operation}' en clave '{key_identifier}'. Count: {current_count}/{max_attempts}")
                return False
            else:
                logger_rl.debug(f"Rate limit OK para '{operation}' en clave '{key_identifier}'. Count: {current_count}/{max_attempts}")
                return True
                
        except Exception as e:
            logger_rl.error(f"Error de Redis en rate limiting para {redis_key}: {e}", exc_info=True)
            # En caso de error de Redis, ¿permitir o bloquear? Por seguridad, bloqueamos.
            return False

    # El método can_check_email ya no es necesario, se llama directo a can_perform_operation
    # async def can_check_email(self, ip_address: str, redis_client: redis.Redis = Depends(get_redis_client)) -> bool:
    #     return await self.can_perform_operation("check_email", key_identifier=ip_address, redis_client=redis_client)


class Auth0ManagementService:
    """
    Servicio para interactuar con la API de Management de Auth0.
    Proporciona métodos para gestionar usuarios, actualizar emails, etc.
    """
    
    def __init__(self):
        settings = get_settings()
        self.domain = settings.AUTH0_DOMAIN
        self.client_id = settings.AUTH0_MGMT_CLIENT_ID
        self.client_secret = settings.AUTH0_MGMT_CLIENT_SECRET
        self.audience = settings.AUTH0_MGMT_AUDIENCE
        self.token = None
        self.token_expires_at = 0
        # Ya no inicializamos los limiters aquí, se usarán directamente
        # self.email_change_limiter = RateLimiter()
        # self.verification_limiter = RateLimiter()
        pass # O mantener los limiters si se usan en más sitios
    
    def get_auth_token(self) -> str:
        """
        Obtiene un token de acceso para la API de Management de Auth0.
        El token se almacena en caché y se renueva automáticamente cuando expira.
        
        Returns:
            str: Token de acceso para la API de Management
        """
        # Verificar si el token actual es válido
        current_time = time.time()
        if self.token and current_time < self.token_expires_at - 60:  # 60 segundos de margen
            return self.token
        
        # Obtener un nuevo token
        import logging
        logger = logging.getLogger("auth0_service")
        logger.info("Solicitando nuevo token de acceso a Auth0 Management API")
        
        url = f"https://{self.domain}/oauth/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "audience": self.audience,
            "grant_type": "client_credentials"
        }
        headers = {"content-type": "application/json"}
        
        try:
            response = requests.post(url, json=payload, headers=headers)
            # Verificar errores antes de raise_for_status
            if response.status_code != 200:
                logger.error(f"Error al obtener token de Auth0. Status: {response.status_code}")
                logger.error(f"Respuesta: {response.text}")
                response.raise_for_status()
            
            data = response.json()
            self.token = data.get("access_token")
            
            # Guardar cuándo expira el token (convertir expires_in a timestamp absoluto)
            expires_in = data.get("expires_in", 86400)
            self.token_expires_at = current_time + expires_in
            
            # Verificar que se han concedido los permisos necesarios
            if 'scope' in data:
                scopes = data.get('scope', '').split()
                required_scopes = ['read:users', 'update:users']
                missing_scopes = [scope for scope in required_scopes if scope not in scopes]
                
                if missing_scopes:
                    logger.warning(f"El token obtenido no tiene todos los permisos necesarios. Faltan: {', '.join(missing_scopes)}")
                    logger.warning("Esto puede causar errores en algunas operaciones. Verifique la configuración en Auth0.")
                else:
                    logger.info("Token obtenido con todos los permisos necesarios")
            
            logger.info(f"Token obtenido correctamente. Expira en {expires_in} segundos")
            return self.token
            
        except requests.RequestException as e:
            logger.error(f"Error al obtener token de Auth0: {str(e)}")
            
            # Información de depuración detallada
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Código de estado: {e.response.status_code}")
                try:
                    error_json = e.response.json()
                    logger.error(f"Detalle del error: {error_json}")
                except:
                    logger.error(f"Texto de respuesta: {e.response.text}")
            
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Error al conectar con Auth0: {str(e)}"
            )
    
    async def update_user_email(self, auth0_id: str, new_email: str, verify_email: bool = False, *, redis_client: Redis) -> Dict[str, Any]:
        """ Actualiza email, AHORA usa RateLimiter con Redis explícito """
        limiter = RateLimiter()
        if not await limiter.can_perform_operation("change_email", key_identifier=auth0_id, redis_client=redis_client):
            # ... (cálculo de tiempo restante puede ser más complejo con Redis)
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Has excedido el límite de cambios de email.")
        
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"
        payload = {"email": new_email, "email_verified": False, "verify_email": verify_email}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            response = requests.patch(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            # ... (manejo de errores existente) ...
            raise HTTPException(status_code=500, detail=e.response.text)
    
    async def check_email_availability(self, email: str, calling_user_id: Optional[str] = None, *, redis_client: Redis) -> bool:
        """
        Verifica si un email está disponible para ser utilizado en Auth0.
        Aplica rate limiting por usuario.
        
        Args:
            email: Email a verificar.
            calling_user_id: Auth0 ID del usuario que realiza la solicitud (para rate limit).
            redis_client: Cliente Redis asíncrono.
            
        Returns:
            bool: True si el email está disponible, False si ya está en uso o si ocurre un error.
        """
        # Aplicar Rate Limiting antes de hacer la llamada externa
        if calling_user_id: 
            limiter = RateLimiter()
            can_proceed = await limiter.can_perform_operation(
                operation="check_email",
                key_identifier=calling_user_id, 
                redis_client=redis_client
            )
            if not can_proceed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Límite de solicitudes excedido para verificar emails."
                )
                    
        # Si el rate limit pasa, proceder con la verificación en Auth0
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users"
        
        # Formato actualizado según documentación de Auth0 para búsqueda exacta
        # Usar sintaxis de Lucene con escape de caracteres especiales
        email_escaped = email.replace('"', '\\"').replace('\\', '\\\\')
        params = {
            "q": f'email:"{email_escaped}"',
            "search_engine": "v3"
        }
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.info(f"Verificando disponibilidad de email: {email}")
            
            response = requests.get(url, headers=headers, params=params)
            
            # Verificar errores específicos de Auth0 antes de raise_for_status
            if response.status_code != 200:
                logger.error(f"Error HTTP {response.status_code} al verificar email: {email}")
                logger.error(f"Respuesta: {response.text}")
                
                # Verificar si es un error de permisos
                if response.status_code == 403:
                    logger.error("Error de permisos en Auth0. Verifique que el token tenga el permiso 'read:users'")
                    return False
                elif response.status_code == 401:
                    logger.error("Error de autenticación en Auth0. Token inválido o expirado.")
                    return False
                    
            # Ahora procedemos con raise_for_status para otros errores
            response.raise_for_status()
            
            users = response.json()
            is_available = len(users) == 0
            logger.info(f"Verificación de disponibilidad para {email}: {is_available}")
            return is_available
            
        except requests.RequestException as e:
            logger.error(f"Error al verificar disponibilidad de email {email} en Auth0: {str(e)}")
            
            # Información de depuración detallada
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Código de estado: {e.response.status_code}")
                try:
                    error_json = e.response.json()
                    logger.error(f"Detalle del error: {error_json}")
                except:
                    logger.error(f"Texto de respuesta: {e.response.text}")
            
            return False  # Falla cerrado
        except Exception as e:
            logger.error(f"Error inesperado procesando respuesta de Auth0 para {email}: {str(e)}", exc_info=True)
            return False  # Falla cerrado

    async def send_verification_email(self, user_id: str, *, redis_client: Redis) -> bool:
        """ Envía verificación, AHORA usa RateLimiter con Redis explícito """
        limiter = RateLimiter()
        if not await limiter.can_perform_operation("verify_email", key_identifier=user_id, redis_client=redis_client):
             raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Has excedido el límite de envíos de verificación.")

        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/jobs/verification-email"
        payload = {"user_id": user_id}
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            # ... (manejo de errores existente) ...
            raise HTTPException(status_code=500, detail=e.response.text)

    def delete_user(self, auth0_id: str) -> bool:
        """
        Elimina un usuario de Auth0 usando la Management API.

        Args:
            auth0_id: ID de Auth0 del usuario a eliminar (sub).

        Returns:
            bool: True si la eliminación fue exitosa (o el usuario ya no existía).

        Raises:
            HTTPException: Si ocurre un error inesperado o de permisos en Auth0.
        """
        token = self.get_auth_token()
        url = f"https://{self.domain}/api/v2/users/{auth0_id}"
        headers = {"Authorization": f"Bearer {token}"}

        try:
            import logging
            logger = logging.getLogger("auth0_service")
            logger.info(f"Intentando eliminar usuario de Auth0: {auth0_id}")
            response = requests.delete(url, headers=headers)
            
            if response.status_code == 204:
                logger.info(f"Usuario {auth0_id} eliminado exitosamente de Auth0.")
                return True
            elif response.status_code == 404:
                logger.warning(f"Usuario {auth0_id} no encontrado en Auth0 al intentar eliminar (status 404). Tratando como éxito.")
                return True
            else:
                response.raise_for_status() # Lanza para otros errores
                # Si raise_for_status no lanza (poco probable), considerar esto un fallo
                logger.error(f"raise_for_status no lanzó excepción para código {response.status_code} al eliminar {auth0_id}")
                return False 

        except requests.RequestException as e:
            error_detail = f"Error al eliminar usuario {auth0_id} de Auth0: {str(e)}"
            status_code = 503 

            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                if status_code == 404:
                    logger.warning(f"Usuario {auth0_id} no encontrado en Auth0 al intentar eliminar (error capturado). Tratando como éxito.")
                    return True
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', e.response.text)
                    error_detail = f"{error_detail} - {error_message}"
                except:
                    error_detail = f"{error_detail} - {e.response.text}"
            
            logger.error(error_detail)
            raise HTTPException(
                status_code=status_code, 
                detail=error_detail
            )
        except Exception as e:
            logger.error(f"Error inesperado en delete_user para {auth0_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Error interno inesperado al intentar eliminar usuario de Auth0."
            )

    # _get_reset_time ya no es relevante para Redis
    # def _get_reset_time(self, ...) -> int: ...


# Instancia global del servicio
auth0_mgmt_service = Auth0ManagementService() 