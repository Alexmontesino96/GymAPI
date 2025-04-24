import secrets
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from app.core.config import get_settings

# Definir el esquema de seguridad para la clave API
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

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
    
    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de configuración: WORKER_API_KEY no está definida"
        )
    
    if not api_key_header:
        # Loguear la dirección IP para ayudar a identificar intentos no autorizados
        client_ip = request.client.host if request.client else "unknown"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Autenticación de worker faltante desde IP: {client_ip}"
        )
    
    # Comparación segura que previene ataques de temporización
    is_valid = secrets.compare_digest(api_key_header, expected_api_key)
    
    if not is_valid:
        client_ip = request.client.host if request.client else "unknown"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Clave API del worker inválida desde IP: {client_ip}"
        )
    
    return True