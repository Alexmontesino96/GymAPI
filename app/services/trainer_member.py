from typing import Dict, List, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.repositories.trainer_member import trainer_member_repository
from app.repositories.user import user_repository
from app.models.user import UserRole
from app.models.trainer_member import RelationshipStatus
from app.schemas.trainer_member import (
    TrainerMemberRelationshipCreate,
    TrainerMemberRelationshipUpdate,
    UserWithRelationship
)


class TrainerMemberService:
    def get_relationship(self, db: Session, relationship_id: int):
        """
        Obtener una relación por su ID.
        """
        relationship = trainer_member_repository.get(db, id=relationship_id)
        if not relationship:
            raise HTTPException(status_code=404, detail="Relación no encontrada")
        return relationship

    def get_all_relationships(self, db: Session, skip: int = 0, limit: int = 100):
        """
        Obtener todas las relaciones (solo para administradores).
        """
        return trainer_member_repository.get_multi(db, skip=skip, limit=limit)

    def get_relationship_by_trainer_and_member(
        self, db: Session, trainer_id: int, member_id: int
    ):
        """
        Obtener una relación específica entre un entrenador y un miembro.
        """
        return trainer_member_repository.get_by_trainer_and_member(
            db, trainer_id=trainer_id, member_id=member_id
        )

    def get_members_by_trainer(
        self, db: Session, trainer_id: int, skip: int = 0, limit: int = 100
    ) -> List:
        """
        Obtener todos los miembros asignados a un entrenador.
        """
        # Verificar que el usuario sea un entrenador
        trainer = user_repository.get(db, id=trainer_id)
        if not trainer or trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=400,
                detail="El usuario especificado no es un entrenador"
            )
        
        # Obtener las relaciones
        relationships = trainer_member_repository.get_by_trainer(
            db, trainer_id=trainer_id, skip=skip, limit=limit
        )
        
        # Obtener los usuarios correspondientes a los miembros
        result = []
        for rel in relationships:
            member = user_repository.get(db, id=rel.member_id)
            if member:
                result.append({
                    "id": member.id,
                    "full_name": member.full_name,
                    "email": member.email,
                    "picture": member.picture,
                    "relationship_id": rel.id,
                    "relationship_status": rel.status,
                    "relationship_start_date": rel.start_date
                })
        
        return result

    def get_trainers_by_member(
        self, db: Session, member_id: int, skip: int = 0, limit: int = 100
    ) -> List:
        """
        Obtener todos los entrenadores asignados a un miembro.
        """
        # Verificar que el usuario sea un miembro
        member = user_repository.get(db, id=member_id)
        if not member or member.role != UserRole.MEMBER:
            raise HTTPException(
                status_code=400,
                detail="El usuario especificado no es un miembro"
            )
        
        # Obtener las relaciones
        relationships = trainer_member_repository.get_by_member(
            db, member_id=member_id, skip=skip, limit=limit
        )
        
        # Obtener los usuarios correspondientes a los entrenadores
        result = []
        for rel in relationships:
            trainer = user_repository.get(db, id=rel.trainer_id)
            if trainer:
                result.append({
                    "id": trainer.id,
                    "full_name": trainer.full_name,
                    "email": trainer.email,
                    "picture": trainer.picture,
                    "relationship_id": rel.id,
                    "relationship_status": rel.status,
                    "relationship_start_date": rel.start_date
                })
        
        return result

    def create_relationship(
        self, db: Session, relationship_in: TrainerMemberRelationshipCreate, created_by_id: int
    ):
        """
        Crear una nueva relación entre un entrenador y un miembro.
        """
        # Verificar que el entrenador exista y sea un entrenador
        trainer = user_repository.get(db, id=relationship_in.trainer_id)
        if not trainer or trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=400,
                detail="El entrenador especificado no existe o no tiene el rol correcto"
            )
        
        # Verificar que el miembro exista y sea un miembro
        member = user_repository.get(db, id=relationship_in.member_id)
        if not member or member.role != UserRole.MEMBER:
            raise HTTPException(
                status_code=400,
                detail="El miembro especificado no existe o no tiene el rol correcto"
            )
        
        # Verificar si ya existe una relación
        existing = trainer_member_repository.get_by_trainer_and_member(
            db, trainer_id=relationship_in.trainer_id, member_id=relationship_in.member_id
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una relación entre este entrenador y miembro"
            )
        
        # Crear la relación
        relationship_data = relationship_in.model_dump()
        relationship_data["created_by"] = created_by_id
        
        return trainer_member_repository.create(
            db, obj_in=TrainerMemberRelationshipCreate(**relationship_data)
        )

    def update_relationship(
        self, db: Session, relationship_id: int, relationship_update: TrainerMemberRelationshipUpdate
    ):
        """
        Actualizar una relación existente.
        """
        relationship = trainer_member_repository.get(db, id=relationship_id)
        if not relationship:
            raise HTTPException(status_code=404, detail="Relación no encontrada")
        
        # Si se actualiza el estado a ACTIVE y no tiene fecha de inicio, establecerla
        if (relationship_update.status == RelationshipStatus.ACTIVE and 
            not relationship.start_date and not relationship_update.start_date):
            relationship_update_dict = relationship_update.model_dump(exclude_unset=True)
            relationship_update_dict["start_date"] = datetime.now()
            return trainer_member_repository.update(
                db, db_obj=relationship, obj_in=relationship_update_dict
            )
        
        return trainer_member_repository.update(
            db, db_obj=relationship, obj_in=relationship_update
        )

    def delete_relationship(self, db: Session, relationship_id: int):
        """
        Eliminar una relación.
        """
        relationship = trainer_member_repository.get(db, id=relationship_id)
        if not relationship:
            raise HTTPException(status_code=404, detail="Relación no encontrada")
        
        return trainer_member_repository.remove(db, id=relationship_id)


trainer_member_service = TrainerMemberService() 