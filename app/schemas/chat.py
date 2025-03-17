from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from datetime import datetime

# Esquemas para salas de chat
class ChatRoomBase(BaseModel):
    name: Optional[str] = None
    is_direct: bool = False
    event_id: Optional[int] = None

class ChatRoomCreate(ChatRoomBase):
    member_ids: List[str]  # Lista de Auth0 IDs

class ChatRoomUpdate(BaseModel):
    name: Optional[str] = None

class ChatRoom(ChatRoomBase):
    id: int
    stream_channel_id: str
    stream_channel_type: str
    created_at: datetime
    
    class Config:
        from_attributes = True

# Esquemas para miembros de chat
class ChatMemberBase(BaseModel):
    user_id: str

class ChatMemberCreate(ChatMemberBase):
    room_id: int

class ChatMember(ChatMemberBase):
    id: int
    room_id: int
    joined_at: datetime
    
    class Config:
        from_attributes = True

# Esquemas para tokens de Stream
class StreamTokenResponse(BaseModel):
    token: str
    api_key: str
    user_id: str

# Esquemas para mensajes
class StreamMessageSend(BaseModel):
    text: str
    attachments: Optional[List[Dict[str, Any]]] = None
    mentioned_users: Optional[List[str]] = None 