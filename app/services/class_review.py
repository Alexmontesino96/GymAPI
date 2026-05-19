"""
Class Review Service

Lógica de negocio para el sistema de reviews de clases.
"""

from typing import List, Optional, Dict, Tuple
from sqlalchemy.orm import Session
from redis.asyncio import Redis
import json
import logging

from app.repositories.class_review import class_review_repository
from app.models.class_review import ClassReview
from app.models.schedule import ClassSession
from app.models.user import User
from app.schemas.class_review import (
    ClassReviewCreate, ClassReviewUpdate, ClassReviewResponse,
    ClassRatingStats, CanReviewResponse, ReviewListResponse
)

logger = logging.getLogger(__name__)

REVIEW_STATS_TTL = 600  # 10 minutos


class ClassReviewService:
    """Service para reviews de clases"""

    # ============= Reviews =============

    async def create_review(
        self,
        db: Session,
        review_in: ClassReviewCreate,
        member_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> ClassReview:
        """Crear una review"""
        review = class_review_repository.create_review(
            db=db,
            session_id=review_in.session_id,
            member_id=member_id,
            gym_id=gym_id,
            rating=review_in.rating,
            comment=review_in.comment
        )

        if redis_client:
            await self._invalidate_review_caches(
                redis_client, gym_id, review_in.session_id, db
            )

        logger.info(f"Review creada: user {member_id} → session {review_in.session_id}, rating {review_in.rating}")
        return review

    async def get_session_reviews(
        self,
        db: Session,
        session_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 50,
        redis_client: Optional[Redis] = None
    ) -> ReviewListResponse:
        """Obtener reviews de una sesión con stats"""
        reviews, total = class_review_repository.get_reviews_by_session(
            db, session_id, gym_id, skip, limit
        )

        # Enriquecer con nombre del miembro
        enriched = self._enrich_reviews(db, reviews)

        stats = class_review_repository.get_session_stats(db, session_id, gym_id)

        return ReviewListResponse(
            reviews=enriched,
            total=total,
            stats=ClassRatingStats(**stats)
        )

    async def get_my_review(
        self,
        db: Session,
        session_id: int,
        member_id: int,
        gym_id: int
    ) -> Optional[ClassReview]:
        """Obtener mi review de una sesión"""
        return class_review_repository.get_review_by_session_and_member(
            db, session_id, member_id, gym_id
        )

    async def get_my_reviews(
        self,
        db: Session,
        member_id: int,
        gym_id: int,
        skip: int = 0,
        limit: int = 50
    ) -> Tuple[List[ClassReviewResponse], int]:
        """Obtener historial de mis reviews"""
        reviews, total = class_review_repository.get_member_reviews(
            db, member_id, gym_id, skip, limit
        )
        enriched = self._enrich_reviews(db, reviews)
        return enriched, total

    async def update_review(
        self,
        db: Session,
        review_id: int,
        review_in: ClassReviewUpdate,
        member_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> ClassReview:
        """Actualizar mi review"""
        # Obtener la review antes de actualizar para saber el session_id
        existing = class_review_repository.get_review(db, review_id, gym_id)
        if not existing:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review no encontrada")

        review = class_review_repository.update_review(
            db, review_id, member_id, gym_id,
            rating=review_in.rating,
            comment=review_in.comment
        )

        if redis_client:
            await self._invalidate_review_caches(
                redis_client, gym_id, review.session_id, db
            )

        return review

    async def delete_review(
        self,
        db: Session,
        review_id: int,
        member_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> bool:
        """Eliminar mi review"""
        # Obtener session_id antes de eliminar
        existing = class_review_repository.get_review(db, review_id, gym_id)
        if not existing:
            from fastapi import HTTPException, status
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review no encontrada")

        session_id = existing.session_id
        class_review_repository.delete_review(db, review_id, member_id, gym_id)

        if redis_client:
            await self._invalidate_review_caches(
                redis_client, gym_id, session_id, db
            )

        return True

    # ============= Can Review =============

    async def can_review_session(
        self,
        db: Session,
        session_id: int,
        member_id: int,
        gym_id: int
    ) -> CanReviewResponse:
        """Verificar si el miembro puede hacer review"""
        can, reason = class_review_repository.can_review(db, session_id, member_id, gym_id)
        return CanReviewResponse(can_review=can, reason=reason)

    # ============= Estadísticas =============

    async def get_class_statistics(
        self,
        db: Session,
        class_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Dict:
        """Estadísticas de una clase"""
        cache_key = f"gym:{gym_id}:reviews:class_stats:{class_id}"

        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        stats = class_review_repository.get_class_stats(db, class_id, gym_id)

        # Agregar nombre de la clase
        from app.models.schedule import Class
        cls = db.query(Class).filter(Class.id == class_id, Class.gym_id == gym_id).first()
        if cls:
            stats["class_name"] = cls.name

        if redis_client:
            try:
                await redis_client.setex(cache_key, REVIEW_STATS_TTL, json.dumps(stats))
            except Exception:
                pass

        return stats

    async def get_session_statistics(
        self,
        db: Session,
        session_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Dict:
        """Estadísticas de una sesión"""
        cache_key = f"gym:{gym_id}:reviews:session_stats:{session_id}"

        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        stats = class_review_repository.get_session_stats(db, session_id, gym_id)

        if redis_client:
            try:
                await redis_client.setex(cache_key, REVIEW_STATS_TTL, json.dumps(stats))
            except Exception:
                pass

        return stats

    async def get_trainer_statistics(
        self,
        db: Session,
        trainer_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Dict:
        """Estadísticas de un entrenador"""
        cache_key = f"gym:{gym_id}:reviews:trainer_stats:{trainer_id}"

        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        stats = class_review_repository.get_trainer_stats(db, trainer_id, gym_id)

        # Agregar nombre del trainer
        trainer = db.query(User).filter(User.id == trainer_id).first()
        if trainer:
            stats["trainer_name"] = trainer.name

        if redis_client:
            try:
                await redis_client.setex(cache_key, REVIEW_STATS_TTL, json.dumps(stats))
            except Exception:
                pass

        return stats

    # ============= Helpers =============

    def _enrich_reviews(self, db: Session, reviews: List[ClassReview]) -> List[ClassReviewResponse]:
        """Enriquecer reviews con nombres de miembro y clase"""
        if not reviews:
            return []

        # Obtener nombres de miembros en batch
        member_ids = list({r.member_id for r in reviews})
        members = {u.id: u.name for u in db.query(User.id, User.name).filter(User.id.in_(member_ids)).all()}

        # Obtener info de sesiones en batch
        session_ids = list({r.session_id for r in reviews})
        sessions = {}
        session_rows = db.query(ClassSession).filter(ClassSession.id.in_(session_ids)).all()
        for s in session_rows:
            sessions[s.id] = s

        # Obtener nombres de clases
        class_ids = list({s.class_id for s in sessions.values()})
        from app.models.schedule import Class
        classes = {c.id: c.name for c in db.query(Class.id, Class.name).filter(Class.id.in_(class_ids)).all()}

        result = []
        for r in reviews:
            session = sessions.get(r.session_id)
            class_name = classes.get(session.class_id) if session else None

            result.append(ClassReviewResponse(
                id=r.id,
                session_id=r.session_id,
                member_id=r.member_id,
                gym_id=r.gym_id,
                rating=r.rating,
                comment=r.comment,
                created_at=r.created_at,
                updated_at=r.updated_at,
                member_name=members.get(r.member_id),
                class_name=class_name,
                session_date=session.start_time if session else None
            ))

        return result

    async def _invalidate_review_caches(
        self, redis_client: Redis, gym_id: int, session_id: int, db: Session
    ):
        """Invalidar caches relacionados a reviews"""
        try:
            keys_to_delete = [
                f"gym:{gym_id}:reviews:session_stats:{session_id}"
            ]

            # Obtener class_id y trainer_id de la sesión
            session = class_review_repository.get_session_context(db, session_id)
            if session:
                keys_to_delete.append(f"gym:{gym_id}:reviews:class_stats:{session.class_id}")
                keys_to_delete.append(f"gym:{gym_id}:reviews:trainer_stats:{session.trainer_id}")

            for key in keys_to_delete:
                await redis_client.delete(key)
        except Exception as e:
            logger.warning(f"Error invalidando cache de reviews: {e}")


class_review_service = ClassReviewService()
