import time
import datetime
import gzip
from typing import Callable, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.types import ASGIApp
from starlette.responses import StreamingResponse
import logging

# Importar contextvars y funciones de registro de cache
try:
    from app.core.profiling import cache_hits_context, cache_misses_context
    HAS_PROFILING = True
except ImportError:
    HAS_PROFILING = False
    cache_hits_context = None
    cache_misses_context = None

logger = logging.getLogger("timing_middleware")

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
            
        # Resetear contadores de cache para esta petición si el sistema de profiling está disponible
        token_hits = None
        token_misses = None
        if HAS_PROFILING:
            # Crear nuevos diccionarios para los contadores de esta petición
            current_cache_hits = {"count": 0, "keys": []}
            current_cache_misses = {"count": 0, "keys": []}
            
            # Establecer nuevos valores en el contexto
            if cache_hits_context is not None:
                token_hits = cache_hits_context.set(current_cache_hits)
            if cache_misses_context is not None:
                token_misses = cache_misses_context.set(current_cache_misses)
        
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
        
        # Añadir información de cache hits/misses si está disponible
        if HAS_PROFILING:
            try:
                hits_data = cache_hits_context.get() if cache_hits_context is not None else {"count": 0}
                misses_data = cache_misses_context.get() if cache_misses_context is not None else {"count": 0}
                
                hits_count = hits_data.get("count", 0)
                misses_count = misses_data.get("count", 0)
                
                # Calcular ratio de cache hits
                total_ops = hits_count + misses_count
                hit_ratio = 0 if total_ops == 0 else (hits_count / total_ops) * 100
                
                # Añadir a cabeceras
                response.headers["X-Cache-Hits"] = str(hits_count)
                response.headers["X-Cache-Misses"] = str(misses_count)
                response.headers["X-Cache-Hit-Ratio"] = f"{hit_ratio:.1f}%"
                
                # Registrar en log
                logger.debug(f"Cache stats for {method} {path}: Hits={hits_count}, Misses={misses_count}, Ratio={hit_ratio:.1f}%")
                
                # Resetear contextos
                if token_hits:
                    cache_hits_context.reset(token_hits)
                if token_misses:
                    cache_misses_context.reset(token_misses)
            except Exception as e:
                logger.error(f"Error al procesar estadísticas de caché: {e}")
        
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