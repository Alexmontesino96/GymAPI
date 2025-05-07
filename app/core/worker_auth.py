import secrets
import logging
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from app.core.config import get_settings

# Configurar logger con nivel DEBUG para asegurar que muestra todos los logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Forzar nivel DEBUG para este módulo

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
    try:
        # Registrar información completa de la petición para depuración
        client_ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path
        
        logger.debug(f"==== INICIO VERIFICACIÓN API KEY ====")
        logger.debug(f"Petición desde IP: {client_ip} a endpoint: {endpoint}")
        logger.debug(f"Headers recibidos: {request.headers}")
        
        # Salida con print explícito para garantizar visibilidad
        if not api_key_header:
            print(f"⚠️ ERROR: No se recibió clave de API en el encabezado X-API-Key.")
            logger.critical("No se recibió clave de API en encabezado X-API-Key")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key requerida"
            )
        
        # Usar patrón anti-timing-attack para la comparación
        expected_api_key = get_settings().WORKER_API_KEY
        
        # Prints explícitos para depuración
        print(f"🔑 API KEY RECIBIDA: {mask_key(api_key_header)}")
        print(f"🔑 API KEY ESPERADA: {mask_key(expected_api_key)}")
        print(f"🔍 LONGITUDES: Recibida={len(api_key_header)} caracteres, Esperada={len(expected_api_key)} caracteres")
        
        # Log detallado para debugging
        logger.debug(f"Comparando API keys - Recibida: {mask_key(api_key_header)}, Esperada: {mask_key(expected_api_key)}")
        
        if not expected_api_key:
            print("⚠️ ERROR: WORKER_API_KEY no está configurada en el servidor")
            logger.critical("WORKER_API_KEY no está configurada en el servidor")
            # No revelar este error en la respuesta
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de configuración del servidor"
            )
        
        is_valid = secrets.compare_digest(api_key_header, expected_api_key)
        
        print(f"🔐 AUTENTICACIÓN: {'✅ VÁLIDA' if is_valid else '❌ INVÁLIDA'}")
        
        # Logs detallados para distintos escenarios
        if is_valid:
            logger.debug("Autenticación exitosa para API key de worker")
            return True
        else:
            logger.error(f"Autenticación fallida para API key, recibida {mask_key(api_key_header)}")
            print(f"⚠️ ERROR: Clave API inválida")
            
            # Verificar si tiene misma longitud pero caracteres diferentes
            if len(api_key_header) == len(expected_api_key):
                print("📝 NOTA: Las claves tienen la misma longitud pero valores diferentes")
                logger.warning("Las claves API tienen la misma longitud pero valores diferentes")
            
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key inválida"
            )
        
    except HTTPException:
        logger.debug(f"==== FIN VERIFICACIÓN API KEY (FALLIDA) ====")
        raise
    except Exception as e:
        logger.error(f"Error inesperado durante la verificación de la API key: {str(e)}", exc_info=True)
        logger.debug(f"==== FIN VERIFICACIÓN API KEY (ERROR) ====")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno durante la autenticación: {str(e)}"
        )