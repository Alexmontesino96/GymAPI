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
        # Asegurar que el creador está en la lista de miembros
        if creator_id not in room_data.member_ids:
            room_data.member_ids.append(creator_id)
        
        # Determinar tipo y ID para el canal
        channel_type = "messaging"
        channel_id = f"room-{room_data.name}-{creator_id}"
        
        if room_data.is_direct and len(room_data.member_ids) == 2:
            # Para chats directos, usar los IDs ordenados como ID del canal
            sorted_ids = sorted(room_data.member_ids)
            channel_id = f"dm-{sorted_ids[0]}-{sorted_ids[1]}"
        
        # Crear canal en Stream
        channel = stream_client.channel(
            channel_type, 
            channel_id,
            data={
                "name": room_data.name or "New Chat",
                "members": room_data.member_ids,
                "created_by_id": creator_id
            }
        )
        
        # Crear/guardar canal en Stream
        response = channel.create()
        
        # Guardar referencia en base de datos local
        db_room = chat_repository.create_room(
            db, 
            stream_channel_id=channel.id,
            stream_channel_type=channel.type,
            room_data=room_data
        )
        
        return {
            "id": db_room.id,
            "stream_channel_id": channel.id,
            "stream_channel_type": channel.type,
            "name": db_room.name,
            "members": response["channel"]["members"]
        }
    
    def get_or_create_direct_chat(self, db: Session, user1_id: str, user2_id: str) -> Dict[str, Any]:
        """Obtiene o crea un chat directo entre dos usuarios"""
        # Buscar chat existente
        db_room = chat_repository.get_direct_chat(db, user1_id=user1_id, user2_id=user2_id)
        
        if db_room:
            # Usar el canal existente
            channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
            response = channel.query()
            
            return {
                "id": db_room.id,
                "stream_channel_id": db_room.stream_channel_id,
                "stream_channel_type": db_room.stream_channel_type,
                "is_direct": True,
                "members": [user1_id, user2_id]
            }
        
        # Crear nuevo chat directo
        room_data = ChatRoomCreate(
            name=f"Chat {user1_id} - {user2_id}",
            is_direct=True,
            member_ids=[user1_id, user2_id]
        )
        
        return self.create_room(db, user1_id, room_data)
    
    def get_or_create_event_chat(self, db: Session, event_id: int, creator_id: str) -> Dict[str, Any]:
        """Obtiene o crea un chat para un evento"""
        # Buscar si ya existe una sala para este evento
        db_room = chat_repository.get_event_room(db, event_id=event_id)
        if db_room:
            # Ya existe, devolver información
            channel = stream_client.channel(db_room.stream_channel_type, db_room.stream_channel_id)
            response = channel.query()
            
            return {
                "id": db_room.id,
                "stream_channel_id": db_room.stream_channel_id,
                "stream_channel_type": db_room.stream_channel_type,
                "event_id": event_id,
                "members": response["members"]
            }
        
        # No existe, crear una nueva
        room_data = ChatRoomCreate(
            name=f"Evento #{event_id}",
            is_direct=False,
            event_id=event_id,
            member_ids=[creator_id]  # Inicialmente solo el creador
        )
        
        return self.create_room(db, creator_id, room_data)
    
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