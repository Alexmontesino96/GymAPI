"""
Schemas de Pydantic para el sistema de historias.
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# Enums
class StoryType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    TEXT = "text"
    WORKOUT = "workout"
    ACHIEVEMENT = "achievement"


class StoryPrivacy(str, Enum):
    PUBLIC = "public"
    FOLLOWERS = "followers"
    CLOSE_FRIENDS = "close_friends"
    PRIVATE = "private"


# Base schemas
class StoryBase(BaseModel):
    """Schema base para historias"""
    caption: Optional[str] = Field(None, max_length=500, description="Caption o texto de la historia")
    story_type: StoryType = Field(..., description="Tipo de historia")
    privacy: StoryPrivacy = Field(StoryPrivacy.PUBLIC, description="Nivel de privacidad")


class StoryCreate(StoryBase):
    """Schema para crear una historia"""
    media_url: Optional[HttpUrl] = Field(None, description="URL de media si ya está subida")
    workout_data: Optional[Dict[str, Any]] = Field(None, description="Datos del entrenamiento")
    duration_hours: int = Field(24, ge=1, le=48, description="Duración en horas antes de expirar")

    @validator('media_url', always=True)
    def validate_media_url(cls, v, values):
        """Validar que media_url es requerida para tipos image/video"""
        story_type = values.get('story_type')
        if story_type in [StoryType.IMAGE, StoryType.VIDEO] and not v:
            raise ValueError(f"media_url es requerida para historias de tipo {story_type}")
        return v

    @validator('workout_data', always=True)
    def validate_workout_data(cls, v, values):
        """Validar workout_data para historias de tipo workout"""
        story_type = values.get('story_type')
        if story_type == StoryType.WORKOUT and not v:
            raise ValueError("workout_data es requerida para historias de tipo workout")
        return v

    class Config:
        schema_extra = {
            "example": {
                "story_type": "image",
                "caption": "Nuevo PR en sentadilla! 💪",
                "privacy": "public",
                "media_url": "https://cdn.example.com/story.jpg",
                "duration_hours": 24
            }
        }


class StoryUpdate(BaseModel):
    """Schema para actualizar una historia"""
    caption: Optional[str] = Field(None, max_length=500)
    privacy: Optional[StoryPrivacy] = None


class StoryInDBBase(StoryBase):
    """Schema base para historias en BD"""
    id: int
    gym_id: int
    user_id: int
    stream_activity_id: Optional[str]
    media_url: Optional[str]
    thumbnail_url: Optional[str]
    workout_data: Optional[Dict[str, Any]]
    view_count: int = 0
    reaction_count: int = 0
    is_pinned: bool = False
    created_at: datetime
    expires_at: datetime

    class Config:
        orm_mode = True


class Story(StoryInDBBase):
    """Schema completo de historia para respuestas"""
    is_expired: bool = Field(..., description="Si la historia ha expirado")
    user_info: Optional[Dict[str, Any]] = Field(None, description="Información del usuario")
    is_own_story: bool = Field(False, description="Si es historia propia del usuario actual")
    has_viewed: bool = Field(False, description="Si el usuario actual ya vio esta historia")
    has_reacted: bool = Field(False, description="Si el usuario actual ya reaccionó")

    @validator('is_expired', always=True)
    def calculate_is_expired(cls, v, values):
        """Calcular si la historia ha expirado"""
        if values.get('is_pinned'):
            return False
        expires_at = values.get('expires_at')
        if expires_at:
            return datetime.utcnow() > expires_at
        return False


class StoryResponse(Story):
    """Schema de respuesta para historias"""
    pass


class StoryListResponse(BaseModel):
    """Schema para lista de historias"""
    stories: List[Story]
    total: int
    has_more: bool
    next_offset: Optional[int]


# View schemas
class StoryViewCreate(BaseModel):
    """Schema para marcar una historia como vista"""
    view_duration_seconds: Optional[int] = Field(None, ge=0, description="Duración de visualización en segundos")
    device_info: Optional[str] = Field(None, max_length=100, description="Información del dispositivo")


class StoryView(BaseModel):
    """Schema para visualización de historia"""
    id: int
    story_id: int
    viewer_id: int
    viewed_at: datetime
    view_duration_seconds: Optional[int]
    device_info: Optional[str]
    viewer_info: Optional[Dict[str, Any]]

    class Config:
        orm_mode = True


class StoryViewerResponse(BaseModel):
    """Schema para lista de usuarios que vieron una historia"""
    viewer_id: int
    viewer_name: str
    viewer_avatar: Optional[str]
    viewed_at: datetime
    view_duration_seconds: Optional[int]


# Reaction schemas
class StoryReactionCreate(BaseModel):
    """Schema para crear una reacción"""
    emoji: str = Field(..., min_length=1, max_length=10, description="Emoji de reacción")
    message: Optional[str] = Field(None, max_length=500, description="Mensaje opcional")

    @validator('emoji')
    def validate_emoji(cls, v):
        """Validar que sea un emoji válido"""
        # Lista de emojis permitidos
        allowed_emojis = ["💪", "🔥", "❤️", "👏", "💯", "🎯", "⚡", "🏆", "💥", "🙌"]
        if v not in allowed_emojis:
            # Si no está en la lista, verificar que sea un emoji unicode válido
            if not (len(v) <= 10 and any(ord(char) > 127 for char in v)):
                raise ValueError(f"Emoji inválido: {v}")
        return v

    class Config:
        schema_extra = {
            "example": {
                "emoji": "💪",
                "message": "Increíble progreso! Sigue así!"
            }
        }


class StoryReaction(BaseModel):
    """Schema para reacción de historia"""
    id: int
    story_id: int
    user_id: int
    emoji: str
    message: Optional[str]
    created_at: datetime
    user_info: Optional[Dict[str, Any]]

    class Config:
        orm_mode = True


class StoryReactionResponse(BaseModel):
    """Respuesta al crear una reacción"""
    success: bool
    reaction_id: int
    message: str = "Reacción agregada exitosamente"


# Report schemas
class StoryReportCreate(BaseModel):
    """Schema para reportar una historia"""
    reason: str = Field(..., description="Razón del reporte: spam, inappropriate, harassment, other")
    description: Optional[str] = Field(None, max_length=1000, description="Descripción adicional")

    @validator('reason')
    def validate_reason(cls, v):
        """Validar razón del reporte"""
        valid_reasons = ["spam", "inappropriate", "harassment", "violence", "false_information", "other"]
        if v not in valid_reasons:
            raise ValueError(f"Razón inválida. Debe ser una de: {', '.join(valid_reasons)}")
        return v


class StoryReport(BaseModel):
    """Schema para reporte de historia"""
    id: int
    story_id: int
    reporter_id: int
    reason: str
    description: Optional[str]
    is_reviewed: bool
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    action_taken: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True


# Highlight schemas
class StoryHighlightCreate(BaseModel):
    """Schema para crear un highlight"""
    title: str = Field(..., min_length=1, max_length=50, description="Título del highlight")
    cover_image_url: Optional[HttpUrl] = Field(None, description="URL de imagen de portada")
    story_ids: List[int] = Field(..., min_items=1, description="IDs de historias para agregar")


class StoryHighlightUpdate(BaseModel):
    """Schema para actualizar un highlight"""
    title: Optional[str] = Field(None, min_length=1, max_length=50)
    cover_image_url: Optional[HttpUrl] = None


class StoryHighlight(BaseModel):
    """Schema para highlight de historias"""
    id: int
    user_id: int
    gym_id: int
    title: str
    cover_image_url: Optional[str]
    is_active: bool
    story_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class StoryHighlightWithStories(StoryHighlight):
    """Schema para highlight con sus historias"""
    stories: List[Story]


# Stats schemas
class StoryStats(BaseModel):
    """Estadísticas de una historia"""
    story_id: int
    view_count: int
    unique_viewers: int
    reaction_count: int
    avg_view_duration: Optional[float]
    top_reactions: List[Dict[str, Any]]  # [{emoji: "💪", count: 10}, ...]
    viewer_demographics: Optional[Dict[str, Any]]  # Por rol, género, etc.


class UserStoryStats(BaseModel):
    """Estadísticas de historias de un usuario"""
    user_id: int
    total_stories: int
    total_views: int
    total_reactions: int
    avg_views_per_story: float
    most_viewed_story: Optional[Story]
    engagement_rate: float  # (reactions + views) / followers
    best_performing_time: Optional[str]  # Hora del día con más engagement


# Feed schemas
class StoryFeedRequest(BaseModel):
    """Request para obtener feed de historias"""
    limit: int = Field(25, ge=1, le=100, description="Número de historias a obtener")
    offset: int = Field(0, ge=0, description="Offset para paginación")
    filter_type: Optional[str] = Field(None, description="Filtro: all, following, close_friends")
    story_types: Optional[List[StoryType]] = Field(None, description="Filtrar por tipos de historia")


class StoryFeedResponse(BaseModel):
    """Response del feed de historias agrupadas por usuario"""
    user_stories: List[Dict[str, Any]]  # Lista de usuarios con sus historias
    total_users: int
    has_more: bool
    next_offset: Optional[int]
    last_update: datetime