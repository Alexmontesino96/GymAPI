from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
import time
import logging
import re
from functools import lru_cache
from datetime import datetime, timedelta
import hashlib

from app.core.stream_client import stream_client
from app.core.config import get_settings
from app.repositories.chat import chat_repository
from app.schemas.chat import ChatRoomCreate, ChatRoomUpdate
from app.models.chat import ChatRoom, ChatMember
from app.models.user import User  # Añadido para consultar auth0_id

# Configuración de logging
logger = logging.getLogger("chat_service")

# Cache en memoria para guardar tokens de usuario (5 minutos de expiración)
user_token_cache = {}
# Cache en memoria para guardar datos de canales (15 minutos de expiración)
channel_cache = {}

class ChatService:
    def get_user_token(self, user_id: int, user_data: Dict[str, Any]) -> str:
        """
        Genera un token para el usuario con cache para mejorar rendimiento.
        
        Args:
            user_id: ID interno del usuario (de la tabla user)
            user_data: Datos adicionales del usuario (nombre, email, etc.)
            
        Returns:
            str: Token para el usuario
        """
        # Verificar si ya existe un token en cache válido
        cache_key = f"token_{user_id}"
        current_time = time.time()
        
        if cache_key in user_token_cache:
            cached_data = user_token_cache[cache_key]
            # Si el token no ha expirado (menos de 5 minutos)
            if current_time - cached_data["timestamp"] < 300:  # 5 minutos
                return cached_data["token"]
        
        try:
            # Para Stream necesitamos el auth0_id, pero esto es solo un detalle de implementación
            # que se maneja internamente y es transparente para el resto del sistema
            from sqlalchemy.orm import Session
            from app.db.session import SessionLocal
            from app.models.user import User
            
            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or not user.auth0_id:
                    raise ValueError(f"Usuario con ID interno {user_id} no encontrado o no tiene auth0_id")
                    
                # Adaptador interno: Convertir ID interno a stream_id (basado en auth0_id)
                stream_id = self._get_stream_id_for_user(user)
                
                # Actualizar usuario en Stream
                stream_client.update_user(
                    {
                        "id": stream_id,
                        "name": user_data.get("name", user.id),  # Usar ID interno como fallback
                        "email": user_data.get("email"),
                        "image": user_data.get("picture")
                    }
                )
                
                # Generar token
                token = stream_client.create_token(stream_id)
                
                # Guardar en cache
                user_token_cache[cache_key] = {
                    "token": token,
                    "timestamp": current_time
                }
                
                return token
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error generando token para usuario interno {user_id}: {str(e)}", exc_info=True)
            # Estrategia de recuperación: si hay un token en cache, devolverlo aunque haya expirado
            if cache_key in user_token_cache:
                logger.warning(f"Usando token expirado como fallback para usuario interno {user_id}")
                return user_token_cache[cache_key]["token"]
            raise ValueError(f"No se pudo generar token: {str(e)}")
    
    def _get_stream_id_for_user(self, user: User) -> str:
        """
        Método adaptador interno para obtener un ID compatible con Stream
        a partir de un objeto de usuario.
        
        Este método encapsula la lógica de adaptación y nos permite cambiar
        fácilmente la implementación si cambia la forma de identificar usuarios en Stream.
        
        Args:
            user: Objeto de usuario de la base de datos
            
        Returns:
            str: ID para usar con Stream
        """
        from app.core.stream_utils import get_stream_id_from_internal
        
        # Usamos el ID interno del usuario para generar el ID de Stream
        return get_stream_id_from_internal(user.id)
    
    def create_room(self, db: Session, creator_id: int, room_data: ChatRoomCreate, gym_id: int) -> Dict[str, Any]:
        """
        Crea un canal de chat en Stream y lo registra localmente.
        
        Args:
            db: Sesión de base de datos
            creator_id: ID interno del creador (en tabla user)
            room_data: Datos de la sala con member_ids como IDs internos
        """
        logger.info(f"[DEBUG-CREATE] Iniciando create_room con creator_id={creator_id}, room_data.event_id={room_data.event_id}")
        
        # Implementar reintentos con backoff exponencial
        max_retries = 3
        retry_delay = 1  # segundos
        
        for attempt in range(max_retries):
            try:
                # Obtener el usuario creador
                creator = db.query(User).filter(User.id == creator_id).first()
                if not creator:
                    logger.error(f"[DEBUG-CREATE] Usuario creador {creator_id} no encontrado")
                    raise ValueError(f"Usuario creador {creator_id} no encontrado")
                
                # Obtener stream_id para el creador (usando el adaptador)
                creator_stream_id = self._get_stream_id_for_user(creator)
                
                # Asegurar que el creador está en la lista de miembros
                if creator_id not in room_data.member_ids:
                    room_data.member_ids.append(creator_id)
                
                # Obtener todos los miembros y sus stream_ids
                member_users = []
                member_stream_ids = []
                
                for member_internal_id in room_data.member_ids:
                    member = db.query(User).filter(User.id == member_internal_id).first()
                    if member:
                        member_users.append(member)
                        member_stream_id = self._get_stream_id_for_user(member)
                        member_stream_ids.append(member_stream_id)
                
                # Crear usuarios en Stream antes de crear el canal
                logger.info(f"[DEBUG-CREATE] Asegurando usuarios en Stream: {member_stream_ids}")
                for i, stream_id in enumerate(member_stream_ids):
                    try:
                        # Crear un objeto de usuario mínimo en Stream si no existe
                        stream_client.update_user({
                            "id": stream_id,
                            "name": getattr(member_users[i], 'email', f"user_{member_users[i].id}"),
                        })
                        logger.info(f"[DEBUG-CREATE] Usuario {stream_id} (ID interno: {member_users[i].id}) creado/actualizado en Stream")
                    except Exception as e:
                        logger.error(f"[DEBUG-CREATE] Error creando usuario {stream_id} en Stream: {str(e)}")
                        # Continuamos aunque haya error para intentar con los demás usuarios
                
                # Sanitizar nombre de sala para formato válido en Stream
                safe_name = ""
                if room_data.name:
                    # Reemplazar caracteres no válidos y limitar longitud
                    safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', room_data.name)[:30]
                else:
                    # Si no hay nombre, generar uno basado en la fecha
                    current_time = datetime.now().strftime("%Y%m%d%H%M%S")
                    safe_name = f"Sala-{current_time}"
                    
                # Determinar el tipo de canal (configurable si es necesario)
                channel_type = "messaging"
                
                # Generar un ID de canal consistente pero único
                # Nota: Stream Chat requiere IDs únicos con máximo 64 caracteres
                if room_data.is_direct:
                    # Para chats directos, usar un formato que los identifique por los usuarios
                    # Ordenar IDs para garantizar mismo ID para mismos usuarios sin importar el orden
                    sorted_ids = sorted([stream_id[:15] for stream_id in member_stream_ids[:2]])
                    channel_id = f"direct_{'_'.join(sorted_ids)}"
                    
                    # Verificar si ya existe un chat directo con mismo ID antes de crearlo
                    existing_room = chat_repository.get_room_by_stream_id(db, stream_channel_id=channel_id)
                    if existing_room:
                        # Reutilizar sala existente - no crear duplicados
                        return self._get_existing_room_info(db, existing_room)
                elif room_data.event_id:
                    # Para eventos, usar el ID del evento y un hash corto del creador
                    creator_hash = hashlib.md5(str(creator_id).encode()).hexdigest()[:8]
                    channel_id = f"event_{room_data.event_id}_{creator_hash}"
                    logger.info(f"[DEBUG-CREATE] Generando ID para chat de evento: event_id={room_data.event_id}, channel_id={channel_id}")
                    
                    # Verificar si ya existe un canal para este evento
                    existing_room = chat_repository.get_event_room(db, event_id=room_data.event_id)
                    if existing_room:
                        # Reutilizar sala existente para el evento
                        logger.info(f"[DEBUG-CREATE] Sala existente encontrada para event_id={room_data.event_id}, id={existing_room.id}")
                        return self._get_existing_room_info(db, existing_room)
                else:
                    # Método 3: Para otros casos, usar un hash MD5 corto basado en IDs internos
                    name_hash = hashlib.md5(f"{safe_name}_{creator_id}".encode()).hexdigest()[:16]
                    channel_id = f"room_{safe_name}_{creator_id}"
                    
                    # Verificar si ya existe un canal con este ID
                    existing_room = chat_repository.get_room_by_stream_id(db, stream_channel_id=channel_id)
                    if existing_room:
                        # Reutilizar sala existente
                        return self._get_existing_room_info(db, existing_room)
                
                # Si después de todo aún es mayor a 64, truncar definitivamente
                if len(channel_id) > 64:
                    channel_id = channel_id[:64]
                    
                # Verificar si ya existe un canal con este ID final
                existing_room = chat_repository.get_room_by_stream_id(db, stream_channel_id=channel_id)
                if existing_room:
                    return self._get_existing_room_info(db, existing_room)
                
                logger.info(f"[DEBUG-CREATE] ID de canal generado: {channel_id} (longitud: {len(channel_id)})")
                
                # PASO 1: Obtener un objeto canal
                channel = stream_client.channel(channel_type, channel_id)
                
                # PASO 2: Crear el canal con el creador
                response = channel.create(user_id=creator_stream_id)
                logger.info(f"[DEBUG-CREATE] Canal creado en Stream: user_id={creator_stream_id} (ID interno: {creator_id})")
                
                # Extraer datos del canal de la respuesta
                if not response or 'channel' not in response:
                    logger.error("[DEBUG-CREATE] Respuesta de creación del canal inválida")
                    raise ValueError("Respuesta de Stream inválida al crear el canal")
                
                # Obtener ID y tipo del canal de la respuesta
                channel_data = response['channel']
                stream_channel_id = channel_data.get('id')
                stream_channel_type = channel_data.get('type')
                
                if not stream_channel_id or not stream_channel_type:
                    logger.error(f"[DEBUG-CREATE] Datos de canal incompletos: {channel_data}")
                    raise ValueError("Datos de canal incompletos en la respuesta de Stream")
                    
                logger.info(f"[DEBUG-CREATE] Canal creado - ID: {stream_channel_id}, Tipo: {stream_channel_type}")
                
                # PASO 3: Añadir miembros al canal si es necesario
                if len(member_stream_ids) > 1:  # No añadir si solo está el creador
                    non_creator_stream_ids = [m for m in member_stream_ids if m != creator_stream_id]
                    if non_creator_stream_ids:
                        logger.info(f"[DEBUG-CREATE] Añadiendo miembros adicionales: {non_creator_stream_ids}")
                        channel.add_members(non_creator_stream_ids)
                
                # PASO 4: Guardar en la base de datos local con IDs internos
                logger.info(f"[DEBUG-CREATE] Guardando sala en BD local: stream_channel_id={stream_channel_id}, event_id={room_data.event_id}")
                try:
                    # Verificar que event_id siga presente y con el valor correcto
                    logger.info(f"[DEBUG-CREATE] Verificación pre-creación: room_data.event_id={room_data.event_id}, is_direct={room_data.is_direct}")
                    
                    db_room = chat_repository.create_room(
                        db, 
                        stream_channel_id=stream_channel_id,
                        stream_channel_type=stream_channel_type,
                        room_data=room_data,  # Contiene member_ids como IDs internos
                        gym_id=gym_id  # Asociar sala al gimnasio
                    )
                    
                    # Verificar que se creó correctamente
                    logger.info(f"[DEBUG-CREATE] Sala creada en BD: id={db_room.id}, event_id={db_room.event_id}, stream_channel_id={db_room.stream_channel_id}")
                    
                    # Verificación adicional
                    verify_room = chat_repository.get_event_room(db, event_id=room_data.event_id)
                    if verify_room:
                        logger.info(f"[DEBUG-CREATE] Verificación: sala encontrada por event_id={room_data.event_id}, id={verify_room.id}")
                    else:
                        logger.warning(f"[DEBUG-CREATE] Verificación: ¡sala NO encontrada por event_id={room_data.event_id}!")
                        
                except Exception as db_error:
                    logger.error(f"[DEBUG-CREATE] Error al crear sala en BD: {str(db_error)}", exc_info=True)
                    raise
        
                # Guardar en la caché para futuras consultas
                cache_key = f"channel_{db_room.id}"
                channel_cache[cache_key] = {
                    "data": {
                        "id": db_room.id,
                        "stream_channel_id": stream_channel_id,
                        "stream_channel_type": stream_channel_type,
                        "name": db_room.name,
                        "event_id": db_room.event_id,  # Añadir event_id a la respuesta
                        "members": self._convert_stream_members_to_internal(
                            channel_data.get("members", []), db
                        ),
                        "created_at": db_room.created_at  # Añadir created_at
                    },
                    "timestamp": time.time()
                }
                
                # Construir y devolver resultado
                logger.info(f"[DEBUG-CREATE] Retornando resultado: id={db_room.id}, event_id={room_data.event_id}, stream_channel_id={stream_channel_id}")
                return channel_cache[cache_key]["data"]
                
            except Exception as e:
                logger.error(f"[DEBUG-CREATE] Intento {attempt+1} fallido: {str(e)}", exc_info=True)
                if attempt < max_retries - 1:
                    # Esperar con backoff exponencial antes de reintentar
                    sleep_time = retry_delay * (2 ** attempt)
                    logger.info(f"[DEBUG-CREATE] Reintentando en {sleep_time} segundos...")
                    time.sleep(sleep_time)
                else:
                    # Incluir datos específicos para diagnóstico
                    error_details = {
                        "creator_id": creator_id,
                        "room_name": room_data.name if room_data.name else "Sin nombre",
                        "is_direct": room_data.is_direct,
                        "event_id": room_data.event_id
                    }
                    logger.error(f"[DEBUG-CREATE] Detalles de la solicitud fallida: {error_details}")
                    raise ValueError(f"Error creando canal en Stream después de {max_retries} intentos: {str(e)}")
    
    def _get_existing_room_info(self, db: Session, room: ChatRoom) -> Dict[str, Any]:
        """
        Obtiene información detallada de una sala existente.
        
        Args:
            db: Sesión de base de datos
            room: Objeto de sala existente
            
        Returns:
            Dict: Información detallada de la sala
        """
        try:
            channel = stream_client.channel(room.stream_channel_type, room.stream_channel_id)
            response = channel.query(
                messages_limit=0,
                watch=False,
                presence=False
            )
            
            # Convertir miembros de stream a IDs internos
            members = self._convert_stream_members_to_internal(
                response.get("members", []), db
            )
            
            return {
                "id": room.id,
                "stream_channel_id": room.stream_channel_id,
                "stream_channel_type": room.stream_channel_type,
                "is_direct": room.is_direct,
                "event_id": room.event_id,
                "name": room.name,
                "members": members,
                "created_at": room.created_at
            }
        except Exception as e:
            logger.error(f"Error obteniendo información de sala existente: {e}")
            # Devolver información básica
            return {
                "id": room.id,
                "stream_channel_id": room.stream_channel_id,
                "stream_channel_type": room.stream_channel_type,
                "is_direct": room.is_direct,
                "event_id": room.event_id,
                "name": room.name,
                "members": [],
                "created_at": room.created_at
            }
        
    def _convert_stream_members_to_internal(self, stream_members: List[Dict[str, Any]], db: Session) -> List[Dict[str, Any]]:
        """
        Convierte miembros de formato Stream a formato interno.
        
        Args:
            stream_members: Lista de miembros en formato Stream
            db: Sesión de base de datos
            
        Returns:
            List: Lista de miembros con IDs internos
        """
        from app.core.stream_utils import get_internal_id_from_stream, is_internal_id_format, is_legacy_id_format
        
        result = []
        for member in stream_members:
            stream_id = member.get("user_id")
            if not stream_id:
                continue
            
            user = None
            
            # Determinar tipo de ID y buscar usuario apropiadamente
            if is_internal_id_format(stream_id):
                # Nuevo formato - obtener ID interno directamente
                try:
                    internal_id = get_internal_id_from_stream(stream_id)
                    user = db.query(User).filter(User.id == internal_id).first()
                except ValueError:
                    logger.warning(f"ID de Stream con formato inválido: {stream_id}")
                    continue
            elif is_legacy_id_format(stream_id):
                # Formato legacy - buscar por auth0_id
                user = db.query(User).filter(User.auth0_id == stream_id).first()
            
            if user:
                # Añadir información del usuario interno
                member_info = {
                    "user_id": user.id,  # ID interno
                    "stream_user_id": stream_id,  # Para compatibilidad si es necesario
                    "created_at": member.get("created_at"),
                    "updated_at": member.get("updated_at")
                }
                result.append(member_info)
        
        return result
    
    def get_or_create_direct_chat(self, db: Session, user1_id: int, user2_id: int, gym_id: int) -> Dict[str, Any]:
        """
        Obtiene o crea un chat directo entre dos usuarios con cache para mejorar rendimiento.
        
        Args:
            db: Sesión de base de datos
            user1_id: ID interno del primer usuario (en tabla user)
            user2_id: ID interno del segundo usuario (en tabla user)
        """
        logger.info(f"Obteniendo/creando chat directo entre usuarios internos: {user1_id} y {user2_id}")
        
        # Cache en memoria usando IDs internos
        cache_key = f"direct_chat_{min(user1_id, user2_id)}_{max(user1_id, user2_id)}"
        current_time = time.time()
        
        # Verificar si hay datos en cache
        if cache_key in channel_cache:
            cached_data = channel_cache[cache_key]
            # Si los datos son recientes (menos de 15 minutos)
            if current_time - cached_data["timestamp"] < 900:  # 15 minutos
                logger.info(f"Usando datos en cache para chat directo entre {user1_id} y {user2_id}")
                return cached_data["data"]
        
        # Buscar chat existente usando IDs internos
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
                    "members": response.get("members", []),
                    "created_at": db_room.created_at
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
        
        # Obtener los auth0_ids correspondientes (necesarios para Stream)
        user1 = db.query(User).filter(User.id == user1_id).first()
        user2 = db.query(User).filter(User.id == user2_id).first()
        
        if not user1 or not user2 or not user1.auth0_id or not user2.auth0_id:
            raise ValueError("Uno o ambos usuarios no existen o no tienen auth0_id")
            
        auth0_user1_id = user1.auth0_id
        auth0_user2_id = user2.auth0_id
        
        # Sanitizar IDs de usuario para Stream
        safe_user1_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', auth0_user1_id)
        safe_user2_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', auth0_user2_id)
        
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
        
        # Crear nuevo chat directo
        logger.info("Creando nuevo chat directo")
        
        # Acortar los IDs sanitizados para evitar que el channel_id exceda los 64 caracteres
        # Máximo 15 caracteres por ID para chats directos
        short_user1_id = safe_user1_id[:15] if len(safe_user1_id) > 15 else safe_user1_id
        short_user2_id = safe_user2_id[:15] if len(safe_user2_id) > 15 else safe_user2_id
        
        # Crear nombre corto para el chat
        chat_name = f"Chat {short_user1_id}-{short_user2_id}"
        
        # Crear el objeto de datos con IDs internos
        room_data = ChatRoomCreate(
            name=chat_name,
            is_direct=True,
            member_ids=[user1_id, user2_id]
        )
        
        # Crear el chat y actualizar la caché automáticamente
        return self.create_room(db, user1_id, room_data, gym_id)
    
    def get_or_create_event_chat(self, db: Session, event_id: int, creator_id: int, gym_id: int) -> Dict[str, Any]:
        """
        Obtiene o crea un chat para un evento.
        
        Args:
            db: Sesión de base de datos
            event_id: ID del evento
            creator_id: ID interno del creador (en tabla user)
        """
        import time
        import logging
        import re
        from app.core.stream_utils import get_stream_id_from_internal
        
        logger = logging.getLogger("chat_service")
        start_time = time.time()
        
        logger.info(f"[DEBUG] Buscando o creando chat para evento {event_id}, usuario interno {creator_id}")
        
        # Obtener el usuario creador
        creator = db.query(User).filter(User.id == creator_id).first()
        if not creator:
            logger.error(f"[DEBUG] Usuario creador {creator_id} no encontrado")
            raise ValueError(f"Usuario creador {creator_id} no encontrado")
            
        # Obtener ID para Stream usando adaptador interno
        creator_stream_id = get_stream_id_from_internal(creator_id)
        
        try:
            # Verificar si el usuario existe en Stream
            user_exists_in_stream = True
            try:
                stream_client.update_user(
                    {
                        "id": creator_stream_id,
                        "name": f"Usuario {creator_id}",  # Nombre genérico basado en ID
                    }
                )
                logger.info(f"[DEBUG] Usuario {creator_stream_id} creado/actualizado en Stream")
            except Exception as e:
                logger.error(f"[DEBUG] Error creando usuario en Stream: {str(e)}")
                # Verificar si el error es porque el usuario fue eliminado
                if "was deleted" in str(e):
                    user_exists_in_stream = False
                    logger.warning(f"[DEBUG] Usuario {creator_stream_id} fue eliminado en Stream. Usaremos system como alternativa.")
                # Continuamos aunque haya error para intentar crear el chat
            
            # Optimización 1: Verificar si el evento existe primero
            from app.models.event import Event
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                logger.warning(f"[DEBUG] Evento {event_id} no encontrado")
                raise ValueError(f"Evento no encontrado: {event_id}")
            
            logger.info(f"[DEBUG] Evento encontrado: id={event.id}, title={event.title}, gym_id={event.gym_id}")
            
            # Optimización 2: Buscar sala existente
            room_query_start = time.time()
            db_room = chat_repository.get_event_room(db, event_id=event_id)
            room_query_time = time.time() - room_query_start
            logger.info(f"[DEBUG] Consulta de sala: {room_query_time:.2f}s, encontrada: {bool(db_room)}")
            
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
                    logger.info(f"[DEBUG] Consulta a Stream: {stream_query_time:.2f}s")
                    
                    # Si llegamos aquí, el canal existe en Stream, verificar miembros
                    members = response.get("members", [])
                    current_members = [member.get("user_id", "") for member in members]
                    
                    # Añadir el usuario actual si no está en el canal y existe en Stream
                    if user_exists_in_stream and creator_stream_id not in current_members:
                        logger.info(f"[DEBUG] Añadiendo usuario {creator_stream_id} al canal existente")
                        try:
                            channel.add_members([creator_stream_id])
                        except Exception as e:
                            logger.warning(f"[DEBUG] No se pudo añadir miembro al canal: {e}")
                            # Continuar aunque falle la adición del miembro
                    
                    # Preparar respuesta
                    result = {
                        "id": db_room.id,
                        "stream_channel_id": db_room.stream_channel_id,
                        "stream_channel_type": db_room.stream_channel_type,
                        "event_id": event_id,
                        "members": members,
                        "created_at": db_room.created_at
                    }
                    
                    total_time = time.time() - start_time
                    logger.info(f"[DEBUG] Sala existente devuelta - tiempo total: {total_time:.2f}s")
                    return result
                    
                except Exception as e:
                    # Error al acceder al canal, lo registramos para depuración
                    logger.error(f"[DEBUG] Error al recuperar canal existente: {e}")
                    # Continuamos para crear uno nuevo
            
            # Si llegamos aquí, necesitamos crear un nuevo canal
            # (porque no existe o porque el existente dio error)
            
            # Crear sala con datos mínimos necesarios y usando ID interno
            logger.info(f"[DEBUG] Construyendo datos para nueva sala, event_id={event_id}")
            room_data = ChatRoomCreate(
                name=f"Evento {event.title[:20]}",  # Limitar el título a 20 caracteres
                is_direct=False,
                event_id=event_id,
                member_ids=[creator_id]  # Usar ID interno del creador
            )
            
            # Verificar si room_data está correctamente configurado
            logger.info(f"[DEBUG] room_data: name={room_data.name}, is_direct={room_data.is_direct}, event_id={room_data.event_id}, member_ids={room_data.member_ids}")
            
            # Si hay una sala antigua en la base de datos que no funcionó, eliminarla
            if db_room:
                logger.info(f"[DEBUG] Eliminando referencia a sala no válida: {db_room.id}")
                db.delete(db_room)
                db.commit()
            
            # Crear la sala
            try:
                # Si el usuario existe en Stream, usar su ID
                if user_exists_in_stream:
                    result = self.create_room(db, creator_id, room_data, gym_id)
                    logger.info(f"[DEBUG] Nueva sala creada - tiempo total: {time.time() - start_time:.2f}s")
                    return result
                else:
                    # Si el usuario no existe en Stream (fue eliminado), crear sala usando "system"
                    logger.info("[DEBUG] Creando sala con usuario system ya que el creador fue eliminado en Stream")
                    # Crear usuario system en Stream si no existe
                    try:
                        stream_client.update_user({
                            "id": "system",
                            "name": "System Bot",
                        })
                        logger.info("[DEBUG] Usuario system creado/actualizado en Stream")
                    except Exception as system_error:
                        logger.error(f"[DEBUG] Error creando usuario system en Stream: {system_error}")
                    
                    # Crear canal usando "system" como ID de usuario
                    channel_type = "messaging"
                    creator_hash = "system"  # Usar system en lugar del hash del creador
                    channel_id = f"event_{room_data.event_id}_{creator_hash}"
                    
                    try:
                        # Crear canal de manera manual
                        channel = stream_client.channel(channel_type, channel_id)
                        response = channel.create(user_id="system")
                        
                        if response and 'channel' in response:
                            # Guardar en base de datos local
                            db_room = chat_repository.create_room(
                                db,
                                stream_channel_id=channel_id,
                                stream_channel_type=channel_type,
                                room_data=room_data,
                                gym_id=gym_id
                            )
                            
                            return {
                                "id": db_room.id,
                                "stream_channel_id": channel_id,
                                "stream_channel_type": channel_type,
                                "event_id": event_id,
                                "name": room_data.name,
                                "members": [],
                                "created_at": db_room.created_at
                            }
                        else:
                            logger.error("[DEBUG] Respuesta inválida al crear canal con system")
                            raise ValueError("Respuesta inválida al crear canal con system")
                    except Exception as channel_error:
                        logger.error(f"[DEBUG] Error creando canal con system: {channel_error}")
                        raise
            except Exception as e:
                logger.error(f"[DEBUG] Error en create_room: {str(e)}", exc_info=True)
                raise ValueError(f"Error creando sala de chat: {str(e)}")
                
        except Exception as e:
            logger.warning(f"[DEBUG] Error de validación: {str(e)}")
            raise ValueError(f"Error creando sala de chat: {str(e)}")
    
    def add_user_to_channel(self, db: Session, room_id: int, user_id: int) -> Dict[str, Any]:
        """
        Añade un usuario a un canal de chat.
        
        Args:
            db: Sesión de base de datos
            room_id: ID de la sala
            user_id: ID interno del usuario (en tabla user)
        """
        # Verificar que la sala existe
        db_room = chat_repository.get_room(db, room_id=room_id)
        if not db_room:
            raise ValueError(f"No existe sala de chat con ID {room_id}")
        
        # Verificar que el usuario existe
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"Usuario con ID interno {user_id} no encontrado")
        
        # Verificar que el usuario tiene un auth0_id (necesario para Stream)
        if not user.auth0_id:
            raise ValueError(f"Usuario {user_id} no tiene auth0_id asignado")
        
        # Sanitizar ID de usuario para Stream
        safe_user_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user.auth0_id)
        
        try:
            # Primero añadir a la base de datos local usando ID interno
            # Si falla, no intentamos añadirlo a Stream
            chat_repository.add_member_to_room(db, room_id=room_id, user_id=user_id)
            
            # Luego intentar crear usuario en Stream antes de añadirlo al canal
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
                # Continuamos aunque haya error para intentar añadirlo al canal
            
            # Añadir a Stream usando auth0_id sanitizado
            channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
            response = channel.add_members([safe_user_id])
            
            return {
                "room_id": room_id,
                "user_id": user_id,
                "stream_response": response
            }
        except Exception as e:
            # Si hay error, intentar eliminar al usuario de la BD local si fue añadido
            try:
                chat_repository.remove_member_from_room(db, room_id=room_id, user_id=user_id)
            except:
                # Ignorar errores en la limpieza
                pass
            
            raise ValueError(f"Error añadiendo usuario al canal: {str(e)}")
    
    def remove_user_from_channel(self, db: Session, room_id: int, user_id: int) -> Dict[str, Any]:
        """
        Elimina un usuario de un canal de chat.
        
        Args:
            db: Sesión de base de datos
            room_id: ID de la sala
            user_id: ID interno del usuario (en tabla user)
        """
        # Verificar que la sala existe
        db_room = chat_repository.get_room(db, room_id=room_id)
        if not db_room:
            raise ValueError(f"No existe sala de chat con ID {room_id}")
        
        # Verificar que el usuario existe
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"Usuario con ID interno {user_id} no encontrado")
        
        # Verificar que el usuario tiene un auth0_id (necesario para Stream)
        if not user.auth0_id:
            raise ValueError(f"Usuario {user_id} no tiene auth0_id asignado")
        
        # Sanitizar ID de usuario para Stream
        safe_user_id = re.sub(r'[^a-zA-Z0-9@_\-]', '_', user.auth0_id)
        
        try:
            # Primero intentar eliminar de Stream usando auth0_id sanitizado
            # Si Stream falla, continuamos para mantener consistente la BD local
            stream_response = None
            try:
                channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
                stream_response = channel.remove_members([safe_user_id])
                logger.info(f"Usuario {safe_user_id} eliminado de Stream Chat")
            except Exception as e:
                logger.error(f"Error eliminando usuario {safe_user_id} de Stream: {str(e)}")
                # Continuamos para eliminar de la BD local
            
            # Eliminar de la base de datos local usando ID interno
            if not chat_repository.remove_member_from_room(db, room_id=room_id, user_id=user_id):
                logger.warning(f"Usuario {user_id} no encontrado en la sala {room_id} en la BD local")
            
            return {
                "room_id": room_id,
                "user_id": user_id,
                "stream_response": stream_response
            }
        except Exception as e:
            raise ValueError(f"Error eliminando usuario del canal: {str(e)}")

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

    def close_event_chat(self, db: Session, event_id: int) -> bool:
        """
        Cierra la sala de chat asociada a un evento cuando este se completa.
        
        Esta función:
        1. Busca la sala asociada al evento
        2. Envía un mensaje de sistema indicando que el evento ha finalizado
        3. Congela el canal para que no se puedan enviar más mensajes, pero mantiene 
           acceso a los usuarios para que puedan ver el histórico de conversaciones
        
        Args:
            db: Sesión de base de datos
            event_id: ID del evento cuya sala se va a cerrar
            
        Returns:
            bool: True si se cerró la sala correctamente, False si no existe o falló
        """
        logger.info(f"Intentando cerrar sala de chat para evento {event_id}")
        
        try:
            # Buscar la sala asociada al evento
            room = chat_repository.get_event_room(db, event_id=event_id)
            if not room:
                logger.warning(f"No se encontró sala de chat para el evento {event_id}")
                return False
                
            # Obtener canal de Stream
            try:
                channel = stream_client.channel(room.stream_channel_type, room.stream_channel_id)
                
                # Enviar mensaje de sistema indicando que el chat se ha cerrado
                system_message = {
                    "text": "Este evento ha finalizado. El chat ha sido archivado y no es posible enviar nuevos mensajes, pero puedes seguir viendo el historial de conversaciones.",
                    "type": "system"
                }
                
                channel.send_message(system_message, user_id="system")
                logger.info(f"Mensaje de sistema enviado al chat del evento {event_id}")
                
                # Congelar el canal para que no se puedan enviar más mensajes
                # pero los usuarios puedan seguir viendo los mensajes
                try:
                    channel.update({"frozen": True})
                    logger.info(f"Canal del evento {event_id} congelado exitosamente")
                except Exception as e:
                    logger.warning(f"No se pudo congelar el canal: {e}")
                    # Continuar aunque falle la congelación
                
                # No eliminamos a los miembros ni de Stream ni de la BD local
                # De esta forma, pueden seguir accediendo para ver el historial
                
                return True
                
            except Exception as e:
                logger.error(f"Error al cerrar sala de chat para evento {event_id} en Stream: {e}", exc_info=True)
                return False
                
        except Exception as e:
            logger.error(f"Error general al cerrar sala de chat para evento {event_id}: {e}", exc_info=True)
            return False

    def get_event_room(self, db: Session, event_id: int) -> Optional[ChatRoom]:
        """
        Obtiene la sala de chat asociada a un evento.
        
        Args:
            db: Sesión de base de datos
            event_id: ID del evento
            
        Returns:
            ChatRoom: La sala encontrada o None si no existe
        """
        try:
            return chat_repository.get_event_room(db, event_id=event_id)
        except Exception as e:
            logger.error(f"Error al buscar sala para evento {event_id}: {e}", exc_info=True)
            return None

    async def delete_channel(self, channel_type: str, channel_id: str) -> bool:
        """
        Delete a channel from Stream Chat.
        """
        try:
            await stream_client.delete_channel(channel_type, channel_id)
            return True
        except Exception as e:
            logger.error(f"Error deleting channel: {str(e)}", exc_info=True)
            return False
            
    async def get_channel_members(self, channel_type: str, channel_id: str) -> List[int]:
        """
        Get all members of a channel.
        
        Args:
            channel_type: Type of channel (messaging, gaming, etc)
            channel_id: Unique identifier of the channel
            
        Returns:
            List of internal user IDs who are members of the channel
        """
        try:
            # Usar stream_client en lugar de self.client
            channel = stream_client.channel(channel_type, channel_id)
            response = await channel.query(members={'limit': 100})  # Adjust limit if needed
            
            # Log para diagnóstico
            logger.info(f"Respuesta de channel.query: {response}")
            
            # Extract member IDs from response (stream_ids)
            if hasattr(response, 'members'):
                stream_members = [member.get('user_id') for member in response.members]
            else:
                # Si response no tiene el atributo members, intentar acceder como diccionario
                stream_members = [member.get('user_id') for member in response.get('members', [])]
            
            # Ahora necesitamos convertir los stream_ids (auth0_ids) a internal_ids
            # Usar una única consulta de base de datos para obtener todos los IDs internos
            from app.db.session import SessionLocal
            from app.models.user import User
            
            if not stream_members:
                return []
                
            db = SessionLocal()
            try:
                # Consulta para obtener los IDs internos correspondientes a los stream_ids
                internal_members = []
                users = db.query(User.id, User.auth0_id).filter(
                    User.auth0_id.in_(stream_members)
                ).all()
                
                # Crear un mapa de auth0_id -> id interno
                auth0_to_internal = {user.auth0_id: user.id for user in users}
                
                # Convertir stream_ids a internal_ids
                internal_members = [auth0_to_internal.get(stream_id) for stream_id in stream_members 
                                  if stream_id in auth0_to_internal]
                
                # Filtrar cualquier None (por si algún stream_id no tiene correspondencia)
                internal_members = [member_id for member_id in internal_members if member_id is not None]
                
                return internal_members
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"Error getting channel members: {str(e)}", exc_info=True)
            return []

    async def send_chat_notification(
        self, 
        db: Session, 
        sender_id: int, 
        chat_room: ChatRoom, 
        message_text: str,
        notification_service
    ) -> bool:
        """
        Envía notificaciones push a los miembros de un chat cuando llega un nuevo mensaje.
        
        Args:
            db: Sesión de base de datos
            sender_id: ID interno del remitente
            chat_room: Sala de chat donde se envió el mensaje
            message_text: Contenido del mensaje
            notification_service: Servicio de notificaciones
            
        Returns:
            bool: True si se enviaron notificaciones exitosamente
        """
        try:
            # Obtener el remitente
            sender = db.query(User).filter(User.id == sender_id).first()
            if not sender:
                logger.warning(f"Remitente {sender_id} no encontrado para notificación")
                return False
            
            # Obtener miembros del chat excluyendo al remitente
            members = db.query(ChatMember).filter(
                ChatMember.room_id == chat_room.id,
                ChatMember.user_id != sender_id
            ).all()
            
            if not members:
                logger.info(f"No hay destinatarios para notificar en chat {chat_room.id}")
                return True
            
            # Preparar lista de user_ids para OneSignal (usar IDs internos como string)
            recipient_ids = [str(member.user_id) for member in members]
            
            # Determinar título y mensaje de la notificación
            sender_name = getattr(sender, 'email', f"Usuario {sender.id}").split('@')[0]
            
            if chat_room.is_direct:
                title = f"💬 Nuevo mensaje de {sender_name}"
            else:
                title = f"💬 {sender_name} en {chat_room.name or 'Grupo'}"
            
            # Truncar mensaje si es muy largo
            display_message = message_text[:100] + "..." if len(message_text) > 100 else message_text
            
            # Datos adicionales para la notificación
            notification_data = {
                "type": "chat_message",
                "chat_room_id": str(chat_room.id),
                "stream_channel_id": chat_room.stream_channel_id,
                "sender_id": str(sender_id)
            }
            
            # Enviar notificación
            result = notification_service.send_to_users(
                user_ids=recipient_ids,
                title=title,
                message=display_message,
                data=notification_data,
                db=db
            )
            
            if result.get("success"):
                logger.info(f"Notificación de chat enviada a {len(recipient_ids)} usuarios")
                return True
            else:
                logger.error(f"Error enviando notificación de chat: {result.get('errors')}")
                return False
                
        except Exception as e:
            logger.error(f"Error enviando notificación de chat: {str(e)}", exc_info=True)
            return False

    async def process_message_mentions(
        self, 
        db: Session, 
        message_text: str, 
        chat_room: ChatRoom,
        sender_id: int,
        notification_service
    ) -> bool:
        """
        Procesa menciones (@usuario) en mensajes y envía notificaciones especiales.
        
        Args:
            db: Sesión de base de datos
            message_text: Contenido del mensaje
            chat_room: Sala de chat
            sender_id: ID del remitente
            notification_service: Servicio de notificaciones
            
        Returns:
            bool: True si se procesaron las menciones exitosamente
        """
        try:
            # Buscar menciones en el formato @usuario
            mentions = re.findall(r'@(\w+)', message_text)
            if not mentions:
                return True
            
            # Obtener el remitente
            sender = db.query(User).filter(User.id == sender_id).first()
            if not sender:
                return False
            
            sender_name = getattr(sender, 'email', f"Usuario {sender.id}").split('@')[0]
            
            # Buscar usuarios mencionados en el chat
            mentioned_users = []
            for mention in mentions:
                # Buscar por email (parte antes del @)
                user = db.query(User).filter(
                    User.email.like(f"{mention}%")
                ).first()
                
                if user:
                    # Verificar que el usuario esté en el chat
                    is_member = db.query(ChatMember).filter(
                        ChatMember.room_id == chat_room.id,
                        ChatMember.user_id == user.id
                    ).first()
                    
                    if is_member and user.id != sender_id:
                        mentioned_users.append(user)
            
            if not mentioned_users:
                return True
            
            # Enviar notificaciones especiales por menciones
            for user in mentioned_users:
                notification_data = {
                    "type": "chat_mention",
                    "chat_room_id": str(chat_room.id),
                    "stream_channel_id": chat_room.stream_channel_id,
                    "sender_id": str(sender_id),
                    "mentioned_user_id": str(user.id)
                }
                
                result = notification_service.send_to_users(
                    user_ids=[str(user.id)],
                    title=f"🔔 {sender_name} te mencionó",
                    message=f"En {chat_room.name or 'chat'}: {message_text[:80]}...",
                    data=notification_data,
                    db=db
                )
                
                if result.get("success"):
                    logger.info(f"Notificación de mención enviada a usuario {user.id}")
                else:
                    logger.warning(f"Error enviando notificación de mención a {user.id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error procesando menciones: {str(e)}", exc_info=True)
            return False

    async def update_chat_activity(
        self, 
        db: Session, 
        chat_room: ChatRoom, 
        sender_id: int
    ) -> bool:
        """
        Actualiza la actividad del chat (último mensaje, timestamp, etc.).
        
        Args:
            db: Sesión de base de datos
            chat_room: Sala de chat
            sender_id: ID del remitente del mensaje
            
        Returns:
            bool: True si se actualizó exitosamente
        """
        try:
            # Actualizar timestamp de último mensaje en la sala
            chat_room.updated_at = datetime.utcnow()
            
            # Actualizar el último usuario que envió mensaje
            if hasattr(chat_room, 'last_message_user_id'):
                chat_room.last_message_user_id = sender_id
            
            db.commit()
            logger.debug(f"Actividad actualizada para chat {chat_room.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando actividad del chat: {str(e)}", exc_info=True)
            db.rollback()
            return False

    def get_chat_statistics(self, db: Session, chat_room_id: int) -> Dict[str, Any]:
        """
        Obtiene estadísticas básicas de un chat.
        
        Args:
            db: Sesión de base de datos
            chat_room_id: ID de la sala de chat
            
        Returns:
            Dict con estadísticas del chat
        """
        try:
            chat_room = chat_repository.get_room_by_id(db, chat_room_id)
            if not chat_room:
                return {"error": "Chat no encontrado"}
            
            # Contar miembros
            member_count = db.query(ChatMember).filter(
                ChatMember.room_id == chat_room_id
            ).count()
            
            # Obtener información básica
            stats = {
                "room_id": chat_room_id,
                "name": chat_room.name,
                "is_direct": chat_room.is_direct,
                "member_count": member_count,
                "created_at": chat_room.created_at.isoformat() if chat_room.created_at else None,
                "updated_at": chat_room.updated_at.isoformat() if chat_room.updated_at else None,
                "stream_channel_id": chat_room.stream_channel_id
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas del chat {chat_room_id}: {str(e)}")
            return {"error": f"Error obteniendo estadísticas: {str(e)}"}


chat_service = ChatService() 