"""
Schemas de Pydantic para el sistema de posts.
"""

from pydantic import BaseModel, Field, HttpUrl, validator
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


# Enums
class PostType(str, Enum):
    SINGLE_IMAGE = "single_image"
    GALLERY = "gallery"
    VIDEO = "video"
    WORKOUT = "workout"


class PostPrivacy(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"


class TagType(str, Enum):
    MENTION = "mention"
    EVENT = "event"
    SESSION = "session"


# Base schemas
class PostBase(BaseModel):
    """Schema base para posts"""
    caption: Optional[str] = Field(None, max_length=2000, description="Texto del post")
    post_type: PostType = Field(..., description="Tipo de post")
    privacy: PostPrivacy = Field(PostPrivacy.PUBLIC, description="Nivel de privacidad")
    location: Optional[str] = Field(None, max_length=100, description="Ubicación del gym/lugar")


class PostCreate(PostBase):
    """Schema para crear un post"""
    workout_data: Optional[Dict[str, Any]] = Field(None, description="Datos del entrenamiento")
    tagged_event_id: Optional[int] = Field(None, description="ID del evento etiquetado")
    tagged_session_id: Optional[int] = Field(None, description="ID de la sesión etiquetada")
    mentioned_user_ids: Optional[List[int]] = Field(None, description="IDs de usuarios mencionados")

    @validator('workout_data', always=True)
    def validate_workout_data(cls, v, values):
        """Validar workout_data para posts de tipo workout"""
        post_type = values.get('post_type')
        if post_type == PostType.WORKOUT and not v:
            raise ValueError("workout_data es requerida para posts de tipo workout")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "post_type": "single_image",
                "caption": "Nuevo PR en sentadilla! 💪 @usuario123 #workout",
                "privacy": "public",
                "location": "Gym Central",
                "tagged_event_id": 5,
                "mentioned_user_ids": [123, 456]
            }
        }
    }


class PostUpdate(BaseModel):
    """Schema para actualizar un post (solo caption y location son editables)"""
    caption: Optional[str] = Field(None, max_length=2000)
    location: Optional[str] = Field(None, max_length=100)


class PostMediaCreate(BaseModel):
    """Schema para crear media de un post"""
    media_url: HttpUrl = Field(..., description="URL del archivo de media")
    thumbnail_url: Optional[HttpUrl] = Field(None, description="URL del thumbnail")
    media_type: str = Field(..., description="Tipo de media: 'image' o 'video'")
    display_order: int = Field(0, ge=0, description="Orden de visualización")
    width: Optional[int] = Field(None, ge=1)
    height: Optional[int] = Field(None, ge=1)


class PostMediaResponse(BaseModel):
    """Schema de respuesta para media de post"""
    id: int
    post_id: int
    media_url: str
    thumbnail_url: Optional[str]
    media_type: str
    display_order: int
    width: Optional[int]
    height: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class PostTagResponse(BaseModel):
    """Schema de respuesta para tags de post"""
    id: int
    tag_type: TagType
    tag_value: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PostInDBBase(PostBase):
    """Schema base para posts en BD"""
    id: int
    gym_id: int
    user_id: int
    stream_activity_id: Optional[str]
    workout_data: Optional[Dict[str, Any]]
    is_edited: bool
    edited_at: Optional[datetime]
    like_count: int
    comment_count: int
    view_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class Post(PostInDBBase):
    """Schema completo de post para respuestas"""
    media: List[PostMediaResponse] = Field(default_factory=list, description="Archivos de media")
    tags: List[PostTagResponse] = Field(default_factory=list, description="Tags del post")
    user_info: Optional[Dict[str, Any]] = Field(None, description="Información del usuario")
    is_own_post: bool = Field(False, description="Si es post propio del usuario actual")
    has_liked: bool = Field(False, description="Si el usuario actual dio like")
    engagement_score: float = Field(0.0, description="Score de engagement calculado")

    class Config:
        orm_mode = True


class PostResponse(BaseModel):
    """Schema de respuesta para un post individual"""
    success: bool = True
    post: Post


class PostListResponse(BaseModel):
    """Schema de respuesta para lista de posts con paginación"""
    posts: List[Post]
    total: int
    limit: int
    offset: int
    has_more: bool
    next_offset: Optional[int] = None


class PostFeedResponse(BaseModel):
    """Schema de respuesta para feed de posts"""
    posts: List[Post]
    total_posts: int
    feed_type: str = Field(..., description="Tipo de feed: 'timeline', 'explore', 'user'")
    has_more: bool
    next_offset: Optional[int] = None
    last_update: Optional[datetime] = None


class PostStatsResponse(BaseModel):
    """Schema para estadísticas de un post"""
    post_id: int
    like_count: int
    comment_count: int
    view_count: int
    engagement_score: float
    top_commenters: List[Dict[str, Any]] = Field(default_factory=list)


# Schemas para crear posts desde multipart/form-data
class PostCreateMultipart(BaseModel):
    """Schema simplificado para crear post desde form-data con archivos"""
    caption: Optional[str] = Field(None, max_length=2000)
    post_type: PostType = PostType.SINGLE_IMAGE
    privacy: PostPrivacy = PostPrivacy.PUBLIC
    location: Optional[str] = Field(None, max_length=100)
    workout_data_json: Optional[str] = Field(None, description="JSON string con workout_data")
    tagged_event_id: Optional[int] = None
    tagged_session_id: Optional[int] = None
    mentioned_user_ids_json: Optional[str] = Field(None, description="JSON array de user IDs")
