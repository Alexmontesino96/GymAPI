"""
Events Module - API Endpoints

This module handles the creation, management, and participation in gym events.
Events can be workshops, special classes, competitions, or any other activities
organized by the gym. The module provides endpoints for:

- Creating and managing events (trainers and admins)
- Viewing event details (all users)
- Registering for events (members)
- Managing event participation (trainers and event creators)
- Administrative operations (admins only)

All endpoints are protected with appropriate permission scopes.
"""

from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Security
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, get_current_user_with_permissions, Auth0User, auth
from app.core.tenant import get_current_gym, verify_gym_access
from app.models.gym import Gym
from app.schemas.event import (
    Event as EventSchema, 
    EventCreate, 
    EventUpdate, 
    EventDetail,
    EventParticipation as EventParticipationSchema, 
    EventParticipationCreate, 
    EventParticipationUpdate,
    EventWithParticipantCount,
    EventsSearchParams
)
from app.models.event import EventStatus, EventParticipationStatus, Event, EventParticipation
from app.models.user import UserRole, User
from app.repositories.event import event_repository, event_participation_repository
from fastapi.responses import JSONResponse


router = APIRouter()


# Event Endpoints
@router.post("/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
async def create_event(
    *,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    current_gym: Gym = Depends(get_current_gym),  # Obtener gimnasio actual
    current_user: Auth0User = Security(auth.get_user, scopes=["create:events"])
) -> Any:
    """
    Create a new event.
    
    This endpoint allows trainers and administrators to create new events
    in the system. The current user is automatically assigned as the creator.
    
    Permissions:
        - Requires 'create:events' scope (trainers and administrators)
        
    Args:
        db: Database session
        event_in: Event data
        current_gym: Current gym context
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        Event: The created event
    """
    # Get Auth0 user ID
    user_id = current_user.id
    
    # Verificar si current_gym es un objeto Gym o un ID (entero)
    gym_id = current_gym.id if hasattr(current_gym, 'id') else current_gym
    
    # Create event
    event = event_repository.create_event(
        db=db, 
        event_in=event_in, 
        creator_id=user_id,
        gym_id=gym_id
    )
    
    # Crear automáticamente sala de chat para el evento
    try:
        # Importar servicio de chat
        from app.services.chat import chat_service
        from app.schemas.chat import ChatRoomCreate
        
        # Crear sala de chat asociada al evento
        chat_room_data = ChatRoomCreate(
            name=f"Evento {event.title}",
            is_direct=False,
            event_id=event.id,
            member_ids=[user_id]  # Inicialmente solo el creador
        )
        
        # Intentar crear la sala de chat (sin esperar respuesta)
        chat_service.create_room(db, user_id, chat_room_data)
        
        # No bloqueamos ni devolvemos error si falla la creación del chat
        # El chat se puede crear más tarde cuando alguien lo solicite
    except Exception as e:
        # Solo loggear el error sin interrumpir la creación del evento
        import logging
        logger = logging.getLogger("events_api")
        logger.error(f"Error al crear sala de chat para evento {event.id}: {e}")
    
    return event


@router.get("/", response_model=List[EventWithParticipantCount])
async def read_events(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    status: Optional[EventStatus] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    title_contains: Optional[str] = None,
    location_contains: Optional[str] = None,
    created_by: Optional[int] = None,
    only_available: bool = False,
    current_gym: Gym = Depends(verify_gym_access),  # Verificar acceso al gimnasio
    current_user: Auth0User = Security(auth.get_user, scopes=["read_events"])
) -> Any:
    """
    Retrieve a list of events for the current gym with optional filters.
    
    This endpoint returns a paginated list of events that can be filtered
    by various criteria such as status, date range, title, location, and 
    availability. Each event includes a count of current participants.
    
    Permissions:
        - Requires 'read_events' scope (all authenticated users)
        - User must be a member of the specified gym
        
    Args:
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        status: Filter by event status (SCHEDULED, CANCELLED, COMPLETED)
        start_date: Filter events starting on or after this date
        end_date: Filter events ending on or before this date
        title_contains: Filter events with titles containing this string
        location_contains: Filter events with locations containing this string
        created_by: Filter events created by a specific user ID
        only_available: If true, only return events with available spots
        current_gym: The current gym (tenant) context
        current_user: Authenticated user
        
    Returns:
        List[EventWithParticipantCount]: List of events with participant counts
    """
    # Usar la versión optimizada que calcula participantes directamente en SQL
    events_with_counts = event_repository.get_events_with_counts(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        start_date=start_date,
        end_date=end_date,
        title_contains=title_contains,
        location_contains=location_contains,
        created_by=created_by,
        only_available=only_available,
        gym_id=current_gym.id  # Filtrar por gimnasio
    )
    
    # Convertir directamente a modelos Pydantic
    result = [EventWithParticipantCount(**event_dict) for event_dict in events_with_counts]
    return result


@router.get("/me", response_model=List[EventSchema])
async def read_my_events(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Security(auth.get_user, scopes=["read:own_events"])
) -> Any:
    """
    Retrieve events created by the authenticated user.
    
    This endpoint allows trainers and administrators to view the events
    they have created. It provides a convenient way to manage one's own events.
    
    Permissions:
        - Requires 'read_own_events' scope (all authenticated users)
        
    Args:
        db: Database session
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return (pagination)
        current_user: Authenticated user
        
    Returns:
        List[Event]: List of events created by the user
    """
    # Get Auth0 user ID
    user_id = current_user.id
    events = event_repository.get_events_by_creator(
        db=db, creator_id=user_id, skip=skip, limit=limit
    )
    return events


@router.get("/{event_id}", response_model=EventDetail)
async def read_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento a obtener", ge=1),
    current_gym: Gym = Depends(verify_gym_access),  # Verificar acceso al gimnasio
    current_user: Auth0User = Security(auth.get_user, scopes=["read_events"])
) -> Any:
    """
    Retrieve details of a specific event by ID.
    
    This endpoint returns detailed information about an event, including
    its title, description, date/time, location, and capacity. The participants
    list is only included if the requesting user is the event creator or an admin.
    
    Permissions:
        - Requires 'read_events' scope (all authenticated users)
        - Viewing participant list requires event ownership or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event to retrieve
        current_gym: The current gym (tenant) context
        current_user: Authenticated user
        
    Returns:
        EventDetail: Detailed event information
        
    Raises:
        HTTPException: 404 if event not found
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Check permissions to view participants
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    is_creator = event.creator_id == user_id
    
    # Create detailed object
    event_dict = EventSchema.from_orm(event).dict()
    
    # Include participants only if admin or creator
    if is_admin or is_creator:
        event_dict["participants"] = [
            EventParticipationSchema.from_orm(p) for p in event.participants
        ]
    else:
        # For normal users, include only count
        event_dict["participants"] = []
        event_dict["participants_count"] = len([
            p for p in event.participants 
            if p.status == EventParticipationStatus.REGISTERED
        ])
        
    return EventDetail(**event_dict)


@router.put("/{event_id}", response_model=EventSchema)
async def update_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    event_in: EventUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["create:events"])
) -> Any:
    """
    Update an existing event.
    
    This endpoint allows the event creator or administrators to update
    event details such as title, description, time, location, capacity,
    and status. Only the creator of the event or administrators can perform
    this operation.
    
    Permissions:
        - Requires 'update:events' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event to update
        event_in: Updated event data
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        Event: The updated event
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    # Verificación previa rápida para evitar consultas innecesarias
    update_data = event_in.dict(exclude_unset=True)
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No update data provided"
        )
    
    # Obtener permisos de usuario para verificaciones
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = any(perm in user_permissions for perm in ["admin:all", "admin:events"])
    
    # Para administradores, podemos omitir la verificación del creador
    if is_admin:
        # Los administradores pueden actualizar cualquier evento
        updated_event = event_repository.update_event_efficient(
            db=db, event_id=event_id, event_in=event_in
        )
        
        if not updated_event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
            
        return updated_event
    
    # Para usuarios normales, verificar si son el creador en una sola consulta
    # Este enfoque evita cargar todo el evento si el usuario no es el creador
    creator_id = db.query(Event.creator_id).filter(Event.id == event_id).scalar()
    
    if not creator_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Verificar si el usuario es el creador
    is_creator = False
    
    # Si el ID de Auth0 del usuario corresponde al creador
    if isinstance(user_id, str):
        # Consulta optimizada que verifica la relación en una sola operación
        creator_auth0_id = db.query(User.auth0_id).filter(User.id == creator_id).scalar()
        is_creator = creator_auth0_id == user_id
    else:
        is_creator = creator_id == user_id
    
    if not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this event"
        )
    
    # Actualizar el evento con el método eficiente
    updated_event = event_repository.update_event_efficient(
        db=db, event_id=event_id, event_in=event_in
    )
    
    return updated_event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["delete:events"])
) -> None:
    """
    Delete an event.
    
    This endpoint allows the event creator or administrators to delete
    an event. This will also remove all associated participations.
    Only the creator of the event or administrators can perform this operation.
    
    Permissions:
        - Requires 'delete:events' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event to delete
        current_user: Authenticated user with appropriate permissions
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Verify permissions
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    # Only the creator or an admin can delete
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to delete this event"
        )
    
    # Delete event
    event_repository.delete_event(db=db, event_id=event_id)
    return None


@router.delete("/admin/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:events"])
) -> None:
    """
    Administrative endpoint to delete any event regardless of ownership.
    
    This is a specialized admin-only endpoint that allows administrators to
    delete any event without ownership verification. It's useful for content
    moderation and managing events when the original creator is unavailable.
    
    Permissions:
        - Requires 'admin:events' scope (administrators only)
        - This is a protected administrative operation
        
    Args:
        db: Database session
        event_id: ID of the event to delete
        current_user: Authenticated administrator
        
    Raises:
        HTTPException: 404 if event not found, 500 for other errors
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Delete event without ownership verification
    try:
        event_repository.delete_event(db=db, event_id=event_id)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting event: {str(e)}"
        )


# Event Participation Endpoints
@router.post("/participation", response_model=EventParticipationSchema, status_code=status.HTTP_201_CREATED)
async def register_for_event(
    *,
    db: Session = Depends(get_db),
    participation_in: EventParticipationCreate,
    current_gym: Gym = Depends(verify_gym_access),  # Verificar acceso al gimnasio
    current_user: Auth0User = Security(auth.get_user, scopes=["create:participations"])
) -> Any:
    """
    Register for an event.
    
    This endpoint allows members to register for events. It performs various
    checks to ensure the event is available, has capacity, and the user isn't
    already registered. If successful, the user is added to the event's participants.
    
    Permissions:
        - Requires 'create:participations' scope (all authenticated users)
        
    Args:
        db: Database session
        participation_in: Participation data including event ID
        current_gym: The current gym context
        current_user: Authenticated user
        
    Returns:
        EventParticipation: The created participation record
        
    Raises:
        HTTPException: 404 if event not found, 400 for validation errors
    """
    # Registro para monitoreo de rendimiento
    import time
    import logging
    logger = logging.getLogger("events_api")
    start_time = time.time()
    
    # Obtener el ID del usuario Auth0
    user_id = current_user.id
    event_id = participation_in.event_id
    gym_id = current_gym.id
    
    logger.info(f"Procesando inscripción - user: {user_id}, event: {event_id}, gym: {gym_id}")
    
    try:
        # 1. Optimización: Realizar todas las verificaciones en una sola consulta
        from sqlalchemy import and_, func, select, text
        from app.models.user import User
        
        # Subconsulta para contar participantes registrados
        registered_count_subq = (
            select(func.count(EventParticipation.id))
            .where(
                and_(
                    EventParticipation.event_id == event_id,
                    EventParticipation.status == EventParticipationStatus.REGISTERED
                )
            )
            .scalar_subquery()
        )
        
        # Obtener usuario interno + evento + recuento de participantes en una sola consulta
        query = db.query(
            User.id.label('user_id'),
            Event.id.label('event_id'),
            Event.status.label('event_status'),
            Event.max_participants.label('max_participants'),
            Event.gym_id.label('gym_id'),
            registered_count_subq.label('registered_count')
        ).outerjoin(
            Event, Event.id == event_id
        ).filter(
            User.auth0_id == user_id,
            Event.gym_id == gym_id
        )
        
        # Ejecutar consulta optimizada
        result = query.first()
        
        # Verificar si el evento existe en el gimnasio actual
        if not result or not result.event_id:
            logger.warning(f"Evento no encontrado - event_id: {event_id}, gym_id: {gym_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found in current gym"
            )
        
        # Verificar estado del evento
        if result.event_status != EventStatus.SCHEDULED:
            logger.warning(f"Evento no disponible - status: {result.event_status}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event is not open for registration"
            )
        
        # Verificar si existe perfil de usuario
        if not result.user_id:
            logger.warning(f"Perfil de usuario no encontrado - auth0_id: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User profile not found"
            )
        
        internal_user_id = result.user_id
        
        # 2. Optimización: Verificar participación existente usando índice compuesto
        existing = db.query(EventParticipation).filter(
            EventParticipation.event_id == event_id,
            EventParticipation.member_id == internal_user_id
        ).first()
        
        # 3. Optimización: Procesar casos de participación existente sin transacciones extra
        if existing:
            status_map = {
                EventParticipationStatus.REGISTERED: "already registered",
                EventParticipationStatus.WAITING_LIST: "on waiting list",
                EventParticipationStatus.CANCELLED: "previously cancelled registration"
            }
            
            message = status_map.get(existing.status, "already has a relationship with this event")
            
            # Si está cancelada, podemos reactivarla
            if existing.status == EventParticipationStatus.CANCELLED:
                logger.info(f"Reactivando participación cancelada - id: {existing.id}")
                
                # Determinar nuevo estado según la capacidad
                has_capacity = (result.max_participants == 0 or 
                                result.registered_count < result.max_participants)
                
                new_status = EventParticipationStatus.REGISTERED if has_capacity else EventParticipationStatus.WAITING_LIST
                
                # Actualizar en una transacción eficiente
                existing.status = new_status
                existing.notes = participation_in.notes
                existing.updated_at = datetime.utcnow()
                
                db.add(existing)
                db.commit()
                
                logger.info(f"Participación reactivada con éxito - nuevo estado: {new_status}")
                return existing
            else:
                # Ya está registrado con otro estado
                logger.info(f"Participación ya existe - id: {existing.id}, status: {existing.status}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"You are {message} for this event"
                )
        
        # 4. Optimización: Crear participación directamente sin llamadas adicionales
        
        # Determinar estado inicial según capacidad
        has_capacity = (result.max_participants == 0 or 
                        result.registered_count < result.max_participants)
        
        participation_status = (EventParticipationStatus.REGISTERED 
                               if has_capacity else 
                               EventParticipationStatus.WAITING_LIST)
        
        # Crear participación con transacción eficiente
        now = datetime.utcnow()
        db_participation = EventParticipation(
            event_id=event_id,
            member_id=internal_user_id,
            gym_id=result.gym_id,
            status=participation_status,
            notes=participation_in.notes,
            registered_at=now,
            updated_at=now,
            attended=False
        )
        
        db.add(db_participation)
        db.commit()
        
        # Evitar refresh completo que generaría consultas adicionales
        elapsed_time = time.time() - start_time
        logger.info(f"Inscripción completada exitosamente - tiempo: {elapsed_time:.2f}s, status: {participation_status}")
        
        return db_participation
        
    except HTTPException:
        # Re-lanzar excepciones HTTP para mantener mensajes
        raise
    except Exception as e:
        # Capturar otros errores
        db.rollback()
        error_message = str(e)
        logger.error(f"Error en inscripción: {error_message}", exc_info=True)
        
        if "capacity" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event is at full capacity"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error registering for event: {error_message}"
            )


@router.get("/participation/me", response_model=List[EventParticipationSchema])
async def read_my_participations(
    *,
    db: Session = Depends(get_db),
    status: Optional[EventParticipationStatus] = None,
    current_user: Auth0User = Security(auth.get_user, scopes=["read_own_participations"])
) -> Any:
    """
    Retrieve participations of the authenticated user.
    
    This endpoint allows users to view the events they have registered for,
    optionally filtered by status (registered, cancelled, waiting list).
    
    Permissions:
        - Requires 'read_own_participations' scope (all authenticated users)
        
    Args:
        db: Database session
        status: Optional filter by participation status
        current_user: Authenticated user
        
    Returns:
        List[EventParticipation]: User's event participations
    """
    # Monitoreo de rendimiento
    import time
    import logging
    logger = logging.getLogger("events_api")
    start_time = time.time()
    
    # Get Auth0 user ID
    user_id = current_user.id
    logger.info(f"Consultando participaciones del usuario: {user_id}")
    
    # Convertir auth0_id a user_id interno con consulta optimizada
    from app.models.user import User
    from sqlalchemy.orm import joinedload
    
    # 1. Optimización: Obtener ID interno con consulta eficiente
    internal_user_id = db.query(User.id).filter(User.auth0_id == user_id).scalar()
    
    if not internal_user_id:
        logger.warning(f"Usuario no encontrado: {user_id}")
        return []
    
    # 2. Optimización: Consulta eficiente con eager loading para evitar N+1 queries
    query = db.query(EventParticipation).options(
        joinedload(EventParticipation.event)  # Precarga los datos del evento
    ).filter(
        EventParticipation.member_id == internal_user_id
    )
    
    # Filtrar por estado si es necesario
    if status:
        query = query.filter(EventParticipation.status == status)
    
    # 3. Optimización: Ordenar por fecha de registro para obtener las más recientes primero
    query = query.order_by(EventParticipation.registered_at.desc())
    
    # Ejecutar consulta
    participations = query.all()
    
    elapsed_time = time.time() - start_time
    logger.info(f"Participaciones obtenidas: {len(participations)}, tiempo: {elapsed_time:.2f}s")
    
    return participations


@router.get("/participation/event/{event_id}", response_model=List[EventParticipationSchema])
async def read_event_participations(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    status: Optional[EventParticipationStatus] = None,
    current_user: Auth0User = Security(auth.get_user, scopes=["read_participations"])
) -> Any:
    """
    Retrieve participations for a specific event.
    
    This endpoint allows event creators and administrators to view all
    participants for a specific event, optionally filtered by status.
    Only the event creator or administrators can access this information.
    
    Permissions:
        - Requires 'read_participations' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event
        status: Optional filter by participation status
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        List[EventParticipation]: List of event participations
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    # Monitoreo de rendimiento
    import time
    import logging
    logger = logging.getLogger("events_api")
    start_time = time.time()
    
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    logger.info(f"Consultando participaciones del evento {event_id} por usuario {user_id}")
    
    # Optimización 1: Obtener información del evento y usuario en una sola consulta
    from app.models.user import User
    from sqlalchemy import select, text
    
    # Obtener usuario interno y creador del evento en una consulta
    query = db.query(
        Event.id.label('event_id'),
        Event.gym_id.label('gym_id'),
        Event.creator_id.label('creator_id'),
        User.id.label('user_id')
    ).outerjoin(
        User, User.auth0_id == user_id
    ).filter(
        Event.id == event_id
    )
    
    result = query.first()
    
    if not result or not result.event_id:
        logger.warning(f"Evento no encontrado: {event_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found"
        )
    
    # Verificar permisos de acceso
    internal_user_id = result.user_id
    event_creator_id = result.creator_id
    
    # Verificar si es admin o creador del evento
    if not (is_admin or event_creator_id == internal_user_id):
        logger.warning(f"Permiso denegado - user_id: {internal_user_id}, creator_id: {event_creator_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to view participants for this event"
        )
    
    # Optimización 2: Consulta eficiente con eager loading para evitar N+1 queries
    from sqlalchemy.orm import joinedload
    
    query = db.query(EventParticipation).options(
        joinedload(EventParticipation.member)  # Precarga datos del miembro
    ).filter(
        EventParticipation.event_id == event_id
    )
    
    # Aplicar filtro por estado si es necesario
    if status:
        query = query.filter(EventParticipation.status == status)
    
    # Ordenar por estado y fecha de registro para mejor usabilidad
    # (primero registrados, luego lista de espera, al final cancelados)
    order_case = text("""
        CASE 
            WHEN status = 'REGISTERED' THEN 1
            WHEN status = 'WAITING_LIST' THEN 2
            WHEN status = 'CANCELLED' THEN 3
            ELSE 4
        END
    """)
    
    query = query.order_by(order_case, EventParticipation.registered_at)
    
    # Ejecutar consulta
    participations = query.all()
    
    elapsed_time = time.time() - start_time
    logger.info(f"Participaciones obtenidas: {len(participations)}, tiempo: {elapsed_time:.2f}s")
    
    return participations


@router.delete("/participation/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_participation(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["delete:own_participations"])
) -> None:
    """
    Cancel participation in an event.
    
    This endpoint allows users to cancel their registration for an event.
    Users can only cancel their own participations.
    
    Permissions:
        - Requires 'delete:own_participations' scope (all authenticated users)
        
    Args:
        db: Database session
        event_id: ID of the event to cancel participation for
        current_user: Authenticated user
        
    Raises:
        HTTPException: 404 if participation not found
    """
    # Get Auth0 user ID and log for debugging
    user_id = current_user.id
    
    import logging
    logger = logging.getLogger("events_api")
    logger.info(f"Attempting to cancel participation - auth0_id: {user_id}, event_id: {event_id}")
    
    # Optimización: Buscar el usuario directamente con una sola consulta
    internal_user_id = db.query(User.id).filter(User.auth0_id == user_id).scalar()
    
    if not internal_user_id:
        logger.warning(f"User profile not found for auth0_id: {user_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    logger.info(f"Found internal user ID: {internal_user_id}")
    
    # Optimización: Buscar participación con una consulta directa usando índices
    participation = db.query(EventParticipation).filter(
        EventParticipation.event_id == event_id,
        EventParticipation.member_id == internal_user_id
    ).first()
    
    if not participation:
        logger.warning(f"Participation not found - user_id: {internal_user_id}, event_id: {event_id}")
        
        # Verificar si el evento existe para dar un mensaje más específico
        event_exists = db.query(Event.id).filter(Event.id == event_id).scalar() is not None
        if not event_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Event not found"
            )
        
        # Verificar si hay otras participaciones del usuario para dar información útil
        other_participations = db.query(EventParticipation).filter(
            EventParticipation.member_id == internal_user_id
        ).count()
        
        if other_participations > 0:
            logger.info(f"User has {other_participations} participations but none for event {event_id}")
        
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participation not found - you are not registered for this event"
        )
    
    logger.info(f"Found participation ID: {participation.id}, status: {participation.status}")
    
    # Optimización: Usar directamente el ID de participación para eliminar
    if event_participation_repository.delete_participation(db=db, participation_id=participation.id):
        logger.info(f"Successfully deleted participation ID: {participation.id}")
        return None
    else:
        logger.error(f"Failed to delete participation ID: {participation.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete participation"
        )


@router.put("/participation/{participation_id}", response_model=EventParticipationSchema)
async def update_participation(
    *,
    db: Session = Depends(get_db),
    participation_id: int = Path(..., title="Participation ID"),
    participation_in: EventParticipationUpdate,
    current_user: Auth0User = Security(auth.get_user, scopes=["update:participations"])
) -> Any:
    """
    Update participation status.
    
    This endpoint allows event creators and administrators to update
    the status of a participant, such as marking attendance or changing
    their status. Only the event creator or administrators can perform
    this operation.
    
    Permissions:
        - Requires 'update:participations' scope (trainers and administrators)
        - Also requires event ownership or admin privileges
        
    Args:
        db: Database session
        participation_id: ID of the participation to update
        participation_in: Updated participation data
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        EventParticipation: The updated participation record
        
    Raises:
        HTTPException: 404 if participation not found, 403 if insufficient permissions
    """
    # Get participation
    participation = event_participation_repository.get_participation(
        db=db, participation_id=participation_id
    )
    
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participation not found"
        )
    
    # Get event
    event = event_repository.get_event(db=db, event_id=participation.event_id)
    
    # Verify permissions
    # Get Auth0 user ID
    user_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = "admin:all" in user_permissions or "admin:events" in user_permissions
    
    # Only the event creator or an admin can update participation
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this participation"
        )
    
    # Update participation
    updated = event_participation_repository.update_participation(
        db=db, participation_id=participation_id, participation_in=participation_in
    )
    return updated 