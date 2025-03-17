import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class EventStatus(str, enum.Enum):
    """Estado del evento."""
    SCHEDULED = "SCHEDULED"  # Evento programado
    CANCELLED = "CANCELLED"  # Evento cancelado
    COMPLETED = "COMPLETED"  # Evento completado


class Event(Base):
    """Modelo para eventos."""
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True, nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(100), nullable=True)
    max_participants = Column(Integer, nullable=False, default=0)  # 0 = sin límite
    status = Column(Enum(EventStatus), default=EventStatus.SCHEDULED)
    
    # Relación con el creador del evento (entrenador o admin)
    creator_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    creator = relationship("User", back_populates="created_events")
    
    # Relación con los participantes (miembros)
    participants = relationship(
        "EventParticipation", 
        back_populates="event", 
        cascade="all, delete-orphan"
    )
    
    # Relación con las salas de chat
    chat_rooms = relationship("ChatRoom", back_populates="event")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class EventParticipationStatus(str, enum.Enum):
    """Estado de la participación del miembro en un evento."""
    REGISTERED = "REGISTERED"  # Usuario registrado y confirmado
    CANCELLED = "CANCELLED"    # Usuario canceló su participación
    WAITING_LIST = "WAITING_LIST"  # Usuario en lista de espera


class EventParticipation(Base):
    """Modelo para la participación de miembros en eventos."""
    __tablename__ = "event_participations"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con el evento
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False)
    event = relationship("Event", back_populates="participants")
    
    # Relación con el miembro
    member_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    member = relationship("User", back_populates="event_participations")
    
    # Estado de la participación
    status = Column(
        Enum(EventParticipationStatus), 
        default=EventParticipationStatus.REGISTERED
    )
    
    # Asistencia al evento
    attended = Column(Boolean, default=False)
    
    # Notas adicionales (por ejemplo, razón de cancelación)
    notes = Column(Text, nullable=True)
    
    registered_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    class Config:
        from_attributes = True 