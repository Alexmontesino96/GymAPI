from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import TYPE_CHECKING

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.gym_module import GymModule

class Module(Base):
    """
    Modelo para representar los módulos o funcionalidades disponibles en el sistema.
    Cada módulo puede estar activo o inactivo para diferentes gimnasios (tenants).
    """
    __tablename__ = "modules"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    is_premium = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    gym_modules = relationship("GymModule", back_populates="module")
