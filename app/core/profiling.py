"""
Módulo de profiling para identificar cuellos de botella en endpoints FastAPI.

Este módulo proporciona funcionalidades para realizar profiling detallado 
de endpoints específicos, con enfoque especial en análisis de deserialización
y operaciones de caché Redis.
"""

import time
import cProfile
import pstats
import io
import logging
import os
import functools
import traceback
import asyncio
import contextlib
from contextvars import ContextVar
from typing import Callable, Dict, Any, Optional, List
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("profiling")

# Definir ContextVar global
timing_data_context: ContextVar[Optional[Dict[str, List[Dict]]]] = ContextVar(
    "timing_data_context", default=None
)
# Agregar contadores para cache hits y misses
cache_hits_context: ContextVar[Dict[str, int]] = ContextVar(
    "cache_hits_context", default={"count": 0}
)
cache_misses_context: ContextVar[Dict[str, int]] = ContextVar(
    "cache_misses_context", default={"count": 0}
)

# --- Nuevos Context Managers para medición manual de tiempos ---
@contextlib.contextmanager
def db_query_timer(name: str = "db_query"):
    """
    Context manager para medir el tiempo de consultas a BD manualmente.
    Solo registra tiempo cuando el bloque efectivamente se ejecuta.
    
    Args:
        name: Nombre identificativo para la operación
    """
    timing_data = timing_data_context.get()
    if timing_data is None:
        yield  # No hay contexto, simplemente ejecutar sin medir
        return
        
    start_time = time.time()
    try:
        yield
    finally:
        elapsed_time = time.time() - start_time
        timing_data["db_queries"].append({
            "name": name,
            "time": elapsed_time,
            "stack": ''.join(traceback.format_stack(limit=3))
        })
        
@contextlib.asynccontextmanager
async def async_db_query_timer(name: str = "async_db_query"):
    """
    Async context manager para medir el tiempo de consultas a BD asíncronas.
    Solo registra tiempo cuando el bloque efectivamente se ejecuta.
    
    Args:
        name: Nombre identificativo para la operación
    """
    timing_data = timing_data_context.get()
    if timing_data is None:
        yield  # No hay contexto, simplemente ejecutar sin medir
        return
        
    start_time = time.time()
    try:
        yield
    finally:
        elapsed_time = time.time() - start_time
        timing_data["db_queries"].append({
            "name": name,
            "time": elapsed_time,
            "stack": ''.join(traceback.format_stack(limit=3))
        })

class ProfilingMiddleware(BaseHTTPMiddleware):
    """
    Middleware para realizar profiling de endpoints FastAPI específicos.
    """
    
    def __init__(self, app, target_paths=None):
        """
        Inicializa el middleware de profiling.
        """
        super().__init__(app)
        self.target_paths = target_paths or ["/api/v1/"]
        self.profile_dir = "profiles"
        os.makedirs(self.profile_dir, exist_ok=True)
        logger.info(f"ProfilingMiddleware inicializado. Targets: {self.target_paths}")
    
    async def dispatch(self, request: Request, call_next):
        """
        Procesa una solicitud HTTP y realiza profiling si la ruta coincide.
        """
        path = request.url.path
        response = None
        token_timing = None
        token_hits = None
        token_misses = None
        
        if any(path.startswith(target) for target in self.target_paths):
            profiler = cProfile.Profile()
            start_time = time.time()
            profiler.enable()
            
            # Crear diccionario para esta petición y resetear por completo
            current_timing_data = {"redis_operations": [], "deserialize_operations": [], "db_queries": []}
            current_cache_hits = {"count": 0, "keys": []}
            current_cache_misses = {"count": 0, "keys": []}
            
            # Establecer NUEVOS contextos para esta petición
            token_timing = timing_data_context.set(current_timing_data)
            token_hits = cache_hits_context.set(current_cache_hits)
            token_misses = cache_misses_context.set(current_cache_misses)
            
            try:
                response = await call_next(request)
            except Exception as e:
                logger.error(f"Error durante request perfilado: {str(e)}", exc_info=True)
                raise
            finally:
                profiler.disable()
                end_time = time.time()
                total_time = end_time - start_time
                
                # Recuperar los datos del contexto actual
                final_timing_data = timing_data_context.get()
                final_cache_hits = cache_hits_context.get()
                final_cache_misses = cache_misses_context.get()

                # Resetear los contextos
                if token_timing: 
                    timing_data_context.reset(token_timing)
                if token_hits:
                    cache_hits_context.reset(token_hits)
                if token_misses:
                    cache_misses_context.reset(token_misses)

                # Crear nombre de archivo único para el perfil
                timestamp = int(start_time)
                profile_filename = os.path.join(
                    self.profile_dir, 
                    f"profile_{request.method}_{path.replace('/', '_').strip('_')}_{timestamp}.prof"
                )
                
                # Obtener y guardar datos del profiler
                s = io.StringIO()
                ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
                ps.print_stats(30)  # Imprimir top 30 funciones
                profile_text = s.getvalue()
                
                # Guardar archivo .prof para análisis detallado posterior
                ps.dump_stats(profile_filename)
                
                # Analizar los tiempos guardados en timing_data si existen
                timing_summary = self._analyze_timing(final_timing_data or {})
                
                # Guardar un informe de texto para revisión rápida
                report_filename = f"{profile_filename}.txt"
                with open(report_filename, "w") as f:
                    f.write(f"=== Profile for {request.method} {path} ===\n")
                    f.write(f"Total time: {total_time:.4f}s\n\n")
                    f.write("=== Cache Statistics ===\n")
                    f.write(f"Cache Hits: {final_cache_hits['count']}\n")
                    f.write(f"Cache Misses: {final_cache_misses['count']}\n")
                    hit_ratio = 0 if (final_cache_hits['count'] + final_cache_misses['count']) == 0 else \
                                final_cache_hits['count'] / (final_cache_hits['count'] + final_cache_misses['count']) * 100
                    f.write(f"Hit Ratio: {hit_ratio:.1f}%\n\n")
                    
                    f.write("=== Timing Summary ===\n")
                    
                    for category, data in timing_summary.items():
                        f.write(f"\n{category.upper()}:\n")
                        f.write(f"  Total operations: {data['count']}\n")
                        f.write(f"  Total time: {data['total_time']:.4f}s ({data.get('percentage', 0.0):.1f}% of total measured)\n")
                        if data['count'] > 0:
                            f.write(f"  Average time: {data.get('avg_time', 0.0):.4f}s\n")
                            f.write(f"  Max time: {data.get('max_time', 0.0):.4f}s\n")
                            
                            if 'operations' in data:
                                f.write("\n  Top operations:\n")
                                for op in data['operations'][:5]:  # Top 5
                                    f.write(f"    - {op.get('name', 'Unknown')}: {op.get('time', 0.0):.4f}s\n")
                    
                    f.write("\n=== cProfile Details ===\n")
                    f.write(profile_text)
                
                # Añadir header con nombre del perfil
                if response is not None and isinstance(response, Response):
                    response.headers["X-Profile-File"] = profile_filename
                    response.headers["X-Total-Time"] = f"{total_time:.4f}s"
                    response.headers["X-Cache-Hit-Ratio"] = f"{hit_ratio:.1f}%"
                
                # Imprimir resumen en consola
                logger.info(f"=== Profile for {request.method} {path} ===")
                logger.info(f"Total time: {total_time:.4f}s")
                logger.info(f"Cache Hits: {final_cache_hits['count']}, Misses: {final_cache_misses['count']}, Ratio: {hit_ratio:.1f}%")
                for category, data in timing_summary.items():
                    logger.info(f"{category}: {data['total_time']:.4f}s ({data.get('percentage', 0.0):.1f}%)")
                logger.info(f"Profile saved to: {profile_filename}")
                logger.info(f"Report saved to: {report_filename}")
            
            return response
        else:
            # Para rutas no perfiladas, simplemente procesar normalmente
            return await call_next(request)
    
    def _analyze_timing(self, timing_data: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
        """
        Analiza los datos de tiempo recopilados durante la petición.
        """
        result = {}
        total_measured_time = 0
        
        for category, operations in timing_data.items():
            if not operations:
                result[category] = {
                    "count": 0,
                    "total_time": 0,
                    "percentage": 0,
                    "avg_time": 0,
                    "max_time": 0
                }
                continue
                
            total_time = sum(op["time"] for op in operations)
            total_measured_time += total_time
            count = len(operations)
            avg_time = total_time / count if count > 0 else 0
            max_time = max(op["time"] for op in operations) if operations else 0
            
            # Ordenar operaciones por tiempo (de mayor a menor)
            sorted_ops = sorted(operations, key=lambda x: x["time"], reverse=True)
            
            result[category] = {
                "count": count,
                "total_time": total_time,
                "avg_time": avg_time,
                "max_time": max_time,
                "operations": sorted_ops
            }
        
        if total_measured_time > 0:
            for category in result:
                result[category]["percentage"] = (result[category]["total_time"] / total_measured_time) * 100
        else:
            for category in result:
                result[category]["percentage"] = 0.0
        
        return result

def register_cache_hit(cache_key: str):
    """
    Registra un cache hit para las métricas.
    """
    hits = cache_hits_context.get()
    if hits is not None:
        hits["count"] += 1
        if "keys" in hits and cache_key:
            hits["keys"].append(cache_key)
    # Loguear para depuración
    logger.debug(f"Registrado cache HIT para clave: {cache_key}")

def register_cache_miss(cache_key: str):
    """
    Registra un cache miss para las métricas.
    """
    misses = cache_misses_context.get()
    if misses is not None:
        misses["count"] += 1
        if "keys" in misses and cache_key:
            misses["keys"].append(cache_key)
    # Loguear para depuración
    logger.debug(f"Registrado cache MISS para clave: {cache_key}")

def time_redis_operation(func):
    """
    Decorador para medir el tiempo de las operaciones Redis.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        op_name = func.__name__
        cache_key = kwargs.get('cache_key', kwargs.get('key', None))
        if cache_key: op_name = f"{op_name}({cache_key})"
        
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            return result
        finally:
            elapsed_time = time.time() - start_time
            timing_data = timing_data_context.get()
            if timing_data is not None:
                timing_data["redis_operations"].append({
                    "name": op_name,
                    "time": elapsed_time,
                    "cache_key": cache_key,
                    "stack": ''.join(traceback.format_stack(limit=3))
                })
            else:
                logger.debug(f"(No context) Redis op {op_name}: {elapsed_time:.4f}s")
    
    return wrapper


def time_deserialize_operation(func):
    """
    Decorador para medir el tiempo de operaciones de deserialización.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        model_class = kwargs.get('model_class', None)
        op_name = func.__name__
        if model_class: op_name = f"{op_name}({model_class.__name__})"
        
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            elapsed_time = time.time() - start_time
            timing_data = timing_data_context.get()
            if timing_data is not None:
                timing_data["deserialize_operations"].append({
                    "name": op_name,
                    "time": elapsed_time,
                    "model_class": model_class.__name__ if model_class else "Unknown",
                    "stack": ''.join(traceback.format_stack(limit=3))
                })
            else:
                logger.debug(f"(No context) Deserialize op {op_name}: {elapsed_time:.4f}s")
    
    return wrapper


def time_db_query(func):
    """
    Decorador para medir el tiempo de consultas a la base de datos.
    IMPORTANTE: Para funciones internas que pueden no ejecutarse (en cache hit),
    se recomienda usar los context managers db_query_timer/async_db_query_timer
    en su lugar.
    """
    if asyncio.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Dejamos este decorador por compatibilidad, pero no deberíamos 
            # aplicarlo a funciones internas DB que se usan en cache_service
            # donde podría never run in case of cache hit
            if func.__name__ == 'db_fetch' and 'caché' in str(traceback.extract_stack()):
                # No medir automáticamente, se debe usar async_db_query_timer
                # Solo ejecutar sin tiempo
                return await func(*args, **kwargs)
            else:
                # Para otras funciones DB, seguir registrando normalmente
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    elapsed_time = time.time() - start_time
                    timing_data = timing_data_context.get()
                    if timing_data is not None:
                        timing_data["db_queries"].append({
                            "name": func.__name__,
                            "time": elapsed_time,
                            "stack": ''.join(traceback.format_list(traceback.extract_stack(limit=3)))
                        })
                    else:
                        logger.debug(f"(No context) Async DB query {func.__name__}: {elapsed_time:.4f}s")
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            if func.__name__ == 'db_fetch' and 'caché' in str(traceback.extract_stack()):
                # No medir automáticamente, se debe usar db_query_timer
                # Solo ejecutar sin tiempo
                return func(*args, **kwargs)
            else:
                # Para otras funciones DB, seguir registrando normalmente
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed_time = time.time() - start_time
                    timing_data = timing_data_context.get()
                    if timing_data is not None:
                        timing_data["db_queries"].append({
                            "name": func.__name__,
                            "time": elapsed_time,
                            "stack": ''.join(traceback.format_list(traceback.extract_stack(limit=3)))
                        })
                    else:
                        logger.debug(f"(No context) Sync DB query {func.__name__}: {elapsed_time:.4f}s")
        return sync_wrapper 