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
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)  # Asociación al gimnasio
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_message_at = Column(DateTime, nullable=True)
    last_message_text = Column(String(200), nullable=True)
    last_message_sender_id = Column(Integer, ForeignKey("user.id"), nullable=True)
    last_message_type = Column(String(20), default="text", nullable=True)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)
    is_direct = Column(Boolean, default=False, index=True)
    status = Column(Enum(ChatRoomStatus), default=ChatRoomStatus.ACTIVE, index=True)
    
    # Relaciones
    gym = relationship("Gym", back_populates="chat_rooms")
    event = relationship("Event", back_populates="chat_rooms")
    members = relationship("ChatMember", back_populates="room")

    # Índices adicionales para optimizar las consultas más frecuentes
    __table_args__ = (
        # Índice compuesto para búsquedas de eventos
        Index('ix_chat_rooms_event_id_type', 'event_id', 'stream_channel_type'),
        # Índice compuesto para búsquedas por gimnasio
        Index('ix_chat_rooms_gym_id_status', 'gym_id', 'status'),
    )

class ChatMember(Base): 
    __tablename__ = "chat_members" 
    
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("chat_rooms.id")) 
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)  # ID interno
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    room = relationship("ChatRoom", back_populates="members") 
    user = relationship("User")  # Relación al usuario

    # Índices compuestos para búsquedas comunes
    __table_args__ = (
        # Para búsquedas de membresías rápidas
        Index('ix_chat_members_user_id_room_id', 'user_id', 'room_id'),
    ) 