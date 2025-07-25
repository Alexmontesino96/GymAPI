from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from datetime import datetime
import logging

from app.models.chat import ChatRoom, ChatMember
from app.schemas.chat import ChatRoomCreate, ChatRoomUpdate

# Configurar logger
logger = logging.getLogger("chat_repository")

class ChatRepository:
    def create_room(
        self,
        db: Session,
        *,
        stream_channel_id: str,
        stream_channel_type: str,
        room_data: ChatRoomCreate,
        gym_id: int
    ) -> ChatRoom:
        """Crea una referencia local a un canal de Stream Chat"""
        logger.info(f"Iniciando creación de sala en BD: stream_id={stream_channel_id}, event_id={room_data.event_id}, gym_id={gym_id}")
        try:
            db_room = ChatRoom(
                stream_channel_id=stream_channel_id,
                stream_channel_type=stream_channel_type,
                name=room_data.name,
                gym_id=gym_id,  # Asociar sala al gimnasio
                is_direct=room_data.is_direct,
                event_id=room_data.event_id
            )
            logger.debug(f"Objeto ChatRoom creado con: {db_room.__dict__}")
            db.add(db_room)
            logger.debug("Objeto añadido a la sesión, realizando commit...")
            db.commit()
            logger.debug("Commit realizado con éxito")
            db.refresh(db_room)
            logger.debug(f"Objeto actualizado después de refresh: id={db_room.id}, event_id={db_room.event_id}, gym_id={db_room.gym_id}")
            
            # Añadir miembros usando IDs internos
            member_count = 0
            for member_id in room_data.member_ids:
                db_member = ChatMember(
                    room_id=db_room.id,
                    user_id=member_id
                )
                db.add(db_member)
                member_count += 1
            
            logger.debug(f"Añadidos {member_count} miembros, realizando commit final...")
            db.commit()
            logger.info(f"Sala creada exitosamente en BD: id={db_room.id}, event_id={db_room.event_id}, gym_id={db_room.gym_id}, stream_id={stream_channel_id}")
            
            return db_room
        except Exception as e:
            logger.error(f"Error al crear sala en BD: {str(e)}", exc_info=True)
            db.rollback()
            raise
    
    def get_room(self, db: Session, *, room_id: int) -> Optional[ChatRoom]:
        """Obtiene una sala por su ID"""
        return db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    
    def get_room_by_stream_id(self, db: Session, *, stream_channel_id: str) -> Optional[ChatRoom]:
        """Obtiene una sala por su ID de Stream"""
        return db.query(ChatRoom).filter(ChatRoom.stream_channel_id == stream_channel_id).first()
    
    def get_direct_chat(self, db: Session, *, user1_id: int, user2_id: int) -> Optional[ChatRoom]:
        """Obtiene un chat directo entre dos usuarios usando sus IDs internos"""
        # Buscar habitaciones donde ambos usuarios sean miembros
        rooms = db.query(ChatRoom).join(ChatMember).filter(
            ChatRoom.is_direct == True,
            ChatMember.user_id.in_([user1_id, user2_id])
        ).all()
        
        # Filtrar para encontrar habitaciones donde ambos usuarios son miembros
        for room in rooms:
            members = [member.user_id for member in room.members]
            if user1_id in members and user2_id in members and len(members) == 2:
                return room
        
        return None
    
    def get_user_rooms(self, db: Session, *, user_id: int) -> List[ChatRoom]:
        """Obtiene todas las salas de un usuario usando su ID interno"""
        return db.query(ChatRoom)\
                .join(ChatMember)\
                .filter(ChatMember.user_id == user_id)\
                .all()
    
    def get_event_room(self, db: Session, *, event_id: int) -> Optional[ChatRoom]:
        """Obtiene la sala asociada a un evento"""
        # Optimización: usar una consulta específica que solo obtiene la sala sin cargar miembros
        # y aprovechar el índice en event_id
        room = db.query(ChatRoom).filter(ChatRoom.event_id == event_id).first()
        logger.debug(f"Búsqueda de sala para evento {event_id}: {'encontrada' if room else 'no encontrada'}")
        return room
    
    def update_room(
        self,
        db: Session,
        *,
        db_obj: ChatRoom,
        obj_in: ChatRoomUpdate
    ) -> ChatRoom:
        """Actualiza una sala de chat"""
        from fastapi.encoders import jsonable_encoder
        update_data = jsonable_encoder(obj_in, exclude_unset=True)
        
        for field in update_data:
            setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def add_member_to_room(
        self,
        db: Session,
        *,
        room_id: int,
        user_id: int  # Ahora usando ID interno
    ) -> ChatMember:
        """Añade un miembro a una sala de chat usando su ID interno"""
        # Verificar si ya es miembro
        existing = db.query(ChatMember).filter(
            ChatMember.room_id == room_id,
            ChatMember.user_id == user_id
        ).first()
        
        if existing:
            return existing
        
        # Crear nuevo miembro
        db_member = ChatMember(
            room_id=room_id,
            user_id=user_id
        )
        db.add(db_member)
        db.commit()
        db.refresh(db_member)
        return db_member
    
    def remove_member_from_room(
        self,
        db: Session,
        *,
        room_id: int,
        user_id: int  # Ahora usando ID interno
    ) -> bool:
        """Elimina un miembro de una sala de chat usando su ID interno"""
        result = db.query(ChatMember).filter(
            ChatMember.room_id == room_id,
            ChatMember.user_id == user_id
        ).delete()
        
        db.commit()
        return result > 0

chat_repository = ChatRepository() 