from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import time
import logging
import re
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib

from app.core.stream_client import stream_client
from app.core.config import settings
from app.repositories.chat import chat_repository
from app.schemas.chat import ChatRoomCreate, ChatRoomUpdate
from app.models.chat import ChatRoom

# Configuración de logging
logger = logging.getLogger("chat_service")

# Cache en memoria para guardar tokens de usuario (5 minutos de expiración)
user_token_cache = {}
# Cache en memoria para guardar datos de canales (15 minutos de expiración)
channel_cache = {}

class ChatService:
    def get_user_token(self, user_id: str, user_data: Dict[str, Any]) -> str:
        """Genera un token para el usuario con cache para mejorar rendimiento"""
        # Verificar si ya existe un token en cache válido
        cache_key = f"token_{user_id}"
        current_time = time.time()
        
        if cache_key in user_token_cache:
            cached_data = user_token_cache[cache_key]
            # Si el token no ha expirado (menos de 5 minutos)
            if current_time - cached_data["timestamp"] < 300:  # 5 minutos
                return cached_data["token"]
        
        try:
            # Actualizar usuario en Stream
            stream_client.update_user(
                {
                    "id": user_id,
                    "name": user_data.get("name", user_id),
                    "email": user_data.get("email"),
                    "image": user_data.get("picture")
                }
            )
            
            # Generar token
            token = stream_client.create_token(user_id)
            
            # Guardar en cache
            user_token_cache[cache_key] = {
                "token": token,
                "timestamp": current_time
            }
            
            return token
            
        except Exception as e:
            logger.error(f"Error generando token para usuario {user_id}: {str(e)}", exc_info=True)
            # Estrategia de recuperación: si hay un token en cache, devolverlo aunque haya expirado
            if cache_key in user_token_cache:
                logger.warning(f"Usando token expirado como fallback para usuario {user_id}")
                return user_token_cache[cache_key]["token"]
            raise ValueError(f"No se pudo generar token: {str(e)}")
    
    def create_room(self, db: Session, creator_id: str, room_data: ChatRoomCreate) -> Dict[str, Any]:
        """Crea un canal de chat en Stream y lo registra localmente"""
        logger.info(f"Creando sala con creator_id: {creator_id}, nombre: {room_data.name}")
        
        # Implementar reintentos con backoff exponencial
        max_retries = 3
        retry_delay = 1  # segundos
        
        for attempt in range(max_retries):
            try:
                # Asegurar que el creador está en la lista de miembros
                if creator_id not in room_data.member_ids:
                    room_data.member_ids.append(creator_id)
                
                # Sanitizar el ID del creador para asegurar formato válido
                # Solo permitir: letras, números, @, _, - (según restricciones de Stream)
                safe_creator_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', creator_id)
                
                # Sanitizar los IDs de todos los miembros para el formato de Stream
                safe_member_ids = []
                for member_id in room_data.member_ids:
                    safe_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', member_id)
                    safe_member_ids.append(safe_id)
                
                # ===== AÑADIR: Crear usuarios en Stream antes de crear el canal =====
                logger.info(f"Asegurando que todos los usuarios existen en Stream: {safe_member_ids}")
                for user_id in safe_member_ids:
                    try:
                        # Crear un objeto de usuario mínimo en Stream si no existe
                        stream_client.update_user(
                            {
                                "id": user_id,
                                "name": user_id,  # Usar ID como nombre por defecto
                            }
                        )
                        logger.info(f"Usuario {user_id} creado/actualizado en Stream")
                    except Exception as e:
                        logger.error(f"Error creando usuario {user_id} en Stream: {str(e)}")
                        # Continuamos aunque haya error para intentar con los demás usuarios
                
                # Sanitizar nombre de sala para formato válido en Stream
                safe_name = ""
                if room_data.name:
                    # Reemplazar caracteres no válidos y limitar longitud
                    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', room_data.name)[:30]
                else:
                    # Si no hay nombre, generar uno basado en la fecha
                    current_time = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                    safe_name = f"Sala-{current_time}"
                    
                # Determinar el tipo de canal (configurable si es necesario)
                channel_type = "messaging"
                
                # Generar un ID de canal consistente pero único
                # Nota: Stream Chat requiere IDs únicos con máximo 64 caracteres
                if room_data.is_direct:
                    # Para chats directos, usar un formato que los identifique por los usuarios
                    # Ordenar IDs para garantizar mismo ID para mismos usuarios sin importar el orden
                    sorted_ids = sorted([safe_user_id[:15] for safe_user_id in safe_member_ids[:2]])
                    channel_id = f"direct_{'_'.join(sorted_ids)}"
                    
                    # Verificar si ya existe un chat directo con mismo ID antes de crearlo
                    existing_room = chat_repository.get_room_by_stream_id(db, stream_channel_id=channel_id)
                    if existing_room:
                        logger.info(f"Canal directo ya existe con ID {channel_id}, usando existente")
                        # Usar el canal existente en lugar de crear uno nuevo
                        channel = stream_client.channel(existing_room.stream_channel_type, existing_room.stream_channel_id)
                        response = channel.query(
                            messages_limit=0,
                            watch=False,
                            presence=False
                        )
                        
                        # Devolver información del canal existente
                        result = {
                            "id": existing_room.id,
                            "stream_channel_id": existing_room.stream_channel_id,
                            "stream_channel_type": existing_room.stream_channel_type,
                            "is_direct": True,
                            "name": existing_room.name,
                            "members": response.get("members", [])
                        }
                        return result
                elif room_data.event_id:
                    # Para eventos, usar el ID del evento y un hash corto del creador
                    # Limitar a 64 caracteres para cumplir con las restricciones de Stream
                    creator_hash = hashlib.md5(safe_creator_id.encode()).hexdigest()[:8]
                    channel_id = f"event_{room_data.event_id}_{creator_hash}"
                    
                    # Verificar si ya existe un canal para este evento
                    existing_room = chat_repository.get_event_room(db, event_id=room_data.event_id)
                    if existing_room:
                        logger.info(f"Canal de evento ya existe con ID {channel_id}, usando existente")
                        # Usar el canal existente en lugar de crear uno nuevo
                        channel = stream_client.channel(existing_room.stream_channel_type, existing_room.stream_channel_id)
                        response = channel.query(
                            messages_limit=0,
                            watch=False,
                            presence=False
                        )
                        
                        # Devolver información del canal existente
                        result = {
                            "id": existing_room.id,
                            "stream_channel_id": existing_room.stream_channel_id,
                            "stream_channel_type": existing_room.stream_channel_type,
                            "event_id": room_data.event_id,
                            "name": existing_room.name,
                            "members": response.get("members", [])
                        }
                        return result
                else:
                    # Método 3: Para otros casos, usar un hash MD5 corto
                    # Calcular hash y usar los primeros 16 caracteres
                    name_hash = hashlib.md5(f"{safe_name}_{safe_creator_id}".encode()).hexdigest()[:16]
                    channel_id = f"room_{safe_name}_{safe_creator_id}"
                    
                    # Verificar si ya existe un canal con este ID
                    existing_room = chat_repository.get_room_by_stream_id(db, stream_channel_id=channel_id)
                    if existing_room:
                        logger.info(f"Canal ya existe con ID {channel_id}, usando existente")
                        # Usar el canal existente en lugar de crear uno nuevo
                        channel = stream_client.channel(existing_room.stream_channel_type, existing_room.stream_channel_id)
                        response = channel.query(
                            messages_limit=0,
                            watch=False,
                            presence=False
                        )
                        
                        # Devolver información del canal existente
                        result = {
                            "id": existing_room.id,
                            "stream_channel_id": existing_room.stream_channel_id,
                            "stream_channel_type": existing_room.stream_channel_type,
                            "name": existing_room.name,
                            "members": response.get("members", [])
                        }
                        return result
                
                # Si después de todo aún es mayor a 64, truncar definitivamente
                if len(channel_id) > 64:
                    channel_id = channel_id[:64]
                    
                # Verificar si ya existe un canal con este ID final
                existing_room = chat_repository.get_room_by_stream_id(db, stream_channel_id=channel_id)
                if existing_room:
                    logger.info(f"Canal ya existe con ID {channel_id}, usando existente")
                    # Usar el canal existente en lugar de crear uno nuevo
                    channel = stream_client.channel(existing_room.stream_channel_type, existing_room.stream_channel_id)
                    response = channel.query(
                        messages_limit=0,
                        watch=False,
                        presence=False
                    )
                    
                    # Devolver información del canal existente
                    result = {
                        "id": existing_room.id,
                        "stream_channel_id": existing_room.stream_channel_id,
                        "stream_channel_type": existing_room.stream_channel_type,
                        "name": existing_room.name,
                        "members": response.get("members", [])
                    }
                    return result
                
                logger.info(f"ID de canal generado: {channel_id} (longitud: {len(channel_id)})")
                
                # PASO 1: Obtener un objeto canal
                channel = stream_client.channel(channel_type, channel_id)
                
                # PASO 2: Crear el canal con el creador
                response = channel.create(user_id=safe_creator_id)
                logger.info(f"Canal creado con user_id: {safe_creator_id}")
                
                # Extraer datos del canal de la respuesta
                if not response or 'channel' not in response:
                    logger.error("Respuesta de creación del canal inválida")
                    raise ValueError("Respuesta de Stream inválida al crear el canal")
                
                # Obtener ID y tipo del canal de la respuesta
                channel_data = response['channel']
                stream_channel_id = channel_data.get('id')
                stream_channel_type = channel_data.get('type')
                
                if not stream_channel_id or not stream_channel_type:
                    logger.error(f"Datos de canal incompletos: {channel_data}")
                    raise ValueError("Datos de canal incompletos en la respuesta de Stream")
                    
                logger.info(f"Canal creado - ID: {stream_channel_id}, Tipo: {stream_channel_type}")
                
                # PASO 3: Añadir miembros al canal si es necesario
                if len(safe_member_ids) > 1:  # No añadir si solo está el creador
                    non_creator_members = [m for m in safe_member_ids if m != safe_creator_id]
                    if non_creator_members:
                        logger.info(f"Añadiendo miembros adicionales: {non_creator_members}")
                        channel.add_members(non_creator_members)
                
                # PASO 4: Guardar en la base de datos local
                db_room = chat_repository.create_room(
                    db, 
                    stream_channel_id=stream_channel_id,
                    stream_channel_type=stream_channel_type,
                    room_data=room_data
                )
        
                # Guardar en la caché para futuras consultas
                cache_key = f"channel_{db_room.id}"
                channel_cache[cache_key] = {
                    "data": {
                        "id": db_room.id,
                        "stream_channel_id": stream_channel_id,
                        "stream_channel_type": stream_channel_type,
                        "name": db_room.name,
                        "members": channel_data.get("members", [])
                    },
                    "timestamp": time.time()
                }
                
                # Construir y devolver resultado
                return channel_cache[cache_key]["data"]
                
            except Exception as e:
                logger.error(f"Intento {attempt+1} fallido: {str(e)}", exc_info=True)
                if attempt < max_retries - 1:
                    # Esperar con backoff exponencial antes de reintentar
                    sleep_time = retry_delay * (2 ** attempt)
                    logger.info(f"Reintentando en {sleep_time} segundos...")
                    time.sleep(sleep_time)
                else:
                    # Incluir datos específicos para diagnóstico
                    error_details = {
                        "creator_id": creator_id,
                        "room_name": room_data.name if room_data.name else "Sin nombre",
                        "is_direct": room_data.is_direct,
                        "event_id": room_data.event_id
                    }
                    logger.error(f"Detalles de la solicitud: {error_details}")
                    raise ValueError(f"Error creando canal en Stream después de {max_retries} intentos: {str(e)}")
    
    def get_or_create_direct_chat(self, db: Session, user1_id: str, user2_id: str) -> Dict[str, Any]:
        """Obtiene o crea un chat directo entre dos usuarios con cache para mejorar rendimiento"""
        logger.info(f"Obteniendo/creando chat directo entre usuarios: {user1_id} y {user2_id}")
        
        # Sanitizar IDs de usuario
        safe_user1_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user1_id)
        safe_user2_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user2_id)
        
        # Asegurar que ambos usuarios existen en Stream
        try:
            # Crear/actualizar el primer usuario en Stream
            stream_client.update_user(
                {
                    "id": safe_user1_id,
                    "name": safe_user1_id[:20],  # Limitar longitud del nombre
                }
            )
            logger.info(f"Usuario {safe_user1_id} creado/actualizado en Stream")
            
            # Crear/actualizar el segundo usuario en Stream
            stream_client.update_user(
                {
                    "id": safe_user2_id,
                    "name": safe_user2_id[:20],  # Limitar longitud del nombre
                }
            )
            logger.info(f"Usuario {safe_user2_id} creado/actualizado en Stream")
        except Exception as e:
            logger.error(f"Error creando usuarios en Stream: {str(e)}")
            # Continuamos aunque haya error para intentar crear el chat
        
        # Crear una clave de cache para este chat directo
        cache_key = f"direct_chat_{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
        current_time = time.time()
        
        # Verificar si hay datos en cache
        if cache_key in channel_cache:
            cached_data = channel_cache[cache_key]
            # Si los datos son recientes (menos de 15 minutos)
            if current_time - cached_data["timestamp"] < 900:  # 15 minutos
                logger.info(f"Usando datos en cache para chat directo entre {user1_id} y {user2_id}")
                return cached_data["data"]
        
        # Buscar chat existente
        db_room = chat_repository.get_direct_chat(db, user1_id=user1_id, user2_id=user2_id)
        
        if db_room:
            # Usar el canal existente
            try:
                channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
                # Configurar opciones de consulta para mejorar rendimiento
                response = channel.query(
                    messages_limit=0,
                    watch=False,
                    presence=False
                )
                
                logger.info(f"Chat directo existente encontrado: {db_room.id}")
                
                # Preparar datos de respuesta
                result = {
                    "id": db_room.id,
                    "stream_channel_id": db_room.stream_channel_id,
                    "stream_channel_type": db_room.stream_channel_type,
                    "is_direct": True,
                    "members": response.get("members", [])
                }
                
                # Guardar en cache
                channel_cache[cache_key] = {
                    "data": result,
                    "timestamp": current_time
                }
                
                return result
            except Exception as e:
                logger.error(f"Error obteniendo canal existente: {e}")
                # Eliminar la referencia obsoleta
                db.delete(db_room)
                db.commit()
                # Continuar para crear un nuevo canal
        
        # Crear nuevo chat directo
        logger.info("Creando nuevo chat directo")
        
        # Acortar los IDs sanitizados para evitar que el channel_id exceda los 64 caracteres
        # Máximo 15 caracteres por ID para chats directos
        short_user1_id = safe_user1_id[:15] if len(safe_user1_id) > 15 else safe_user1_id
        short_user2_id = safe_user2_id[:15] if len(safe_user2_id) > 15 else safe_user2_id
        
        # Crear nombre corto para el chat
        chat_name = f"Chat {short_user1_id}-{short_user2_id}"
        
        room_data = ChatRoomCreate(
            name=chat_name,
            is_direct=True,
            member_ids=[user1_id, user2_id]
        )
        
        # Crear el chat y actualizar la caché automáticamente
        return self.create_room(db, user1_id, room_data)
    
    def get_or_create_event_chat(self, db: Session, event_id: int, creator_id: str) -> Dict[str, Any]:
        """Obtiene o crea un chat para un evento"""
        import time
        import logging
        import re
        logger = logging.getLogger("chat_service")
        start_time = time.time()
        
        logger.info(f"Buscando o creando chat para evento {event_id}, usuario {creator_id}")
        
        # Sanitizar el creator_id para evitar errores de formato
        safe_creator_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', creator_id)
        
        try:
            # Asegurar que el creador existe en Stream
            try:
                stream_client.update_user(
                    {
                        "id": safe_creator_id,
                        "name": safe_creator_id[:20],  # Limitar longitud del nombre
                    }
                )
                logger.info(f"Usuario {safe_creator_id} creado/actualizado en Stream")
            except Exception as e:
                logger.error(f"Error creando usuario en Stream: {str(e)}")
                # Continuamos aunque haya error para intentar crear el chat
            
            # Optimización 1: Verificar si el evento existe primero
            from app.models.event import Event
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                logger.warning(f"Evento {event_id} no encontrado")
                raise ValueError(f"Evento no encontrado: {event_id}")
            
            # Optimización 2: Buscar sala existente
            room_query_start = time.time()
            db_room = chat_repository.get_event_room(db, event_id=event_id)
            room_query_time = time.time() - room_query_start
            logger.info(f"Consulta de sala: {room_query_time:.2f}s, encontrada: {bool(db_room)}")
            
            if db_room:
                # Ya existe, intentar recuperar información
                try:
                    # Optimización 3: Limitar la consulta a Stream
                    stream_query_start = time.time()
                    channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
                    
                    # Opciones limitadas para mejorar rendimiento
                    response = channel.query(
                        messages_limit=0,
                        count=None,
                        state=True,
                        watch=False,
                        presence=False
                    )
                    stream_query_time = time.time() - stream_query_start
                    logger.info(f"Consulta a Stream: {stream_query_time:.2f}s")
                    
                    # Si llegamos aquí, el canal existe en Stream, verificar miembros
                    members = response.get("members", [])
                    current_members = [member.get("user_id", "") for member in members]
                    
                    # Añadir el usuario actual si no está en el canal
                    if safe_creator_id not in current_members:
                        logger.info(f"Añadiendo usuario {safe_creator_id} al canal existente")
                        try:
                            channel.add_members([safe_creator_id])
                        except Exception as e:
                            logger.warning(f"No se pudo añadir miembro al canal: {e}")
                            # Continuar aunque falle la adición del miembro
                    
                    # Preparar respuesta
                    result = {
                        "id": db_room.id,
                        "stream_channel_id": db_room.stream_channel_id,
                        "stream_channel_type": db_room.stream_channel_type,
                        "event_id": event_id,
                        "members": members
                    }
                    
                    total_time = time.time() - start_time
                    logger.info(f"Sala existente devuelta - tiempo total: {total_time:.2f}s")
                    return result
                    
                except Exception as e:
                    # Error al acceder al canal, lo registramos para depuración
                    logger.error(f"Error al recuperar canal existente: {e}")
                    # Continuamos para crear uno nuevo
            
            # Si llegamos aquí, necesitamos crear un nuevo canal
            # (porque no existe o porque el existente dio error)
            
            # Crear sala con datos mínimos necesarios
            room_data = ChatRoomCreate(
                name=f"Evento {event.title[:20]}",  # Limitar el título a 20 caracteres
                is_direct=False,
                event_id=event_id,
                member_ids=[safe_creator_id]  # Inicialmente solo el creador
            )
            
            # Si hay una sala antigua en la base de datos que no funcionó, eliminarla
            if db_room:
                logger.info(f"Eliminando referencia a sala no válida: {db_room.id}")
                db.delete(db_room)
                db.commit()
            
            # Crear nueva sala
            creation_start = time.time()
            try:
                result = self.create_room(db, safe_creator_id, room_data)
                creation_time = time.time() - creation_start
                logger.info(f"Creación de sala: {creation_time:.2f}s")
                
                total_time = time.time() - start_time
                logger.info(f"Nueva sala creada - tiempo total: {total_time:.2f}s")
                
                return result
            except Exception as e:
                logger.error(f"Error en create_room: {str(e)}")
                raise ValueError(f"Error creando sala de chat: {str(e)}")
                
        except ValueError as e:
            # Errores específicos que queremos comunicar al usuario
            logger.warning(f"Error de validación: {e}")
            raise
        except Exception as e:
            # Otros errores inesperados
            logger.error(f"Error inesperado al obtener/crear sala de chat: {e}", exc_info=True)
            raise ValueError(f"Error al crear sala de chat: {str(e)}")
    
    def add_user_to_channel(self, db: Session, room_id: int, user_id: str) -> Dict[str, Any]:
        """Añade un usuario a un canal de chat"""
        db_room = chat_repository.get_room(db, room_id=room_id)
        if not db_room:
            raise ValueError(f"No existe sala de chat con ID {room_id}")
        
        # Sanitizar ID de usuario
        safe_user_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user_id)
        
        # Crear usuario en Stream antes de añadirlo al canal
        try:
            stream_client.update_user(
                {
                    "id": safe_user_id,
                    "name": safe_user_id,  # Usar ID como nombre por defecto
                }
            )
            logger.info(f"Usuario {safe_user_id} creado/actualizado en Stream antes de añadirlo al canal")
        except Exception as e:
            logger.error(f"Error creando usuario {safe_user_id} en Stream: {str(e)}")
            # Intentamos añadirlo de todos modos
        
        # Añadir a Stream
        channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
        response = channel.add_members([safe_user_id])
        
        # Añadir a la base de datos local
        chat_repository.add_member_to_room(db, room_id=room_id, user_id=user_id)
        
        return {
            "room_id": room_id,
            "user_id": user_id,
            "stream_response": response
        }
    
    def remove_user_from_channel(self, db: Session, room_id: int, user_id: str) -> Dict[str, Any]:
        """Elimina un usuario de un canal de chat"""
        db_room = chat_repository.get_room(db, room_id=room_id)
        if not db_room:
            raise ValueError(f"No existe sala de chat con ID {room_id}")
        
        # Sanitizar ID de usuario
        safe_user_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user_id)
        
        # Eliminar de Stream
        channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
        response = channel.remove_members([safe_user_id])
        
        # Eliminar de la base de datos local
        chat_repository.remove_member_from_room(db, room_id=room_id, user_id=user_id)
        
        return {
            "room_id": room_id,
            "user_id": user_id,
            "stream_response": response
        }

    # Método para limpiar las caches periódicamente
    def cleanup_caches(self):
        """Elimina entradas expiradas de las caches"""
        current_time = time.time()
        
        # Limpiar cache de tokens (expiración: 5 minutos)
        token_expiration = 300  # 5 minutos
        expired_tokens = [
            key for key, data in user_token_cache.items()
            if current_time - data["timestamp"] > token_expiration
        ]
        for key in expired_tokens:
            del user_token_cache[key]
            
        # Limpiar cache de canales (expiración: 15 minutos)
        channel_expiration = 900  # 15 minutos
        expired_channels = [
            key for key, data in channel_cache.items()
            if current_time - data["timestamp"] > channel_expiration
        ]
        for key in expired_channels:
            del channel_cache[key]
            
        logger.info(f"Limpieza de cache completada. Eliminadas {len(expired_tokens)} entradas de tokens y {len(expired_channels)} entradas de canales.")


chat_service = ChatService() 