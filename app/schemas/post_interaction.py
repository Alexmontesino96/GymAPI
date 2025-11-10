"""
Schemas de Pydantic para interacciones con posts (likes, comentarios, reportes).
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# Enums
class ReportReason(str, Enum):
    SPAM = "spam"
    INAPPROPRIATE = "inappropriate"
    HARASSMENT = "harassment"
    FALSE_INFO = "false_information"
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    OTHER = "other"


# Schemas de Likes
class PostLikeCreate(BaseModel):
    """Schema para crear/toggle like en un post"""
    pass  # No necesita datos adicionales, solo el user_id y post_id del contexto


class PostLikeResponse(BaseModel):
    """Schema de respuesta para like"""
    id: int
    post_id: int
    user_id: int
    created_at: datetime
    user_info: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class LikeToggleResponse(BaseModel):
    """Schema de respuesta para toggle de like"""
    success: bool
    action: str = Field(..., description="'liked' o 'unliked'")
    total_likes: int
    message: str


class PostLikesListResponse(BaseModel):
    """Schema de respuesta para lista de likes de un post"""
    likes: List[PostLikeResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


# Schemas de Comentarios
class CommentCreate(BaseModel):
    """Schema para crear un comentario"""
    comment_text: str = Field(..., min_length=1, max_length=2000, description="Texto del comentario")

    class Config:
        schema_extra = {
            "example": {
                "comment_text": "¡Excelente post! Sigue así 💪"
            }
        }


class CommentUpdate(BaseModel):
    """Schema para actualizar un comentario"""
    comment_text: str = Field(..., min_length=1, max_length=2000)


class CommentResponse(BaseModel):
    """Schema de respuesta para un comentario"""
    id: int
    post_id: int
    user_id: int
    gym_id: int
    comment_text: str
    is_edited: bool
    edited_at: Optional[datetime]
    like_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    user_info: Optional[Dict[str, Any]] = None
    has_liked: bool = Field(False, description="Si el usuario actual dio like al comentario")

    model_config = {"from_attributes": True}


class CommentCreateResponse(BaseModel):
    """Schema de respuesta al crear comentario"""
    success: bool
    comment: CommentResponse
    message: str = "Comentario agregado exitosamente"


class CommentsListResponse(BaseModel):
    """Schema de respuesta para lista de comentarios"""
    comments: List[CommentResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


# Schemas de Likes en Comentarios
class CommentLikeToggleResponse(BaseModel):
    """Schema de respuesta para toggle de like en comentario"""
    success: bool
    action: str = Field(..., description="'liked' o 'unliked'")
    total_likes: int


# Schemas de Reportes
class PostReportCreate(BaseModel):
    """Schema para crear un reporte de post"""
    reason: ReportReason = Field(..., description="Razón del reporte")
    description: Optional[str] = Field(None, max_length=1000, description="Descripción adicional")

    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "spam",
                "description": "Este post contiene spam publicitario no relacionado con el gimnasio"
            }
        }
    }


class PostReportResponse(BaseModel):
    """Schema de respuesta para un reporte"""
    id: int
    post_id: int
    reporter_id: int
    reason: ReportReason
    description: Optional[str]
    is_reviewed: bool
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]
    action_taken: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportCreateResponse(BaseModel):
    """Schema de respuesta al crear reporte"""
    success: bool
    report_id: int
    message: str = "Reporte enviado exitosamente. Será revisado por un administrador."


# Schemas de Estadísticas
class UserPostStats(BaseModel):
    """Estadísticas de posts de un usuario"""
    total_posts: int
    total_likes: int
    total_comments: int
    average_likes_per_post: float
    average_comments_per_post: float
    most_liked_post_id: Optional[int] = None
    most_commented_post_id: Optional[int] = None


class PostEngagementStats(BaseModel):
    """Estadísticas de engagement de un post"""
    post_id: int
    like_count: int
    comment_count: int
    unique_commenters: int
    engagement_rate: float
    top_likers: List[Dict[str, Any]] = Field(default_factory=list)
    recent_comments: List[CommentResponse] = Field(default_factory=list)
