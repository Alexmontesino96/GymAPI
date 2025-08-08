from sqlalchemy import Boolean, Column, Integer, String, DateTime, Text, Enum, Float
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum

from app.db.base_class import Base


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"  # Administrador de la plataforma con acceso a todos los gimnasios
    ADMIN = "ADMIN"              # Administrador de un gimnasio específico
    TRAINER = "TRAINER"          # Entrenador
    MEMBER = "MEMBER"            # Miembro regular


class User(Base):
    __tablename__ = "user"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    first_name = Column(String, index=True, nullable=True)
    last_name = Column(String, index=True, nullable=True)
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
    color = Column(String(7), nullable=True)  # color hexadecimal para el perfil del usuario
    qr_code = Column(String, unique=True, index=True, nullable=True)  # Código QR único para cada usuario
    
    # Relaciones para multi-tenant
    gyms = relationship("UserGym", back_populates="user")
    
    # Relaciones para Stripe
    stripe_profiles = relationship("UserGymStripeProfile", back_populates="user")
    
    # Relaciones para eventos
    created_events = relationship("Event", back_populates="creator")
    event_participations = relationship("EventParticipation", back_populates="member")
    
    # Relaciones para health tracking
    health_records = relationship("UserHealthRecord", back_populates="user", cascade="all, delete-orphan")
    health_goals = relationship("UserGoal", back_populates="user", cascade="all, delete-orphan")
    achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    
    # Relaciones para nutrición
    created_nutrition_plans = relationship("NutritionPlan", back_populates="creator")
    followed_nutrition_plans = relationship("NutritionPlanFollower", back_populates="user")
    nutrition_progress = relationship("UserDailyProgress", back_populates="user")
    meal_completions = relationship("UserMealCompletion", back_populates="user") 