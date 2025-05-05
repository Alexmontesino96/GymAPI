from sqlalchemy import Column, Integer, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.db.base_class import Base

class GymModule(Base):
    """
    Modelo para representar la relación entre gimnasios (tenants) y módulos.
    Define qué módulos están activos para cada gimnasio.
    """
    __tablename__ = "gym_modules"
    
    gym_id = Column(Integer, ForeignKey("gyms.id", ondelete="CASCADE"), primary_key=True)
    module_id = Column(Integer, ForeignKey("modules.id", ondelete="CASCADE"), primary_key=True)
    active = Column(Boolean, default=True, nullable=False)
    activated_at = Column(DateTime, default=datetime.utcnow)
    deactivated_at = Column(DateTime, nullable=True)
    
    # Relaciones
    gym = relationship("Gym", back_populates="modules")
    module = relationship("Module", back_populates="gym_modules")
