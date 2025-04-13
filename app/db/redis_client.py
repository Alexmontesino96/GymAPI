import redis.asyncio as redis # Usar cliente asíncrono para FastAPI
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Variable global para mantener la conexión
redis_client = None

async def get_redis_client() -> redis.Redis:
    """
    Dependencia FastAPI para obtener una instancia del cliente Redis asíncrono.
    Maneja la conexión y la reutilización.
    """
    global redis_client
    if redis_client is None:
        try:
            logger.info(f"Conectando a Redis en {settings.REDIS_URL}...")
            # Crear el cliente usando la URL de configuración
            # Añadir decode_responses=True para que las respuestas de Redis sean strings
            redis_client = await redis.from_url(
                settings.REDIS_URL, 
                encoding="utf-8", 
                decode_responses=True
            )
            # Verificar conexión
            await redis_client.ping()
            logger.info("Conexión a Redis establecida correctamente.")
        except Exception as e:
            logger.error(f"Error al conectar con Redis: {e}", exc_info=True)
            # Devolver None o lanzar una excepción para indicar el fallo
            redis_client = None # Resetear para intentar reconectar la próxima vez
            raise HTTPException(status_code=503, detail=f"No se pudo conectar a Redis: {e}")
    
    # Verificar si el cliente sigue conectado antes de devolverlo
    if redis_client:
         try:
            await redis_client.ping()
         except Exception as e:
             logger.error(f"Perdida conexión con Redis, intentando reconectar: {e}")
             redis_client = None
             return await get_redis_client() # Intentar reconectar recursivamente
             
    return redis_client

async def close_redis_client():
    """Cierra la conexión Redis si existe."""
    global redis_client
    if redis_client:
        logger.info("Cerrando conexión Redis...")
        await redis_client.close()
        redis_client = None
        logger.info("Conexión Redis cerrada.")

# Puedes añadir listeners de eventos de FastAPI en main.py para llamar a 
# get_redis_client (al inicio) y close_redis_client (al cerrar)
# o usar la dependencia directamente en los servicios/endpoints que la necesiten. 