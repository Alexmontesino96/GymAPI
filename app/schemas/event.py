from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ValidationError
import pytz

from app.models.event import EventStatus, EventParticipationStatus, RefundPolicyType, PaymentStatusType


# Base schemas for Event
class EventBase(BaseModel):
    title: str = Field(..., max_length=100)
    description: Optional[str] = Field(None)
    start_time: datetime
    end_time: datetime
    location: Optional[str] = Field(None, max_length=100)
    max_participants: int = Field(0, description="0 significa sin límite de participantes")
    status: EventStatus = EventStatus.SCHEDULED

    # Campos de monetización
    is_paid: bool = Field(False, description="Si el evento requiere pago")
    price_cents: Optional[int] = Field(None, description="Precio en centavos (ej: 2999 = €29.99)")
    currency: Optional[str] = Field("EUR", max_length=3, description="Código de moneda ISO")
    refund_policy: Optional[RefundPolicyType] = Field(None, description="Política de reembolso del evento")
    refund_deadline_hours: Optional[int] = Field(24, description="Horas antes del evento para solicitar reembolso")
    partial_refund_percentage: Optional[int] = Field(50, ge=0, le=100, description="Porcentaje de reembolso parcial")


# Esquema para usar en CREATE con validadores estrictos
class EventCreateBase(EventBase):
    @field_validator('start_time')
    @classmethod
    def start_time_must_be_future(cls, v):
        # Validar que la fecha incluya zona horaria (ISO-8601 con Z o +00:00)
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("La fecha de inicio debe incluir zona horaria (ej. 2025-06-30T12:00:00Z)")
        now = datetime.now(tz=pytz.UTC)
        if v <= now:
            raise ValueError("La fecha de inicio debe ser posterior a la hora actual")
        return v
        
    @field_validator('end_time')
    @classmethod
    def end_time_must_be_future(cls, v, info):
        if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
            raise ValueError("La fecha de finalización debe incluir zona horaria (ej. 2025-06-30T14:00:00Z)")
        now = datetime.now(tz=pytz.UTC)
        if v <= now:
            raise ValueError("La fecha de finalización debe ser posterior a la hora actual")

        # Verificar que end_time sea posterior a start_time si start_time está presente
        values = info.data
        if 'start_time' in values and values['start_time'] is not None:
            if v <= values['start_time']:
                raise ValueError("La fecha de finalización debe ser posterior a la fecha de inicio")

        return v

    @field_validator('price_cents')
    @classmethod
    def validate_price(cls, v, info):
        values = info.data
        if values.get('is_paid') and (v is None or v <= 0):
            raise ValueError("El precio debe ser mayor a 0 para eventos de pago")
        if not values.get('is_paid') and v is not None and v > 0:
            raise ValueError("No se puede establecer precio para eventos gratuitos")
        return v

    @field_validator('refund_policy')
    @classmethod
    def validate_refund_policy(cls, v, info):
        values = info.data
        if values.get('is_paid') and v is None:
            raise ValueError("Debe especificar una política de reembolso para eventos de pago")
        if not values.get('is_paid') and v is not None:
            raise ValueError("No se puede establecer política de reembolso para eventos gratuitos")
        return v


class EventCreate(EventCreateBase):
    """Esquema para crear un evento (status fijado a SCHEDULED)."""
    first_message_chat: Optional[str] = Field(
        None,
        max_length=500,
        description="Primer mensaje enviado al crear la sala de chat del evento"
    )

    model_config = {"extra": "forbid"}


class EventUpdate(BaseModel):
    """Esquema para actualizar un evento."""
    title: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = Field(None, max_length=100)
    max_participants: Optional[int] = None
    status: Optional[EventStatus] = None

    # Campos de monetización (se pueden actualizar)
    is_paid: Optional[bool] = None
    price_cents: Optional[int] = None
    currency: Optional[str] = Field(None, max_length=3)
    refund_policy: Optional[RefundPolicyType] = None
    refund_deadline_hours: Optional[int] = None
    partial_refund_percentage: Optional[int] = Field(None, ge=0, le=100)
    
    @field_validator('start_time')
    @classmethod
    def start_time_must_be_future_if_provided(cls, v):
        if v is not None:
            if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
                raise ValueError("La fecha de inicio debe incluir zona horaria (ej. 2025-06-30T12:00:00Z)")
            now = datetime.now(tz=pytz.UTC)
            if v <= now:
                raise ValueError("La fecha de inicio debe ser posterior a la hora actual")
        return v
        
    @field_validator('end_time')
    @classmethod
    def end_time_must_be_future_if_provided(cls, v, info):
        if v is not None:
            if v.tzinfo is None or v.tzinfo.utcoffset(v) is None:
                raise ValueError("La fecha de finalización debe incluir zona horaria (ej. 2025-06-30T14:00:00Z)")
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

    # Campos de pago
    payment_status: Optional[PaymentStatusType] = None
    amount_paid_cents: Optional[int] = None
    payment_date: Optional[datetime] = None


class EventParticipationCreate(BaseModel):
    """Esquema para crear una participación en un evento."""
    event_id: int


# --- NUEVO: Bulk participation ---
class EventBulkParticipationCreate(BaseModel):
    """Registrar varios miembros (IDs internos) a un evento."""
    event_id: int = Field(..., description="ID del evento")
    user_ids: List[int] = Field(..., min_items=1, description="Lista de IDs internos de usuarios a registrar")

    model_config = {"extra": "forbid"}


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

    # Campos adicionales de pago (solo lectura)
    stripe_payment_intent_id: Optional[str] = None
    refund_date: Optional[datetime] = None
    refund_amount_cents: Optional[int] = None
    payment_expiry: Optional[datetime] = None

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

    # Campos de Stripe (solo lectura)
    stripe_product_id: Optional[str] = None
    stripe_price_id: Optional[str] = None

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


# Schema específico para la respuesta del worker (ID, gym_id, estado y fecha de finalización)
class EventWorkerResponse(BaseModel):
    """Esquema simplificado para la respuesta del endpoint del worker,
    conteniendo el ID, gym ID, estado y fecha de finalización del evento.
    """
    event_id: int = Field(..., alias='id') # Mapear 'id' del modelo a 'event_id'
    gym_id: int # Añadir gym_id
    end_time: datetime
    status: EventStatus
    
    class Config:
        from_attributes = True
        populate_by_name = True # Permite usar el alias en la creación


# Schema para respuesta de registro con información de pago
class EventParticipationWithPayment(EventParticipation):
    """Esquema de participación con información de pago si aplica."""
    # Payment Intent info para eventos de pago
    payment_required: Optional[bool] = Field(False, description="Si se requiere pago para completar el registro")
    payment_client_secret: Optional[str] = Field(None, description="Client secret del Payment Intent de Stripe")
    payment_amount: Optional[int] = Field(None, description="Monto a pagar en centavos")
    payment_currency: Optional[str] = Field(None, description="Moneda del pago")
    payment_deadline: Optional[datetime] = Field(None, description="Fecha límite para realizar el pago (solo lista de espera)")

    class Config:
        from_attributes = True


# Alias para Event usado en endpoints
EventSchema = Event
EventParticipationSchema = EventParticipation 