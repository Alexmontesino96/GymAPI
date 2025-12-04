"""
AsyncTrainerMemberRepository - Repositorio async para relaciones trainer-member.

Este repositorio hereda de AsyncBaseRepository y agrega métodos específicos
para gestionar relaciones entre entrenadores y miembros.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, or_, select

from app.repositories.async_base import AsyncBaseRepository
from app.models.trainer_member import TrainerMemberRelationship, RelationshipStatus
from app.schemas.trainer_member import (
    TrainerMemberRelationshipCreate,
    TrainerMemberRelationshipUpdate
)


class AsyncTrainerMemberRepository(
    AsyncBaseRepository[
        TrainerMemberRelationship,
        TrainerMemberRelationshipCreate,
        TrainerMemberRelationshipUpdate
    ]
):
    """
    Repositorio async para relaciones trainer-member.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener relación por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples relaciones
    - create(db, obj_in, gym_id) - Crear relación
    - update(db, db_obj, obj_in, gym_id) - Actualizar relación
    - remove(db, id, gym_id) - Eliminar relación
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos:
    - get_by_trainer_and_member() - Buscar relación específica
    - get_by_trainer() - Todas las relaciones de un entrenador
    - get_by_member() - Todas las relaciones de un miembro
    - get_active_by_trainer() - Relaciones activas de entrenador
    - get_active_by_member() - Relaciones activas de miembro
    - get_pending_relationships() - Relaciones pendientes de un usuario
    """

    async def get_by_trainer_and_member(
        self,
        db: AsyncSession,
        *,
        trainer_id: int,
        member_id: int
    ) -> Optional[TrainerMemberRelationship]:
        """
        Obtiene una relación específica entre un entrenador y un miembro.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            member_id: ID del miembro

        Returns:
            Relación encontrada o None

        Example:
            relation = await async_trainer_member_repository.get_by_trainer_and_member(
                db,
                trainer_id=5,
                member_id=10
            )
        """
        stmt = select(TrainerMemberRelationship).where(
            and_(
                TrainerMemberRelationship.trainer_id == trainer_id,
                TrainerMemberRelationship.member_id == member_id
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_trainer(
        self,
        db: AsyncSession,
        *,
        trainer_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene todas las relaciones de un entrenador con sus miembros.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de relaciones del entrenador
        """
        stmt = select(TrainerMemberRelationship).where(
            TrainerMemberRelationship.trainer_id == trainer_id
        ).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_member(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene todas las relaciones de un miembro con sus entrenadores.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de relaciones del miembro
        """
        stmt = select(TrainerMemberRelationship).where(
            TrainerMemberRelationship.member_id == member_id
        ).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_trainer(
        self,
        db: AsyncSession,
        *,
        trainer_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene las relaciones ACTIVAS de un entrenador.

        Args:
            db: Sesión async de base de datos
            trainer_id: ID del entrenador
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de relaciones activas del entrenador
        """
        stmt = select(TrainerMemberRelationship).where(
            and_(
                TrainerMemberRelationship.trainer_id == trainer_id,
                TrainerMemberRelationship.status == RelationshipStatus.ACTIVE
            )
        ).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_active_by_member(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene las relaciones ACTIVAS de un miembro.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de relaciones activas del miembro
        """
        stmt = select(TrainerMemberRelationship).where(
            and_(
                TrainerMemberRelationship.member_id == member_id,
                TrainerMemberRelationship.status == RelationshipStatus.ACTIVE
            )
        ).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_pending_relationships(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[TrainerMemberRelationship]:
        """
        Obtiene las relaciones PENDIENTES de un usuario (como entrenador o miembro).

        Args:
            db: Sesión async de base de datos
            user_id: ID del usuario (puede ser trainer_id o member_id)
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de relaciones pendientes donde el usuario participa
        """
        stmt = select(TrainerMemberRelationship).where(
            and_(
                or_(
                    TrainerMemberRelationship.trainer_id == user_id,
                    TrainerMemberRelationship.member_id == user_id
                ),
                TrainerMemberRelationship.status == RelationshipStatus.PENDING
            )
        ).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())


# Instancia singleton del repositorio async
async_trainer_member_repository = AsyncTrainerMemberRepository(TrainerMemberRelationship)
