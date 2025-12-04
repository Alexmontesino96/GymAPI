"""
AsyncTrainerMemberService - Servicio async para gestión de relaciones trainer-member.

Este módulo proporciona un servicio totalmente async para gestionar la asignación
y seguimiento de relaciones entre entrenadores y miembros del gimnasio.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import Dict, List, Optional
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.async_trainer_member import async_trainer_member_repository
from app.repositories.async_user import async_user_repository
from app.models.user import UserRole
from app.models.trainer_member import RelationshipStatus
from app.schemas.trainer_member import (
    TrainerMemberRelationshipCreate,
    TrainerMemberRelationshipUpdate,
    UserWithRelationship
)


class AsyncTrainerMemberService:
    """
    Servicio async para gestionar relaciones trainer-member.

    Todos los métodos son async y utilizan AsyncSession y repositorios async.

    Métodos principales:
    - get_relationship() - Obtener relación por ID
    - get_all_relationships() - Lista de todas las relaciones
    - get_relationship_by_trainer_and_member() - Buscar relación específica
    - get_members_by_trainer() - Miembros asignados a un trainer
    - get_trainers_by_member() - Trainers asignados a un member
    - create_relationship() - Crear asignación trainer-member
    - update_relationship() - Actualizar estado de relación
    - delete_relationship() - Eliminar relación
    """

    async def get_relationship(
        self, db: AsyncSession, relationship_id: int, gym_id: int
    ):
        """
        Obtener una relación por su ID.

        Args:
            db: Sesión async de base de datos
            relationship_id: ID de la relación
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Relación trainer-member

        Raises:
            HTTPException: Si la relación no existe
        """
        relationship = await async_trainer_member_repository.get(
            db, id=relationship_id, gym_id=gym_id
        )
        if not relationship:
            raise HTTPException(status_code=404, detail="Relación no encontrada")
        return relationship

    async def get_all_relationships(
        self, db: AsyncSession, gym_id: int, skip: int = 0, limit: int = 100
    ):
        """
        Obtener todas las relaciones (solo para administradores).

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio (multi-tenant)
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de relaciones del gimnasio
        """
        return await async_trainer_member_repository.get_multi(
            db, skip=skip, limit=limit, gym_id=gym_id
        )

    async def get_relationship_by_trainer_and_member(
        self, db: AsyncSession, trainer_id: int, member_id: int, gym_id: int
    ):
        """
        Obtener una relación específica entre un entrenador y un miembro.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            member_id: ID del miembro
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Relación o None si no existe
        """
        return await async_trainer_member_repository.get_by_trainer_and_member(
            db, trainer_id=trainer_id, member_id=member_id, gym_id=gym_id
        )

    async def get_members_by_trainer(
        self, db: AsyncSession, trainer_id: int, gym_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict]:
        """
        Obtener todos los miembros asignados a un entrenador.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            gym_id: ID del gimnasio (multi-tenant)
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de miembros con información de relación

        Raises:
            HTTPException: Si el usuario no es un entrenador

        Note:
            Retorna diccionarios con: id, full_name, email, picture,
            relationship_id, relationship_status, relationship_start_date
        """
        # Verificar que el usuario sea un entrenador
        trainer = await async_user_repository.get(db, id=trainer_id, gym_id=gym_id)
        if not trainer or trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=400,
                detail="El usuario especificado no es un entrenador"
            )

        # Obtener las relaciones
        relationships = await async_trainer_member_repository.get_by_trainer(
            db, trainer_id=trainer_id, gym_id=gym_id, skip=skip, limit=limit
        )

        # Obtener los usuarios correspondientes a los miembros
        result = []
        for rel in relationships:
            member = await async_user_repository.get(db, id=rel.member_id, gym_id=gym_id)
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

    async def get_trainers_by_member(
        self, db: AsyncSession, member_id: int, gym_id: int, skip: int = 0, limit: int = 100
    ) -> List[Dict]:
        """
        Obtener todos los entrenadores asignados a un miembro.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            gym_id: ID del gimnasio (multi-tenant)
            skip: Registros a omitir (paginación)
            limit: Máximo de registros a devolver

        Returns:
            Lista de entrenadores con información de relación

        Raises:
            HTTPException: Si el usuario no es un miembro

        Note:
            Retorna diccionarios con: id, full_name, email, picture,
            relationship_id, relationship_status, relationship_start_date
        """
        # Verificar que el usuario sea un miembro
        member = await async_user_repository.get(db, id=member_id, gym_id=gym_id)
        if not member or member.role != UserRole.MEMBER:
            raise HTTPException(
                status_code=400,
                detail="El usuario especificado no es un miembro"
            )

        # Obtener las relaciones
        relationships = await async_trainer_member_repository.get_by_member(
            db, member_id=member_id, gym_id=gym_id, skip=skip, limit=limit
        )

        # Obtener los usuarios correspondientes a los entrenadores
        result = []
        for rel in relationships:
            trainer = await async_user_repository.get(db, id=rel.trainer_id, gym_id=gym_id)
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

    async def create_relationship(
        self,
        db: AsyncSession,
        relationship_in: TrainerMemberRelationshipCreate,
        created_by_id: int,
        gym_id: int
    ):
        """
        Crear una nueva relación entre un entrenador y un miembro.

        Args:
            db: Sesión async de base de datos
            relationship_in: Datos de la relación a crear
            created_by_id: ID del usuario que crea la relación
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Relación creada

        Raises:
            HTTPException: Si el trainer o member no existen, no tienen el rol correcto,
                          o ya existe una relación entre ellos
        """
        # Verificar que el entrenador exista y sea un entrenador
        trainer = await async_user_repository.get(db, id=relationship_in.trainer_id, gym_id=gym_id)
        if not trainer or trainer.role != UserRole.TRAINER:
            raise HTTPException(
                status_code=400,
                detail="El entrenador especificado no existe o no tiene el rol correcto"
            )

        # Verificar que el miembro exista y sea un miembro
        member = await async_user_repository.get(db, id=relationship_in.member_id, gym_id=gym_id)
        if not member or member.role != UserRole.MEMBER:
            raise HTTPException(
                status_code=400,
                detail="El miembro especificado no existe o no tiene el rol correcto"
            )

        # Verificar si ya existe una relación
        existing = await async_trainer_member_repository.get_by_trainer_and_member(
            db, trainer_id=relationship_in.trainer_id, member_id=relationship_in.member_id, gym_id=gym_id
        )
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Ya existe una relación entre este entrenador y miembro"
            )

        # Crear la relación
        relationship_data = relationship_in.model_dump()
        relationship_data["created_by"] = created_by_id

        return await async_trainer_member_repository.create(
            db, obj_in=TrainerMemberRelationshipCreate(**relationship_data), gym_id=gym_id
        )

    async def update_relationship(
        self,
        db: AsyncSession,
        relationship_id: int,
        relationship_update: TrainerMemberRelationshipUpdate,
        gym_id: int
    ):
        """
        Actualizar una relación existente.

        Args:
            db: Sesión async de base de datos
            relationship_id: ID de la relación
            relationship_update: Datos de actualización
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Relación actualizada

        Raises:
            HTTPException: Si la relación no existe

        Note:
            Si se actualiza el estado a ACTIVE y no tiene fecha de inicio,
            se establece automáticamente a la fecha actual.
        """
        relationship = await async_trainer_member_repository.get(
            db, id=relationship_id, gym_id=gym_id
        )
        if not relationship:
            raise HTTPException(status_code=404, detail="Relación no encontrada")

        # Si se actualiza el estado a ACTIVE y no tiene fecha de inicio, establecerla
        if (relationship_update.status == RelationshipStatus.ACTIVE and
            not relationship.start_date and not relationship_update.start_date):
            relationship_update_dict = relationship_update.model_dump(exclude_unset=True)
            relationship_update_dict["start_date"] = datetime.now()
            return await async_trainer_member_repository.update(
                db, db_obj=relationship, obj_in=relationship_update_dict, gym_id=gym_id
            )

        return await async_trainer_member_repository.update(
            db, db_obj=relationship, obj_in=relationship_update, gym_id=gym_id
        )

    async def delete_relationship(
        self, db: AsyncSession, relationship_id: int, gym_id: int
    ):
        """
        Eliminar una relación.

        Args:
            db: Sesión async de base de datos
            relationship_id: ID de la relación
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Relación eliminada

        Raises:
            HTTPException: Si la relación no existe
        """
        relationship = await async_trainer_member_repository.get(
            db, id=relationship_id, gym_id=gym_id
        )
        if not relationship:
            raise HTTPException(status_code=404, detail="Relación no encontrada")

        return await async_trainer_member_repository.remove(db, id=relationship_id, gym_id=gym_id)


# Instancia singleton del servicio async
async_trainer_member_service = AsyncTrainerMemberService()
