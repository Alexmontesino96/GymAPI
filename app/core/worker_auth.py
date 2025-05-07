import secrets
import logging
import sys
import traceback
from fastapi import Security, HTTPException, status, Request
from fastapi.security import APIKeyHeader
from app.core.config import get_settings

# Configurar logger específico para autenticación
auth_logger = logging.getLogger("auth.worker")
auth_logger.setLevel(logging.DEBUG)

# Asegurar que haya un handler para stdout
if not auth_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    auth_logger.addHandler(handler)

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
    mediante la clave API.
    """
    print("\n=== VERIFICACIÓN DE API KEY ===")
    print(f"URL: {request.url.path}")
    print(f"Método: {request.method}")
    
    try:
        auth_logger.info(f"Iniciando verificación de API key para {request.url.path}")
        
        # Obtener configuración
        try:
            settings = get_settings()
            expected_key = settings.WORKER_API_KEY
            auth_logger.debug("Configuración obtenida correctamente")
            print("Configuración obtenida correctamente")
        except Exception as config_error:
            error_msg = f"Error al obtener configuración: {str(config_error)}"
            print(f"ERROR: {error_msg}")
            auth_logger.error(error_msg)
            traceback.print_exc()
            # Continuar para evitar fallar silenciosamente
            expected_key = None
        
        # Imprimir claves enmascaradas
        print(f"API Key recibida: {mask_key(api_key_header)}")
        print(f"API Key esperada: {mask_key(expected_key)}")
        auth_logger.debug(f"API Key recibida: {mask_key(api_key_header)}")
        auth_logger.debug(f"API Key esperada: {mask_key(expected_key)}")
        
        # Verificar si la clave API está presente
        if not api_key_header:
            error_msg = "Falta cabecera X-API-Key"
            print(f"ERROR: {error_msg}")
            auth_logger.error(error_msg)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="API key required"
            )
        
        # Verificar si la clave API coincide
        if api_key_header != expected_key:
            error_msg = "Las claves API no coinciden"
            print(f"ERROR: {error_msg}")
            auth_logger.error(f"API key inválida: {mask_key(api_key_header)} != {mask_key(expected_key)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid API key"
            )
        
        # Si llega aquí, la clave es válida
        success_msg = "Verificación de API key exitosa"
        print(f"ÉXITO: {success_msg}")
        auth_logger.info(success_msg)
        return True
        
    except HTTPException:
        # Re-lanzar excepciones HTTP para que FastAPI las maneje
        print("=== FIN VERIFICACIÓN (ERROR HTTP) ===")
        raise
        
    except Exception as e:
        # Capturar y registrar cualquier otra excepción
        error_msg = f"Error inesperado durante verificación: {str(e)}"
        print(f"ERROR CRÍTICO: {error_msg}")
        auth_logger.exception(error_msg)
        
        # Imprimir traceback para debugging
        print("Traceback:")
        traceback.print_exc()
        
        # Relanzar como HTTPException para que FastAPI la maneje adecuadamente
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during authentication: {str(e)}"
        )
    finally:
        print("=== FIN VERIFICACIÓN DE API KEY ===\n")