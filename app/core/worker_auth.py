import secrets
import logging
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from app.core.config import get_settings

# Configurar logger
logger = logging.getLogger(__name__)

# Definir el esquema de seguridad para la clave API
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def mask_key(key: str) -> str:
    """
    Enmascara la clave para mostrar solo los primeros y últimos 4 caracteres.
    """
    if not key or len(key) < 8:
        return "***" if key else "empty"
    
    return f"{key[:4]}...{key[-4:]}"

async def verify_worker_api_key(
    request: Request,
    api_key_header: str = Security(api_key_header)
):
    """
    Verifica que la petición provenga del worker SQS autorizado
    mediante la validación de la clave API.
    
    Args:
        request: La petición HTTP
        api_key_header: La clave API extraída de la cabecera
        
    Returns:
        True si la autenticación es exitosa
        
    Raises:
        HTTPException: 401 si la clave es inválida o ausente,
                      500 si hay un error de configuración
    """
    settings = get_settings()
    expected_api_key = settings.WORKER_API_KEY
    
    # Registrar las claves (enmascaradas) para depuración
    logger.info(f"Autenticación worker - Clave recibida: '{mask_key(api_key_header)}', Clave esperada: '{mask_key(expected_api_key)}'")
    
    if not expected_api_key:
        logger.error("Error de configuración: WORKER_API_KEY no está definida en la configuración")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de configuración: WORKER_API_KEY no está definida"
        )
    
    if not api_key_header:
        # Loguear la dirección IP para ayudar a identificar intentos no autorizados
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(f"Autenticación de worker faltante desde IP: {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Autenticación de worker faltante desde IP: {client_ip}"
        )
    
    # Comparación segura que previene ataques de temporización
    is_valid = secrets.compare_digest(api_key_header, expected_api_key)
    
    # Registrar el resultado de la validación
    logger.info(f"Resultado validación worker: {'SUCCESS' if is_valid else 'FAILED'}")
    
    if not is_valid:
        client_ip = request.client.host if request.client else "unknown"
        # Registrar detalles adicionales que pueden ayudar a diagnosticar
        logger.warning(f"Clave API del worker inválida desde IP: {client_ip}, longitudes - recibida: {len(api_key_header)}, esperada: {len(expected_api_key)}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Clave API del worker inválida desde IP: {client_ip}"
        )
    
    return True