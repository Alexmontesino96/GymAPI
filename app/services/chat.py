from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.stream_client import stream_client
from app.core.config import settings
from app.repositories.chat import chat_repository
from app.schemas.chat import ChatRoomCreate, ChatRoomUpdate
from app.models.chat import ChatRoom


class ChatService:
    def get_user_token(self, user_id: str, user_data: Dict[str, Any]) -> str:
        """Genera un token para el usuario"""
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
        return stream_client.create_token(user_id)
    
    def create_room(self, db: Session, creator_id: str, room_data: ChatRoomCreate) -> Dict[str, Any]:
        """Crea un canal de chat en Stream y lo registra localmente"""
        # Registrar para depuración
        import logging
        import re
        logger = logging.getLogger("chat_service")
        logger.info(f"Creando sala con creator_id: {creator_id}, nombre: {room_data.name}")
        
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
            
            # Sanitizar nombre de sala para formato válido en Stream
            safe_name = ""
            if room_data.name:
                safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', room_data.name)
                safe_name = safe_name.strip('_')  # Eliminar guiones bajos al inicio/final
                if not safe_name:  # Si quedó vacío después de sanitizar
                    safe_name = "chat"
            else:
                safe_name = "chat"
                
            # Determinar tipo y ID para el canal
            channel_type = "messaging"
            
            # Crear un channel_id seguro (permitiendo solo a-z, 0-9, _, -)
            if room_data.is_direct and len(safe_member_ids) == 2:
                # Para chats directos, usar los IDs ordenados como ID del canal
                sorted_ids = sorted(safe_member_ids)
                channel_id = f"dm_{sorted_ids[0]}_{sorted_ids[1]}"
            elif room_data.event_id:
                # Para chats de eventos, usar el ID del evento
                channel_id = f"event_{room_data.event_id}_{safe_creator_id}"
            else:
                # Para otros chats
                channel_id = f"room_{safe_name}_{safe_creator_id}"
                
            # Asegurar que el channel_id no comienza con números (algunas APIs lo restringen)
            if channel_id[0].isdigit():
                channel_id = f"ch_{channel_id}"
                
            logger.info(f"ID de canal generado: {channel_id}")
            
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
            
            # Construir y devolver resultado
            return {
                "id": db_room.id,
                "stream_channel_id": stream_channel_id,
                "stream_channel_type": stream_channel_type,
                "name": db_room.name,
                "members": channel_data.get("members", [])
            }
            
        except Exception as e:
            logger.error(f"Error creando canal en Stream: {str(e)}", exc_info=True)
            # Incluir datos específicos para diagnóstico
            error_details = {
                "creator_id": creator_id,
                "room_name": room_data.name if room_data.name else "Sin nombre",
                "is_direct": room_data.is_direct,
                "event_id": room_data.event_id
            }
            logger.error(f"Detalles de la solicitud: {error_details}")
            raise ValueError(f"Error creando canal en Stream: {str(e)}")
    
    def get_or_create_direct_chat(self, db: Session, user1_id: str, user2_id: str) -> Dict[str, Any]:
        """Obtiene o crea un chat directo entre dos usuarios"""
        # Añadir logging para depuración
        import logging
        import re
        logger = logging.getLogger("chat_service")
        logger.info(f"Obteniendo/creando chat directo entre usuarios: {user1_id} y {user2_id}")
        
        # Sanitizar IDs de usuario
        safe_user1_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user1_id)
        safe_user2_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user2_id)
        
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
                return {
                    "id": db_room.id,
                    "stream_channel_id": db_room.stream_channel_id,
                    "stream_channel_type": db_room.stream_channel_type,
                    "is_direct": True,
                    "members": response.get("members", [])
                }
            except Exception as e:
                logger.error(f"Error obteniendo canal existente: {e}")
                # Eliminar la referencia obsoleta
                db.delete(db_room)
                db.commit()
                # Continuar para crear un nuevo canal
        
        # Crear nuevo chat directo
        logger.info("Creando nuevo chat directo")
        room_data = ChatRoomCreate(
            name=f"Chat {safe_user1_id} - {safe_user2_id}",
            is_direct=True,
            member_ids=[user1_id, user2_id]
        )
        
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
                name=f"Evento {event.title}",
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
        
        # Añadir a Stream
        channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
        response = channel.add_members([user_id])
        
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
        
        # Eliminar de Stream
        channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
        response = channel.remove_members([user_id])
        
        # Eliminar de la base de datos local
        chat_repository.remove_member_from_room(db, room_id=room_id, user_id=user_id)
        
        return {
            "room_id": room_id,
            "user_id": user_id,
            "stream_response": response
        }


chat_service = ChatService() 