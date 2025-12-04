"""
AsyncEventRepository - Repositorio async para operaciones de eventos.

Este repositorio hereda de AsyncBaseRepository y agrega métodos específicos
para operaciones de eventos con full async/await.

Migrado en FASE 2 de la conversión sync → async.
"""
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy import func, and_, or_, select
from fastapi.encoders import jsonable_encoder

from app.models.event import Event, EventParticipation, EventStatus, EventParticipationStatus
from app.models.user import User
from app.repositories.async_base import AsyncBaseRepository
from app.schemas.event import EventCreate, EventUpdate, EventParticipationCreate, EventParticipationUpdate


class AsyncEventRepository(AsyncBaseRepository[Event, EventCreate, EventUpdate]):
    """
    Repositorio async para operaciones de eventos.

    Hereda de AsyncBaseRepository:
    - get(db, id, gym_id) - Obtener evento por ID
    - get_multi(db, skip, limit, gym_id, filters) - Obtener múltiples eventos
    - create(db, obj_in, gym_id) - Crear evento
    - update(db, db_obj, obj_in, gym_id) - Actualizar evento
    - remove(db, id, gym_id) - Eliminar evento
    - exists(db, id, gym_id) - Verificar existencia

    Métodos específicos de Event:
    - create_event() - Crear evento con creator_id
    - get_events() - Búsqueda avanzada con filtros
    - get_event() - Obtener con relaciones cargadas
    - update_event() - Actualizar con tracking de cambios
    - delete_event() - Eliminar con verificación
    - get_events_by_creator() - Eventos de un creador
    - is_event_creator() - Verificar autoría
    - mark_event_completed() - Cambiar estado a completado
    """

    async def create_event(
        self,
        db: AsyncSession,
        *,
        event_in: EventCreate,
        creator_id: int,
        gym_id: int = 1
    ) -> Event:
        """
        Crear un nuevo evento con creator_id.

        Args:
            db: Sesión async de base de datos
            event_in: Datos del evento a crear
            creator_id: ID interno del usuario creador
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Evento creado

        Note:
            El campo first_message_chat se elimina automáticamente
            ya que no es parte del modelo Event.
        """
        event_data = event_in.dict()

        # Eliminar first_message_chat si existe (solo para chat inicial)
        if 'first_message_chat' in event_data:
            event_data.pop('first_message_chat')

        db_event = Event(**event_data, creator_id=creator_id, gym_id=gym_id)
        db.add(db_event)
        await db.flush()
        await db.refresh(db_event)
        return db_event

    async def get_events(
        self,
        db: AsyncSession,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[EventStatus] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        title_contains: Optional[str] = None,
        location_contains: Optional[str] = None,
        created_by: Optional[Union[int, str]] = None,
        only_available: bool = False,
        gym_id: Optional[int] = None
    ) -> List[Event]:
        """
        Obtener eventos con filtros opcionales avanzados.

        Args:
            db: Sesión async de base de datos
            skip: Registros a omitir (paginación)
            limit: Máximo de registros
            status: Filtrar por estado del evento
            start_date: Filtrar eventos que terminan después de esta fecha
            end_date: Filtrar eventos que empiezan antes de esta fecha
            title_contains: Búsqueda parcial en título
            location_contains: Búsqueda parcial en ubicación
            created_by: ID o auth0_id del creador
            only_available: Solo eventos con cupos disponibles
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Lista de eventos ordenados por start_time
        """
        stmt = select(Event).options(selectinload(Event.participants))

        filters = []

        # Filtrar por gimnasio (multi-tenant)
        if gym_id is not None:
            filters.append(Event.gym_id == gym_id)

        # Filtrar por estado
        if status:
            filters.append(Event.status == status)

        # Filtrar por rango de fechas
        if start_date:
            filters.append(Event.end_time >= start_date)

        if end_date:
            filters.append(Event.start_time <= end_date)

        # Búsquedas de texto (case-insensitive)
        if title_contains:
            filters.append(Event.title.ilike(f"%{title_contains}%"))

        if location_contains:
            filters.append(Event.location.ilike(f"%{location_contains}%"))

        # Filtrar por creador
        if created_by:
            if isinstance(created_by, str):
                # Resolver auth0_id a user_id
                user_stmt = select(User.id).where(User.auth0_id == created_by)
                user_result = await db.execute(user_stmt)
                user_id = user_result.scalar_one_or_none()
                if user_id:
                    filters.append(Event.creator_id == user_id)
                else:
                    return []  # Usuario no encontrado
            else:
                filters.append(Event.creator_id == created_by)

        # Aplicar filtros
        if filters:
            stmt = stmt.where(and_(*filters))

        # Filtrar solo eventos disponibles
        if only_available:
            count_stmt = select(func.count(EventParticipation.id)).where(
                EventParticipation.event_id == Event.id,
                EventParticipation.status == EventParticipationStatus.REGISTERED
            ).scalar_subquery()

            stmt = stmt.where(
                or_(
                    Event.max_participants == 0,  # Sin límite
                    Event.max_participants > count_stmt  # Con cupos
                )
            )

        # Ordenar y paginar
        stmt = stmt.order_by(Event.start_time)

        if limit > 0:
            stmt = stmt.limit(limit)

        if skip > 0:
            stmt = stmt.offset(skip)

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_event(self, db: AsyncSession, event_id: int) -> Optional[Event]:
        """
        Obtener un evento por ID con todas sus relaciones cargadas.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento

        Returns:
            Evento con participants, creator y chat_rooms cargados, o None
        """
        stmt = select(Event).options(
            selectinload(Event.participants),
            joinedload(Event.creator),
            selectinload(Event.chat_rooms)
        ).where(Event.id == event_id)

        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_event(
        self,
        db: AsyncSession,
        *,
        event_id: int,
        event_in: EventUpdate
    ) -> Optional[Event]:
        """
        Actualizar un evento existente.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento a actualizar
            event_in: Datos de actualización

        Returns:
            Evento actualizado o None si no existe

        Note:
            Solo actualiza campos modificados y actualiza updated_at automáticamente.
        """
        stmt = select(Event).where(Event.id == event_id)
        result = await db.execute(stmt)
        db_event = result.scalar_one_or_none()

        if not db_event:
            return None

        update_data = jsonable_encoder(event_in, exclude_unset=True)

        if not update_data:
            return db_event

        # Actualizar solo campos modificados
        modified = False
        for field, value in update_data.items():
            if getattr(db_event, field) != value:
                setattr(db_event, field, value)
                modified = True

        if modified:
            db_event.updated_at = datetime.now(timezone.utc)
            db.add(db_event)
            await db.flush()

        return db_event

    async def delete_event(self, db: AsyncSession, *, event_id: int) -> bool:
        """
        Eliminar un evento.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento a eliminar

        Returns:
            True si se eliminó, False si no existía
        """
        event = await self.get_event(db, event_id=event_id)
        if not event:
            return False

        await db.delete(event)
        await db.flush()
        return True

    async def get_events_by_creator(
        self,
        db: AsyncSession,
        *,
        creator_id: Union[int, str],
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None
    ) -> List[Event]:
        """
        Obtener eventos creados por un usuario.

        Args:
            db: Sesión async de base de datos
            creator_id: ID interno o auth0_id del creador
            skip: Registros a omitir
            limit: Máximo de registros
            gym_id: ID del gimnasio (multi-tenant)

        Returns:
            Lista de eventos del creador
        """
        # Resolver auth0_id si es string
        if isinstance(creator_id, str):
            user_stmt = select(User.id).where(User.auth0_id == creator_id)
            user_result = await db.execute(user_stmt)
            user_id = user_result.scalar_one_or_none()
            if user_id:
                creator_id = user_id
            else:
                return []

        stmt = select(Event).options(
            selectinload(Event.participants)
        ).where(Event.creator_id == creator_id)

        if gym_id is not None:
            stmt = stmt.where(Event.gym_id == gym_id)

        stmt = stmt.order_by(Event.start_time).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def is_event_creator(
        self,
        db: AsyncSession,
        *,
        event_id: int,
        user_id: Union[int, str]
    ) -> bool:
        """
        Verificar si un usuario es el creador de un evento.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            user_id: ID interno o auth0_id del usuario

        Returns:
            True si el usuario es el creador, False en caso contrario
        """
        # Resolver auth0_id si es string
        if isinstance(user_id, str):
            user_stmt = select(User.id).where(User.auth0_id == user_id)
            user_result = await db.execute(user_stmt)
            user = user_result.scalar_one_or_none()
            if user:
                user_id = user
            else:
                return False

        event = await self.get_event(db, event_id=event_id)
        if not event:
            return False

        return event.creator_id == user_id

    async def mark_event_completed(
        self,
        db: AsyncSession,
        *,
        event_id: int
    ) -> Optional[Event]:
        """
        Marcar un evento como COMPLETED.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento

        Returns:
            Evento actualizado o None si no existe o no está SCHEDULED

        Note:
            Solo eventos en estado SCHEDULED pueden marcarse como completados.
        """
        try:
            stmt = select(Event).where(
                Event.id == event_id,
                Event.status == EventStatus.SCHEDULED
            )
            result = await db.execute(stmt)
            event = result.scalar_one_or_none()

            if not event:
                return None

            event.status = EventStatus.COMPLETED
            event.updated_at = datetime.now(timezone.utc)

            db.add(event)
            await db.flush()

            return event
        except Exception as e:
            await db.rollback()
            print(f"Error al marcar evento como completado: {e}")
            return None


# Instancia singleton del repositorio async
async_event_repository = AsyncEventRepository(Event)
