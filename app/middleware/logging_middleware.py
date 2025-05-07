import logging
import time
import json
import sys
from typing import Callable
from uuid import uuid4
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Configurar logger para garantizar visibilidad
logger = logging.getLogger("app.middleware")
logger.setLevel(logging.DEBUG)

# Asegurar que haya un handler para stdout
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para registrar todas las solicitudes y respuestas HTTP.
    Imprime información detallada en formato de log y con prints directos
    para garantizar visibilidad incluso si la configuración de logging falla.
    """
    def __init__(self, app: FastAPI):
        super().__init__(app)
        
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generar ID único para esta solicitud
        request_id = str(uuid4())
        
        # Extraer información básica de la solicitud
        path = request.url.path
        method = request.method
        query_params = str(request.query_params) if request.query_params else ""
        client_host = request.client.host if request.client else "unknown"
        
        # Registrar inicio de solicitud (log y print)
        start_time = time.time()
        start_msg = f"[{request_id}] Iniciando {method} {path} desde {client_host}"
        print(f"\n=== INICIO SOLICITUD === {start_msg}")
        logger.info(start_msg)
        
        # Registrar headers relevantes (enmascarando datos sensibles)
        headers = dict(request.headers)
        if "x-api-key" in headers:
            key = headers["x-api-key"]
            headers["x-api-key"] = f"{key[:4]}...{key[-4:]}" if len(key) > 8 else "***"
            
        print(f"Headers: {json.dumps(headers, indent=2)}")
        logger.debug(f"[{request_id}] Headers: {json.dumps(headers)}")
        
        # Intentar registrar el body si es JSON
        try:
            body_bytes = await request.body()
            if body_bytes:
                body = await request.json()
                print(f"Body: {json.dumps(body, indent=2)}")
                logger.debug(f"[{request_id}] Body: {json.dumps(body)}")
        except:
            # El body no es JSON o ya fue consumido
            pass
        
        try:
            # Procesar la solicitud
            response = await call_next(request)
            
            # Calcular tiempo y crear mensaje de finalización
            process_time = time.time() - start_time
            status_code = response.status_code
            result = "éxito" if status_code < 400 else "error"
            
            # Registrar finalización (log y print)
            end_msg = f"[{request_id}] Completada {method} {path} con {status_code} ({result}) en {process_time:.4f}s"
            print(f"=== FIN SOLICITUD === {end_msg}")
            logger.info(end_msg)
            
            # Añadir headers de seguimiento a la respuesta
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.4f}"
            
            return response
            
        except Exception as e:
            # Registrar error (log y print)
            process_time = time.time() - start_time
            error_msg = f"[{request_id}] Error en {method} {path}: {str(e)} en {process_time:.4f}s"
            print(f"=== ERROR SOLICITUD === {error_msg}")
            logger.exception(error_msg)
            
            # Re-lanzar la excepción para que FastAPI la maneje
            raise 