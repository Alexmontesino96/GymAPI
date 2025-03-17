from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.repositories.base import BaseRepository
from app.models.trainer_member import TrainerMemberRelationship, RelationshipStatus
from app.schemas.trainer_member import (
    TrainerMemberRelationshipCreate,
    TrainerMemberRelationshipUpdate
)


class TrainerMemberRepository(
    BaseRepository[
        TrainerMemberRelationship,
        TrainerMemberRelationshipCreate,
        TrainerMemberRelationshipUpdate
    ]
):
    def get_by_trainer_and_member(
        self, db: Session, *, trainer_id: int, member_id: int
    ) -> Optional[TrainerMemberRelationship]:
        """
        Obtiene una relación específica entre un entrenador y un miembro.
        """
        return db.query(TrainerMemberRelationship).filter(
            and_(
                TrainerMemberRelationship.trainer_id == trainer_id,
                TrainerMemberRelationship.member_id == member_id
            )
        ).first()
    
    def get_by_trainer(
        self, db: Session, *, trainer_id: int, skip: int = 0, limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene todas las relaciones de un entrenador con sus miembros.
        """
        return db.query(TrainerMemberRelationship).filter(
            TrainerMemberRelationship.trainer_id == trainer_id
        ).offset(skip).limit(limit).all()
    
    def get_by_member(
        self, db: Session, *, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene todas las relaciones de un miembro con sus entrenadores.
        """
        return db.query(TrainerMemberRelationship).filter(
            TrainerMemberRelationship.member_id == member_id
        ).offset(skip).limit(limit).all()
    
    def get_active_by_trainer(
        self, db: Session, *, trainer_id: int, skip: int = 0, limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene las relaciones activas de un entrenador.
        """
        return db.query(TrainerMemberRelationship).filter(
            and_(
                TrainerMemberRelationship.trainer_id == trainer_id,
                TrainerMemberRelationship.status == RelationshipStatus.ACTIVE
            )
        ).offset(skip).limit(limit).all()
    
    def get_active_by_member(
        self, db: Session, *, member_id: int, skip: int = 0, limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene las relaciones activas de un miembro.
        """
        return db.query(TrainerMemberRelationship).filter(
            and_(
                TrainerMemberRelationship.member_id == member_id,
                TrainerMemberRelationship.status == RelationshipStatus.ACTIVE
            )
        ).offset(skip).limit(limit).all()
    
    def get_pending_relationships(
        self, db: Session, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene las relaciones pendientes de un usuario (como entrenador o miembro).
        """
        return db.query(TrainerMemberRelationship).filter(
            and_(
                or_(
                    TrainerMemberRelationship.trainer_id == user_id,
                    TrainerMemberRelationship.member_id == user_id
                ),
                TrainerMemberRelationship.status == RelationshipStatus.PENDING
            )
        ).offset(skip).limit(limit).all()


trainer_member_repository = TrainerMemberRepository(TrainerMemberRelationship) 