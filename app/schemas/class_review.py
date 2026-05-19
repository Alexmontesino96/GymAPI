"""
Class Review Schemas

Schemas de validación para el sistema de reviews de clases.
"""

from typing import Optional, Dict, List
from datetime import datetime
from pydantic import BaseModel, Field


# ============= Create/Update =============

class ClassReviewCreate(BaseModel):
    """Schema para crear una review"""
    session_id: int
    rating: int = Field(..., ge=1, le=5, description="Calificación de 1 a 5 estrellas")
    comment: Optional[str] = Field(None, max_length=1000, description="Comentario opcional")


class ClassReviewUpdate(BaseModel):
    """Schema para actualizar una review"""
    rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = Field(None, max_length=1000)


# ============= Response =============

class ClassReviewResponse(BaseModel):
    """Schema de respuesta para una review"""
    id: int
    session_id: int
    member_id: int
    gym_id: int
    rating: int
    comment: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    member_name: Optional[str] = None
    class_name: Optional[str] = None
    session_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============= Statistics =============

class ClassRatingStats(BaseModel):
    """Estadísticas de rating"""
    average_rating: float
    total_reviews: int
    rating_distribution: Dict[int, int] = Field(
        default_factory=lambda: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    )


class ClassStatistics(ClassRatingStats):
    """Estadísticas de una clase"""
    class_id: int
    class_name: Optional[str] = None


class TrainerStatistics(ClassRatingStats):
    """Estadísticas de un entrenador"""
    trainer_id: int
    trainer_name: Optional[str] = None


# ============= Utility =============

class CanReviewResponse(BaseModel):
    """Respuesta de verificación de si puede hacer review"""
    can_review: bool
    reason: Optional[str] = None


class ReviewListResponse(BaseModel):
    """Respuesta paginada de reviews con stats"""
    reviews: List[ClassReviewResponse]
    total: int
    stats: ClassRatingStats
