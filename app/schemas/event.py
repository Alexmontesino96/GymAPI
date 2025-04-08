from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.models.event import EventStatus, EventParticipationStatus


# Base schemas for Event
class EventBase(BaseModel):
    title: str = Field(..., max_length=100)
    description: Optional[str] = Field(None)
    start_time: datetime
    end_time: datetime
    location: Optional[str] = Field(None, max_length=100)
    max_participants: int = Field(0, description="0 significa sin límite de participantes")
    status: EventStatus = EventStatus.SCHEDULED


class EventCreate(EventBase):
    """Esquema para crear un evento."""
    pass


class EventUpdate(BaseModel):
    """Esquema para actualizar un evento."""
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=100)
    max_participants: Optional[int] = None
    status: Optional[EventStatus] = None


# Base schemas for EventParticipation
class EventParticipationBase(BaseModel):
    status: EventParticipationStatus = EventParticipationStatus.REGISTERED
    notes: Optional[str] = None
    attended: bool = False


class EventParticipationCreate(EventParticipationBase):
    """Esquema para crear una participación en un evento."""
    event_id: int


class EventParticipationUpdate(BaseModel):
    """Esquema para actualizar una participación en un evento."""
    status: Optional[EventParticipationStatus] = None
    notes: Optional[str] = None
    attended: Optional[bool] = None


# Response schemas
class EventParticipation(EventParticipationBase):
    id: int
    event_id: int
    member_id: int
    registered_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Event(EventBase):
    id: int
    creator_id: int
    created_at: datetime
    updated_at: datetime
    participants_count: Optional[int] = 0

    class Config:
        from_attributes = True


class EventDetail(Event):
    """Esquema detallado de un evento, incluye participantes."""
    participants: List[EventParticipation] = []


class EventWithParticipantCount(Event):
    """Esquema para evento con conteo de participantes."""
    participants_count: int
    
    class Config:
        orm_mode = True
        from_attributes = True
        arbitrary_types_allowed = True


# Schemas for filtering and pagination
class EventsSearchParams(BaseModel):
    """Parámetros para búsqueda y filtrado de eventos."""
    status: Optional[EventStatus] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    title_contains: Optional[str] = None
    location_contains: Optional[str] = None
    created_by: Optional[int] = None  # ID del creador
    only_available: Optional[bool] = False  # Solo eventos con plazas disponibles 