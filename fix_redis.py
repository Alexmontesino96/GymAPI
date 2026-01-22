# app/db/redis_client.py - FIX PARA RENDER
import os
import redis
from redis.exceptions import ConnectionError, TimeoutError
import logging

logger = logging.getLogger(__name__)

def get_redis_client():
    """
    Obtener cliente Redis con fallback para cuando no está disponible.
    En Render, usar Redis remoto si está configurado.
    """
    redis_url = os.getenv("REDIS_URL")

    if not redis_url:
        # Si no hay Redis configurado, retornar cliente dummy
        logger.warning("⚠️ REDIS_URL no configurado - Cache deshabilitado")
        return DummyRedisClient()

    try:
        # Intentar conectar a Redis remoto
        logger.info(f"🔌 Conectando a Redis: {redis_url.split('@')[1] if '@' in redis_url else 'local'}")

        client = redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            retry_on_error=[ConnectionError, TimeoutError],
            max_connections=50,
            health_check_interval=30
        )

        # Verificar conexión
        client.ping()
        logger.info("✅ Redis conectado correctamente")
        return client

    except Exception as e:
        logger.error(f"❌ No se pudo conectar a Redis: {e}")
        logger.warning("⚠️ Usando DummyRedisClient (sin cache)")
        return DummyRedisClient()


class DummyRedisClient:
    """Cliente Redis dummy para cuando Redis no está disponible"""

    async def get(self, key):
        return None

    async def set(self, key, value, ex=None):
        return True

    async def setex(self, key, seconds, value):
        return True

    async def delete(self, *keys):
        return 0

    async def exists(self, key):
        return False

    async def expire(self, key, seconds):
        return True

    async def ttl(self, key):
        return -1

    async def keys(self, pattern):
        return []

    async def ping(self):
        return True

    def pipeline(self):
        return self

    async def execute(self):
        return []

# Singleton
redis_client = None

def get_redis():
    """Obtener instancia singleton de Redis"""
    global redis_client
    if redis_client is None:
        redis_client = get_redis_client()
    return redis_client
