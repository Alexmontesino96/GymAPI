from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# Esquemas para salas de chat
class ChatRoomBase(BaseModel):
    name: Optional[str] = None
    is_direct: bool = False
    event_id: Optional[int] = None

class ChatRoomCreate(ChatRoomBase):
    member_ids: List[int]  # Lista de user_ids internos (cambiado de Auth0 IDs)

class ChatRoomUpdate(BaseModel):
    name: Optional[str] = None

class ChatRoom(ChatRoomBase):
    id: int
    stream_channel_id: str
    stream_channel_type: str
    created_at: datetime
    last_message_at: Optional[datetime] = None
    last_message_text: Optional[str] = None
    last_message_sender_id: Optional[int] = None
    last_message_type: Optional[str] = "text"
    
    class Config:
        from_attributes = True

# Esquemas para miembros de chat
class ChatMemberBase(BaseModel):
    user_id: int  # ID interno del usuario (cambiado de Auth0 ID)

class ChatMemberCreate(ChatMemberBase):
    room_id: int

class ChatMember(ChatMemberBase):
    id: int
    room_id: int
    joined_at: datetime
    auth0_user_id: Optional[str] = None  # Campo adicional para retrocompatibilidad
    
    class Config:
        from_attributes = True

# Esquemas para tokens de Stream
class StreamTokenResponse(BaseModel):
    token: str
    api_key: str
    internal_user_id: int  # ID interno para uso en la aplicación

# Esquemas para mensajes
class StreamMessageSend(BaseModel):
    text: str
    attachments: Optional[List[Dict[str, Any]]] = None
    mentioned_users: Optional[List[int]] = None  # Cambiado a IDs internos

class StreamMessageResponse(BaseModel):
    message_id: str
    text: str
    user_id: str  # ID de usuario en Stream (auth0_id)
    internal_user_id: Optional[int] = None  # ID interno del usuario
    created_at: datetime
    attachments: Optional[List[Dict[str, Any]]] = None
    mentioned_users: Optional[List[Dict[str, Any]]] = None 