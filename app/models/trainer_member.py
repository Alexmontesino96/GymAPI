from sqlalchemy import Column, Integer, ForeignKey, DateTime, String, Enum
from sqlalchemy.sql import func
import enum

from app.db.base_class import Base


class RelationshipStatus(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    TERMINATED = "terminated"
    PENDING = "pending"


class TrainerMemberRelationship(Base):
    id = Column(Integer, primary_key=True, index=True)
    trainer_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    
    # Estado de la relación
    status = Column(Enum(RelationshipStatus), default=RelationshipStatus.PENDING)
    
    # Fechas importantes
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    start_date = Column(DateTime(timezone=True), nullable=True)  # Fecha de inicio oficial
    end_date = Column(DateTime(timezone=True), nullable=True)  # Fecha de finalización (si aplica)
    
    # Notas y detalles
    notes = Column(String, nullable=True)  # Notas de la relación
    
    # Campos para tracking
    created_by = Column(Integer, ForeignKey("user.id"), nullable=True)  # Quién creó la relación 