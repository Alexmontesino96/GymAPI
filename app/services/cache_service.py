import json
import logging
from typing import Any, Optional, TypeVar, Generic, Type, List, Dict, Callable
from datetime import datetime, time, timedelta

from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.orm import Session
from pydantic_core import Url

from app.core.profiling import time_redis_operation, time_deserialize_operation, time_db_query, register_cache_hit, register_cache_miss, db_query_timer

logger = logging.getLogger(__name__) 

T = TypeVar('T', bound=BaseModel)

# Serializador JSON personalizado para manejar objetos datetime, Url y SQLAlchemy models
def json_serializer(obj):
    """Serializador JSON personalizado que maneja objetos datetime, Url de Pydantic y SQLAlchemy models."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Url):
        return str(obj)
    if isinstance(obj, time):
        return obj.isoformat()
    # Manejar objetos SQLAlchemy anidados (como ClassCategoryCustom)
    if hasattr(obj, '__dict__') and hasattr(obj, '__tablename__'):
        # Es un objeto SQLAlchemy, convertir a dict excluyendo atributos internos
        return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
    # Manejar objetos genéricos con __dict__ (fallback)
    if hasattr(obj, '__dict__'):
        try:
            return {k: v for k, v in obj.__dict__.items() if not k.startswith('_')}
        except:
            pass
    raise TypeError(f"Tipo no serializable: {type(obj)}")

class CacheService:
    """
    Servicio genérico para cachear objetos usando Redis.
    Permite cachear y recuperar modelos Pydantic o listas de modelos.
    """
    
    @staticmethod
    @time_redis_operation
    async def get_or_set(
        redis_client: Redis,
        cache_key: str,
        db_fetch_func: Callable,
        model_class: Type[T],
        expiry_seconds: int = 300,  # 5 minutos por defecto
        is_list: bool = False
    ) -> Any:
        """
        Obtiene un objeto de Redis o lo establece si no existe. Maneja Pydantic de forma transparente.
        Utiliza una función asíncrona para obtener datos de la BD si es necesario.
        
        Args:
            redis_client: Cliente Redis a usar
            cache_key: Clave única para identificar el objeto en caché
            db_fetch_func: Función que obtiene los datos de la BD si no están en caché
            model_class: Clase del modelo Pydantic que se debe devolver
            expiry_seconds: Tiempo de expiración en segundos
            is_list: Si es True, se espera/devuelve una lista de objetos
            
        Returns:
            El objeto o lista de objetos solicitados
        """
        if not redis_client:
            logger.warning("Cliente Redis no disponible, ejecutando consulta sin caché")
            return await db_fetch_func()
            
        # Intentar obtener del caché
        try:
            start_time = datetime.now()
            @time_redis_operation
            async def _redis_get(key): return await redis_client.get(key)
            cached_data = await _redis_get(cache_key)
            if cached_data:
                # ¡CACHE HIT! Registrar para métricas
                register_cache_hit(cache_key)
                
                print(f"DEBUG CACHE HIT para clave: {cache_key}")
                logger.debug(f"Cache hit para clave: {cache_key}")
                
                try:
                    data_dict = json.loads(cached_data)
                    
                    @time_deserialize_operation
                    def _deserialize(data, model, is_list_flag):
                        if is_list_flag:
                            return [model.model_validate(item) for item in data]
                        else:
                            return model.model_validate(data)
                            
                    result = _deserialize(data_dict, model_class, is_list)
                    logger.debug(f"Deserialización exitosa desde caché para clave: {cache_key}")
                    return result
                except Exception as e:
                    logger.error(f"Error al deserializar datos de caché para clave {cache_key}: {e}", exc_info=True)
                    # Fallback a BD en caso de error de deserialización
                    register_cache_miss(cache_key)
                    logger.warning(f"Ignorando datos en caché corruptos, consultando BD para {cache_key}")
                    # Eliminar la clave corrupta
                    await redis_client.delete(cache_key)
                    
        except Exception as e:
            logger.error(f"Error al leer del caché: {str(e)}", exc_info=True)
            # Continuamos con la consulta a BD en caso de error
        
        # Si no está en caché o hay error, obtener de la BD
        # ¡CACHE MISS! Registrar para métricas
        register_cache_miss(cache_key)
        
        print(f"DEBUG CACHE MISS para clave: {cache_key}")
        logger.debug(f"Cache miss para clave: {cache_key}")
        db_start_time = datetime.now()
        
        # Aquí es donde ejecutamos realmente la consulta a BD
        # Eliminar el decorador @time_db_query y medir manualmente solo si se ejecuta
        try:
            with db_query_timer():  # Reemplazar el decorador con un contexto
                data = await db_fetch_func()
        except Exception as e:
            logger.error(f"Error en DB fetch para {cache_key}: {e}")
            # Relanzar para que el manejador de excepciones superior lo capture
            raise
            
        db_time = (datetime.now() - db_start_time).total_seconds()
        logger.debug(f"Consulta a BD tomó {db_time:.4f}s para clave {cache_key}")
        
        # Guardar en caché
        try:
            if data is not None:  # Permitir guardar en caché una lista vacía pero no None
                # Preparamos los datos para guardar en caché
                if is_list:
                    # Si tenemos una lista de objetos
                    if not data:  # Lista vacía
                        logger.debug(f"Guardando lista vacía en caché para {cache_key}")
                        serialized_data = "[]"
                    else:
                        # Comprobar si los items son modelos Pydantic
                        if all(hasattr(item, 'model_dump') for item in data):
                            # Todos son modelos Pydantic, usamos su método model_dump
                            logger.debug(f"Serializando lista de {len(data)} modelos Pydantic para {cache_key}")
                            json_data = [item.model_dump() for item in data]
                        else:
                            # Convertimos manualmente los objetos a diccionarios serializables
                            logger.debug(f"Serializando lista de {len(data)} objetos no-Pydantic para {cache_key}")
                            json_data = []
                            for item in data:
                                if hasattr(item, '__dict__'):
                                    # Excluir atributos SQLAlchemy internos
                                    item_dict = {k: v for k, v in item.__dict__.items() 
                                               if not k.startswith('_')}
                                    json_data.append(item_dict)
                                else:
                                    # Si no es un objeto con __dict__, intentar convertir directamente
                                    json_data.append(item)
                        
                        # Serializar la lista de diccionarios a JSON
                        try:
                            serialized_data = json.dumps(json_data, default=json_serializer)
                            logger.debug(f"Serialización exitosa para lista de {len(json_data)} elementos")
                        except Exception as e:
                            logger.error(f"Error al serializar lista para {cache_key}: {e}", exc_info=True)
                            # No almacenar en caché si hay error
                            return data
                else:
                    # Si tenemos un objeto único
                    if hasattr(data, 'model_dump'):
                        # Es un modelo Pydantic, usamos su método model_dump
                        logger.debug(f"Serializando modelo Pydantic para {cache_key}")
                        json_data = data.model_dump()
                    elif hasattr(data, '__dict__'):
                        # Objeto con __dict__, excluir atributos internos
                        logger.debug(f"Serializando objeto __dict__ para {cache_key}")
                        json_data = {k: v for k, v in data.__dict__.items() 
                                   if not k.startswith('_')}
                    else:
                        # Otro tipo de objeto, intentar usar directamente
                        logger.debug(f"Serializando objeto tipo {type(data)} para {cache_key}")
                        json_data = data
                    
                    # Serializar el diccionario a JSON
                    try:
                        serialized_data = json.dumps(json_data, default=json_serializer)
                        logger.debug(f"Serialización exitosa para objeto único")
                    except Exception as e:
                        logger.error(f"Error al serializar objeto para {cache_key}: {e}", exc_info=True)
                        # No almacenar en caché si hay error
                        return data
                
                # Almacenar en Redis
                try:
                    @time_redis_operation
                    async def _redis_set(key, value, ex): return await redis_client.set(key, value, ex=ex)
                    result = await _redis_set(cache_key, serialized_data, expiry_seconds)
                    if result:
                        logger.debug(f"Datos guardados correctamente en caché con clave: {cache_key}, TTL: {expiry_seconds}s")
                    else:
                        logger.warning(f"Redis SET devolvió False para clave: {cache_key}")
                except Exception as e:
                    logger.error(f"Error al guardar en Redis para {cache_key}: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Error general al guardar en caché: {str(e)}", exc_info=True)
            # Continuamos retornando los datos aunque el caché falle
            
        return data
    
    @staticmethod
    @time_redis_operation
    async def get_or_set_profiles_optimized(
        redis_client: Redis,
        cache_key: str,
        db_fetch_func: Callable,
        expiry_seconds: int = 300  # 5 minutos por defecto
    ) -> List["UserPublicProfile"]:
        """
        Método optimizado específicamente para manejar listas de perfiles públicos de usuario.
        Utiliza el modelo ligero UserPublicProfileLight para la serialización/deserialización 
        reduciendo el overhead de validación en Pydantic.
        
        Args:
            redis_client: Cliente Redis a usar
            cache_key: Clave única para identificar el objeto en caché
            db_fetch_func: Función que obtiene los datos de la BD si no están en caché
            expiry_seconds: Tiempo de expiración en segundos
            
        Returns:
            Lista de objetos UserPublicProfile
        """
        from app.schemas.user import UserPublicProfile, UserPublicProfileLight
        
        # Intentar usar orjson para mejor rendimiento
        try:
            import orjson
            has_orjson = True
        except ImportError:
            has_orjson = False
            logger.debug("orjson no está disponible, usando json estándar")
        
        if not redis_client:
            logger.warning("Cliente Redis no disponible, ejecutando consulta sin caché")
            return await db_fetch_func()
        
        # Intentar obtener del caché
        try:
            start_time = datetime.now()
            @time_redis_operation
            async def _redis_get(key): return await redis_client.get(key)
            cached_data = await _redis_get(cache_key)
            redis_get_time = (datetime.now() - start_time).total_seconds()
            logger.debug(f"Redis GET tomó {redis_get_time:.4f}s para clave {cache_key}")
            
            if cached_data:
                # ¡CACHE HIT! Registrar para métricas
                register_cache_hit(cache_key)
                
                print(f"DEBUG CACHE HIT para clave: {cache_key}")
                logger.debug(f"Cache hit optimizado para clave: {cache_key}")
                
                # Deserializar JSON
                @time_deserialize_operation
                def _json_loads(data):
                    return orjson.loads(data) if has_orjson else json.loads(data)
                data_list = _json_loads(cached_data)
                
                # Deserializar usando modelo ligero y convertir al final
                @time_deserialize_operation
                def _deserialize_light(items):
                    return [UserPublicProfileLight(**item) for item in items]
                light_profiles = _deserialize_light(data_list)
                
                conversion_start = datetime.now()
                result = [profile.to_public_profile() for profile in light_profiles]
                conversion_time = (datetime.now() - conversion_start).total_seconds()
                logger.debug(f"Conversión a UserPublicProfile tomó {conversion_time:.4f}s para {len(light_profiles)} perfiles")
                
                total_time = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Tiempo total de recuperación de caché: {total_time:.4f}s (GET: {redis_get_time:.4f}s, JSON: {redis_get_time:.4f}s, Model: {conversion_time:.4f}s)")
                
                return result
                
        except Exception as e:
            logger.error(f"Error al leer del caché optimizado: {str(e)}", exc_info=True)
            # Continuamos con la consulta a BD en caso de error
        
        # Si no está en caché o hay error, obtener de la BD
        # ¡CACHE MISS! Registrar para métricas
        register_cache_miss(cache_key)
        
        print(f"DEBUG CACHE MISS para clave: {cache_key}")
        logger.debug(f"Cache miss optimizado para clave: {cache_key}")
        db_start_time = datetime.now()
        
        # Medir manualmente la consulta a BD solo cuando realmente ocurre
        try:
            with db_query_timer():  # Usar el contexto en lugar del decorador
                profiles = await db_fetch_func()
        except Exception as e:
            logger.error(f"Error en DB fetch para {cache_key}: {e}")
            raise
            
        db_time = (datetime.now() - db_start_time).total_seconds()
        logger.debug(f"Consulta a BD tomó {db_time:.4f}s para clave {cache_key}")
        
        # Guardar en caché usando el formato ligero
        try:
            if profiles:
                # Medir tiempo de conversión y serialización
                start_time = datetime.now()
                
                # Convertir a formato ligero para serialización
                conversion_start = datetime.now()
                light_profiles = [UserPublicProfileLight.from_public_profile(profile) for profile in profiles]
                light_dicts = [profile.model_dump() for profile in light_profiles]
                conversion_time = (datetime.now() - conversion_start).total_seconds()
                logger.debug(f"Conversión a formato ligero tomó {conversion_time:.4f}s para {len(profiles)} perfiles")
                
                # Serializar con orjson si está disponible
                serialize_start = datetime.now()
                if has_orjson:
                    serialized_data = orjson.dumps(light_dicts).decode('utf-8')
                else:
                    serialized_data = json.dumps(light_dicts, default=json_serializer)
                serialize_time = (datetime.now() - serialize_start).total_seconds()
                logger.debug(f"Serialización tomó {serialize_time:.4f}s para {len(light_dicts)} perfiles")
                
                # Guardar en Redis
                @time_redis_operation
                async def _redis_set(key, value, ex): return await redis_client.set(key, value, ex=ex)
                await _redis_set(cache_key, serialized_data, expiry_seconds)
                redis_set_time = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Redis SET tomó {redis_set_time:.4f}s para clave {cache_key}")
                
                total_time = (datetime.now() - start_time).total_seconds()
                logger.debug(f"Tiempo total de guardado en caché: {total_time:.4f}s (Convert: {conversion_time:.4f}s, Serialize: {serialize_time:.4f}s, SET: {redis_set_time:.4f}s)")
                logger.debug(f"Datos guardados en caché optimizada con clave: {cache_key}, TTL: {expiry_seconds}s")
                
        except Exception as e:
            logger.error(f"Error al guardar en caché optimizada: {str(e)}", exc_info=True)
        
        return profiles
    
    @staticmethod
    @time_redis_operation
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
                @time_redis_operation
                async def _redis_delete(*keys_to_del): return await redis_client.delete(*keys_to_del)
                count = await _redis_delete(*keys)
                logger.info(f"Eliminadas {count} claves con patrón: {pattern}")
                return count
            return 0
            
        except Exception as e:
            logger.error(f"Error al eliminar claves con patrón {pattern}: {str(e)}", exc_info=True)
            return 0
            
    @staticmethod
    @time_redis_operation
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
            patterns.append(f"user_public_profile:{user_id}")
            patterns.append(f"user_gym_membership:{user_id}:*")
            patterns.append(f"user_gym_membership_obj:{user_id}:*")
        else:
            # Invalidar todas las cachés de usuarios
            patterns.append("users:*")
            patterns.append("user_public_profile:*")
            patterns.append("user_gym_membership:*")
            patterns.append("user_gym_membership_obj:*")
            
        for pattern in patterns:
            await CacheService.delete_pattern(redis_client, pattern)

    @staticmethod
    @time_redis_operation
    async def get_or_set_json(
        redis_client: Redis,
        cache_key: str,
        db_fetch_func: Callable,
        expiry_seconds: int = 300  # 5 minutos por defecto
    ) -> Any:
        """
        Obtiene y deserializa datos JSON de Redis o los establece si no existen.
        Esta versión es específica para datos que no requieren un modelo Pydantic.
        
        Args:
            redis_client: Cliente Redis a usar
            cache_key: Clave única para identificar el objeto en caché
            db_fetch_func: Función que obtiene los datos de la BD si no están en caché
            expiry_seconds: Tiempo de expiración en segundos
            
        Returns:
            Diccionario o lista de diccionarios con los datos deserializados
        """
        if not redis_client:
            logger.warning("Cliente Redis no disponible, ejecutando consulta sin caché")
            return await db_fetch_func()
            
        # Intentar obtener del caché
        try:
            start_time = datetime.now()
            @time_redis_operation
            async def _redis_get(key): return await redis_client.get(key)
            cached_data = await _redis_get(cache_key)
            if cached_data:
                # ¡CACHE HIT! Registrar para métricas
                register_cache_hit(cache_key)
                
                print(f"DEBUG CACHE HIT para clave: {cache_key}")
                logger.debug(f"Cache hit para clave: {cache_key}")
                
                try:
                    data_dict = json.loads(cached_data)
                    logger.debug(f"Deserialización exitosa desde caché para clave: {cache_key}")
                    return data_dict
                except Exception as e:
                    logger.error(f"Error al deserializar datos JSON de caché para clave {cache_key}: {e}", exc_info=True)
                    # Fallback a BD en caso de error de deserialización
                    register_cache_miss(cache_key)
                    logger.warning(f"Ignorando datos en caché corruptos, consultando BD para {cache_key}")
                    # Eliminar la clave corrupta
                    await redis_client.delete(cache_key)
                    
        except Exception as e:
            logger.error(f"Error al leer del caché: {str(e)}", exc_info=True)
            # Continuamos con la consulta a BD en caso de error
        
        # Si no está en caché o hay error, obtener de la BD
        # ¡CACHE MISS! Registrar para métricas
        register_cache_miss(cache_key)
        
        print(f"DEBUG CACHE MISS para clave: {cache_key}")
        logger.debug(f"Cache miss para clave: {cache_key}")
        db_start_time = datetime.now()
        
        # Aquí es donde ejecutamos realmente la consulta a BD
        try:
            with db_query_timer():  # Reemplazar el decorador con un contexto
                data = await db_fetch_func()
        except Exception as e:
            logger.error(f"Error en DB fetch para {cache_key}: {e}")
            # Relanzar para que el manejador de excepciones superior lo capture
            raise
            
        db_time = (datetime.now() - db_start_time).total_seconds()
        logger.debug(f"Consulta a BD tomó {db_time:.4f}s para clave {cache_key}")
        
        # Guardar en caché
        try:
            if data is not None:
                # Serializar los datos a JSON
                try:
                    serialized_data = json.dumps(data, default=json_serializer)
                    logger.debug(f"Serialización JSON exitosa para clave {cache_key}")
                except Exception as e:
                    logger.error(f"Error al serializar JSON para {cache_key}: {e}", exc_info=True)
                    # No almacenar en caché si hay error
                    return data
                
                # Almacenar en Redis
                try:
                    @time_redis_operation
                    async def _redis_set(key, value, ex): return await redis_client.set(key, value, ex=ex)
                    result = await _redis_set(cache_key, serialized_data, expiry_seconds)
                    if result:
                        logger.debug(f"Datos JSON guardados correctamente en caché con clave: {cache_key}, TTL: {expiry_seconds}s")
                    else:
                        logger.warning(f"Redis SET devolvió False para clave: {cache_key}")
                except Exception as e:
                    logger.error(f"Error al guardar JSON en Redis para {cache_key}: {e}", exc_info=True)
                
        except Exception as e:
            logger.error(f"Error general al guardar JSON en caché: {str(e)}", exc_info=True)
            # Continuamos retornando los datos aunque el caché falle
            
        return data

# Instancia global del servicio
cache_service = CacheService() 
