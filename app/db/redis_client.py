"""
Cliente Redis con Connection Pooling

Este módulo proporciona acceso a Redis utilizando connection pooling para optimizar el rendimiento.

Beneficios implementados:
1. Reducción de latencia: Elimina los 1-5ms por operación al reutilizar conexiones
2. Mayor throughput: Puede servir más solicitudes por segundo
3. Menor uso de recursos: Reduce la presión sobre descriptores de archivo y memoria
4. Mayor estabilidad: Menos probabilidades de agotar conexiones durante picos de tráfico
5. Keepalive: Las conexiones se mantienen activas para evitar reconexiones frecuentes

Configuración ajustable mediante variables de entorno:
- REDIS_POOL_MAX_CONNECTIONS: Número máximo de conexiones en el pool (default: 20)
- REDIS_POOL_SOCKET_TIMEOUT: Timeout para operaciones de socket (default: 2 segundos)
- REDIS_POOL_HEALTH_CHECK_INTERVAL: Intervalo para verificar salud de conexiones (default: 30 segundos)
- REDIS_POOL_RETRY_ON_TIMEOUT: Si se debe reintentar automáticamente en timeout (default: True)
- REDIS_POOL_SOCKET_KEEPALIVE: Si se debe mantener la conexión TCP viva (default: True)

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
import sys
import time
import traceback

logger = logging.getLogger(__name__)

# Configurar logger específico para Redis con salida directa a stdout para máxima visibilidad
redis_logger = logging.getLogger("redis.client")
redis_logger.setLevel(logging.DEBUG)
if not redis_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    redis_logger.addHandler(handler)

# Declaración global del pool de conexiones
REDIS_POOL = None
# Estado para el modo fallback
REDIS_IN_FALLBACK_MODE = False
# Contador de intentos de conexión fallidos
REDIS_FAILED_ATTEMPTS = 0
# Timestamp del último intento de conexión fallido
REDIS_LAST_ATTEMPT = 0

async def initialize_redis_pool():
    """
    Inicializa el pool de conexiones a Redis.
    Debe llamarse una sola vez al iniciar la aplicación.
    """
    global REDIS_POOL, REDIS_IN_FALLBACK_MODE, REDIS_FAILED_ATTEMPTS, REDIS_LAST_ATTEMPT
    
    if REDIS_POOL is None:
        settings = get_settings()
        try:
            # Verificar si estamos en modo fallback y si ha pasado suficiente tiempo para reintentar
            current_time = time.time()
            if REDIS_IN_FALLBACK_MODE and (current_time - REDIS_LAST_ATTEMPT < 60):  # 60 segundos entre reintentos
                redis_logger.warning(f"Redis en modo fallback. Próximo reintento en {60 - (current_time - REDIS_LAST_ATTEMPT):.1f}s")
                return
            
            REDIS_LAST_ATTEMPT = current_time
            
            # <<< DIAGNÓSTICO EXTENDIDO >>>
            redis_logger.info("=== INICIANDO CONEXIÓN A REDIS ===")
            redis_logger.info(f"Obteniendo configuración de Redis...")
            
            # Usar la URL desde la configuración
            redis_url = settings.REDIS_URL
            redis_logger.info(f"REDIS_URL desde configuración: '{redis_url}'")
            
            # Limpiar la URL
            if redis_url:
                # Eliminar comentarios (todo lo que sigue a #)
                if '#' in redis_url:
                    redis_url = redis_url.split('#')[0]
                # Eliminar espacios en blanco al principio y final
                redis_url = redis_url.strip()
                redis_logger.info(f"URL procesada: '{redis_url}'")
            else:
                redis_url = ""
                redis_logger.warning("REDIS_URL está vacía o no configurada.")
            
            # Información de diagnóstico
            redis_logger.info(f"Variables de Redis:")
            redis_logger.info(f"REDIS_HOST: '{settings.REDIS_HOST}'")
            redis_logger.info(f"REDIS_PORT: '{settings.REDIS_PORT}' (tipo: {type(settings.REDIS_PORT)})")
            redis_logger.info(f"REDIS_PASSWORD: '{'***' if settings.REDIS_PASSWORD else 'None'}'")
            
            # Intentar parsear la URL manualmente para diagnóstico
            import urllib.parse
            try:
                parsed = urllib.parse.urlparse(redis_url)
                redis_logger.info(f"URL parseada: scheme='{parsed.scheme}', netloc='{parsed.netloc}', port='{parsed.port}'")
            except Exception as parse_error:
                redis_logger.error(f"Error al parsear la URL: {parse_error}")
                print(f"Error al parsear URL de Redis: {parse_error}")
            
            # Si la URL procesada está vacía, lanzar error
            if not redis_url:
                 redis_logger.error("La URL de Redis procesada está vacía.")
                 raise ValueError("La URL de Redis está vacía.")
            
            redis_logger.info(f"Inicializando connection pool para Redis...")
            
            # Agregar prints para diagnóstico inmediato
            print(f"Redis URL: {redis_url}")
            print(f"Intentando conectar a Redis...")
            
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
            
            # Probar la conexión
            test_client = Redis(connection_pool=REDIS_POOL)
            await test_client.ping()
            await test_client.close()
            
            # Si llegamos aquí, la conexión fue exitosa
            redis_logger.info(f"Connection pool de Redis inicializado correctamente!")
            print(f"Conexión a Redis EXITOSA")
            
            # Restaurar el estado normal si estábamos en fallback
            if REDIS_IN_FALLBACK_MODE:
                redis_logger.info("Saliendo del modo fallback de Redis")
                print("Saliendo del modo fallback de Redis")
            
            REDIS_IN_FALLBACK_MODE = False
            REDIS_FAILED_ATTEMPTS = 0
            
        except Exception as e:
            REDIS_FAILED_ATTEMPTS += 1
            redis_logger.error(f"Error {REDIS_FAILED_ATTEMPTS} al inicializar Redis: {e}")
            print(f"Error al conectar a Redis: {e}")
            print(traceback.format_exc())
            
            # Activar modo fallback después de varios intentos fallidos
            if REDIS_FAILED_ATTEMPTS >= 2:
                redis_logger.warning(f"Activando modo fallback de Redis después de {REDIS_FAILED_ATTEMPTS} intentos fallidos")
                print(f"ACTIVANDO MODO FALLBACK DE REDIS - La aplicación seguirá funcionando sin caché")
                REDIS_IN_FALLBACK_MODE = True
            
            REDIS_POOL = None
            # No propagar la excepción para evitar bloquear la aplicación

# Variable global para mantener la conexión compartida para compatibilidad
redis_client = None

class DummyRedis:
    """
    Clase que simula las funciones básicas de Redis pero no hace nada.
    Útil para el modo fallback cuando Redis no está disponible.
    """
    async def ping(self):
        return True
        
    async def get(self, key):
        return None
        
    async def set(self, key, value, ex=None):
        return True
        
    async def delete(self, *keys):
        return 0
        
    async def exists(self, *keys):
        return 0
        
    async def close(self):
        return True
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return False

async def get_redis_client() -> Redis:
    """
    Dependencia FastAPI para obtener una instancia del cliente Redis asíncrono
    usando el connection pool.
    
    Returns:
        Redis: Cliente Redis usando el connection pool compartido o un DummyRedis en fallback
    """
    global REDIS_POOL, redis_client, REDIS_IN_FALLBACK_MODE
    
    # Si estamos en modo fallback, devolver un cliente dummy que no hará nada
    if REDIS_IN_FALLBACK_MODE:
        redis_logger.debug("Usando cliente Redis en modo fallback (dummy)")
        return DummyRedis()
    
    # Inicializar el pool si no existe
    if REDIS_POOL is None:
        try:
            await initialize_redis_pool()
        except Exception as e:
            redis_logger.error(f"Error al inicializar Redis: {e}")
            print(f"Error al inicializar Redis: {e}")
            # Activar modo fallback para evitar futuros intentos
            REDIS_IN_FALLBACK_MODE = True
            return DummyRedis()
        
    if REDIS_POOL is None:
        # Si aún es None después de intentar inicializar, activar fallback
        redis_logger.warning("No se pudo establecer el connection pool de Redis, usando fallback")
        print("Redis no disponible - Usando modo fallback")
        REDIS_IN_FALLBACK_MODE = True
        return DummyRedis()
    
    try:
        # Para mantener compatibilidad con código existente que usa la variable redis_client
        if redis_client is None:
            redis_client = Redis(connection_pool=REDIS_POOL)
            
        # Verificar conexión
        try:
            await redis_client.ping()
            return redis_client
        except Exception as ping_error:
            # Si la conexión falla, intentar crear una nueva
            redis_logger.warning(f"Ping a Redis falló: {ping_error}, creando nueva conexión")
            redis_client = Redis(connection_pool=REDIS_POOL)
            await redis_client.ping()  # Si esto falla, pasará a la excepción general
            return redis_client
            
    except Exception as e:
        redis_logger.error(f"Error con conexión Redis: {e}")
        print(f"Error con conexión Redis: {e}")
        traceback.print_exc()
        
        # Activar modo fallback para evitar futuros intentos
        REDIS_IN_FALLBACK_MODE = True
        return DummyRedis()

async def close_redis_client():
    """
    Cierra el pool de conexiones Redis al finalizar la aplicación.
    """
    global REDIS_POOL, redis_client, REDIS_IN_FALLBACK_MODE
    
    # No hacer nada si estamos en modo fallback
    if REDIS_IN_FALLBACK_MODE:
        redis_logger.info("Redis en modo fallback, no hay conexiones que cerrar")
        return
    
    if redis_client:
        redis_logger.info("Cerrando cliente Redis...")
        try:
            await redis_client.close()
        except Exception as e:
            redis_logger.error(f"Error al cerrar cliente Redis: {e}")
        redis_client = None
    
    if REDIS_POOL:
        redis_logger.info("Cerrando connection pool de Redis...")
        try:
            await REDIS_POOL.disconnect()
            redis_logger.info("Connection pool de Redis cerrado correctamente")
        except Exception as e:
            redis_logger.error(f"Error al cerrar connection pool de Redis: {e}")
        REDIS_POOL = None

# Puedes añadir listeners de eventos de FastAPI en main.py para llamar a 
# get_redis_client (al inicio) y close_redis_client (al cerrar)
# o usar la dependencia directamente en los servicios/endpoints que la necesiten. 