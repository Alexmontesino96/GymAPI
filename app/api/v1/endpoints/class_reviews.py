"""
Class Review API Endpoints

Endpoints REST para el sistema de reviews de clases con estrellas.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Security
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis_client import get_redis_client
from app.core.auth0_fastapi import Auth0User, auth
from app.core.tenant import verify_gym_access, GymSchema
from app.models.user import User
from app.schemas.class_review import (
    ClassReviewCreate, ClassReviewUpdate, ClassReviewResponse,
    ClassRatingStats, ClassStatistics, TrainerStatistics,
    CanReviewResponse, ReviewListResponse
)
from app.services.class_review import class_review_service
import logging

logger = logging.getLogger("class_reviews_api")

router = APIRouter()


def _get_internal_user(db: Session, auth0_id: str) -> User:
    """Obtener usuario interno desde Auth0 ID"""
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    return user


# ============= Member Endpoints =============

@router.post("/", response_model=ClassReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client),
    review_in: ClassReviewCreate
):
    """
    Crear una review para una sesión de clase.

    Requiere haber asistido a la sesión (status ATTENDED).
    Solo se permite una review por miembro por sesión.
    """
    user = _get_internal_user(db, current_user.id)

    review = await class_review_service.create_review(
        db=db,
        review_in=review_in,
        member_id=user.id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Enriquecer respuesta
    enriched = class_review_service._enrich_reviews(db, [review])
    return enriched[0] if enriched else review


@router.get("/my", response_model=List[ClassReviewResponse])
async def get_my_reviews(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Obtener mis reviews"""
    user = _get_internal_user(db, current_user.id)
    reviews, total = await class_review_service.get_my_reviews(
        db=db, member_id=user.id, gym_id=current_gym.id,
        skip=skip, limit=limit
    )
    return reviews


@router.get("/session/{session_id}", response_model=ReviewListResponse)
async def get_session_reviews(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client),
    session_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100)
):
    """Obtener todas las reviews de una sesión con estadísticas"""
    return await class_review_service.get_session_reviews(
        db=db, session_id=session_id, gym_id=current_gym.id,
        skip=skip, limit=limit, redis_client=redis_client
    )


@router.get("/session/{session_id}/my", response_model=ClassReviewResponse)
async def get_my_session_review(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    session_id: int
):
    """Obtener mi review de una sesión específica"""
    user = _get_internal_user(db, current_user.id)
    review = await class_review_service.get_my_review(
        db=db, session_id=session_id, member_id=user.id, gym_id=current_gym.id
    )
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes review para esta sesión"
        )
    enriched = class_review_service._enrich_reviews(db, [review])
    return enriched[0]


@router.get("/session/{session_id}/can-review", response_model=CanReviewResponse)
async def can_review_session(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    session_id: int
):
    """Verificar si puedo hacer review de una sesión"""
    user = _get_internal_user(db, current_user.id)
    return await class_review_service.can_review_session(
        db=db, session_id=session_id, member_id=user.id, gym_id=current_gym.id
    )


@router.put("/{review_id}", response_model=ClassReviewResponse)
async def update_review(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client),
    review_id: int,
    review_in: ClassReviewUpdate
):
    """Actualizar mi review"""
    user = _get_internal_user(db, current_user.id)
    review = await class_review_service.update_review(
        db=db, review_id=review_id, review_in=review_in,
        member_id=user.id, gym_id=current_gym.id,
        redis_client=redis_client
    )
    enriched = class_review_service._enrich_reviews(db, [review])
    return enriched[0]


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client),
    review_id: int
):
    """Eliminar mi review"""
    user = _get_internal_user(db, current_user.id)
    await class_review_service.delete_review(
        db=db, review_id=review_id, member_id=user.id,
        gym_id=current_gym.id, redis_client=redis_client
    )


# ============= Statistics Endpoints =============

@router.get("/stats/class/{class_id}", response_model=ClassStatistics)
async def get_class_stats(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client),
    class_id: int
):
    """Obtener estadísticas de rating de una clase"""
    return await class_review_service.get_class_statistics(
        db=db, class_id=class_id, gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/stats/session/{session_id}", response_model=ClassRatingStats)
async def get_session_stats(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client),
    session_id: int
):
    """Obtener estadísticas de rating de una sesión"""
    return await class_review_service.get_session_statistics(
        db=db, session_id=session_id, gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/stats/trainer/{trainer_id}", response_model=TrainerStatistics)
async def get_trainer_stats(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client),
    trainer_id: int
):
    """Obtener estadísticas de rating de un entrenador"""
    return await class_review_service.get_trainer_statistics(
        db=db, trainer_id=trainer_id, gym_id=current_gym.id,
        redis_client=redis_client
    )
