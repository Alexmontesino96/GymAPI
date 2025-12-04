"""
AsyncEventParticipationRepository - Repositorio async para participaciones en eventos.

Este repositorio hereda de AsyncBaseRepository y agrega métodos específicos
para gestionar participaciones en eventos.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List, Optional, Union
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import select, and_

from app.models.event import Event, EventParticipation, EventParticipationStatus, PaymentStatusType
from app.models.user import User
from app.repositories.async_base import AsyncBaseRepository
from app.schemas.event import EventParticipationCreate, EventParticipationUpdate


class AsyncEventParticipationRepository(
    AsyncBaseRepository[EventParticipation, EventParticipationCreate, EventParticipationUpdate]
):
    """
    Repositorio async para operaciones de participaciones en eventos.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener participación por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples participaciones
    - create(db, obj_in, gym_id) - Crear participación
    - update(db, db_obj, obj_in, gym_id) - Actualizar participación
    - remove(db, id, gym_id) - Eliminar participación
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos de EventParticipation:
    - create_participation() - Crear con validaciones
    - get_participation_by_member_and_event() - Buscar participación específica
    - get_event_participants() - Participantes de un evento
    - get_member_events() - Eventos de un miembro
    - cancel_participation() - Cancelar participación
    - fill_vacancies_from_waiting_list() - Promover desde lista de espera
    """

    async def create_participation(
        self,
        db: AsyncSession,
        *,
        event_id: int,
        member_id: int,
        status: EventParticipationStatus = EventParticipationStatus.REGISTERED,
        payment_status: Optional[PaymentStatusType] = None
    ) -> EventParticipation:
        """
        Crear una nueva participación en un evento.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            member_id: ID del miembro participante
            status: Estado inicial de la participación
            payment_status: Estado del pago (opcional)

        Returns:
            Participación creada

        Note:
            No valida capacidad del evento. Usar en servicios con validación previa.
        """
        participation = EventParticipation(
            event_id=event_id,
            member_id=member_id,
            status=status,
            payment_status=payment_status,
            registered_at=datetime.utcnow()
        )

        db.add(participation)
        await db.flush()
        await db.refresh(participation)
        return participation

    async def get_participation(
        self,
        db: AsyncSession,
        participation_id: int
    ) -> Optional[EventParticipation]:
        """
        Obtener una participación por ID con relaciones cargadas.

        Args:
            db: Sesión async de base de datos
            participation_id: ID de la participación

        Returns:
            Participación con event y member cargados, o None
        """
        stmt = select(EventParticipation).options(
            joinedload(EventParticipation.event),
            joinedload(EventParticipation.member)
        ).where(EventParticipation.id == participation_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_participation_by_member_and_event(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        event_id: int
    ) -> Optional[EventParticipation]:
        """
        Obtener la participación de un miembro en un evento específico.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            event_id: ID del evento

        Returns:
            Participación encontrada o None
        """
        stmt = select(EventParticipation).options(
            joinedload(EventParticipation.event),
            joinedload(EventParticipation.member)
        ).where(
            and_(
                EventParticipation.member_id == member_id,
                EventParticipation.event_id == event_id
            )
        )

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_participation(
        self,
        db: AsyncSession,
        *,
        participation_id: int,
        participation_in: EventParticipationUpdate
    ) -> Optional[EventParticipation]:
        """
        Actualizar una participación existente.

        Args:
            db: Sesión async de base de datos
            participation_id: ID de la participación
            participation_in: Datos de actualización

        Returns:
            Participación actualizada o None si no existe
        """
        participation = await self.get_participation(db, participation_id)
        if not participation:
            return None

        update_data = participation_in.dict(exclude_unset=True)

        for field, value in update_data.items():
            if hasattr(participation, field):
                setattr(participation, field, value)

        db.add(participation)
        await db.flush()
        await db.refresh(participation)
        return participation

    async def delete_participation(
        self,
        db: AsyncSession,
        *,
        participation_id: int
    ) -> bool:
        """
        Eliminar una participación.

        Args:
            db: Sesión async de base de datos
            participation_id: ID de la participación

        Returns:
            True si se eliminó, False si no existía
        """
        participation = await self.get_participation(db, participation_id)
        if not participation:
            return False

        await db.delete(participation)
        await db.flush()
        return True

    async def get_event_participants(
        self,
        db: AsyncSession,
        *,
        event_id: int,
        status: Optional[EventParticipationStatus] = None
    ) -> List[EventParticipation]:
        """
        Obtener todos los participantes de un evento.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            status: Filtrar por estado de participación (opcional)

        Returns:
            Lista de participaciones con member cargado
        """
        stmt = select(EventParticipation).options(
            joinedload(EventParticipation.member)
        ).where(EventParticipation.event_id == event_id)

        if status:
            stmt = stmt.where(EventParticipation.status == status)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_member_events(
        self,
        db: AsyncSession,
        *,
        member_id: int,
        status: Optional[EventParticipationStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[EventParticipation]:
        """
        Obtener eventos en los que participa un miembro.

        Args:
            db: Sesión async de base de datos
            member_id: ID del miembro
            status: Filtrar por estado de participación (opcional)
            skip: Registros a omitir
            limit: Máximo de registros

        Returns:
            Lista de participaciones con event cargado
        """
        stmt = select(EventParticipation).options(
            joinedload(EventParticipation.event)
        ).where(EventParticipation.member_id == member_id)

        if status:
            stmt = stmt.where(EventParticipation.status == status)

        stmt = stmt.offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def cancel_participation(
        self,
        db: AsyncSession,
        *,
        participation_id: int
    ) -> Optional[EventParticipation]:
        """
        Cancelar una participación.

        Args:
            db: Sesión async de base de datos
            participation_id: ID de la participación

        Returns:
            Participación cancelada o None si no existe

        Note:
            Cambia el estado a CANCELLED y registra la fecha de cancelación.
        """
        participation = await self.get_participation(db, participation_id)
        if not participation:
            return None

        participation.status = EventParticipationStatus.CANCELLED
        participation.cancelled_at = datetime.utcnow()

        db.add(participation)
        await db.flush()
        await db.refresh(participation)
        return participation

    async def fill_vacancies_from_waiting_list(
        self,
        db: AsyncSession,
        event_id: int
    ) -> List[EventParticipation]:
        """
        Promover participantes de lista de espera a registrados.

        Args:
            db: AsyncSession de base de datos
            event_id: ID del evento

        Returns:
            Lista de participaciones promovidas

        Note:
            Promueve automáticamente a participantes en espera cuando hay cupos.
        """
        # Obtener evento para verificar capacidad
        event_stmt = select(Event).where(Event.id == event_id)
        event_result = await db.execute(event_stmt)
        event = event_result.scalar_one_or_none()

        if not event or event.max_participants == 0:
            return []  # Sin límite o evento no existe

        # Contar participantes registrados
        registered_stmt = select(EventParticipation).where(
            EventParticipation.event_id == event_id,
            EventParticipation.status == EventParticipationStatus.REGISTERED
        )
        registered_result = await db.execute(registered_stmt)
        registered_count = len(list(registered_result.scalars().all()))

        vacancies = event.max_participants - registered_count

        if vacancies <= 0:
            return []  # No hay vacantes

        # Obtener participantes en espera (ordenados por registered_at)
        waiting_stmt = select(EventParticipation).where(
            EventParticipation.event_id == event_id,
            EventParticipation.status == EventParticipationStatus.WAITING_LIST
        ).order_by(EventParticipation.registered_at).limit(vacancies)

        waiting_result = await db.execute(waiting_stmt)
        waiting_participants = list(waiting_result.scalars().all())

        # Promover participantes
        promoted = []
        for participant in waiting_participants:
            participant.status = EventParticipationStatus.REGISTERED
            participant.registered_at = datetime.utcnow()
            db.add(participant)
            promoted.append(participant)

        if promoted:
            await db.flush()
            for p in promoted:
                await db.refresh(p)

        return promoted


# Instancia singleton del repositorio async
async_event_participation_repository = AsyncEventParticipationRepository(EventParticipation)
