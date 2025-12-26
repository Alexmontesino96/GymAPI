"""
Middleware simplificado para verificación básica de tenant y autenticación.

Este middleware solo verifica:
1. Que las rutas que requieren X-Gym-ID lo tengan
2. Que las rutas que requieren autenticación tengan un token Bearer

NO hace validación completa del JWT - eso es responsabilidad de cada endpoint.
"""

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
import json
import logging
import time

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
    "/api/v1/webhooks/",
    "/"
]

# Rutas que no requieren autenticación
AUTH_EXEMPT_PATHS = [
    "/api/v1/auth/",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
    "/api/v1/webhooks/",
    "/"
]

class SimpleTenantAuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware simplificado que solo hace verificaciones básicas.
    La validación completa del JWT se hace en cada endpoint.
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        logger.info("SimpleTenantAuthMiddleware inicializado")

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.time()
        path = request.url.path

        # Inicializar state para esta request
        request.state.gym_id = None
        request.state.has_auth = False

        # 1. Verificar si la ruta requiere X-Gym-ID
        requires_gym = not any(path.startswith(exempt) for exempt in GYM_EXEMPT_PATHS)

        if requires_gym:
            try:
                gym_id_header = request.headers.get("X-Gym-ID")
                if gym_id_header:
                    gym_id = int(gym_id_header)
                    request.state.gym_id = gym_id
                    logger.debug(f"X-Gym-ID establecido: {gym_id}")
                else:
                    logger.warning(f"Acceso a {path} denegado: Falta X-Gym-ID")
                    return Response(
                        content=json.dumps({"detail": "Se requiere el header X-Gym-ID"}),
                        status_code=status.HTTP_400_BAD_REQUEST,
                        media_type="application/json"
                    )
            except (ValueError, TypeError):
                logger.warning(f"X-Gym-ID inválido: {request.headers.get('X-Gym-ID')}")
                return Response(
                    content=json.dumps({"detail": f"Formato inválido para X-Gym-ID: {request.headers.get('X-Gym-ID')}"}),
                    status_code=status.HTTP_400_BAD_REQUEST,
                    media_type="application/json"
                )

        # 2. Verificar si la ruta requiere autenticación
        requires_auth = not any(path.startswith(exempt) for exempt in AUTH_EXEMPT_PATHS)

        if requires_auth:
            auth_header = request.headers.get("Authorization", "")
            if auth_header and auth_header.startswith("Bearer "):
                request.state.has_auth = True
                logger.debug(f"Token Bearer detectado para {path}")
            else:
                logger.warning(f"Acceso a {path} denegado: Token no encontrado o formato inválido")
                return Response(
                    content=json.dumps({"detail": "Token de autenticación requerido"}),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    media_type="application/json"
                )

        # 3. Ejecutar el resto de la request
        response = await call_next(request)

        # 4. Logging del tiempo de procesamiento
        process_time = (time.time() - start_time) * 1000
        logger.debug(f"SimpleTenantAuthMiddleware: {request.method} {path} procesado en {process_time:.2f}ms")

        return response

# Función helper para configurar el middleware en la aplicación
def setup_simple_tenant_auth_middleware(app):
    """
    Configura el middleware simplificado en la aplicación.

    Args:
        app: Aplicación FastAPI
    """
    app.add_middleware(SimpleTenantAuthMiddleware)
    logger.info("SimpleTenantAuthMiddleware configurado en la aplicación")