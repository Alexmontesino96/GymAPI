"""
Class Review Repository

Operaciones de base de datos para el sistema de reviews de clases.
"""

from typing import List, Optional, Dict, Tuple
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, desc
from fastapi import HTTPException, status
import logging

from app.models.class_review import ClassReview
from app.models.schedule import ClassSession, ClassParticipation, ClassParticipationStatus, ClassSessionStatus
from app.models.user import User

logger = logging.getLogger(__name__)


class ClassReviewRepository:
    """Repository para operaciones de reviews de clases"""

    # ============= Validación =============

    def _validate_can_review(
        self, db: Session, session_id: int, member_id: int, gym_id: int
    ) -> ClassSession:
        """Valida que el miembro puede hacer review de la sesión.
        Retorna la sesión si es válido, lanza HTTPException si no."""

        # Verificar que la sesión existe y pertenece al gym
        session = db.query(ClassSession).filter(
            and_(
                ClassSession.id == session_id,
                ClassSession.gym_id == gym_id
            )
        ).first()

        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Sesión no encontrada"
            )

        # Verificar que la sesión está completada
        if session.status != ClassSessionStatus.COMPLETED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Solo se pueden hacer reviews de sesiones completadas"
            )

        # Verificar que la sesión ya terminó
        now = datetime.now(timezone.utc)
        if session.end_time and session.end_time > now:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La sesión aún no ha terminado"
            )

        # Verificar que el miembro asistió
        participation = db.query(ClassParticipation).filter(
            and_(
                ClassParticipation.session_id == session_id,
                ClassParticipation.member_id == member_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED
            )
        ).first()

        if not participation:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo los miembros que asistieron pueden hacer review"
            )

        # Verificar que no existe review duplicada
        existing = db.query(ClassReview).filter(
            and_(
                ClassReview.session_id == session_id,
                ClassReview.member_id == member_id
            )
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya existe una review para esta sesión"
            )

        return session

    def can_review(
        self, db: Session, session_id: int, member_id: int, gym_id: int
    ) -> Tuple[bool, Optional[str]]:
        """Verifica si un miembro puede hacer review sin lanzar excepciones."""
        try:
            self._validate_can_review(db, session_id, member_id, gym_id)
            return True, None
        except HTTPException as e:
            return False, e.detail

    # ============= CRUD =============

    def create_review(
        self, db: Session, session_id: int, member_id: int, gym_id: int,
        rating: int, comment: Optional[str] = None
    ) -> ClassReview:
        """Crear una nueva review"""
        self._validate_can_review(db, session_id, member_id, gym_id)

        review = ClassReview(
            session_id=session_id,
            member_id=member_id,
            gym_id=gym_id,
            rating=rating,
            comment=comment
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    def get_review(self, db: Session, review_id: int, gym_id: int) -> Optional[ClassReview]:
        """Obtener una review por ID"""
        return db.query(ClassReview).filter(
            and_(ClassReview.id == review_id, ClassReview.gym_id == gym_id)
        ).first()

    def get_review_by_session_and_member(
        self, db: Session, session_id: int, member_id: int, gym_id: int
    ) -> Optional[ClassReview]:
        """Obtener la review de un miembro para una sesión"""
        return db.query(ClassReview).filter(
            and_(
                ClassReview.session_id == session_id,
                ClassReview.member_id == member_id,
                ClassReview.gym_id == gym_id
            )
        ).first()

    def get_reviews_by_session(
        self, db: Session, session_id: int, gym_id: int,
        skip: int = 0, limit: int = 50
    ) -> Tuple[List[ClassReview], int]:
        """Obtener reviews de una sesión con paginación"""
        query = db.query(ClassReview).filter(
            and_(ClassReview.session_id == session_id, ClassReview.gym_id == gym_id)
        )
        total = query.count()
        reviews = query.order_by(desc(ClassReview.created_at)).offset(skip).limit(limit).all()
        return reviews, total

    def get_reviews_by_class(
        self, db: Session, class_id: int, gym_id: int,
        skip: int = 0, limit: int = 50
    ) -> Tuple[List[ClassReview], int]:
        """Obtener reviews de todas las sesiones de una clase"""
        query = db.query(ClassReview).join(
            ClassSession, ClassReview.session_id == ClassSession.id
        ).filter(
            and_(ClassSession.class_id == class_id, ClassReview.gym_id == gym_id)
        )
        total = query.count()
        reviews = query.order_by(desc(ClassReview.created_at)).offset(skip).limit(limit).all()
        return reviews, total

    def get_member_reviews(
        self, db: Session, member_id: int, gym_id: int,
        skip: int = 0, limit: int = 50
    ) -> Tuple[List[ClassReview], int]:
        """Obtener historial de reviews de un miembro"""
        query = db.query(ClassReview).filter(
            and_(ClassReview.member_id == member_id, ClassReview.gym_id == gym_id)
        )
        total = query.count()
        reviews = query.order_by(desc(ClassReview.created_at)).offset(skip).limit(limit).all()
        return reviews, total

    def update_review(
        self, db: Session, review_id: int, member_id: int, gym_id: int,
        rating: Optional[int] = None, comment: Optional[str] = None
    ) -> ClassReview:
        """Actualizar una review (solo el dueño)"""
        review = db.query(ClassReview).filter(
            and_(
                ClassReview.id == review_id,
                ClassReview.member_id == member_id,
                ClassReview.gym_id == gym_id
            )
        ).first()

        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review no encontrada o no tienes permiso para editarla"
            )

        if rating is not None:
            review.rating = rating
        if comment is not None:
            review.comment = comment

        db.commit()
        db.refresh(review)
        return review

    def delete_review(
        self, db: Session, review_id: int, member_id: int, gym_id: int
    ) -> bool:
        """Eliminar una review (solo el dueño)"""
        review = db.query(ClassReview).filter(
            and_(
                ClassReview.id == review_id,
                ClassReview.member_id == member_id,
                ClassReview.gym_id == gym_id
            )
        ).first()

        if not review:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Review no encontrada o no tienes permiso para eliminarla"
            )

        db.delete(review)
        db.commit()
        return True

    # ============= Estadísticas =============

    def _get_stats_query(self, db: Session, filters) -> Dict:
        """Helper para calcular estadísticas de rating"""
        result = db.query(
            func.avg(ClassReview.rating).label("average"),
            func.count(ClassReview.id).label("total")
        ).filter(*filters).first()

        average = round(float(result.average), 2) if result.average else 0.0
        total = result.total or 0

        # Distribución de ratings
        distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        if total > 0:
            dist_rows = db.query(
                ClassReview.rating,
                func.count(ClassReview.id)
            ).filter(*filters).group_by(ClassReview.rating).all()
            for rating_val, count in dist_rows:
                distribution[rating_val] = count

        return {
            "average_rating": average,
            "total_reviews": total,
            "rating_distribution": distribution
        }

    def get_session_stats(self, db: Session, session_id: int, gym_id: int) -> Dict:
        """Estadísticas de una sesión"""
        filters = [ClassReview.session_id == session_id, ClassReview.gym_id == gym_id]
        return self._get_stats_query(db, filters)

    def get_class_stats(self, db: Session, class_id: int, gym_id: int) -> Dict:
        """Estadísticas de una clase (todas sus sesiones)"""
        # Subquery para obtener session_ids de la clase
        session_ids = db.query(ClassSession.id).filter(
            and_(ClassSession.class_id == class_id, ClassSession.gym_id == gym_id)
        ).subquery()

        filters = [ClassReview.session_id.in_(session_ids), ClassReview.gym_id == gym_id]
        stats = self._get_stats_query(db, filters)
        stats["class_id"] = class_id
        return stats

    def get_trainer_stats(self, db: Session, trainer_id: int, gym_id: int) -> Dict:
        """Estadísticas de un entrenador (todas sus sesiones)"""
        session_ids = db.query(ClassSession.id).filter(
            and_(ClassSession.trainer_id == trainer_id, ClassSession.gym_id == gym_id)
        ).subquery()

        filters = [ClassReview.session_id.in_(session_ids), ClassReview.gym_id == gym_id]
        stats = self._get_stats_query(db, filters)
        stats["trainer_id"] = trainer_id
        return stats

    def get_session_context(self, db: Session, session_id: int) -> Optional[ClassSession]:
        """Obtener sesión con su clase para enriquecer datos"""
        return db.query(ClassSession).options(
            joinedload(ClassSession.class_definition)
        ).filter(ClassSession.id == session_id).first()


class_review_repository = ClassReviewRepository()
