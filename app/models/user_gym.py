from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Enum
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
    """
    __tablename__ = "user_gyms"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)
    role = Column(Enum(GymRoleType), nullable=False, default=GymRoleType.MEMBER)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    user = relationship("User", back_populates="gyms")
    gym = relationship("Gym", back_populates="users")
    
    # Un usuario solo puede tener un rol por gimnasio
    __table_args__ = (
        UniqueConstraint('user_id', 'gym_id', name='uq_user_gym'),
    ) 