"""
Modelos de salud y tracking de usuario.

Este módulo contiene todos los modelos relacionados con:
- Historial de mediciones de salud (peso, grasa corporal, etc.)
- Sistema de metas y objetivos personales
- Logros y achievements automáticos
- Snapshots diarios para análisis de tendencias
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Date, Text, ForeignKey, Enum, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import enum
from datetime import datetime, date

from app.db.base_class import Base


class MeasurementType(str, enum.Enum):
    """Tipos de medición de salud."""
    MANUAL = "manual"          # Ingresado manualmente por el usuario
    SCALE = "scale"           # Desde báscula inteligente
    TRAINER = "trainer"       # Medido por un entrenador
    DEVICE = "device"         # Desde dispositivo wearable


class GoalType(str, enum.Enum):
    """Tipos de objetivos personales."""
    WEIGHT_LOSS = "weight_loss"         # Pérdida de peso
    WEIGHT_GAIN = "weight_gain"         # Ganancia de peso
    MUSCLE_GAIN = "muscle_gain"         # Ganancia muscular
    BODY_FAT_LOSS = "body_fat_loss"     # Pérdida de grasa corporal
    ENDURANCE = "endurance"             # Resistencia cardiovascular
    STRENGTH = "strength"               # Fuerza muscular
    ATTENDANCE = "attendance"           # Asistencia al gimnasio
    NUTRITION = "nutrition"             # Objetivos nutricionales


class GoalStatus(str, enum.Enum):
    """Estados de objetivos."""
    ACTIVE = "active"         # Objetivo activo
    COMPLETED = "completed"   # Objetivo completado
    PAUSED = "paused"        # Objetivo pausado
    CANCELLED = "cancelled"   # Objetivo cancelado
    EXPIRED = "expired"      # Objetivo expirado


class AchievementType(str, enum.Enum):
    """Tipos de logros."""
    ATTENDANCE_STREAK = "attendance_streak"     # Racha de asistencia
    WEIGHT_GOAL = "weight_goal"                 # Meta de peso alcanzada
    CLASS_MILESTONE = "class_milestone"         # Hito de clases completadas
    SOCIAL_ENGAGEMENT = "social_engagement"     # Participación social
    STRENGTH_GAIN = "strength_gain"             # Ganancia de fuerza
    ENDURANCE_MILESTONE = "endurance_milestone" # Hito de resistencia
    CONSISTENCY = "consistency"                 # Consistencia en entrenamientos


class UserHealthRecord(Base):
    """
    Registro histórico de mediciones de salud del usuario.
    
    Permite tracking detallado de peso, grasa corporal, masa muscular
    y otras métricas a lo largo del tiempo con multi-tenant support.
    """
    __tablename__ = "user_health_records"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Mediciones de salud
    weight = Column(Float, nullable=True, comment="Peso en kg")
    body_fat_percentage = Column(Float, nullable=True, comment="Porcentaje de grasa corporal")
    muscle_mass = Column(Float, nullable=True, comment="Masa muscular en kg")
    visceral_fat = Column(Float, nullable=True, comment="Grasa visceral")
    bone_mass = Column(Float, nullable=True, comment="Masa ósea en kg")
    water_percentage = Column(Float, nullable=True, comment="Porcentaje de agua corporal")
    
    # Metadata de la medición
    recorded_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    measurement_type = Column(Enum(MeasurementType), default=MeasurementType.MANUAL)
    notes = Column(Text, nullable=True, comment="Notas adicionales sobre la medición")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="health_records")
    gym = relationship("Gym")


class UserGoal(Base):
    """
    Sistema de metas y objetivos personales del usuario.
    
    Permite definir objetivos específicos con tracking automático
    de progreso y notificaciones de hitos.
    """
    __tablename__ = "user_goals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Definición del objetivo
    goal_type = Column(Enum(GoalType), nullable=False)
    title = Column(String(255), nullable=False, comment="Título personalizado del objetivo")
    description = Column(Text, nullable=True, comment="Descripción detallada")
    
    # Valores del objetivo
    target_value = Column(Float, nullable=False, comment="Valor objetivo a alcanzar")
    current_value = Column(Float, nullable=False, default=0.0, comment="Valor actual")
    start_value = Column(Float, nullable=True, comment="Valor inicial al crear el objetivo")
    unit = Column(String(50), nullable=False, comment="Unidad de medida (kg, lbs, reps, minutes)")
    
    # Timeline del objetivo
    target_date = Column(Date, nullable=True, comment="Fecha objetivo para completar")
    status = Column(Enum(GoalStatus), default=GoalStatus.ACTIVE)
    
    # Configuración
    is_public = Column(Boolean, default=False, comment="Si el objetivo es público a otros miembros")
    notifications_enabled = Column(Boolean, default=True, comment="Notificaciones de progreso")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relaciones
    user = relationship("User", back_populates="goals")
    gym = relationship("Gym")


class UserAchievement(Base):
    """
    Sistema de logros y achievements del usuario.
    
    Registra automáticamente logros basados en actividad real
    del usuario para gamificación y motivación.
    """
    __tablename__ = "user_achievements"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Definición del logro
    achievement_type = Column(Enum(AchievementType), nullable=False)
    title = Column(String(255), nullable=False, comment="Título del logro")
    description = Column(Text, nullable=False, comment="Descripción del logro")
    icon = Column(String(100), nullable=False, comment="Emoji o código de icono")
    
    # Datos del logro
    value = Column(Float, nullable=False, comment="Valor numérico del logro (ej: 30 días, 10kg)")
    unit = Column(String(50), nullable=True, comment="Unidad del valor")
    rarity = Column(String(50), default="common", comment="Rareza: common, rare, epic, legendary")
    
    # Metadata
    earned_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    is_milestone = Column(Boolean, default=False, comment="Si es un hito importante")
    points_awarded = Column(Integer, default=10, comment="Puntos otorgados por el logro")
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="achievements")
    gym = relationship("Gym")


class UserHealthSnapshot(Base):
    """
    Snapshots diarios optimizados para análisis de tendencias.
    
    Pre-calculados para queries rápidas de dashboard y análisis
    de progreso a lo largo del tiempo.
    """
    __tablename__ = "user_health_snapshots"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Fecha del snapshot (solo uno por día por usuario)
    snapshot_date = Column(Date, nullable=False, index=True)
    
    # Métricas de salud
    weight = Column(Float, nullable=True)
    bmi = Column(Float, nullable=True)
    body_fat_percentage = Column(Float, nullable=True)
    muscle_mass = Column(Float, nullable=True)
    
    # Métricas de actividad
    weekly_workouts = Column(Integer, default=0, comment="Entrenamientos en la semana")
    current_streak = Column(Integer, default=0, comment="Racha actual de días activos")
    classes_attended_week = Column(Integer, default=0)
    total_workout_minutes_week = Column(Integer, default=0)
    
    # Métricas sociales
    social_score = Column(Float, default=0.0, comment="Score social calculado")
    chat_messages_week = Column(Integer, default=0)
    
    # Campos de auditoría
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    user = relationship("User")
    gym = relationship("Gym")
    
    # Constraint único por usuario, gym y fecha
    __table_args__ = (
        {"comment": "Snapshots diarios para análisis de tendencias y performance del dashboard"}
    )