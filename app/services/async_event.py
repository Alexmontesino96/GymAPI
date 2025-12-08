"""
AsyncEventService - Servicio async para gestión de eventos con soporte para caché.

Este módulo proporciona un servicio totalmente async que encapsula la lógica de negocio
relacionada con eventos utilizando caché Redis y repositorios async.

Migrado en FASE 3 de la conversión sync → async.
"""

import logging
from typing import List, Optional, Union, Dict, Any
from datetime import datetime

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.async_event import async_event_repository
from app.repositories.async_event_participation import async_event_participation_repository
from app.models.event import Event, EventParticipation, EventStatus, EventParticipationStatus
from app.schemas.event import (
    Event as EventSchema,
    EventCreate,
    EventUpdate,
    EventParticipationCreate,
    EventParticipationUpdate,
    EventWithParticipantCount,
    EventDetail
)
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class AsyncEventService:
    """
    Servicio async para gestionar eventos con soporte para caché.

    Todos los métodos son async y utilizan AsyncSession y repositorios async.
    Compatible con Redis async para caching de alto rendimiento.

    Métodos principales:
    - get_events_cached() - Obtener lista de eventos con filtros y caché
    - get_event_cached() - Obtener evento por ID con caché
    - get_events_by_creator_cached() - Eventos de un creador con caché
    - create_event() - Crear evento e invalidar caché
    - update_event() - Actualizar evento con promoción desde waiting list
    - delete_event() - Eliminar evento y limpiar SQS
    - get_event_participants_cached() - Obtener participantes con caché
    - invalidate_event_caches() - Invalidar cachés por patrones
    """

    async def get_events_cached(
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
        gym_id: Optional[int] = None,
        redis_client: Optional[Redis] = None
    ) -> List[EventWithParticipantCount]:
        """
        Obtiene eventos con filtro y paginación, utilizando caché.

        Args:
            db: Sesión async de base de datos
            skip: Número de registros a omitir (paginación)
            limit: Límite de registros a devolver (paginación)
            status: Filtrar por estado del evento
            start_date: Filtrar eventos que terminan después de esta fecha
            end_date: Filtrar eventos que comienzan antes de esta fecha
            title_contains: Filtrar por título (búsqueda parcial)
            location_contains: Filtrar por ubicación (búsqueda parcial)
            created_by: Filtrar por creador (ID o Auth0 ID)
            only_available: Filtrar solo eventos con cupo disponible
            gym_id: Filtrar por gimnasio específico
            redis_client: Cliente Redis para caché

        Returns:
            Lista de eventos que cumplen con los criterios

        Note:
            Caché TTL: 5 minutos
            Clave de caché incluye todos los parámetros de filtro
        """
        # Construir clave de caché basada en parámetros
        cache_parts = [
            f"events:list",
            f"skip:{skip}",
            f"limit:{limit}"
        ]

        if status:
            cache_parts.append(f"status:{status}")
        if start_date:
            cache_parts.append(f"start:{start_date.isoformat()}")
        if end_date:
            cache_parts.append(f"end:{end_date.isoformat()}")
        if title_contains:
            cache_parts.append(f"title:{title_contains}")
        if location_contains:
            cache_parts.append(f"location:{location_contains}")
        if created_by:
            cache_parts.append(f"creator:{created_by}")
        if only_available:
            cache_parts.append("only_available:true")
        if gym_id:
            cache_parts.append(f"gym:{gym_id}")

        cache_key = ":".join(cache_parts)

        # Definir función de consulta a BD
        async def db_fetch():
            # Obtener diccionarios desde el repositorio async
            event_dicts = await async_event_repository.get_events_with_counts(
                db,
                skip=skip,
                limit=limit,
                status=status,
                start_date=start_date,
                end_date=end_date,
                title_contains=title_contains,
                location_contains=location_contains,
                created_by=created_by,
                only_available=only_available,
                gym_id=gym_id
            )

            # Convertir diccionarios a objetos EventWithParticipantCount
            events_with_counts = []
            for event_dict in event_dicts:
                event_with_count = EventWithParticipantCount(**event_dict)
                events_with_counts.append(event_with_count)

            return events_with_counts

        try:
            # Usar el servicio de caché genérico
            if redis_client:
                result = await CacheService.get_or_set(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=db_fetch,
                    model_class=EventWithParticipantCount,
                    expiry_seconds=300,  # 5 minutos de TTL
                    is_list=True
                )
                return result
            else:
                return await db_fetch()
        except Exception as e:
            logger.error(f"Error obteniendo eventos cacheados: {e}", exc_info=True)
            # Fallback a la BD en caso de error
            return await db_fetch()

    async def get_event_cached(
        self,
        db: AsyncSession,
        event_id: int,
        gym_id: Optional[int] = None,
        redis_client: Optional[Redis] = None
    ) -> Optional[EventDetail]:
        """
        Obtiene un evento por ID utilizando caché.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            gym_id: ID del gimnasio (opcional, para validación multi-tenant)
            redis_client: Cliente Redis para caché

        Returns:
            Detalle del evento o None si no existe

        Note:
            gym_id es opcional para compatibilidad con workers.
            Caché TTL: 5 minutos
        """
        # Definir clave de caché
        cache_key = f"event:detail:{event_id}"
        if gym_id:
            cache_key += f":gym:{gym_id}"

        # Definir función de consulta a BD
        async def db_fetch():
            event = await async_event_repository.get_event(db, event_id=event_id)
            if not event:
                return None

            # Verificar que el evento pertenece al gimnasio actual (solo si gym_id se proporciona)
            if gym_id and event.gym_id != gym_id:
                return None

            # Obtener datos adicionales para EventDetail
            participants_count = len(event.participants) if event.participants else 0

            # Crear objeto EventDetail
            event_detail = EventDetail(
                id=event.id,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                location=event.location,
                max_participants=event.max_participants,
                status=event.status,
                created_at=event.created_at,
                updated_at=event.updated_at,
                creator_id=event.creator_id,
                creator=event.creator,
                participants=event.participants,
                participants_count=participants_count,
                gym_id=event.gym_id
            )
            return event_detail

        try:
            # Usar el servicio de caché genérico
            if redis_client:
                result = await CacheService.get_or_set(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=db_fetch,
                    model_class=EventDetail,
                    expiry_seconds=300,  # 5 minutos de TTL
                    is_list=False
                )
                return result
            else:
                return await db_fetch()
        except Exception as e:
            logger.error(f"Error obteniendo evento cacheado: {e}", exc_info=True)
            # Fallback a la BD en caso de error
            return await db_fetch()

    async def get_events_by_creator_cached(
        self,
        db: AsyncSession,
        creator_id: Union[int, str],
        skip: int = 0,
        limit: int = 100,
        gym_id: Optional[int] = None,
        redis_client: Optional[Redis] = None
    ) -> List[EventWithParticipantCount]:
        """
        Obtiene eventos creados por un usuario específico utilizando caché.

        Args:
            db: Sesión async de base de datos
            creator_id: ID del creador (interno o Auth0)
            skip: Número de registros a omitir (paginación)
            limit: Límite de registros a devolver (paginación)
            gym_id: Filtrar por gimnasio específico
            redis_client: Cliente Redis para caché

        Returns:
            Lista de eventos creados por el usuario

        Note:
            Caché TTL: 5 minutos
            Incluye contador de participantes
        """
        # Definir clave de caché
        cache_key = f"events:creator:{creator_id}:skip:{skip}:limit:{limit}"
        if gym_id:
            cache_key += f":gym:{gym_id}"

        logger.debug(f"Buscando en caché con clave: {cache_key}")

        # Definir función de consulta a BD
        async def db_fetch():
            try:
                logger.debug(f"Cache miss. Consultando eventos de BD para creador {creator_id}")
                # Obtener eventos del repositorio async
                events = await async_event_repository.get_events_by_creator(
                    db,
                    creator_id=creator_id,
                    skip=skip,
                    limit=limit,
                    gym_id=gym_id
                )

                # Convertir objetos SQLAlchemy a modelos Pydantic
                event_schemas = []
                for event in events:
                    try:
                        # Calcular el conteo de participantes de manera segura
                        participants_count = len(event.participants) if hasattr(event, 'participants') and event.participants is not None else 0

                        # Crear objeto EventWithParticipantCount
                        event_schema = EventWithParticipantCount(
                            id=event.id,
                            title=event.title,
                            description=event.description,
                            start_time=event.start_time,
                            end_time=event.end_time,
                            location=event.location if hasattr(event, 'location') else None,
                            max_participants=event.max_participants,
                            status=event.status,
                            created_at=event.created_at,
                            updated_at=event.updated_at,
                            creator_id=event.creator_id,
                            participants_count=participants_count,
                            gym_id=event.gym_id
                        )
                        event_schemas.append(event_schema)
                    except Exception as e:
                        logger.error(f"Error convirtiendo evento a schema: {e}", exc_info=True)
                        continue

                logger.debug(f"Obtenidos {len(event_schemas)} eventos de BD para clave {cache_key}")
                return event_schemas
            except Exception as e:
                logger.error(f"Error general en db_fetch para eventos: {e}", exc_info=True)
                return []

        try:
            # Usar el servicio de caché genérico
            if redis_client:
                try:
                    logger.debug(f"Intentando obtener/almacenar en caché con clave: {cache_key}")
                    result = await CacheService.get_or_set(
                        redis_client=redis_client,
                        cache_key=cache_key,
                        db_fetch_func=db_fetch,
                        model_class=EventWithParticipantCount,
                        expiry_seconds=300,  # 5 minutos de TTL
                        is_list=True
                    )
                    logger.debug(f"Éxito en CacheService.get_or_set. Obtenidos {len(result)} eventos.")
                    return result
                except Exception as e:
                    logger.error(f"Error en CacheService.get_or_set para {cache_key}: {e}", exc_info=True)
                    logger.warning(f"Fallback a consulta directa a BD para {cache_key}")
                    return await db_fetch()
            else:
                logger.debug("Redis client no disponible, consultando directamente a BD")
                return await db_fetch()
        except Exception as e:
            logger.error(f"Error general obteniendo eventos por creador: {e}", exc_info=True)
            # Fallback a la BD en caso de error
            try:
                return await db_fetch()
            except Exception as fetch_error:
                logger.error(f"Error en fallback a BD: {fetch_error}", exc_info=True)
                return []

    async def create_event(
        self,
        db: AsyncSession,
        event_in: EventCreate,
        creator_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Event:
        """
        Crea un nuevo evento e invalida cachés relacionadas.

        Args:
            db: Sesión async de base de datos
            event_in: Datos del evento
            creator_id: ID del creador
            gym_id: ID del gimnasio
            redis_client: Cliente Redis para invalidar caché

        Returns:
            El evento creado

        Note:
            Invalida automáticamente cachés de:
            - Lista de eventos
            - Eventos del gimnasio
            - Eventos del creador
        """
        event = await async_event_repository.create(
            db,
            obj_in=event_in,
            creator_id=creator_id,
            gym_id=gym_id
        )

        # Invalidar cachés relacionadas
        if redis_client:
            await self.invalidate_event_caches(redis_client, gym_id=gym_id, creator_id=creator_id)

        return event

    async def update_event(
        self,
        db: AsyncSession,
        event_id: int,
        event_in: EventUpdate,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> Optional[Event]:
        """
        Actualiza un evento e invalida cachés relacionadas.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            event_in: Datos de actualización
            gym_id: ID del gimnasio (multi-tenant)
            redis_client: Cliente Redis para invalidar caché

        Returns:
            El evento actualizado o None si no existe

        Note:
            Si aumenta la capacidad, promociona usuarios desde waiting list.
            Invalida cachés automáticamente.
        """
        # Obtener evento para conocer su capacidad actual y creador
        event = await async_event_repository.get(db, id=event_id, gym_id=gym_id)
        if not event:
            return None

        creator_id = event.creator_id
        old_capacity = event.max_participants

        # Actualizar evento
        updated_event = await async_event_repository.update(
            db,
            db_obj=event,
            obj_in=event_in,
            gym_id=gym_id
        )

        # Si aumentó la capacidad, llenar huecos desde la waiting list
        try:
            if updated_event and updated_event.max_participants and old_capacity is not None:
                if updated_event.max_participants > old_capacity > 0:
                    promoted = await async_event_participation_repository.fill_vacancies_from_waiting_list(
                        db, event_id=event_id
                    )
                    if promoted:
                        logger.info(
                            f"Se promovieron {len(promoted)} usuarios de la waiting list para evento {event_id}"
                        )
        except Exception as promo_exc:
            logger.error(
                f"Error al promover usuarios de la waiting list tras aumentar capacidad de evento {event_id}: {promo_exc}",
                exc_info=True,
            )

        # Invalidar cachés relacionadas
        if redis_client and updated_event:
            await self.invalidate_event_caches(redis_client, event_id=event_id, gym_id=gym_id, creator_id=creator_id)

        return updated_event

    async def delete_event(
        self,
        db: AsyncSession,
        event_id: int,
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> bool:
        """
        Elimina un evento e invalida cachés relacionadas.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            gym_id: ID del gimnasio (multi-tenant)
            redis_client: Cliente Redis para invalidar caché

        Returns:
            True si el evento fue eliminado, False si no existe

        Note:
            También elimina mensajes pendientes en SQS relacionados con el evento.
            Invalida cachés automáticamente.
        """
        # Obtener evento para conocer su creador
        event = await async_event_repository.get(db, id=event_id, gym_id=gym_id)
        if not event:
            return False

        creator_id = event.creator_id

        # Eliminar evento
        result = await async_event_repository.remove(db, id=event_id, gym_id=gym_id)

        # Invalidar cachés relacionadas
        if redis_client and result:
            await self.invalidate_event_caches(redis_client, event_id=event_id, gym_id=gym_id, creator_id=creator_id)

        # Eliminar mensajes pendientes en SQS relacionados con este evento
        try:
            from app.services.async_queue_services import AsyncQueueService
            await AsyncQueueService.cancel_event_processing(event_id)
        except Exception as sqs_exc:
            logger.error(
                f"Error al limpiar mensajes de SQS para evento {event_id}: {sqs_exc}",
                exc_info=True,
            )

        return result is not None

    async def invalidate_event_caches(
        self,
        redis_client: Redis,
        event_id: Optional[int] = None,
        gym_id: Optional[int] = None,
        creator_id: Optional[int] = None
    ) -> None:
        """
        Invalida cachés relacionadas con eventos.

        Args:
            redis_client: Cliente Redis
            event_id: ID del evento específico (opcional)
            gym_id: ID del gimnasio (opcional)
            creator_id: ID del creador (opcional)

        Note:
            Usa patrones de Redis SCAN para invalidar múltiples claves.
            Patrones invalidados:
            - event:detail:{event_id}
            - events:list:*
            - events:list:*gym:{gym_id}*
            - events:creator:{creator_id}:*
        """
        patterns = []

        # Invalidar caché de evento específico
        if event_id:
            patterns.append(f"event:detail:{event_id}")

        # Invalidar cachés de listas de eventos
        patterns.append("events:list:*")

        # Invalidar cachés específicas de gimnasio
        if gym_id:
            patterns.append(f"events:list:*gym:{gym_id}*")

        # Invalidar cachés específicas de creador
        if creator_id:
            patterns.append(f"events:creator:{creator_id}:*")

        # Eliminar cachés usando patrones
        for pattern in patterns:
            try:
                count = await CacheService.delete_pattern(redis_client, pattern)
                logger.debug(f"Invalidadas {count} cachés con patrón: {pattern}")
            except Exception as e:
                logger.error(f"Error invalidando cachés con patrón {pattern}: {e}", exc_info=True)

    # === Métodos para participaciones === #

    async def get_event_participants_cached(
        self,
        db: AsyncSession,
        event_id: int,
        status: Optional[EventParticipationStatus] = None,
        redis_client: Optional[Redis] = None
    ) -> List[EventParticipation]:
        """
        Obtiene participantes de un evento utilizando caché.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento
            status: Filtrar por estado de participación
            redis_client: Cliente Redis para caché

        Returns:
            Lista de participaciones en el evento

        Note:
            Caché TTL: 5 minutos
            Soporta filtrado por estado (CONFIRMED, WAITING_LIST, CANCELLED)
        """
        # Definir clave de caché
        cache_key = f"event:{event_id}:participants"
        if status:
            cache_key += f":status:{status}"

        # Definir función de consulta a BD
        async def db_fetch():
            return await async_event_participation_repository.get_event_participants(
                db,
                event_id=event_id,
                status=status
            )

        try:
            # Usar el servicio de caché genérico
            if redis_client:
                from app.schemas.event import EventParticipation as EventParticipationSchema
                result = await CacheService.get_or_set(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=db_fetch,
                    model_class=EventParticipationSchema,
                    expiry_seconds=300,  # 5 minutos de TTL
                    is_list=True
                )
                return result
            else:
                return await db_fetch()
        except Exception as e:
            logger.error(f"Error obteniendo participantes de evento: {e}", exc_info=True)
            # Fallback a la BD en caso de error
            return await db_fetch()


# Instancia singleton del servicio async
async_event_service = AsyncEventService()
