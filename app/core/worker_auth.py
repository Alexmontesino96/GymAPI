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
        
        # Obtener la clave API esperada desde settings
        settings = get_settings()
        expected_api_key = settings.WORKER_API_KEY
        
        # Registrar las claves (enmascaradas) para depuración
        # Usar DEBUG para asegurar que se muestra siempre
        logger.debug(f"X-API-Key recibida: '{api_key_header}'")
        logger.debug(f"X-API-Key esperada: '{expected_api_key}'")
        
        # Versión enmascarada para INFO logs
        logger.info(f"Autenticación worker - Clave recibida (enmascarada): '{mask_key(api_key_header)}', Clave esperada (enmascarada): '{mask_key(expected_api_key)}'")
        
        if not expected_api_key:
            logger.error("Error de configuración: WORKER_API_KEY no está definida en la configuración")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error de configuración: WORKER_API_KEY no está definida"
            )
        
        if not api_key_header:
            logger.warning(f"Autenticación de worker faltante desde IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Autenticación de worker faltante desde IP: {client_ip}"
            )
        
        # Registrar la longitud de ambas claves para verificar si hay problemas de espacio/formato
        logger.debug(f"Longitud clave recibida: {len(api_key_header)} caracteres")
        logger.debug(f"Longitud clave esperada: {len(expected_api_key)} caracteres")
        
        # Verificar si hay espacios en blanco o caracteres invisibles
        if api_key_header.strip() != api_key_header:
            logger.warning(f"La clave API recibida contiene espacios en blanco o caracteres invisibles")
            # Intentar limpiar la clave
            api_key_header = api_key_header.strip()
            logger.debug(f"Clave API después de limpiar: '{api_key_header}', longitud: {len(api_key_header)}")
        
        # Comparación segura que previene ataques de temporización
        is_valid = secrets.compare_digest(api_key_header, expected_api_key)
        
        # Registrar el resultado de la validación
        logger.info(f"Resultado validación worker: {'SUCCESS' if is_valid else 'FAILED'}")
        
        if not is_valid:
            # Registrar detalles adicionales que pueden ayudar a diagnosticar
            logger.warning(f"Clave API del worker inválida desde IP: {client_ip}")
            logger.debug(f"Datos para diagnóstico - Recibida: '{api_key_header}', Esperada: '{expected_api_key}'")
            
            # Comparar carácter por carácter para identificar el punto exacto del fallo
            min_len = min(len(api_key_header), len(expected_api_key))
            for i in range(min_len):
                if api_key_header[i] != expected_api_key[i]:
                    logger.debug(f"Primera diferencia encontrada en la posición {i}: '{api_key_header[i]}' != '{expected_api_key[i]}'")
                    break
            
            # Verificar si las longitudes son diferentes
            if len(api_key_header) != len(expected_api_key):
                logger.debug(f"Longitudes diferentes: recibida ({len(api_key_header)}) != esperada ({len(expected_api_key)})")
            
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Clave API del worker inválida desde IP: {client_ip}"
            )
        
        logger.debug(f"==== FIN VERIFICACIÓN API KEY (ÉXITO) ====")
        return True
        
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