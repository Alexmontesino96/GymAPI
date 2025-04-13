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
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Security, BackgroundTasks
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
    EventParticipationWithEvent
)
from app.models.event import EventStatus, EventParticipationStatus, Event, EventParticipation
from app.models.user import UserRole, User
from app.repositories.event import event_repository, event_participation_repository
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
import logging
import time

logger = logging.getLogger("events_api")

router = APIRouter()

# --- Funciones para tareas en segundo plano --- 
async def create_chat_room_background(db_session_factory, event_id: int, user_id: int, event_title: str):
    """Tarea en segundo plano para crear/obtener sala de chat para un evento."""
    db = None
    try:
        # Crear una nueva sesión de BD para la tarea en segundo plano
        db = db_session_factory()
        from app.services.chat import chat_service
        from app.schemas.chat import ChatRoomCreate
        logger.info(f"[BG Task] Iniciando creación de chat para evento {event_id}")
        
        # Nota: chat_service.create_room ya maneja la obtención si existe
        # No necesitamos pasar ChatRoomCreate, solo los datos relevantes
        chat_service.get_or_create_event_chat(db, event_id, user_id)
        
        logger.info(f"[BG Task] Chat para evento {event_id} creado/obtenido.")
    except Exception as e:
        logger.error(f"[BG Task] Error creando chat para evento {event_id}: {e}", exc_info=True)
        # Considera añadir reintentos o notificaciones si falla aquí
    finally:
        if db: # Asegurarse de cerrar la sesión de la tarea
            db.close()

async def schedule_event_completion_background(event_id: int, end_time: datetime):
    """Tarea en segundo plano para programar la finalización automática de un evento."""
    try:
        from app.core.scheduler import schedule_event_completion
        logger.info(f"[BG Task] Programando finalización para evento {event_id} a las {end_time}")
        schedule_event_completion(event_id, end_time)
        logger.info(f"[BG Task] Finalización para evento {event_id} programada.")
    except Exception as e:
        logger.error(f"[BG Task] Error programando finalización para evento {event_id}: {e}", exc_info=True)
        # Considera añadir reintentos o notificaciones
# --- Fin Funciones Background --- 


# Event Endpoints
@router.post("/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
async def create_event(
    *,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    background_tasks: BackgroundTasks,
    current_gym: Gym = Depends(verify_gym_access),  # Obtener gimnasio actual
    current_user: Auth0User = Security(auth.get_user, scopes=["create:events"])
) -> JSONResponse:
    """
    Create a new event.
    
    This endpoint allows trainers and administrators to create new events
    in the system. The current user is automatically assigned as the creator.
    If the creator is a trainer, they will be automatically registered as participant.
    
    Chat room creation and event completion scheduling are performed in the background.
    
    Permissions:
        - Requires 'create:events' scope (trainers and administrators)
        
    Args:
        db: Database session
        event_in: Event data
        background_tasks: FastAPI BackgroundTasks instance
        current_gym: Current gym context
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        Event: The created event
    """
    start_time = time.time()
    
    # --- Optimización: Buscar usuario interno UNA SOLA VEZ --- 
    auth0_user_id = current_user.id
    internal_user = db.query(User).filter(User.auth0_id == auth0_user_id).first()
    if not internal_user:
         logger.error(f"Perfil de usuario no encontrado para Auth0 ID: {auth0_user_id}")
         raise HTTPException(status_code=404, detail="User profile not found")
    internal_user_id = internal_user.id
    logger.info(f"Usuario interno encontrado: {internal_user_id}")
    # --- Fin Optimización --- 
    
    gym_id = current_gym.id if hasattr(current_gym, 'id') else current_gym
    
    # Crear Evento en BD (Pasar ID interno)
    try:
        event = event_repository.create_event(
            db=db, 
            event_in=event_in, 
            creator_id=internal_user_id,
            gym_id=gym_id
        )
        logger.info(f"Evento {event.id} creado en BD por usuario {internal_user_id}")
    except ValueError as ve:
        logger.error(f"Error al crear evento en repositorio: {ve}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error inesperado al crear evento en BD: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error creating event in database")

    # Lógica de Auto-Registro para Entrenador (usa internal_user_id)
    try:
        # Verificar si el usuario es un entrenador para registrarlo automáticamente
        from app.models.user_gym import UserGym, GymRoleType
        
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == internal_user_id,
            UserGym.gym_id == gym_id
        ).first()
            
        is_trainer = user_gym and user_gym.role == GymRoleType.TRAINER
            
        # Si es entrenador, registrarlo automáticamente como participante
        if is_trainer:
            logger.info(f"Intentando auto-registrar al entrenador {internal_user_id} para evento {event.id}")
            participation_in = EventParticipationCreate(event_id=event.id)
            try:
                # Usar el repositorio para crear la participación
                participation = event_participation_repository.create_participation(
                    db=db, 
                    participation_in=participation_in, 
                    member_id=internal_user_id
                )
                if participation:
                    logger.info(f"Entrenador {internal_user_id} registrado automáticamente (participación ID: {participation.id})")
                else:
                    # Esto no debería ocurrir si la creación del evento fue exitosa
                    logger.warning(f"Auto-registro del entrenador {internal_user_id} devolvió None para evento {event.id}")
            except Exception as part_exc:
                # Capturar errores específicos de la creación de participación
                logger.error(f"Error en auto-registro de entrenador {internal_user_id} para evento {event.id}: {part_exc}", exc_info=True)
                # No relanzamos la excepción para no fallar la creación del evento

    except Exception as e:
        # Si falla la consulta del rol, solo loggeamos el error sin interrumpir
        logger.error(f"Error verificando rol de entrenador para auto-registro (evento {event.id}): {e}", exc_info=True)
    
    # --- Desacoplar operaciones lentas --- 
    # Encolar creación de chat en segundo plano
    # Necesitamos pasar una forma de obtener una sesión de BD a la tarea
    from app.db.session import SessionLocal
    background_tasks.add_task(
        create_chat_room_background, SessionLocal, event.id, internal_user_id, event.title
    )
    logger.info(f"Tarea de creación de chat para evento {event.id} encolada.")

    # Encolar programación de finalización en segundo plano
    background_tasks.add_task(
        schedule_event_completion_background, event.id, event.end_time
    )
    logger.info(f"Tarea de programación de finalización para evento {event.id} encolada.")
    # --- Fin Desacoplamiento --- 
    
    # Calcular tiempo y añadir encabezado antes de retornar
    process_time = (time.time() - start_time) * 1000 # en ms
    headers = {"X-Process-Time-ms": f"{process_time:.2f}"} 
    logger.info(f"Endpoint create_event completado en {process_time:.2f} ms para evento {event.id}")
    
    # Retorna la respuesta INMEDIATAMENTE con encabezado de tiempo
    # Usar jsonable_encoder para convertir datetime a string antes de JSONResponse
    event_schema = EventSchema.from_orm(event)
    json_compatible_content = jsonable_encoder(event_schema)
    return JSONResponse(content=json_compatible_content, headers=headers)


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
        - Requires 'read:events' scope (all authenticated users)
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
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
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
        current_gym: The current gym (tenant) context
        current_user: Authenticated user
        
    Returns:
        List[Event]: List of events created by the user
    """
    # Get Auth0 user ID
    user_id = current_user.id
    events = event_repository.get_events_by_creator(
        db=db, creator_id=user_id, skip=skip, limit=limit,
        gym_id=current_gym.id  # Filtrar por gimnasio actual
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
        - Requires 'read:events' scope (all authenticated users)
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
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:events"])
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
        current_gym: The current gym (tenant) context
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
    
    # Verificar que el evento pertenezca al gimnasio actual primero
    event_gym_id = db.query(Event.gym_id).filter(Event.id == event_id).scalar()
    if not event_gym_id or event_gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found in current gym"
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
            
        # Si se actualizó la hora de finalización, registramos que se completará automáticamente
        if 'end_time' in update_data and updated_event.status == EventStatus.SCHEDULED:
            try:
                # Programar o reprogramar la tarea
                from app.core.scheduler import schedule_event_completion
                schedule_event_completion(event_id, updated_event.end_time)
                
                import logging
                logger = logging.getLogger("events_api")
                logger.info(f"Evento {updated_event.id} actualizado y reprogramado para completarse automáticamente a las {updated_event.end_time}")
            except Exception as e:
                # Si falla la programación, solo loggeamos el error sin interrumpir
                import logging
                logger = logging.getLogger("events_api")
                logger.error(f"Error al reprogramar la finalización automática del evento {updated_event.id}: {e}")
            
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
    
    # Si se actualizó la hora de finalización, registramos que se completará automáticamente
    if 'end_time' in update_data and updated_event.status == EventStatus.SCHEDULED:
        try:
            # Programar o reprogramar la tarea
            from app.core.scheduler import schedule_event_completion
            schedule_event_completion(event_id, updated_event.end_time)
            
            import logging
            logger = logging.getLogger("events_api")
            logger.info(f"Evento {updated_event.id} actualizado y reprogramado para completarse automáticamente a las {updated_event.end_time}")
        except Exception as e:
            # Si falla la programación, solo loggeamos el error sin interrumpir
            import logging
            logger = logging.getLogger("events_api")
            logger.error(f"Error al reprogramar la finalización automática del evento {updated_event.id}: {e}")
    
    return updated_event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
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
        current_gym: The current gym (tenant) context
        current_user: Authenticated user with appropriate permissions
        
    Raises:
        HTTPException: 404 if event not found, 403 if insufficient permissions
    """
    # Verificar primero que el evento pertenezca al gimnasio actual
    event = db.query(Event).filter(
        Event.id == event_id,
        Event.gym_id == current_gym.id
    ).first()
    
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found in current gym"
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
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
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
        current_gym: The current gym (tenant) context
        current_user: Authenticated administrator
        
    Raises:
        HTTPException: 404 if event not found, 500 for other errors
    """
    # Verificar primero que el evento pertenezca al gimnasio actual
    event_exists = db.query(Event.id).filter(
        Event.id == event_id,
        Event.gym_id == current_gym.id
    ).scalar() is not None
    
    if not event_exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found in current gym"
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
    participation_in: EventParticipationCreate = Body(...),
    current_gym: Gym = Depends(verify_gym_access),  # Verifica y obtiene el gimnasio actual
    current_user: Auth0User = Security(auth.get_user, scopes=["create:participations"])
) -> EventParticipationSchema:
    """
    Registra al usuario autenticado para un evento específico.

    Este endpoint permite a los miembros (usuarios autenticados) inscribirse en 
    eventos disponibles en su gimnasio actual. Realiza varias comprobaciones:
    
    1.  **Existencia y Gimnasio**: Verifica que el evento existe y pertenece al gimnasio 
        actual del usuario.
    2.  **Estado del Evento**: Confirma que el evento esté programado (`SCHEDULED`) y abierto 
        para inscripciones.
    3.  **Perfil de Usuario**: Asegura que el usuario autenticado tenga un perfil 
        en la base de datos local.
    4.  **Participación Previa**: Comprueba si el usuario ya está registrado, en 
        lista de espera o si había cancelado previamente.
    5.  **Capacidad**: Evalúa si hay plazas disponibles o si el usuario debe ser 
        añadido a la lista de espera.
    
    Si la inscripción es exitosa (o si se reactiva una inscripción cancelada), 
    se crea o actualiza el registro de participación.
    
    **Permisos Necesarios:**
    -   Requiere el scope `create:participations` (otorgado a todos los usuarios autenticados).
    
    **Parámetros:**
    -   `db` (Inyección de dependencia): Sesión de la base de datos SQLAlchemy.
    -   `participation_in` (Cuerpo de la solicitud): Objeto `EventParticipationCreate` 
        que debe contener:
        -   `event_id` (int, **Requerido**): ID del evento al que se desea inscribir.
        *(Nota: El campo `notes` ya no se utiliza. Los campos `status` y `attended` del modelo base 
        son ignorados en la creación y gestionados por el servidor)*.
    -   `current_gym` (Inyección de dependencia): Objeto `Gym` que representa el 
        gimnasio actual del usuario (determinado a partir de la solicitud).
    -   `current_user` (Inyección de dependencia): Objeto `Auth0User` que representa 
        al usuario autenticado (obtenido a partir del token JWT).
        
    **Retorna:**
    -   `EventParticipationSchema`: Un objeto que representa el registro de participación 
        creado o actualizado, incluyendo su estado (`REGISTERED` o `WAITING_LIST`).
        
    **Posibles Errores (Excepciones HTTP):**
    -   `404 Not Found`: Si el evento no se encuentra en el gimnasio actual o si el 
        perfil del usuario no existe.
    -   `400 Bad Request`: Si el evento no está abierto para inscripciones (`SCHEDULED`) 
        o si el usuario ya tiene cualquier tipo de registro previo para este evento 
        (sea `REGISTERED`, `WAITING_LIST` o `CANCELLED`).
    -   `500 Internal Server Error`: Si ocurre un error inesperado durante el 
        proceso de inscripción.
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
        
        # 2. Verificar si ya existe una participación para este usuario y evento
        existing_participation = db.query(EventParticipation).filter(
            EventParticipation.event_id == event_id,
            EventParticipation.member_id == internal_user_id
        ).first()
        
        # Si ya existe una participación (independientemente del estado),
        # informar al usuario y no permitir registrarse de nuevo.
        if existing_participation:
            status_message = existing_participation.status.value.lower().replace('_', ' ')
            logger.info(f"Participación ya existe - id: {existing_participation.id}, status: {existing_participation.status.value}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You already have a registration for this event with status '{status_message}'. Cancel it first if you want to try registering again."
            )
        
        # 3. Si no existe participación, determinar estado inicial según capacidad
        has_capacity = (result.max_participants == 0 or 
                        result.registered_count < result.max_participants)
        
        new_participation_status = EventParticipationStatus.REGISTERED if has_capacity else EventParticipationStatus.WAITING_LIST
        
        # 4. Crear nueva participación
        now = datetime.utcnow()
        db_participation = EventParticipation(
            event_id=event_id,
            member_id=internal_user_id,
            gym_id=result.gym_id,
            status=new_participation_status,
            registered_at=now,
            updated_at=now,
            attended=False
        )
        
        db.add(db_participation)
        db.commit()
        
        elapsed_time = time.time() - start_time
        logger.info(f"Inscripción completada exitosamente - tiempo: {elapsed_time:.2f}s, status: {new_participation_status.value}")
        
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


@router.get("/participation/me", response_model=List[EventParticipationWithEvent])
async def read_my_participations(
    *,
    db: Session = Depends(get_db),
    participation_status: Optional[EventParticipationStatus] = None,
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
    current_user: Auth0User = Security(auth.get_user, scopes=["read:own_participations"])
) -> List[EventParticipationWithEvent]:
    """
    Retrieve participations of the authenticated user, including event details.
    
    This endpoint allows users to view the events they have registered for,
    optionally filtered by status (registered, cancelled, waiting list).
    Each participation record now includes the full details of the associated event.
    
    Permissions:
        - Requires 'read_own_participations' scope (all authenticated users)
        
    Args:
        db: Database session
        participation_status: Optional filter by participation status
        current_gym: The current gym (tenant) context
        current_user: Authenticated user
        
    Returns:
        List[EventParticipationWithEvent]: User's event participations, each including 
                                         the full details of the related event.
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
        EventParticipation.member_id == internal_user_id,
        EventParticipation.gym_id == current_gym.id  # Filtrar por gimnasio actual
    )
    
    # Filtrar por estado si es necesario
    if participation_status:
        query = query.filter(EventParticipation.status == participation_status)
    
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
    participation_status: Optional[EventParticipationStatus] = None,
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
    current_user: Auth0User = Security(auth.get_user, scopes=["read:participations"])
) -> Any:
    """
    Retrieve participations for a specific event.
    
    This endpoint allows event creators and administrators to view all
    participants for a specific event, optionally filtered by status.
    Only the event creator or administrators can access this information.
    
    Permissions:
        - Requires 'read:participations' scope (trainers and administrators)
        - Also requires ownership of the event or admin privileges
        
    Args:
        db: Database session
        event_id: ID of the event
        participation_status: Optional filter by participation status
        current_gym: The current gym (tenant) context
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
        Event.id == event_id,
        Event.gym_id == current_gym.id  # Verificar pertenencia al gimnasio actual
    )
    
    result = query.first()
    
    if not result or not result.event_id:
        logger.warning(f"Evento no encontrado: {event_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found in current gym"
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
        EventParticipation.event_id == event_id,
        EventParticipation.gym_id == current_gym.id  # Filtrar por gimnasio actual
    )
    
    # Aplicar filtro por estado si es necesario
    if participation_status:
        query = query.filter(EventParticipation.status == participation_status)
    
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
    current_gym: Gym = Depends(verify_gym_access),  # Añadir verificación de gimnasio
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
        current_gym: The current gym (tenant) context
        current_user: Authenticated user
        
    Raises:
        HTTPException: 404 if participation not found
    """
    # Get Auth0 user ID and log for debugging
    user_id = current_user.id
    
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
    
    # Verificar primero que el evento pertenezca al gimnasio actual
    event_in_gym = db.query(Event.id).filter(
        Event.id == event_id,
        Event.gym_id == current_gym.id
    ).scalar() is not None
    
    if not event_in_gym:
        logger.warning(f"Event not found in current gym - event_id: {event_id}, gym_id: {current_gym.id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found in current gym"
        )
    
    # Optimización: Buscar participación con una consulta directa usando índices
    participation = db.query(EventParticipation).filter(
        EventParticipation.event_id == event_id,
        EventParticipation.member_id == internal_user_id,
        EventParticipation.gym_id == current_gym.id  # Filtrar por gimnasio actual
    ).first()
    
    if not participation:
        logger.warning(f"Participation not found - user_id: {internal_user_id}, event_id: {event_id}")
        
        # Verificar si hay otras participaciones del usuario para dar información útil
        other_participations = db.query(EventParticipation).filter(
            EventParticipation.member_id == internal_user_id,
            EventParticipation.gym_id == current_gym.id
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


@router.put("/participation/event/{event_id}/user/{user_id}", response_model=EventParticipationSchema)
async def update_attendance(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    user_id: int = Path(..., title="Internal User ID of the participant"),
    attendance_data: EventParticipationUpdate = Body(...), # Renombrado para claridad
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["update:participations"])
) -> EventParticipationSchema:
    """
    Update a specific user's attendance for a specific event.

    This endpoint allows event creators and administrators to mark whether a specific 
    participant (identified by their internal user ID) attended a specific event 
    (identified by its ID). Only the event creator or administrators can perform this operation.
    
    Permissions:
        - Requires 'update:participations' scope (trainers and administrators)
        - Also requires event ownership or admin privileges
        
    Args:
        db: Database session
        event_id (Path): ID of the event.
        user_id (Path): Internal ID of the participant whose attendance is being updated.
        attendance_data (Body): Object containing the `attended` status (boolean).
        current_gym: The current gym (tenant) context
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        EventParticipationSchema: The updated participation record.
        
    Raises:
        HTTPException: 404 if participation, event, or user not found in current gym, 
                       403 if insufficient permissions.
    """
    # Buscar la participación específica usando event_id y user_id
    participation = event_participation_repository.get_participation_by_member_and_event(
        db=db, member_id=user_id, event_id=event_id
    )
    
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Participation record not found for user {user_id} in event {event_id}"
        )
        
    # Verificar que la participación pertenezca al gimnasio actual
    if participation.gym_id != current_gym.id:
         raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, # O 403? 404 parece más adecuado si no debería verlo
            detail="Participation record not found in current gym"
        )

    # Obtener evento para verificar creador (si no es admin)
    event = db.query(Event).filter(
        Event.id == event_id, 
        Event.gym_id == current_gym.id # Doble check por si acaso
    ).first()
    if not event: # Esto no debería ocurrir si la participación existe, pero por seguridad
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated event not found in current gym"
        )
    
    # Verify permissions
    requesting_user_auth0_id = current_user.id
    user_permissions = getattr(current_user, "permissions", []) or []
    is_admin = any(p in user_permissions for p in ["admin:all", "admin:events"])
    
    # Obtener el ID interno del usuario que hace la solicitud para comparar con el creador
    requesting_internal_user_id = db.query(User.id).filter(User.auth0_id == requesting_user_auth0_id).scalar()
    
    # Only the event creator or an admin can update participation
    if not (is_admin or event.creator_id == requesting_internal_user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have permission to update this participation"
        )
    
    # Actualizar participación usando el repositorio
    # Pasamos el objeto de participación existente para que el repo no tenga que buscarlo de nuevo
    updated = event_participation_repository.update_participation(
        db=db, 
        db_obj=participation, # Pasar el objeto encontrado 
        participation_in=attendance_data # attendance_data solo tiene 'attended'
    )
    
    if not updated: # Si la actualización fallase por alguna razón en el repo
         raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update participation record"
        )
        
    return updated 