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


class RefundPolicyType(str, enum.Enum):
    """Política de reembolso para eventos de pago."""
    NO_REFUND = "NO_REFUND"          # Sin reembolso
    FULL_REFUND = "FULL_REFUND"      # Reembolso completo
    PARTIAL_REFUND = "PARTIAL_REFUND"  # Reembolso parcial
    CREDIT = "CREDIT"                 # Crédito para otros eventos


class PaymentStatusType(str, enum.Enum):
    """Estado del pago de una participación."""
    PENDING = "PENDING"    # Pago pendiente
    PAID = "PAID"          # Pagado
    REFUNDED = "REFUNDED"  # Reembolsado
    CREDITED = "CREDITED"  # Crédito otorgado
    EXPIRED = "EXPIRED"    # Expiró el tiempo para pagar (lista de espera)


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

    # Campos de monetización
    is_paid = Column(Boolean, default=False, nullable=False, index=True)
    price_cents = Column(Integer, nullable=True)  # Precio en centavos (ej: 2999 = €29.99)
    currency = Column(String(3), default="EUR", nullable=True)
    refund_policy = Column(Enum(RefundPolicyType), nullable=True)
    refund_deadline_hours = Column(Integer, default=24, nullable=True)  # Horas antes del evento para reembolso
    partial_refund_percentage = Column(Integer, default=50, nullable=True)  # % de reembolso parcial

    # Integración con Stripe (se poblará cuando se cree el producto)
    stripe_product_id = Column(String(255), nullable=True, index=True)
    stripe_price_id = Column(String(255), nullable=True, index=True)

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
    
    # Relación con respuestas de encuestas (para feedback post-evento)
    survey_responses = relationship("SurveyResponse", back_populates="event")
    
    # Contador de intentos fallidos de completar el evento
    completion_attempts = Column(Integer, default=0, nullable=False,
                                comment="Número de intentos fallidos de marcar el evento como completado")

    # Campos de auditoría de cancelación
    cancellation_date = Column(DateTime(timezone=True), nullable=True,
                              comment="Fecha en que el evento fue cancelado")
    cancelled_by_user_id = Column(Integer, ForeignKey("user.id"), nullable=True, index=True,
                                  comment="ID del usuario que canceló el evento (admin/owner)")
    cancellation_reason = Column(Text, nullable=True,
                                comment="Razón de la cancelación del evento")
    total_refunded_cents = Column(Integer, nullable=True,
                                 comment="Total de dinero reembolsado en cancelación masiva (en centavos)")

    # Relación con el usuario que canceló
    cancelled_by = relationship("User", foreign_keys=[cancelled_by_user_id])

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
    REGISTERED = "REGISTERED"  # Usuario registrado y confirmado (ocupa plaza)
    PENDING_PAYMENT = "PENDING_PAYMENT"  # Esperando confirmación de pago (NO ocupa plaza)
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

    # Campos de pago
    payment_status = Column(Enum(PaymentStatusType), default=PaymentStatusType.PENDING, nullable=True, index=True)
    stripe_payment_intent_id = Column(String(255), nullable=True, index=True)
    amount_paid_cents = Column(Integer, nullable=True)  # Monto pagado en centavos
    payment_date = Column(DateTime(timezone=True), nullable=True)
    refund_date = Column(DateTime(timezone=True), nullable=True)
    refund_amount_cents = Column(Integer, nullable=True)  # Monto reembolsado
    payment_expiry = Column(DateTime(timezone=True), nullable=True)  # Fecha límite para pagar (lista de espera)

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