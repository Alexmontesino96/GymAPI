"""
Esquemas para estadísticas de usuario y dashboard.

Este módulo define todos los modelos Pydantic para el sistema de estadísticas
comprehensivas del usuario, incluyendo métricas de fitness, eventos, social
y análisis de tendencias.
"""

from typing import List, Dict, Any, Optional, Union
from datetime import datetime
from datetime import date as DateType
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class PeriodType(str, Enum):
    """Tipos de períodos para análisis estadístico."""
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"


class TrendDirection(str, Enum):
    """Direcciones de tendencia."""
    increasing = "increasing"
    decreasing = "decreasing"
    stable = "stable"


class GoalStatus(str, Enum):
    """Estados de objetivos personales."""
    on_track = "on_track"
    behind = "behind"
    ahead = "ahead"
    completed = "completed"


class BMICategory(str, Enum):
    """Categorías de IMC."""
    underweight = "underweight"
    normal = "normal"
    overweight = "overweight"
    obese = "obese"


# === Métricas Básicas ===

class FitnessMetrics(BaseModel):
    """Métricas de fitness y actividad física."""
    classes_attended: int = Field(..., description="Clases asistidas en el período")
    classes_scheduled: int = Field(..., description="Clases programadas")
    attendance_rate: float = Field(..., ge=0, le=100, description="Tasa de asistencia en porcentaje")
    total_workout_hours: float = Field(..., ge=0, description="Total de horas de entrenamiento")
    average_session_duration: float = Field(..., ge=0, description="Duración promedio de sesión en minutos")
    streak_current: int = Field(..., ge=0, description="Racha actual de días activos")
    streak_longest: int = Field(..., ge=0, description="Racha más larga de días activos")
    favorite_class_types: List[str] = Field(default_factory=list, description="Tipos de clase favoritos")
    peak_workout_times: List[str] = Field(default_factory=list, description="Horarios pico de entrenamiento")
    calories_burned_estimate: Optional[int] = Field(None, ge=0, description="Estimación de calorías quemadas")

    @field_validator('attendance_rate')
    @classmethod
    def validate_attendance_rate(cls, v):
        """Validar que el porcentaje esté entre 0 y 100."""
        if v < 0 or v > 100:
            raise ValueError('Attendance rate must be between 0 and 100')
        return v


class EventsMetrics(BaseModel):
    """Métricas de participación en eventos."""
    events_attended: int = Field(..., ge=0, description="Eventos asistidos")
    events_registered: int = Field(..., ge=0, description="Eventos registrados")
    events_created: int = Field(..., ge=0, description="Eventos creados (si es trainer/admin)")
    attendance_rate: float = Field(..., ge=0, le=100, description="Tasa de asistencia a eventos")
    favorite_event_types: List[str] = Field(default_factory=list, description="Tipos de evento favoritos")

    @field_validator('attendance_rate')
    @classmethod
    def validate_attendance_rate(cls, v):
        """Validar que el porcentaje esté entre 0 y 100."""
        if v < 0 or v > 100:
            raise ValueError('Event attendance rate must be between 0 and 100')
        return v


class SocialMetrics(BaseModel):
    """Métricas de actividad social y chat."""
    chat_messages_sent: int = Field(..., ge=0, description="Mensajes de chat enviados")
    chat_rooms_active: int = Field(..., ge=0, description="Salas de chat activas")
    social_score: float = Field(..., ge=0, le=10, description="Puntuación social (0-10)")
    trainer_interactions: int = Field(..., ge=0, description="Interacciones con entrenadores")

    @field_validator('social_score')
    @classmethod
    def validate_social_score(cls, v):
        """Validar que la puntuación esté entre 0 y 10."""
        if v < 0 or v > 10:
            raise ValueError('Social score must be between 0 and 10')
        return v


class AppUsageMetrics(BaseModel):
    """Métricas de uso de la aplicación."""
    last_access: Optional[datetime] = Field(None, description="Último acceso")
    total_sessions: int = Field(0, ge=0, description="Total de sesiones")
    sessions_this_month: int = Field(0, ge=0, description="Sesiones este mes")
    avg_sessions_per_week: float = Field(0, ge=0, description="Promedio semanal")
    consecutive_days: int = Field(0, ge=0, description="Días consecutivos de uso")
    is_active_today: bool = Field(False, description="Accedió hoy")


class GoalProgress(BaseModel):
    """Progreso de un objetivo específico."""
    goal_id: int = Field(..., description="ID del objetivo")
    goal_type: str = Field(..., description="Tipo de objetivo")
    target_value: float = Field(..., description="Valor objetivo")
    current_value: float = Field(..., description="Valor actual")
    progress_percentage: float = Field(..., ge=0, le=100, description="Porcentaje de progreso")
    status: GoalStatus = Field(..., description="Estado del objetivo")

    @field_validator('progress_percentage')
    @classmethod
    def validate_progress_percentage(cls, v):
        """Validar que el porcentaje esté entre 0 y 100."""
        if v < 0 or v > 100:
            raise ValueError('Progress percentage must be between 0 and 100')
        return v


class HealthMetrics(BaseModel):
    """Métricas de salud y bienestar."""
    current_weight: Optional[float] = Field(None, gt=0, description="Peso actual en kg")
    current_height: Optional[float] = Field(None, gt=0, description="Altura actual en cm")
    bmi: Optional[float] = Field(None, ge=10, le=50, description="Índice de masa corporal")
    bmi_category: Optional[BMICategory] = Field(None, description="Categoría de IMC")
    weight_change: Optional[float] = Field(None, description="Cambio de peso en el período")
    goals_progress: List[GoalProgress] = Field(default_factory=list, description="Progreso de objetivos")


class MembershipUtilization(BaseModel):
    """Utilización y valor de la membresía."""
    plan_name: str = Field(..., description="Nombre del plan de membresía")
    utilization_rate: float = Field(..., ge=0, le=100, description="Tasa de utilización en porcentaje")
    value_score: float = Field(..., ge=0, le=10, description="Puntuación de valor obtenido (0-10)")
    days_until_renewal: Optional[int] = Field(None, ge=0, description="Días hasta renovación")
    recommended_actions: List[str] = Field(default_factory=list, description="Acciones recomendadas")

    @field_validator('utilization_rate')
    @classmethod
    def validate_utilization_rate(cls, v):
        """Validar que el porcentaje esté entre 0 y 100."""
        if v < 0 or v > 100:
            raise ValueError('Utilization rate must be between 0 and 100')
        return v

    @field_validator('value_score')
    @classmethod
    def validate_value_score(cls, v):
        """Validar que la puntuación esté entre 0 y 10."""
        if v < 0 or v > 10:
            raise ValueError('Value score must be between 0 and 10')
        return v


class Achievement(BaseModel):
    """Logro o badge obtenido."""
    id: int = Field(..., description="ID del logro")
    type: str = Field(..., description="Tipo de logro")
    name: str = Field(..., description="Nombre del logro")
    description: str = Field(..., description="Descripción del logro")
    earned_at: datetime = Field(..., description="Fecha y hora de obtención")
    badge_icon: str = Field(..., description="Icono del badge")


class TrendAnalysis(BaseModel):
    """Análisis de tendencias."""
    attendance_trend: TrendDirection = Field(..., description="Tendencia de asistencia")
    workout_intensity_trend: TrendDirection = Field(..., description="Tendencia de intensidad")
    social_engagement_trend: TrendDirection = Field(..., description="Tendencia de engagement social")


# === Respuestas de Endpoints ===

class DashboardSummary(BaseModel):
    """Resumen rápido para dashboard principal (ultra optimizado)."""
    user_id: int = Field(..., description="ID del usuario")
    current_streak: int = Field(..., ge=0, description="Racha actual de días")
    weekly_workouts: int = Field(..., ge=0, description="Entrenamientos esta semana")
    monthly_goal_progress: float = Field(..., ge=0, le=100, description="Progreso del objetivo mensual")
    next_class: Optional[str] = Field(None, description="Próxima clase programada")
    recent_achievement: Optional[Achievement] = Field(None, description="Logro más reciente")
    membership_status: str = Field(..., description="Estado de membresía")
    last_attendance_date: Optional[datetime] = Field(None, description="Fecha y hora de la última asistencia")
    has_attended_first_class: bool = Field(False, description="Indica si el usuario ha asistido a su primera clase")
    quick_stats: Dict[str, Union[int, float, str]] = Field(
        default_factory=dict,
        description="Estadísticas rápidas clave"
    )


class ComprehensiveUserStats(BaseModel):
    """Estadísticas comprehensivas del usuario."""
    user_id: int = Field(..., description="ID del usuario")
    period: PeriodType = Field(..., description="Período de análisis")
    period_start: datetime = Field(..., description="Inicio del período")
    period_end: datetime = Field(..., description="Fin del período")
    fitness_metrics: FitnessMetrics = Field(..., description="Métricas de fitness")
    events_metrics: EventsMetrics = Field(..., description="Métricas de eventos")
    social_metrics: SocialMetrics = Field(..., description="Métricas sociales")
    health_metrics: HealthMetrics = Field(..., description="Métricas de salud")
    membership_utilization: MembershipUtilization = Field(..., description="Utilización de membresía")
    app_usage: Optional[AppUsageMetrics] = Field(None, description="Métricas de uso de app")
    achievements: List[Achievement] = Field(default_factory=list, description="Logros obtenidos")
    trends: TrendAnalysis = Field(..., description="Análisis de tendencias")
    recommendations: List[str] = Field(default_factory=list, description="Recomendaciones personalizadas")


class WeeklyBreakdown(BaseModel):
    """Desglose diario de una semana."""
    date: DateType = Field(..., description="Fecha del día")
    day_name: str = Field(..., description="Nombre del día")
    workouts: int = Field(..., ge=0, description="Entrenamientos realizados")
    duration_minutes: int = Field(..., ge=0, description="Duración total en minutos")
    classes: List[str] = Field(default_factory=list, description="Clases asistidas")
    events: List[str] = Field(default_factory=list, description="Eventos asistidos")
    chat_activity: int = Field(..., ge=0, description="Actividad de chat")
    energy_level: Optional[int] = Field(None, ge=1, le=10, description="Nivel de energía autoreportado")


class WeeklyGoal(BaseModel):
    """Objetivo semanal y su progreso."""
    goal_type: str = Field(..., description="Tipo de objetivo semanal")
    target: Union[int, float] = Field(..., description="Valor objetivo")
    achieved: Union[int, float] = Field(..., description="Valor logrado")
    status: str = Field(..., description="Estado del objetivo")


class WeeklySummary(BaseModel):
    """Resumen semanal detallado."""
    user_id: int = Field(..., description="ID del usuario")
    week_start: datetime = Field(..., description="Inicio de la semana")
    week_end: datetime = Field(..., description="Fin de la semana")
    week_number: int = Field(..., ge=1, le=53, description="Número de semana del año")
    summary: Dict[str, Union[int, float, bool]] = Field(..., description="Resumen general de la semana")
    daily_breakdown: List[WeeklyBreakdown] = Field(..., description="Desglose día por día")
    week_goals: List[WeeklyGoal] = Field(default_factory=list, description="Objetivos de la semana")
    compared_to_average: Dict[str, float] = Field(
        default_factory=dict, 
        description="Comparación con promedios históricos"
    )


class MonthlyDataPoint(BaseModel):
    """Punto de datos mensual para análisis de tendencias."""
    month: str = Field(..., description="Mes en formato YYYY-MM")
    workouts: int = Field(..., ge=0, description="Total de entrenamientos")
    hours: float = Field(..., ge=0, description="Total de horas")
    attendance_rate: float = Field(..., ge=0, le=100, description="Tasa de asistencia")
    weight: Optional[float] = Field(None, gt=0, description="Peso promedio del mes")
    avg_session_duration: float = Field(..., ge=0, description="Duración promedio de sesión")


class TrendMetric(BaseModel):
    """Métrica de tendencia con dirección y confianza."""
    direction: TrendDirection = Field(..., description="Dirección de la tendencia")
    rate: float = Field(..., description="Tasa de cambio")
    confidence: float = Field(..., ge=0, le=100, description="Nivel de confianza en porcentaje")


class SeasonalPatterns(BaseModel):
    """Patrones estacionales de actividad."""
    best_month: str = Field(..., description="Mejor mes histórico")
    worst_month: str = Field(..., description="Peor mes histórico")
    peak_days: List[str] = Field(..., description="Días de mayor actividad")
    preferred_times: List[str] = Field(..., description="Horarios preferidos")


class NextMonthPrediction(BaseModel):
    """Predicción para el próximo mes."""
    expected_workouts: int = Field(..., ge=0, description="Entrenamientos esperados")
    confidence_range: List[int] = Field(..., description="Rango de confianza [min, max]")
    recommended_goals: Dict[str, Union[int, float]] = Field(..., description="Objetivos recomendados")


class Forecasting(BaseModel):
    """Pronósticos y predicciones."""
    next_month_prediction: NextMonthPrediction = Field(..., description="Predicción del próximo mes")


class MonthlyTrends(BaseModel):
    """Análisis de tendencias mensuales."""
    user_id: int = Field(..., description="ID del usuario")
    analysis_period: Dict[str, Union[datetime, int]] = Field(..., description="Período de análisis")
    monthly_data: List[MonthlyDataPoint] = Field(..., description="Datos mensuales")
    trends: Dict[str, TrendMetric] = Field(..., description="Métricas de tendencia")
    seasonal_patterns: SeasonalPatterns = Field(..., description="Patrones estacionales")
    forecasting: Forecasting = Field(..., description="Pronósticos")


# === Validadores están ahora dentro de cada clase específica ===