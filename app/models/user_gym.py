from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from datetime import datetime
import enum

from app.db.base_class import Base

class GymRoleType(str, enum.Enum):
    """
    Roles específicos para un usuario dentro de un gimnasio.
    """
    OWNER = "OWNER"         # Propietario del gimnasio
    ADMIN = "ADMIN"         # Administrador del gimnasio
    TRAINER = "TRAINER"     # Entrenador
    MEMBER = "MEMBER"       # Miembro regular

class UserGym(Base):
    """
    Relación entre usuarios y gimnasios.
    Un usuario puede pertenecer a múltiples gimnasios con diferentes roles.
    Ahora incluye información de membresía y pagos.
    """
    __tablename__ = "user_gyms"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)
    role = Column(Enum(GymRoleType), nullable=False, default=GymRoleType.MEMBER)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # --- Campos de Membresía ---
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    membership_expires_at = Column(DateTime, nullable=True, index=True)
    membership_type = Column(String(50), default="free", nullable=False)  # "free", "paid", "trial"
    
    # --- Campos de Stripe ---
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, index=True)
    
    # --- Metadatos adicionales ---
    last_payment_at = Column(DateTime, nullable=True)
    notes = Column(String(500), nullable=True)  # Notas administrativas
    
    # --- Campos de tracking de uso de app ---
    last_app_access = Column(DateTime, nullable=True, index=True)
    total_app_opens = Column(Integer, default=0, nullable=False)
    monthly_app_opens = Column(Integer, default=0, nullable=False)
    monthly_reset_date = Column(DateTime, nullable=True)
    
    # Relaciones
    user = relationship("User", back_populates="gyms")
    gym = relationship("Gym", back_populates="users")
    
    # Un usuario solo puede tener un rol por gimnasio
    __table_args__ = (
        UniqueConstraint('user_id', 'gym_id', name='uq_user_gym'),
    ) 