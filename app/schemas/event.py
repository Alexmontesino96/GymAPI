from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationError
import pytz

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
    
    @field_validator('start_time')
    @classmethod
    def start_time_must_be_future(cls, v):
        now = datetime.now(tz=pytz.UTC)
        if v <= now:
            raise ValueError("La fecha de inicio debe ser posterior a la hora actual")
        return v
        
    @field_validator('end_time')
    @classmethod
    def end_time_must_be_future(cls, v, info):
        now = datetime.now(tz=pytz.UTC)
        if v <= now:
            raise ValueError("La fecha de finalización debe ser posterior a la hora actual")
            
        # Verificar que end_time sea posterior a start_time si start_time está presente
        values = info.data
        if 'start_time' in values and values['start_time'] is not None:
            if v <= values['start_time']:
                raise ValueError("La fecha de finalización debe ser posterior a la fecha de inicio")
                
        return v


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
    
    @field_validator('start_time')
    @classmethod
    def start_time_must_be_future_if_provided(cls, v):
        if v is not None:
            now = datetime.now(tz=pytz.UTC)
            if v <= now:
                raise ValueError("La fecha de inicio debe ser posterior a la hora actual")
        return v
        
    @field_validator('end_time')
    @classmethod
    def end_time_must_be_future_if_provided(cls, v, info):
        if v is not None:
            now = datetime.now(tz=pytz.UTC)
            if v <= now:
                raise ValueError("La fecha de finalización debe ser posterior a la hora actual")
                
            # Verificar que end_time sea posterior a start_time si start_time está presente y se proporciona
            values = info.data
            if 'start_time' in values and values['start_time'] is not None:
                if v <= values['start_time']:
                    raise ValueError("La fecha de finalización debe ser posterior a la fecha de inicio")
                    
        return v


# Base schemas for EventParticipation
class EventParticipationBase(BaseModel):
    status: EventParticipationStatus = EventParticipationStatus.REGISTERED
    attended: bool = False


class EventParticipationCreate(BaseModel):
    """Esquema para crear una participación en un evento."""
    event_id: int


class EventParticipationUpdate(BaseModel):
    """Esquema para actualizar la asistencia a un evento."""
    attended: bool = Field(..., description="Indica si el miembro asistió al evento")


# Response schemas
class EventParticipation(EventParticipationBase):
    id: int
    event_id: int
    member_id: int
    registered_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Nuevo esquema para incluir detalles del evento en la participación
class EventParticipationWithEvent(EventParticipation): 
    event: EventBase # Incluir el objeto Event completo

    class Config:
        from_attributes = True


class Event(EventBase):
    id: int
    creator_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
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