"""
Base metrics definitions and utilities for Prometheus monitoring.
"""
from typing import Dict, Any, Optional, Callable
from functools import wraps
import time
from datetime import datetime
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    REGISTRY,
    CollectorRegistry
)
import logging

logger = logging.getLogger(__name__)

# Crear registro personalizado si se desea aislar métricas
metrics_registry = REGISTRY  # Usar el registro global por defecto

# ============================================================================
# MÉTRICAS HTTP
# ============================================================================

http_requests_total = Counter(
    'gymapi_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code', 'gym_id'],
    registry=metrics_registry
)

http_request_duration_seconds = Histogram(
    'gymapi_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint', 'status_code'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=metrics_registry
)

http_request_size_bytes = Summary(
    'gymapi_http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    registry=metrics_registry
)

http_response_size_bytes = Summary(
    'gymapi_http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    registry=metrics_registry
)

# ============================================================================
# MÉTRICAS DE BASE DE DATOS
# ============================================================================

db_query_duration_seconds = Histogram(
    'gymapi_db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5),
    registry=metrics_registry
)

db_connections_active = Gauge(
    'gymapi_db_connections_active',
    'Active database connections',
    registry=metrics_registry
)

db_connections_total = Counter(
    'gymapi_db_connections_total',
    'Total database connections created',
    ['status'],  # success, failed
    registry=metrics_registry
)

db_transactions_total = Counter(
    'gymapi_db_transactions_total',
    'Total database transactions',
    ['status'],  # committed, rolled_back
    registry=metrics_registry
)

# ============================================================================
# MÉTRICAS DE REDIS
# ============================================================================

redis_operations_total = Counter(
    'gymapi_redis_operations_total',
    'Total Redis operations',
    ['operation', 'status'],  # get/set/del, success/failed
    registry=metrics_registry
)

redis_operation_duration_seconds = Histogram(
    'gymapi_redis_operation_duration_seconds',
    'Redis operation duration in seconds',
    ['operation'],
    buckets=(0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1),
    registry=metrics_registry
)

redis_cache_hits_total = Counter(
    'gymapi_redis_cache_hits_total',
    'Total Redis cache hits',
    ['cache_type'],
    registry=metrics_registry
)

redis_cache_misses_total = Counter(
    'gymapi_redis_cache_misses_total',
    'Total Redis cache misses',
    ['cache_type'],
    registry=metrics_registry
)

redis_connection_errors_total = Counter(
    'gymapi_redis_connection_errors_total',
    'Total Redis connection errors',
    registry=metrics_registry
)

# ============================================================================
# MÉTRICAS DE NEGOCIO
# ============================================================================

business_events_total = Counter(
    'gymapi_business_events_total',
    'Total business events',
    ['event_type', 'gym_id', 'status'],
    registry=metrics_registry
)

active_users_gauge = Gauge(
    'gymapi_active_users',
    'Current active users',
    ['gym_id', 'user_type'],
    registry=metrics_registry
)

# ============================================================================
# MÉTRICAS DE SISTEMA
# ============================================================================

app_info = Gauge(
    'gymapi_app_info',
    'Application information',
    ['version', 'environment'],
    registry=metrics_registry
)

# ============================================================================
# CLASE REGISTRY
# ============================================================================

class MetricsRegistry:
    """Registro centralizado de métricas."""

    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.custom_collectors: list = []

    def register_metric(self, name: str, metric: Any) -> None:
        """Registrar una métrica personalizada."""
        self.metrics[name] = metric

    def get_metric(self, name: str) -> Optional[Any]:
        """Obtener una métrica por nombre."""
        return self.metrics.get(name)

    def register_collector(self, collector: Any) -> None:
        """Registrar un collector personalizado."""
        self.custom_collectors.append(collector)
        REGISTRY.register(collector)

# Instancia global del registry
metrics_registry_instance = MetricsRegistry()

# ============================================================================
# FUNCIONES DE TRACKING
# ============================================================================

def track_request(method: str, endpoint: str, status_code: int, duration: float,
                 gym_id: Optional[int] = None, request_size: int = 0,
                 response_size: int = 0):
    """Trackear una petición HTTP."""
    try:
        gym_id_str = str(gym_id) if gym_id else "unknown"

        # Incrementar contador
        http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code),
            gym_id=gym_id_str
        ).inc()

        # Registrar duración
        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
            status_code=str(status_code)
        ).observe(duration)

        # Registrar tamaños si están disponibles
        if request_size > 0:
            http_request_size_bytes.labels(
                method=method,
                endpoint=endpoint
            ).observe(request_size)

        if response_size > 0:
            http_response_size_bytes.labels(
                method=method,
                endpoint=endpoint
            ).observe(response_size)

    except Exception as e:
        logger.error(f"Error tracking request metrics: {e}")

def track_db_query(operation: str, table: str, duration: float):
    """Trackear una consulta de base de datos."""
    try:
        db_query_duration_seconds.labels(
            operation=operation,
            table=table
        ).observe(duration)
    except Exception as e:
        logger.error(f"Error tracking DB query metrics: {e}")

def track_redis_operation(operation: str, success: bool, duration: float,
                         cache_type: Optional[str] = None, is_hit: Optional[bool] = None):
    """Trackear una operación de Redis."""
    try:
        # Contador de operaciones
        redis_operations_total.labels(
            operation=operation,
            status="success" if success else "failed"
        ).inc()

        # Duración
        redis_operation_duration_seconds.labels(
            operation=operation
        ).observe(duration)

        # Cache hits/misses si aplica
        if cache_type and is_hit is not None:
            if is_hit:
                redis_cache_hits_total.labels(cache_type=cache_type).inc()
            else:
                redis_cache_misses_total.labels(cache_type=cache_type).inc()

    except Exception as e:
        logger.error(f"Error tracking Redis operation metrics: {e}")

def track_business_event(event_type: str, gym_id: int, status: str = "success"):
    """Trackear un evento de negocio."""
    try:
        business_events_total.labels(
            event_type=event_type,
            gym_id=str(gym_id),
            status=status
        ).inc()
    except Exception as e:
        logger.error(f"Error tracking business event metrics: {e}")

# ============================================================================
# DECORADORES
# ============================================================================

def measure_time(metric_name: str = "db_query"):
    """Decorador para medir tiempo de ejecución."""
    def decorator(func: Callable):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time

                # Determinar qué métrica usar
                if metric_name == "db_query":
                    operation = func.__name__
                    table = kwargs.get('table', 'unknown')
                    track_db_query(operation, table, duration)
                elif metric_name == "redis":
                    operation = func.__name__
                    track_redis_operation(operation, True, duration)

                return result
            except Exception as e:
                duration = time.time() - start_time
                if metric_name == "redis":
                    operation = func.__name__
                    track_redis_operation(operation, False, duration)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                if metric_name == "db_query":
                    operation = func.__name__
                    table = kwargs.get('table', 'unknown')
                    track_db_query(operation, table, duration)
                elif metric_name == "redis":
                    operation = func.__name__
                    track_redis_operation(operation, True, duration)

                return result
            except Exception as e:
                duration = time.time() - start_time
                if metric_name == "redis":
                    operation = func.__name__
                    track_redis_operation(operation, False, duration)
                raise

        # Retornar el wrapper apropiado
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator

# ============================================================================
# INICIALIZACIÓN
# ============================================================================

def setup_metrics(app_version: str = "1.0.0", environment: str = "production"):
    """Inicializar métricas de la aplicación."""
    try:
        # Establecer información de la aplicación
        app_info.labels(
            version=app_version,
            environment=environment
        ).set(1)

        logger.info(f"Metrics initialized - Version: {app_version}, Environment: {environment}")

    except Exception as e:
        logger.error(f"Error setting up metrics: {e}")

def get_metrics_registry() -> MetricsRegistry:
    """Obtener la instancia del registry de métricas."""
    return metrics_registry_instance