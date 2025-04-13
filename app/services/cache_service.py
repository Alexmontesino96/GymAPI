import json
import logging
from typing import Any, Optional, TypeVar, Generic, Type, List, Dict, Callable
from datetime import datetime, timedelta

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)

# Serializador JSON personalizado para manejar objetos datetime
def json_serializer(obj):
    """Serializador JSON personalizado que maneja objetos datetime."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Tipo no serializable: {type(obj)}")

class CacheService:
    """
    Servicio genérico para cachear objetos usando Redis.
    Permite cachear y recuperar modelos Pydantic o listas de modelos.
    """
    
    @staticmethod
    async def get_or_set(
        redis_client: Redis,
        cache_key: str,
        db_fetch_func: Callable,
        model_class: Type[T],
        expiry_seconds: int = 300,  # 5 minutos por defecto
        is_list: bool = False
    ) -> Any:
        """
        Obtiene un valor del caché o lo establece si no existe.
        
        Args:
            redis_client: Cliente Redis a usar
            cache_key: Clave única para identificar el objeto en caché
            db_fetch_func: Función que obtiene los datos de la BD si no están en caché
            model_class: Clase del modelo Pydantic para deserialización
            expiry_seconds: Tiempo de expiración en segundos
            is_list: Si es True, se serializa/deserializa como lista de objetos
            
        Returns:
            El objeto o lista de objetos solicitados
        """
        if not redis_client:
            logger.warning("Cliente Redis no disponible, ejecutando consulta sin caché")
            return await db_fetch_func()
            
        # Intentar obtener del caché
        try:
            cached_data = await redis_client.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit para clave: {cache_key}")
                data_dict = json.loads(cached_data)
                
                if is_list:
                    # Deserializar lista de objetos
                    return [model_class.parse_obj(item) for item in data_dict]
                else:
                    # Deserializar objeto único
                    return model_class.parse_obj(data_dict)
                    
        except Exception as e:
            logger.error(f"Error al leer del caché: {str(e)}", exc_info=True)
            # Continuamos con la consulta a BD en caso de error
        
        # Si no está en caché o hay error, obtener de la BD
        logger.debug(f"Cache miss para clave: {cache_key}")
        data = await db_fetch_func()
        
        # Guardar en caché
        try:
            if data:
                if is_list:
                    # Convertir modelos SQLAlchemy a Pydantic antes de serializar
                    pydantic_items = []
                    for item in data:
                        # Si es un modelo SQLAlchemy, convertir a diccionario y luego a modelo Pydantic
                        if hasattr(item, '__tablename__'):  # SQLAlchemy model check
                            # Usar from_orm para convertir un modelo ORM a Pydantic
                            pydantic_item = model_class.from_orm(item)
                            pydantic_items.append(pydantic_item.dict())
                        elif hasattr(item, 'dict'):  # Ya es un modelo Pydantic
                            pydantic_items.append(item.dict())
                        else:
                            # Si no es un modelo reconocido, intentar convertir a diccionario
                            logger.warning(f"Tipo de modelo no reconocido: {type(item)}")
                            pydantic_items.append(item.__dict__)
                            
                    # Usar el serializador personalizado para manejar datetime
                    serialized_data = json.dumps(pydantic_items, default=json_serializer)
                else:
                    # Objeto único - mismo proceso
                    if hasattr(data, '__tablename__'):  # SQLAlchemy model
                        pydantic_item = model_class.from_orm(data)
                        serialized_data = json.dumps(pydantic_item.dict(), default=json_serializer)
                    elif hasattr(data, 'dict'):  # Pydantic model
                        serialized_data = json.dumps(data.dict(), default=json_serializer)
                    else:
                        # Intentar serializar como diccionario
                        logger.warning(f"Tipo de modelo no reconocido: {type(data)}")
                        serialized_data = json.dumps(data.__dict__, default=json_serializer)
                    
                await redis_client.set(
                    cache_key, 
                    serialized_data, 
                    ex=expiry_seconds
                )
                logger.debug(f"Datos guardados en caché con clave: {cache_key}, TTL: {expiry_seconds}s")
                
        except Exception as e:
            logger.error(f"Error al guardar en caché: {str(e)}", exc_info=True)
            # Continuamos retornando los datos aunque el caché falle
            
        return data
    
    @staticmethod
    async def delete_pattern(redis_client: Redis, pattern: str) -> int:
        """
        Elimina todas las claves que coinciden con un patrón.
        Útil para invalidación de caché después de modificaciones.
        
        Args:
            redis_client: Cliente Redis a usar
            pattern: Patrón de claves a eliminar (ej: "users:role:*")
            
        Returns:
            int: Número de claves eliminadas
        """
        if not redis_client:
            return 0
            
        try:
            # Obtener claves que coinciden con el patrón
            keys = []
            async for key in redis_client.scan_iter(match=pattern):
                keys.append(key)
                
            if keys:
                count = await redis_client.delete(*keys)
                logger.info(f"Eliminadas {count} claves con patrón: {pattern}")
                return count
            return 0
            
        except Exception as e:
            logger.error(f"Error al eliminar claves con patrón {pattern}: {str(e)}", exc_info=True)
            return 0
            
    @staticmethod
    async def invalidate_user_caches(redis_client: Redis, user_id: Optional[int] = None) -> None:
        """
        Invalida todas las cachés relacionadas con usuarios.
        Si se proporciona un ID de usuario, solo invalida las cachés relacionadas con ese usuario.
        
        Args:
            redis_client: Cliente Redis a usar
            user_id: ID opcional del usuario específico
        """
        patterns = []
        
        if user_id:
            # Invalidar caché específico del usuario
            patterns.append(f"users:id:{user_id}")
            patterns.append(f"users:*:members:{user_id}")
        else:
            # Invalidar todas las cachés de usuarios
            patterns.append("users:*")
            
        for pattern in patterns:
            await CacheService.delete_pattern(redis_client, pattern)

# Instancia global del servicio
cache_service = CacheService() 