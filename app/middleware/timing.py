import time
import datetime
import gzip
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette.responses import StreamingResponse

class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware que mide el tiempo de respuesta de cada solicitud, aplica compresión
    cuando es beneficioso y añade información de diagnóstico en cabeceras.
    """
    
    def __init__(self, app: ASGIApp, min_size_to_compress: int = 1000):
        super().__init__(app)
        self.min_size_to_compress = min_size_to_compress
        # Mantener estadísticas para operaciones lentas específicas
        self.endpoint_stats = {}
    
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Registrar el tiempo de inicio y la información de la solicitud
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        # Preprocesar la solicitud para identificar operaciones críticas
        is_critical_operation = False
        if method == "POST" and "/events/participation" in path:
            is_critical_operation = True
        
        # Procesar la solicitud
        response = await call_next(request)
        
        # Calcular tiempo de procesamiento
        process_time = (time.time() - start_time) * 1000  # En milisegundos
        process_time_str = f"{process_time:.2f}ms"
        
        # Categorizar respuesta por velocidad
        speed_category = "FAST"
        if process_time > 300:
            speed_category = "MEDIUM"
        if process_time > 700:
            speed_category = "SLOW"
        if process_time > 1500:
            speed_category = "VERY_SLOW"
            
            # Registrar estadísticas para endpoints lentos
            endpoint_key = f"{method}:{path}"
            if endpoint_key not in self.endpoint_stats:
                self.endpoint_stats[endpoint_key] = {
                    "count": 0,
                    "total_time": 0,
                    "max_time": 0,
                    "min_time": float('inf')
                }
            stats = self.endpoint_stats[endpoint_key]
            stats["count"] += 1
            stats["total_time"] += process_time
            stats["max_time"] = max(stats["max_time"], process_time)
            stats["min_time"] = min(stats["min_time"], process_time)
        
        # Añadir cabeceras con información de diagnóstico
        response.headers["X-Process-Time"] = process_time_str
        response.headers["X-Process-Speed"] = speed_category
        response.headers["X-Request-Method"] = method
        response.headers["X-Request-Path"] = path
        
        # Para operaciones críticas, dar recomendaciones de optimización específicas
        if is_critical_operation and process_time > 1000:
            if "/events/participation" in path:
                response.headers["X-Optimization-Hint"] = "Consider using bulk operations or caching user information"
        elif process_time > 1000:
            response.headers["X-Optimization-Hint"] = "Consider adding database indexes or optimizing the query"
        
        # Aplicar compresión para respuestas grandes si el cliente la soporta
        should_compress = (
            "gzip" in request.headers.get("accept-encoding", "").lower() and
            int(response.headers.get("content-length", "0")) > self.min_size_to_compress and
            response.headers.get("content-type", "").startswith(("application/json", "text/"))
        )
        
        if should_compress:
            try:
                # Comprimir el contenido
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                
                compressed_body = gzip.compress(body)
                
                # Crear respuesta comprimida
                new_response = Response(
                    compressed_body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type
                )
                
                # Añadir cabeceras de compresión
                new_response.headers["Content-Encoding"] = "gzip"
                new_response.headers["Content-Length"] = str(len(compressed_body))
                return new_response
            except Exception:
                # En caso de error al comprimir, devolver respuesta original
                pass
                
        return response 