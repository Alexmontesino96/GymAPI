from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Boolean, Index
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base

class ChatRoom(Base):
    __tablename__ = "chat_rooms"
    
    id = Column(Integer, primary_key=True, index=True)
    stream_channel_id = Column(String, unique=True, index=True)
    stream_channel_type = Column(String, default="messaging")
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    event_id = Column(Integer, ForeignKey("events.id"), nullable=True, index=True)
    is_direct = Column(Boolean, default=False, index=True)
    
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
    user_id = Column(String, nullable=False)  # Auth0 ID
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    room = relationship("ChatRoom", back_populates="members") 