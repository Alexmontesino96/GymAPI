"""
Rate Limiting Middleware para GymAPI

Protege contra ataques DDoS y abuso mediante limitación de velocidad
usando slowapi (basado en Flask-Limiter).
"""

import logging
from typing import Callable
from fastapi import Request, Response, HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
import redis
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Configurar backend de Redis para rate limiting
def get_redis_client():
    """Obtener cliente Redis para rate limiting"""
    try:
        if settings.REDIS_URL:
            return redis.from_url(settings.REDIS_URL)
        else:
            return redis.Redis(
                host=settings.REDIS_HOST or "localhost",
                port=settings.REDIS_PORT or 6379,
                db=settings.REDIS_DB or 0,
                password=settings.REDIS_PASSWORD or None,
                decode_responses=True
            )
    except Exception as e:
        logger.warning(f"No se pudo conectar a Redis para rate limiting: {e}")
        return None

# Crear limiter con backend Redis si está disponible
redis_client = get_redis_client()
if redis_client:
    from slowapi.util import get_remote_address
    limiter = Limiter(
        key_func=get_remote_address,
        storage_uri=settings.REDIS_URL or f"redis://{settings.REDIS_HOST or 'localhost'}:{settings.REDIS_PORT or 6379}",
        default_limits=["1000 per day", "100 per hour"]
    )
    logger.info("✅ Rate limiting configurado con backend Redis")
else:
    # Fallback a memoria local (solo para desarrollo)
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["1000 per day", "100 per hour"]
    )
    logger.warning("⚠️ Rate limiting usando memoria local (solo desarrollo)")

# Configurar límites específicos por tipo de endpoint
RATE_LIMITS = {
    # Endpoints críticos de autenticación
    "auth": "10 per minute",
    "login": "5 per minute",
    "register": "3 per minute",
    "password_reset": "2 per minute",

    # Endpoints de billing (críticos)
    "billing_create": "5 per minute",
    "billing_webhook": "100 per minute",  # Webhooks de Stripe pueden ser frecuentes
    "stripe_checkout": "10 per minute",

    # Endpoints de API general
    "api_read": "200 per minute",
    "api_write": "50 per minute",

    # Endpoints de chat
    "chat_send": "30 per minute",
    "chat_read": "100 per minute",

    # Endpoints de uploads
    "file_upload": "10 per minute",

    # Endpoints de notificaciones de nutrición
    "nutrition_notification_test": "5 per hour",
    "nutrition_notification_settings": "10 per hour",
    "nutrition_notification_read": "60 per minute",

    # Endpoints públicos
    "public": "500 per hour"
}

def get_rate_limit_for_endpoint(request: Request) -> str:
    """Determinar el límite de velocidad basado en el endpoint"""
    path = request.url.path.lower()

    # Endpoints críticos de autenticación
    if any(x in path for x in ["/auth/login", "/auth/token"]):
        return RATE_LIMITS["login"]
    elif any(x in path for x in ["/auth/register", "/auth/signup"]):
        return RATE_LIMITS["register"]
    elif any(x in path for x in ["/auth/password", "/auth/reset"]):
        return RATE_LIMITS["password_reset"]
    elif "/auth/" in path:
        return RATE_LIMITS["auth"]

    # Endpoints de billing
    elif any(x in path for x in ["/memberships/create", "/memberships/subscribe"]):
        return RATE_LIMITS["billing_create"]
    elif "/webhooks/" in path:
        return RATE_LIMITS["billing_webhook"]
    elif any(x in path for x in ["/checkout", "/payment"]):
        return RATE_LIMITS["stripe_checkout"]

    # Endpoints de notificaciones de nutrición (antes de chat para mayor especificidad)
    elif "/nutrition/notifications/test" in path:
        return RATE_LIMITS["nutrition_notification_test"]
    elif "/nutrition/notifications/settings" in path and request.method in ["PUT", "POST"]:
        return RATE_LIMITS["nutrition_notification_settings"]
    elif "/nutrition/notifications" in path:
        return RATE_LIMITS["nutrition_notification_read"]

    # Endpoints de chat
    elif "/chat/" in path and request.method == "POST":
        return RATE_LIMITS["chat_send"]
    elif "/chat/" in path:
        return RATE_LIMITS["chat_read"]

    # Endpoints de uploads
    elif any(x in path for x in ["/upload", "/file"]):
        return RATE_LIMITS["file_upload"]

    # Endpoints de API por método
    elif request.method in ["POST", "PUT", "DELETE", "PATCH"]:
        return RATE_LIMITS["api_write"]
    elif request.method == "GET":
        return RATE_LIMITS["api_read"]

    # Default para endpoints públicos
    else:
        return RATE_LIMITS["public"]

def get_client_identifier(request: Request) -> str:
    """Obtener identificador único del cliente para rate limiting de forma segura.

    - Por defecto usa la IP del socket (ASGI client).
    - Si TRUST_PROXY_HEADERS=True, usa el primer IP de X-Forwarded-For (cliente original) cuando existe.
    """
    settings = get_settings()
    try:
        if settings.TRUST_PROXY_HEADERS:
            # X-Forwarded-For: client, proxy1, proxy2 ... -> tomar el primero
            fwd = request.headers.get("X-Forwarded-For") or request.headers.get("x-forwarded-for")
            if fwd:
                return fwd.split(",")[0].strip()
            real_ip = request.headers.get("X-Real-IP") or request.headers.get("x-real-ip")
            if real_ip:
                return real_ip
        # Fallback seguro: IP del cliente según ASGI/uvicorn
        if request.client and request.client.host:
            return request.client.host
    except Exception:
        pass
    return get_remote_address(request)

# Configurar función de identificación personalizada
limiter.key_func = get_client_identifier

def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Handler personalizado para rate limit exceeded"""
    logger.warning(
        f"Rate limit exceeded para {get_client_identifier(request)} "
        f"en {request.url.path} - Límite: {exc.detail}"
    )
    
    response = HTTPException(
        status_code=429,
        detail={
            "error": "Rate limit exceeded",
            "message": "Demasiadas solicitudes. Intenta nuevamente más tarde.",
            "limit": exc.detail,
            "retry_after": getattr(exc, 'retry_after', 60)
        }
    )
    return response

# Middleware personalizado para logging y monitoreo
class RateLimitMiddleware:
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            request = Request(scope, receive)
            
            # Log de solicitudes para monitoreo
            client_ip = get_client_identifier(request)
            logger.debug(f"Request from {client_ip} to {request.url.path}")
            
            # Verificar si es un endpoint sensible
            if any(x in request.url.path.lower() for x in ["/auth/", "/billing/", "/webhooks/"]):
                logger.info(f"Sensitive endpoint access: {client_ip} -> {request.url.path}")
        
        await self.app(scope, receive, send)

# Función para aplicar rate limiting dinámico
def apply_rate_limit(request: Request):
    """Aplicar rate limiting dinámico basado en el endpoint"""
    rate_limit = get_rate_limit_for_endpoint(request)
    
    # Aplicar el límite usando slowapi
    try:
        limiter.check_request_limit(request, rate_limit)
    except RateLimitExceeded as e:
        raise custom_rate_limit_exceeded_handler(request, e)

# Exportar limiter para uso en decoradores
__all__ = ["limiter", "RateLimitMiddleware", "apply_rate_limit", "RATE_LIMITS"] 
