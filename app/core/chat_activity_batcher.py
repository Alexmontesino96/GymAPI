"""
Chat Activity Batcher

Sistema eficiente para actualizar la actividad de chats en lotes, 
evitando sobrecargar la base de datos con UPDATEs frecuentes.

Funcionalidad:
- Cache en memoria de timestamps de último mensaje
- Flush periódico a base de datos (batch updates)
- Fallback para consultar actividad cuando sea necesario
- Thread-safe para uso concurrente
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, List
from threading import Lock
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import SessionLocal
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class ChatActivityBatcher:
    """
    Maneja actualizaciones en lote de actividad de chats para optimizar performance.
    """
    
    def __init__(self, flush_interval: int = 300, max_cache_age: int = 3600):
        """
        Inicializa el batcher.
        
        Args:
            flush_interval: Intervalo en segundos para flush automático (default: 5 min)
            max_cache_age: TTL máximo del cache en segundos (default: 1 hora)
        """
        self.flush_interval = flush_interval
        self.max_cache_age = max_cache_age
        
        # Cache en memoria: {chat_room_id: (timestamp, cache_time)}
        self._activity_cache: Dict[int, Tuple[datetime, float]] = {}
        
        # Lock para thread safety
        self._cache_lock = Lock()
        
        # Control de flush
        self._last_flush = time.time()
        self._flush_in_progress = False
        
        logger.info(f"ChatActivityBatcher inicializado: flush_interval={flush_interval}s, max_cache_age={max_cache_age}s")
    
    def update_activity(
        self, 
        chat_room_id: int, 
        message_timestamp: datetime,
        message_text: str = None,
        sender_id: int = None,
        message_type: str = "text"
    ) -> None:
        """
        Actualiza la actividad de un chat en el cache.
        
        Args:
            chat_room_id: ID de la sala de chat
            message_timestamp: Timestamp del mensaje desde Stream
            message_text: Preview del texto del mensaje (opcional)
            sender_id: ID interno del usuario que envió el mensaje (opcional)
            message_type: Tipo de mensaje - text, image, file, etc. (opcional)
        """
        if not isinstance(chat_room_id, int) or not isinstance(message_timestamp, datetime):
            logger.warning(f"Parámetros inválidos: chat_room_id={chat_room_id}, timestamp={message_timestamp}")
            return
        
        current_time = time.time()
        
        with self._cache_lock:
            # Actualizar cache - ahora incluye datos del mensaje
            self._activity_cache[chat_room_id] = (
                message_timestamp, 
                current_time,
                message_text,
                sender_id, 
                message_type
            )
            
            logger.debug(f"Cache actualizado: chat_room_id={chat_room_id}, timestamp={message_timestamp}, type={message_type}")
            
            # Auto-flush si es necesario
            if self._should_auto_flush():
                logger.info("Iniciando auto-flush por intervalo de tiempo")
                self._schedule_flush()
    
    def get_activity(self, chat_room_id: int) -> Optional[datetime]:
        """
        Obtiene la última actividad de un chat desde el cache.
        
        Args:
            chat_room_id: ID de la sala de chat
            
        Returns:
            datetime: Timestamp de última actividad o None si no está en cache
        """
        with self._cache_lock:
            if chat_room_id in self._activity_cache:
                cache_data = self._activity_cache[chat_room_id]
                
                # Compatibilidad con formato anterior y nuevo
                if len(cache_data) == 2:
                    # Formato anterior: (timestamp, cache_time)
                    timestamp, cache_time = cache_data
                else:
                    # Formato nuevo: (timestamp, cache_time, message_text, sender_id, message_type)
                    timestamp, cache_time = cache_data[0], cache_data[1]
                
                # Verificar si el cache no está expirado
                if time.time() - cache_time < self.max_cache_age:
                    return timestamp
                else:
                    # Cache expirado, eliminarlo
                    del self._activity_cache[chat_room_id]
                    logger.debug(f"Cache expirado eliminado para chat_room_id={chat_room_id}")
        
        return None
    
    def flush_to_database(self, force: bool = False) -> int:
        """
        Flush del cache a la base de datos usando batch update.
        
        Args:
            force: Forzar flush aunque no haya pasado el intervalo
            
        Returns:
            int: Número de chats actualizados
        """
        if self._flush_in_progress and not force:
            logger.debug("Flush ya en progreso, saltando")
            return 0
        
        if not force and not self._should_auto_flush():
            logger.debug("No es necesario hacer flush aún")
            return 0
        
        with self._cache_lock:
            if not self._activity_cache:
                logger.debug("Cache vacío, no hay nada que hacer flush")
                return 0
            
            # Copiar cache para procesar fuera del lock
            cache_copy = self._activity_cache.copy()
            
        self._flush_in_progress = True
        updates_count = 0
        
        try:
            logger.info(f"Iniciando flush de {len(cache_copy)} chats a base de datos")
            
            # Crear nueva sesión de BD
            db = SessionLocal()
            try:
                # Preparar datos para bulk update
                update_data = []
                for chat_room_id, cache_data in cache_copy.items():
                    # Compatibilidad con formato anterior y nuevo
                    if len(cache_data) == 2:
                        # Formato anterior: solo timestamp
                        timestamp, _ = cache_data
                        update_data.append({
                            'id': chat_room_id,
                            'last_message_at': timestamp,
                            'last_message_text': None,
                            'last_message_sender_id': None,
                            'last_message_type': 'text'
                        })
                    else:
                        # Formato nuevo: incluye datos del mensaje
                        timestamp, _, message_text, sender_id, message_type = cache_data
                        update_data.append({
                            'id': chat_room_id,
                            'last_message_at': timestamp,
                            'last_message_text': message_text,
                            'last_message_sender_id': sender_id,
                            'last_message_type': message_type or 'text'
                        })
                
                if update_data:
                    # Ejecutar bulk update usando SQL raw para mejor performance
                    # UPDATE múltiples campos usando CASE statements
                    
                    timestamp_cases = []
                    text_cases = []
                    sender_cases = []
                    type_cases = []
                    room_ids = []
                    
                    for data in update_data:
                        room_id = data['id']
                        room_ids.append(str(room_id))
                        
                        # CASE para timestamp
                        timestamp_cases.append(f"WHEN {room_id} THEN '{data['last_message_at'].isoformat()}'")
                        
                        # CASE para text (con escape de comillas)
                        text_value = data['last_message_text']
                        if text_value:
                            # Escapar comillas simples para SQL
                            escaped_text = text_value.replace("'", "''")
                            text_cases.append(f"WHEN {room_id} THEN '{escaped_text}'")
                        else:
                            text_cases.append(f"WHEN {room_id} THEN NULL")
                        
                        # CASE para sender_id
                        sender_id = data['last_message_sender_id']
                        if sender_id:
                            sender_cases.append(f"WHEN {room_id} THEN {sender_id}")
                        else:
                            sender_cases.append(f"WHEN {room_id} THEN NULL")
                        
                        # CASE para message_type
                        msg_type = data['last_message_type'] or 'text'
                        type_cases.append(f"WHEN {room_id} THEN '{msg_type}'")
                    
                    if room_ids:
                        sql = f"""
                        UPDATE chat_rooms 
                        SET 
                            last_message_at = CASE id {' '.join(timestamp_cases)} END,
                            last_message_text = CASE id {' '.join(text_cases)} END,
                            last_message_sender_id = CASE id {' '.join(sender_cases)} END,
                            last_message_type = CASE id {' '.join(type_cases)} END
                        WHERE id IN ({','.join(room_ids)})
                        """
                        
                        result = db.execute(text(sql))
                        db.commit()
                        updates_count = result.rowcount if result.rowcount else len(update_data)
                        
                        logger.info(f"Bulk update completado: {updates_count} chats actualizados con preview")
                    
            except Exception as e:
                logger.error(f"Error durante flush de BD: {str(e)}", exc_info=True)
                db.rollback()
                raise
            finally:
                db.close()
            
            # Limpiar cache solo de los elementos que se procesaron exitosamente
            with self._cache_lock:
                for chat_room_id in cache_copy.keys():
                    if chat_room_id in self._activity_cache:
                        # Solo eliminar si el timestamp no ha cambiado (no hubo actualización concurrent)
                        cached_data = self._activity_cache[chat_room_id]
                        original_data = cache_copy[chat_room_id]
                        
                        # Comparar timestamps para verificar que no hubo updates concurrentes
                        cached_timestamp = cached_data[0] if len(cached_data) >= 1 else None
                        original_timestamp = original_data[0] if len(original_data) >= 1 else None
                        
                        if cached_timestamp == original_timestamp:
                            del self._activity_cache[chat_room_id]
                
                self._last_flush = time.time()
            
            logger.info(f"Flush completado exitosamente: {updates_count} chats actualizados")
            
        except Exception as e:
            logger.error(f"Error durante flush: {str(e)}", exc_info=True)
            # No limpiar cache en caso de error para reintentarlo después
        finally:
            self._flush_in_progress = False
        
        return updates_count
    
    def cleanup_expired_cache(self) -> int:
        """
        Limpia entradas expiradas del cache.
        
        Returns:
            int: Número de entradas eliminadas
        """
        current_time = time.time()
        expired_keys = []
        
        with self._cache_lock:
            for chat_room_id, cache_data in self._activity_cache.items():
                # Compatibilidad con formato anterior y nuevo
                if len(cache_data) == 2:
                    _, cache_time = cache_data
                else:
                    _, cache_time = cache_data[0], cache_data[1]
                    
                if current_time - cache_time > self.max_cache_age:
                    expired_keys.append(chat_room_id)
            
            for key in expired_keys:
                del self._activity_cache[key]
        
        if expired_keys:
            logger.info(f"Cache cleanup: {len(expired_keys)} entradas expiradas eliminadas")
        
        return len(expired_keys)
    
    def get_cache_stats(self) -> Dict[str, any]:
        """
        Obtiene estadísticas del cache para monitoring.
        
        Returns:
            Dict con estadísticas del cache
        """
        with self._cache_lock:
            cache_size = len(self._activity_cache)
            
            if cache_size == 0:
                return {
                    "cache_size": 0,
                    "oldest_entry": None,
                    "newest_entry": None,
                    "last_flush": self._last_flush,
                    "time_since_flush": time.time() - self._last_flush,
                    "flush_in_progress": self._flush_in_progress
                }
            
            # Calcular estadísticas
            cache_times = []
            for cache_data in self._activity_cache.values():
                # Compatibilidad con formato anterior y nuevo
                if len(cache_data) == 2:
                    _, cache_time = cache_data
                else:
                    _, cache_time = cache_data[0], cache_data[1]
                cache_times.append(cache_time)
                
            oldest_cache_time = min(cache_times)
            newest_cache_time = max(cache_times)
            
            return {
                "cache_size": cache_size,
                "oldest_entry": datetime.fromtimestamp(oldest_cache_time).isoformat(),
                "newest_entry": datetime.fromtimestamp(newest_cache_time).isoformat(),
                "last_flush": self._last_flush,
                "time_since_flush": time.time() - self._last_flush,
                "flush_in_progress": self._flush_in_progress,
                "config": {
                    "flush_interval": self.flush_interval,
                    "max_cache_age": self.max_cache_age
                }
            }
    
    def force_flush(self) -> int:
        """
        Fuerza un flush inmediato del cache.
        
        Returns:
            int: Número de chats actualizados
        """
        logger.info("Flush forzado solicitado")
        return self.flush_to_database(force=True)
    
    def _should_auto_flush(self) -> bool:
        """
        Determina si es necesario hacer auto-flush.
        
        Returns:
            bool: True si debe hacer flush
        """
        return (time.time() - self._last_flush) >= self.flush_interval
    
    def _schedule_flush(self) -> None:
        """
        Programa un flush para ejecutar en background.
        Puede ser expandido para usar un task queue en el futuro.
        """
        # Por ahora, ejecutar inmediatamente
        # En el futuro se puede integrar con Celery, RQ, etc.
        try:
            self.flush_to_database()
        except Exception as e:
            logger.error(f"Error en flush programado: {str(e)}", exc_info=True)


# Instancia global del batcher
# Se inicializa con configuración desde settings
def _initialize_batcher() -> ChatActivityBatcher:
    """Inicializa el batcher con configuración desde settings."""
    try:
        settings = get_settings()
        return ChatActivityBatcher(
            flush_interval=settings.CHAT_ACTIVITY_FLUSH_INTERVAL,
            max_cache_age=settings.CHAT_ACTIVITY_CACHE_MAX_AGE
        )
    except Exception as e:
        logger.warning(f"Error cargando configuración del batcher, usando valores por defecto: {e}")
        return ChatActivityBatcher()

chat_activity_batcher = _initialize_batcher()

def get_chat_activity_batcher() -> ChatActivityBatcher:
    """
    Obtiene la instancia global del batcher.
    
    Returns:
        ChatActivityBatcher: Instancia del batcher
    """
    return chat_activity_batcher

def reconfigure_batcher(flush_interval: int = None, max_cache_age: int = None) -> None:
    """
    Reconfigura el batcher global con nuevos parámetros.
    
    Args:
        flush_interval: Nuevo intervalo de flush en segundos
        max_cache_age: Nuevo TTL de cache en segundos
    """
    global chat_activity_batcher
    
    if flush_interval is not None:
        chat_activity_batcher.flush_interval = flush_interval
        logger.info(f"Flush interval actualizado a {flush_interval}s")
    
    if max_cache_age is not None:
        chat_activity_batcher.max_cache_age = max_cache_age
        logger.info(f"Max cache age actualizado a {max_cache_age}s")

def get_latest_chat_activity(chat_room_id: int, db_last_message_at: Optional[datetime] = None) -> Optional[datetime]:
    """
    Obtiene la actividad más reciente de un chat, consultando primero el batcher
    y usando la BD como fallback.
    
    Args:
        chat_room_id: ID de la sala de chat
        db_last_message_at: Timestamp de last_message_at de la BD (opcional)
        
    Returns:
        datetime: El timestamp más reciente de actividad, o None si no hay información
    """
    try:
        batcher = get_chat_activity_batcher()
        
        # Intentar obtener del cache primero
        cache_activity = batcher.get_activity(chat_room_id)
        
        if cache_activity and db_last_message_at:
            # Retornar el más reciente entre cache y BD
            return max(cache_activity, db_last_message_at)
        elif cache_activity:
            # Solo hay información en cache
            return cache_activity
        elif db_last_message_at:
            # Solo hay información en BD
            return db_last_message_at
        else:
            # No hay información disponible
            return None
            
    except Exception as e:
        logger.error(f"Error obteniendo actividad de chat {chat_room_id}: {e}")
        # En caso de error, retornar la información de BD si está disponible
        return db_last_message_at