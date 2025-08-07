from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Time, DateTime, Text, Enum, CheckConstraint, Date
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from datetime import time, datetime
import sqlalchemy as sa

from app.db.base_class import Base


class DayOfWeek(int, enum.Enum):
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class ClassDifficultyLevel(str, enum.Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class ClassCategory(str, enum.Enum):
    CARDIO = "cardio"
    STRENGTH = "strength"
    FLEXIBILITY = "flexibility"
    HIIT = "hiit"
    YOGA = "yoga"
    PILATES = "pilates"
    FUNCTIONAL = "functional"
    OTHER = "other"


class ClassSessionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ClassParticipationStatus(str, enum.Enum):
    REGISTERED = "registered"
    ATTENDED = "attended"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class GymHours(Base):
    """Horarios de apertura y cierre del gimnasio para cada día de la semana"""
    __tablename__ = "gym_hours"
    
    id = Column(Integer, primary_key=True, index=True)
    day_of_week = Column(Integer, nullable=False)
    open_time = Column(Time, nullable=True) # Permitir NULL si is_closed es True
    close_time = Column(Time, nullable=True) # Permitir NULL si is_closed es True
    is_closed = Column(Boolean, default=False)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)  # ID del gimnasio al que pertenecen estos horarios
    
    # Relación con gimnasio
    gym = relationship("Gym")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint('day_of_week >= 0 AND day_of_week <= 6',
                       name='check_valid_day_of_week'),
    )


class GymSpecialHours(Base):
    """Horarios especiales para días específicos (festivos, eventos, etc.)"""
    __tablename__ = "gym_special_hours"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True) 
    open_time = Column(Time, nullable=True)  # Null si está cerrado
    close_time = Column(Time, nullable=True)  # Null si está cerrado
    is_closed = Column(Boolean, default=False)
    description = Column(String(255), nullable=True)  # Descripción (ej. Festivo, Evento X)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Relación con gimnasio
    gym = relationship("Gym")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("user.id"), nullable=True)
    
    # Añadir índice único compuesto
    __table_args__ = (
        sa.UniqueConstraint('gym_id', 'date', name='uq_gym_special_hours_gym_date'),
    )


class ClassCategoryCustom(Base):
    """Categorías de clases personalizables por gimnasio"""
    __tablename__ = "class_category_custom"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    color = Column(String, nullable=True)  # Código de color para mostrar en UI
    icon = Column(String, nullable=True)  # Nombre o URL del icono
    is_active = Column(Boolean, default=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)  # ID del gimnasio al que pertenece esta categoría
    
    # Relaciones
    classes = relationship("Class", back_populates="custom_category")
    gym = relationship("Gym")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("user.id"), nullable=True)


class Class(Base):
    """Definición de clases que se ofrecen"""
    __tablename__ = "class"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    duration = Column(Integer, nullable=False)  # Duración en minutos
    max_capacity = Column(Integer, nullable=False)
    difficulty_level = Column(Enum(ClassDifficultyLevel), nullable=False)
    # Se modifican los campos de categoría para permitir categorías personalizadas
    category_id = Column(Integer, ForeignKey("class_category_custom.id"), nullable=True)
    category_enum = Column(Enum(ClassCategory), nullable=True)  # Mantener por compatibilidad
    is_active = Column(Boolean, default=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)  # Añadir campo gym_id
    
    # Relaciones
    sessions = relationship("ClassSession", back_populates="class_definition")
    custom_category = relationship("ClassCategoryCustom", back_populates="classes")
    gym = relationship("Gym")  # Añadir relación con el gimnasio
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("user.id"), nullable=True)


class ClassSession(Base):
    """Sesiones específicas de clases (instancias concretas en tiempo)"""
    __tablename__ = "class_session"
    
    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("class.id"), nullable=False)
    trainer_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)  # Ahora almacena UTC
    end_time = Column(DateTime(timezone=True), nullable=False)  # Ahora almacena UTC
    room = Column(String, nullable=True)  # Sala o ubicación
    is_recurring = Column(Boolean, default=False)  # Si es una clase recurrente
    recurrence_pattern = Column(String, nullable=True)  # Patrón de recurrencia (por ejemplo, "WEEKLY:0,2,4" para lunes, miércoles, viernes)
    status = Column(Enum(ClassSessionStatus), default=ClassSessionStatus.SCHEDULED)
    current_participants = Column(Integer, default=0)
    override_capacity = Column(Integer, nullable=True) # Capacidad específica para esta sesión, si es diferente a la de la clase
    notes = Column(Text, nullable=True)
    
    # Relaciones
    class_definition = relationship("Class", back_populates="sessions")
    participations = relationship("ClassParticipation", back_populates="session")
    gym = relationship("Gym", back_populates="class_sessions")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("user.id"), nullable=True)


class ClassParticipation(Base):
    """Participación de miembros en sesiones de clase"""
    __tablename__ = "class_participation"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("class_session.id"), nullable=False)
    member_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False)  # ID del gimnasio para habilitar filtrado multi-tenant
    status = Column(Enum(ClassParticipationStatus), default=ClassParticipationStatus.REGISTERED)
    registration_time = Column(DateTime(timezone=True), server_default=func.now())
    attendance_time = Column(DateTime(timezone=True), nullable=True)  # Cuando se registró la asistencia
    cancellation_time = Column(DateTime(timezone=True), nullable=True)  # Cuando se canceló
    cancellation_reason = Column(String, nullable=True)
    
    # Relaciones
    session = relationship("ClassSession", back_populates="participations")
    gym = relationship("Gym")  # Relación con el gimnasio
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now()) 