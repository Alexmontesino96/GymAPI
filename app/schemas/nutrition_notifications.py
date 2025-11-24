"""
Schemas Pydantic para el sistema de notificaciones de nutrición.
"""

from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import re


class MealType(str, Enum):
    """Tipos de comida para notificaciones"""
    BREAKFAST = "breakfast"
    MID_MORNING = "mid_morning"
    LUNCH = "lunch"
    AFTERNOON = "afternoon"
    DINNER = "dinner"
    POST_WORKOUT = "post_workout"
    LATE_SNACK = "late_snack"


class NotificationType(str, Enum):
    """Tipos de notificaciones de nutrición"""
    MEAL_REMINDER = "meal_reminder"
    ACHIEVEMENT = "achievement"
    DAILY_PLAN = "daily_plan"
    CHALLENGE_UPDATE = "challenge_update"
    STREAK_MILESTONE = "streak_milestone"


# ============================================================================
# SCHEMAS DE CONFIGURACIÓN
# ============================================================================

class NotificationTimes(BaseModel):
    """Horarios de notificación por tipo de comida"""
    breakfast: str = Field(
        default="08:00",
        description="Hora para recordatorio de desayuno (formato HH:MM)"
    )
    lunch: str = Field(
        default="13:00",
        description="Hora para recordatorio de almuerzo (formato HH:MM)"
    )
    dinner: str = Field(
        default="20:00",
        description="Hora para recordatorio de cena (formato HH:MM)"
    )

    @validator('breakfast', 'lunch', 'dinner')
    def validate_time_format(cls, v):
        """Validar formato de hora HH:MM"""
        if v and not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', v):
            raise ValueError('Formato de hora inválido. Use HH:MM (ej: 08:00, 13:30)')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "breakfast": "07:30",
                "lunch": "13:00",
                "dinner": "20:30"
            }
        }


class NotificationSettingsUpdate(BaseModel):
    """Schema para actualizar configuración de notificaciones"""
    enabled: Optional[bool] = Field(
        default=None,
        description="Habilitar/deshabilitar notificaciones globalmente"
    )
    notification_times: Optional[NotificationTimes] = Field(
        default=None,
        description="Horarios personalizados para recordatorios"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "enabled": True,
                "notification_times": {
                    "breakfast": "07:30",
                    "lunch": "13:00",
                    "dinner": "20:30"
                }
            }
        }


class PlanNotificationConfig(BaseModel):
    """Configuración de notificaciones para un plan específico"""
    plan_id: int
    plan_title: str
    plan_type: str
    notifications_enabled: bool
    notification_times: NotificationTimes


class NotificationSettingsResponse(BaseModel):
    """Respuesta con configuración completa de notificaciones"""
    has_active_plans: bool
    global_enabled: bool
    default_times: NotificationTimes
    active_plans: List[PlanNotificationConfig]

    class Config:
        json_schema_extra = {
            "example": {
                "has_active_plans": True,
                "global_enabled": True,
                "default_times": {
                    "breakfast": "08:00",
                    "lunch": "13:00",
                    "dinner": "20:00"
                },
                "active_plans": [
                    {
                        "plan_id": 1,
                        "plan_title": "Plan de Pérdida de Peso",
                        "plan_type": "template",
                        "notifications_enabled": True,
                        "notification_times": {
                            "breakfast": "07:30",
                            "lunch": "13:00",
                            "dinner": "20:00"
                        }
                    }
                ]
            }
        }


class NotificationSettingsUpdateResponse(BaseModel):
    """Respuesta después de actualizar configuración"""
    success: bool
    message: str
    plan_id: Optional[int] = None
    plans_updated: Optional[int] = None
    updated_settings: Dict[str, Any]


# ============================================================================
# SCHEMAS DE NOTIFICACIONES DE PRUEBA
# ============================================================================

class TestNotificationRequest(BaseModel):
    """Request para enviar notificación de prueba"""
    notification_type: NotificationType = Field(
        default=NotificationType.MEAL_REMINDER,
        description="Tipo de notificación a probar"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "notification_type": "meal_reminder"
            }
        }


class TestNotificationResponse(BaseModel):
    """Respuesta de notificación de prueba"""
    success: bool
    message: str
    notification_type: str


# ============================================================================
# SCHEMAS DE ANALYTICS
# ============================================================================

class NotificationTypeStats(BaseModel):
    """Estadísticas por tipo de notificación"""
    sent: int = 0
    failed: int = 0


class DailyNotificationTrend(BaseModel):
    """Tendencia diaria de notificaciones"""
    date: str
    sent: int
    failed: int
    success_rate: float


class NotificationAnalyticsResponse(BaseModel):
    """Respuesta completa de analytics de notificaciones"""
    gym_id: int
    period_days: int
    total_sent: int
    total_failed: int
    success_rate: float
    by_type: Dict[str, NotificationTypeStats]
    daily_trend: List[DailyNotificationTrend]
    last_updated: str

    class Config:
        json_schema_extra = {
            "example": {
                "gym_id": 1,
                "period_days": 7,
                "total_sent": 245,
                "total_failed": 12,
                "success_rate": 95.33,
                "by_type": {
                    "breakfast": {"sent": 85, "failed": 4},
                    "lunch": {"sent": 82, "failed": 3},
                    "dinner": {"sent": 78, "failed": 5}
                },
                "daily_trend": [
                    {
                        "date": "20250124",
                        "sent": 35,
                        "failed": 2,
                        "success_rate": 94.59
                    }
                ],
                "last_updated": "2025-01-24T15:30:00"
            }
        }


# ============================================================================
# SCHEMAS DE ESTADO DE USUARIO
# ============================================================================

class UserNotificationsTodayStatus(BaseModel):
    """Estado de notificaciones enviadas hoy"""
    breakfast: bool = False
    lunch: bool = False
    dinner: bool = False


class UserNotificationStatusResponse(BaseModel):
    """Estado completo de notificaciones de un usuario"""
    user_id: int
    notifications_today: UserNotificationsTodayStatus
    last_notification: Optional[str] = None
    streak_days: int = 0
    total_notifications_received: int = 0

    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "notifications_today": {
                    "breakfast": True,
                    "lunch": True,
                    "dinner": False
                },
                "last_notification": "2025-01-24T13:00:00",
                "streak_days": 7,
                "total_notifications_received": 45
            }
        }