"""
Cliente Redis con Connection Pooling (Async - Fase 2 Ready)

Este módulo proporciona acceso a Redis utilizando redis.asyncio y connection pooling
para optimizar el rendimiento en arquitectura completamente asíncrona.

Beneficios implementados:
1. Cliente por request: Cada request tiene su propio cliente aislado (evita blocking)
2. Connection pool compartido: Reutiliza conexiones eficientemente (150 max por defecto)
3. Sin ping overhead: No verificamos conexión en cada request (usa health_check_interval)
4. Reducción de latencia: Elimina los 1-5ms por operación al reutilizar conexiones
5. Mayor throughput: Puede servir más solicitudes por segundo sin blocking
6. Menor uso de recursos: Reduce la presión sobre descriptores de archivo y memoria
7. Mayor estabilidad: Pool grande evita exhaustion durante picos de tráfico (150 vs 50)
8. Keepalive: Las conexiones se mantienen activas para evitar reconexiones frecuentes
9. Async nativo: Integración perfecta con asyncio y FastAPI async

Configuración ajustable mediante variables de entorno:
- REDIS_POOL_MAX_CONNECTIONS: Número máximo de conexiones en el pool (default: 150)
- REDIS_POOL_SOCKET_TIMEOUT: Timeout para operaciones de socket (default: 5 segundos)
- REDIS_POOL_HEALTH_CHECK_INTERVAL: Intervalo para verificar salud de conexiones (default: 30 segundos)
- REDIS_POOL_RETRY_ON_TIMEOUT: Si se debe reintentar automáticamente en timeout (default: True)
- REDIS_POOL_SOCKET_KEEPALIVE: Si se debe mantener la conexión TCP viva (default: True)

Optimizaciones de performance (2024-12-03):
- Cliente por request: Evita que un request lento bloquee a otros
- Pool aumentado: 50 → 150 conexiones para manejar bursts de tráfico
- Sin ping(): Elimina overhead de 1-2ms por request

Para usar en endpoints:
```python
@router.get("/items/{item_id}")
async def read_item(item_id: int, redis: Redis = Depends(get_redis_client)):
    cached_data = await redis.get(f"item:{item_id}")
    # ...
```
"""

import redis.asyncio as redis # Usar cliente asíncrono para FastAPI
from redis.asyncio import ConnectionPool, Redis
from app.core.config import get_settings # Importar get_settings
import logging
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Declaración global del pool de conexiones
REDIS_POOL = None

async def initialize_redis_pool():
    """
    Inicializa el pool de conexiones a Redis.
    Debe llamarse una sola vez al iniciar la aplicación.
    """
    global REDIS_POOL
    if REDIS_POOL is None:
        settings = get_settings()
        try:
            redis_url = settings.REDIS_URL

            # Limpiar la URL
            if redis_url:
                # Eliminar comentarios (todo lo que sigue a #)
                if '#' in redis_url:
                    redis_url = redis_url.split('#')[0]
                # Eliminar espacios en blanco al principio y final
                redis_url = redis_url.strip()
            else:
                redis_url = ""
                logger.warning("REDIS_URL está vacía o no configurada.")

            # Si la URL procesada está vacía, lanzar error
            if not redis_url:
                logger.error("La URL de Redis procesada está vacía. No se puede inicializar el pool.")
                raise ValueError("La URL de Redis procesada está vacía.")
            
            logger.info(f"Inicializando connection pool para Redis en {redis_url}...")
            REDIS_POOL = ConnectionPool.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_POOL_MAX_CONNECTIONS,
                socket_keepalive=settings.REDIS_POOL_SOCKET_KEEPALIVE,
                socket_timeout=settings.REDIS_POOL_SOCKET_TIMEOUT,
                health_check_interval=settings.REDIS_POOL_HEALTH_CHECK_INTERVAL,
                retry_on_timeout=settings.REDIS_POOL_RETRY_ON_TIMEOUT
            )
            logger.info(f"Connection pool de Redis inicializado correctamente (max_connections={settings.REDIS_POOL_MAX_CONNECTIONS}).")
        except Exception as e:
            logger.error(f"Error al inicializar connection pool de Redis: {e}", exc_info=True)
            REDIS_POOL = None
            raise

async def get_redis_client() -> Redis:
    """
    Dependencia FastAPI para obtener una instancia del cliente Redis asíncrono
    usando el connection pool.

    IMPORTANTE: Crea un cliente NUEVO por request para evitar blocking entre requests.
    El connection pool se reutiliza para eficiencia, pero cada request tiene su propio
    cliente aislado. Esto previene que un request lento bloquee a otros.

    Returns:
        Redis: Cliente Redis usando el connection pool compartido
    """
    global REDIS_POOL

    # Inicializar el pool si no existe
    if REDIS_POOL is None:
        await initialize_redis_pool()

    if REDIS_POOL is None:
        # Si aún es None después de intentar inicializar, hay un problema
        logger.error("No se pudo establecer el connection pool de Redis")
        raise HTTPException(status_code=503, detail="No se pudo conectar a Redis")

    try:
        # ✅ FIX: Crear cliente NUEVO por request (no compartido globalmente)
        # Esto evita que un cliente bloqueado afecte a otros requests
        # El pool de conexiones se reutiliza para eficiencia
        client = Redis(connection_pool=REDIS_POOL)

        # ✅ FIX: No hacer ping() por request - overhead innecesario
        # El health_check_interval del pool ya verifica las conexiones
        # Solo hacemos ping si hay un error explícito

        return client
    except Exception as e:
        logger.error(f"Error al obtener conexión del pool de Redis: {e}", exc_info=True)

        # Reintentar inicializando de nuevo el pool
        try:
            logger.info("Intentando reinicializar el connection pool...")
            REDIS_POOL = None
            await initialize_redis_pool()
            client = Redis(connection_pool=REDIS_POOL)

            # Ping solo en caso de error para verificar conectividad
            await client.ping()
            logger.info("Reconexión a Redis exitosa")
            return client
        except Exception as retry_e:
            logger.error(f"Error al reintentar conexión con Redis: {retry_e}", exc_info=True)
            raise HTTPException(status_code=503, detail=f"No se pudo conectar a Redis: {retry_e}")

async def close_redis_client():
    """
    Cierra el pool de conexiones Redis al finalizar la aplicación.
    """
    global REDIS_POOL

    if REDIS_POOL:
        logger.info("Cerrando connection pool de Redis...")
        await REDIS_POOL.disconnect()
        REDIS_POOL = None
        logger.info("Connection pool de Redis cerrado.")

# Puedes añadir listeners de eventos de FastAPI en main.py para llamar a 
# get_redis_client (al inicio) y close_redis_client (al cerrar)
# o usar la dependencia directamente en los servicios/endpoints que la necesiten. 