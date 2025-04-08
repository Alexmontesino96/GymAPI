from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import TYPE_CHECKING

from app.db.base_class import Base

# Imports condicionales para evitar referencias circulares
if TYPE_CHECKING:
    from app.models.schedule import ClassSession
    from app.models.user_gym import UserGym
    from app.models.event import Event

class Gym(Base):
    """
    Modelo para representar un gimnasio (tenant) en el sistema.
    Cada gimnasio tiene sus propios usuarios, eventos, clases, etc.
    """
    __tablename__ = "gyms"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(100), unique=True, nullable=False, index=True)
    logo_url = Column(String(255), nullable=True)
    address = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    users = relationship("UserGym", back_populates="gym")
    events = relationship("Event", back_populates="gym")
    # Eliminamos relaciones a modelos que no existen
    class_sessions = relationship("ClassSession", back_populates="gym") 