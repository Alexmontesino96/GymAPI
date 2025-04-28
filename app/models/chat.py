from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Index, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.db.base_class import Base

class ChatRoomStatus(str, enum.Enum):
    """Estado de la sala de chat."""
    ACTIVE = "ACTIVE"     # Sala activa
    CLOSED = "CLOSED"     # Sala cerrada

class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    stream_channel_id = Column(String, unique=True, index=True)
    stream_channel_type = Column(String, default="messaging")
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)
    is_direct = Column(Boolean, default=False, index=True)
    status = Column(Enum(ChatRoomStatus), default=ChatRoomStatus.ACTIVE, index=True)
    
    # Relaciones
    event = relationship("Event", back_populates="chat_rooms")
    members = relationship("ChatMember", back_populates="room")

    # Índices adicionales para optimizar las consultas más frecuentes
    __table_args__ = (
        # Índice compuesto para búsquedas de eventos
        Index('ix_chat_rooms_event_id_type', 'event_id', 'stream_channel_type'),
    )

class ChatMember(Base): 
    __tablename__ = "chat_members" 
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id")) 
    # Mantener la columna original para migración gradual
    auth0_user_id = Column(String, nullable=True)  # Auth0 ID (para retrocompatibilidad)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=True)  # ID interno (nuevo)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    room = relationship("ChatRoom", back_populates="members") 
    user = relationship("User")  # Nueva relación al usuario

    # Índices compuestos para búsquedas comunes
    __table_args__ = (
        # Para búsquedas de membresías rápidas
        Index('ix_chat_members_user_id_room_id', 'user_id', 'room_id'),
        # Para búsqueda temporal por auth0_id hasta completar la migración
        Index('ix_chat_members_auth0_user_id', 'auth0_user_id'),
    ) 