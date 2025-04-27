import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text, Enum, Boolean, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

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
    # Campo para multi-tenant
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    title = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    location = Column(String(100), nullable=True)
    max_participants = Column(Integer, nullable=False, default=0)  # 0 = sin límite
    status = Column(Enum(EventStatus), default=EventStatus.SCHEDULED, index=True)
    
    # Relación con el creador del evento (entrenador o admin)
    creator_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    creator = relationship("User", back_populates="created_events")
    
    # Relación con el gimnasio (tenant)
    gym = relationship("Gym", back_populates="events")
    
    # Relación con los participantes (miembros)
    participants = relationship(
        "EventParticipation", 
        back_populates="event", 
        cascade="all, delete-orphan"
    )
    
    # Relación con las salas de chat
    chat_rooms = relationship("ChatRoom", back_populates="event", cascade="all, delete-orphan")
    
    # Contador de intentos fallidos de completar el evento
    completion_attempts = Column(Integer, default=0, nullable=False, 
                                comment="Número de intentos fallidos de marcar el evento como completado")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Índices para mejorar consultas multi-tenant
    __table_args__ = (
        # Índice compuesto para filtrar eventos por gimnasio y estado
        Index('ix_events_gym_status', 'gym_id', 'status'),
        # Índice para búsqueda por fecha en un gimnasio específico
        Index('ix_events_gym_dates', 'gym_id', 'start_time', 'end_time'),
        # Índice para filtrar eventos por creador y gimnasio
        Index('ix_events_creator_gym', 'creator_id', 'gym_id'),
    )


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
    event_id = Column(Integer, ForeignKey("events.id"), nullable=False, index=True)
    event = relationship("Event", back_populates="participants")
    
    # Relación con el miembro
    member_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    member = relationship("User", back_populates="event_participations")
    
    # Campo para multi-tenant
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Estado de la participación
    status = Column(
        Enum(EventParticipationStatus), 
        default=EventParticipationStatus.REGISTERED,
        index=True
    )
    
    # Asistencia al evento
    attended = Column(Boolean, default=False)
    
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Índices compuestos para mejorar rendimiento
    __table_args__ = (
        # Índice compuesto para búsqueda rápida de participación de un miembro en un evento
        Index('ix_event_participation_event_member', 'event_id', 'member_id'),
        # Índice para buscar participaciones por gimnasio y estado
        Index('ix_event_participation_gym_status', 'gym_id', 'status'),
    )
    
    class Config:
        from_attributes = True 