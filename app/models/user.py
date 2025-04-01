from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text, Enum, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base_class import Base


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    TRAINER = "TRAINER" 
    MEMBER = "MEMBER"


class User(Base):
    __tablename__ = "user"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=True)  # Puede ser nulo si usamos Auth0
    full_name = Column(String, index=True)
    is_active = Column(Boolean(), default=True)
    is_superuser = Column(Boolean(), default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Auth0 fields
    auth0_id = Column(String, index=True, unique=True, nullable=True)
    picture = Column(String, nullable=True)
    locale = Column(String(5), nullable=True)
    auth0_metadata = Column(Text, nullable=True)  # JSON data almacenado como texto
    
    # Campos adicionales para el perfil
    role = Column(Enum(UserRole), default=UserRole.MEMBER)
    phone_number = Column(String, nullable=True)
    birth_date = Column(DateTime, nullable=True)
    height = Column(Float, nullable=True)  # altura en cm
    weight = Column(Float, nullable=True)  # peso en kg
    bio = Column(Text, nullable=True)
    goals = Column(Text, nullable=True)  # objetivos de fitness (JSON)
    health_conditions = Column(Text, nullable=True)  # condiciones de salud (JSON)
    
    # Relaciones para multi-tenant
    gyms = relationship("UserGym", back_populates="user")
    
    # Relaciones para eventos
    created_events = relationship("Event", back_populates="creator")
    event_participations = relationship("EventParticipation", back_populates="member") 