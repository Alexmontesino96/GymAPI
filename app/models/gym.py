from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import TYPE_CHECKING
from enum import Enum as PyEnum

from app.db.base_class import Base

class GymType(str, PyEnum):
    """Tipos de gimnasio soportados"""
    gym = "gym"
    personal_trainer = "personal_trainer"

# Imports condicionales para evitar referencias circulares
if TYPE_CHECKING:
    from app.models.schedule import ClassSession, Class, GymHours, GymSpecialHours, ClassParticipation
    from app.models.user_gym import UserGym
    from app.models.event import Event
    from app.models.gym_module import GymModule
    from app.models.membership import MembershipPlan

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
    timezone = Column(String(50), nullable=False, default='UTC')  # Zona horaria del gimnasio (ej: 'America/Mexico_City')
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Nuevos campos para soporte de entrenadores personales
    type = Column(SQLEnum(GymType, name="gym_type_enum"), nullable=False, default=GymType.gym, index=True)
    trainer_specialties = Column(JSON, nullable=True)  # ["Fuerza", "CrossFit", "Yoga"]
    trainer_certifications = Column(JSON, nullable=True)  # [{"name": "NASM-CPT", "year": 2020}]
    max_clients = Column(Integer, nullable=True)  # Límite de clientes activos para entrenadores
    
    # Relaciones
    users = relationship("UserGym", back_populates="gym")
    events = relationship("Event", back_populates="gym")
    classes = relationship("Class", back_populates="gym")
    class_sessions = relationship("ClassSession", back_populates="gym")
    
    # Nuevas relaciones para multi-tenant
    gym_hours = relationship("GymHours", back_populates="gym")
    special_hours = relationship("GymSpecialHours", back_populates="gym")
    class_participations = relationship("ClassParticipation", back_populates="gym") 
    
    # Relación con módulos
    modules = relationship("GymModule", back_populates="gym")
    
    # Relación con planes de membresía
    membership_planes = relationship("MembershipPlan", back_populates="gym")
    
    # Relaciones con Stripe
    stripe_account = relationship("GymStripeAccount", back_populates="gym", uselist=False)
    stripe_profiles = relationship("UserGymStripeProfile", back_populates="gym")
    
    # Relación con salas de chat
    chat_rooms = relationship("ChatRoom", back_populates="gym")
    
    # Relación con planes nutricionales
    nutrition_plans = relationship("NutritionPlan", back_populates="gym")
    
    # Relación con encuestas
    surveys = relationship("Survey", back_populates="gym")
    survey_responses = relationship("SurveyResponse", back_populates="gym")
    survey_templates = relationship("SurveyTemplate", back_populates="gym")

    # Relación con historias
    stories = relationship("Story", back_populates="gym", cascade="all, delete-orphan")

    # Relación con posts
    posts = relationship("Post", back_populates="gym", cascade="all, delete-orphan")

    # Propiedades helper para verificación de tipo
    @property
    def is_personal_trainer(self) -> bool:
        """Verifica si es un espacio de entrenador personal"""
        return self.type == GymType.personal_trainer

    @property
    def is_traditional_gym(self) -> bool:
        """Verifica si es un gimnasio tradicional"""
        return self.type == GymType.gym

    @property
    def display_name(self) -> str:
        """Retorna nombre formateado según el tipo"""
        if self.is_personal_trainer and self.name.startswith("Entrenamiento Personal "):
            return self.name.replace("Entrenamiento Personal ", "")
        return self.name

    @property
    def entity_type_label(self) -> str:
        """Label contextual para UI"""
        return "Espacio de Trabajo" if self.is_personal_trainer else "Gimnasio"