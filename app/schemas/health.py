"""
Schemas para el módulo de salud y logros.

Este módulo contiene todos los schemas Pydantic para:
- Logros y achievements
- Milestones próximos
- Respuestas de endpoints de achievements
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class AchievementResponse(BaseModel):
    """Schema de respuesta para un logro individual."""
    id: int = Field(..., description="ID del logro")
    achievement_type: str = Field(..., description="Tipo de logro")
    title: str = Field(..., description="Título del logro")
    description: str = Field(..., description="Descripción del logro")
    icon: str = Field(..., description="Emoji o icono del logro")
    value: float = Field(..., description="Valor numérico del logro")
    unit: Optional[str] = Field(None, description="Unidad del valor")
    rarity: str = Field(..., description="Rareza: common, rare, epic, legendary")
    is_milestone: bool = Field(..., description="Si es un hito importante")
    points_awarded: int = Field(..., description="Puntos otorgados")
    earned_at: datetime = Field(..., description="Fecha cuando se obtuvo el logro")

    class Config:
        from_attributes = True


class AchievementsByRarity(BaseModel):
    """Logros agrupados por rareza."""
    common: List[AchievementResponse] = Field(default_factory=list, description="Logros comunes")
    rare: List[AchievementResponse] = Field(default_factory=list, description="Logros raros")
    epic: List[AchievementResponse] = Field(default_factory=list, description="Logros épicos")
    legendary: List[AchievementResponse] = Field(default_factory=list, description="Logros legendarios")


class UserAchievementsResponse(BaseModel):
    """Respuesta completa de logros del usuario."""
    user_id: int = Field(..., description="ID del usuario")
    gym_id: int = Field(..., description="ID del gimnasio")
    total_achievements: int = Field(..., description="Total de logros obtenidos")
    total_points: int = Field(..., description="Total de puntos acumulados")
    achievements_by_rarity: AchievementsByRarity = Field(..., description="Logros agrupados por rareza")
    recent_achievements: List[AchievementResponse] = Field(..., description="Últimos 5 logros obtenidos")


class NextMilestone(BaseModel):
    """Siguiente milestone/hito a desbloquear."""
    achievement_type: str = Field(..., description="Tipo de logro")
    title: str = Field(..., description="Título del milestone")
    description: str = Field(..., description="Descripción del objetivo")
    icon: str = Field(..., description="Emoji o icono")
    current_value: float = Field(..., description="Valor actual del usuario")
    target_value: float = Field(..., description="Valor objetivo para desbloquear")
    unit: str = Field(..., description="Unidad de medida")
    progress_percentage: float = Field(..., ge=0, le=100, description="Porcentaje de progreso (0-100)")
    rarity: str = Field(..., description="Rareza del milestone")
    points_to_earn: int = Field(..., description="Puntos que se obtendrán")


class NextMilestonesResponse(BaseModel):
    """Respuesta de próximos milestones a desbloquear."""
    user_id: int = Field(..., description="ID del usuario")
    gym_id: int = Field(..., description="ID del gimnasio")
    next_milestones: List[NextMilestone] = Field(..., description="Próximos milestones ordenados por cercanía")
