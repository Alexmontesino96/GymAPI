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
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Security, BackgroundTasks, Request
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.db.session import get_db
from app.db.redis_client import get_redis_client
from app.core.auth0_fastapi import get_current_user, get_current_user_with_permissions, Auth0User, auth
from app.core.tenant import verify_gym_access, get_current_gym, GymSchema
from app.core.tenant_cache import verify_gym_access_cached
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
from app.services.event import event_service
from app.services.chat import chat_service
from app.core.config import get_settings
from app.services import sqs_service, queue_service

logger = logging.getLogger("events_api")

router = APIRouter()

# Constante para el tipo de acción SQS
CREATE_EVENT_CHAT = "create_event_chat"

# Event Endpoints
@router.post("/", response_model=EventSchema, status_code=status.HTTP_201_CREATED)
async def create_event(
    *,
    request: Request,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    background_tasks: BackgroundTasks,
    current_gym: GymSchema = Depends(verify_gym_access_cached),
    redis_client: Redis = Depends(get_redis_client),
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:events"])
) -> JSONResponse:
    """
    Create a new event.
    
    This endpoint allows trainers and administrators to create new events
    in the system. The current user is automatically assigned as the creator.
    If the creator is a trainer, they will be automatically registered as participant.
    
    Chat room creation and event completion scheduling are performed through
    messaging queues for asynchronous processing by worker services.
    
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
    
    # Obtener el usuario actual desde la request para evitar duplicación
    current_user = request.state.current_user
    
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
    # Enviar un único mensaje a SQS para procesar el evento (crear chat y programar finalización)
    try:
        # Usar el servicio de colas para publicar el mensaje unificado
        process_response = queue_service.publish_event_processing(
            event_id=event.id,
            creator_id=internal_user_id,
            gym_id=gym_id,
            event_title=event.title,
            end_time=event.end_time,
            first_message_chat=event_in.first_message_chat if hasattr(event_in, 'first_message_chat') else None
        )
        
        # Verificar si hubo error en la respuesta
        if "error" in process_response:
            logger.error(f"Error al solicitar procesamiento del evento: {process_response['error']}")
        else:
            logger.info(f"Solicitud de procesamiento para evento {event.id} enviada correctamente")
            
    except Exception as e:
        logger.error(f"Excepción al solicitar procesamiento del evento: {str(e)}", exc_info=True)
        # No fallar la creación del evento si el envío del mensaje falla
    # --- Fin Desacoplamiento ---
    
    # Calcular tiempo y añadir encabezado antes de retornar
    process_time = (time.time() - start_time) * 1000 # en ms
    headers = {"X-Process-Time-ms": f"{process_time:.2f}"} 
    logger.info(f"Endpoint create_event completado en {process_time:.2f} ms para evento {event.id}")
    
    # Retorna la respuesta INMEDIATAMENTE con encabezado de tiempo
    # Usar jsonable_encoder para convertir datetime a string antes de JSONResponse
    event_schema = EventSchema.from_orm(event)
    
    # Asegurar que created_at y updated_at tienen valores para serialización
    if event_schema.created_at is None:
        event_schema.created_at = datetime.now(timezone.utc)
    if event_schema.updated_at is None:
        event_schema.updated_at = datetime.now(timezone.utc)
        
    json_compatible_content = jsonable_encoder(event_schema)
    return JSONResponse(content=json_compatible_content, headers=headers)


@router.get("/", response_model=List[EventWithParticipantCount])
async def read_events(
    *,
    request: Request,
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
    current_gym: GymSchema = Depends(verify_gym_access_cached),
    redis_client: Redis = Depends(get_redis_client),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:events"])
) -> Any:
    """
    Obtener lista de eventos con filtros opcionales.
    
    Este endpoint permite a los usuarios obtener eventos con diferentes criterios
    de filtrado: estado, rango de fechas, búsqueda por título o ubicación, etc.
    Los resultados son paginados y ordenados cronológicamente.
    
    Permissions:
        - Requires 'read:events' scope (all authenticated users)
    """
    start_time = time.time()
    
    # Usar el servicio de eventos con caché
    try:
        # Llamar al método con soporte para caché
        events = await event_service.get_events_cached(
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
            gym_id=current_gym.id if current_gym else None,
            redis_client=redis_client
        )
        
        process_time = (time.time() - start_time) * 1000
        logger.info(f"Endpoint read_events completado en {process_time:.2f}ms")
        return events
        
    except Exception as e:
        logger.error(f"Error obteniendo eventos: {e}", exc_info=True)
        # Fallback a la implementación original en caso de error
        events_with_counts = event_repository.get_events_with_counts(
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
            gym_id=current_gym.id if current_gym else None
        )
        process_time = (time.time() - start_time) * 1000
        logger.warning(f"Endpoint read_events completado con fallback en {process_time:.2f}ms")
        return events_with_counts


@router.get("/me", response_model=List[EventSchema])
async def read_my_events(
    *,
    request: Request,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_gym: GymSchema = Depends(verify_gym_access_cached),
    redis_client: Redis = Depends(get_redis_client),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:events"])
) -> Any:
    """
    Obtener eventos creados por el usuario actual.
    
    Este endpoint devuelve todos los eventos que el usuario ha creado,
    filtrados por el gimnasio actual si se especifica.
    
    Permissions:
        - Requires 'read:own_events' scope (all authenticated users)
    """
    start_time = time.time()
    # Obtener el usuario actual desde la request para evitar duplicación
    current_user = request.state.current_user
    auth0_id = current_user.id
    
    try:
        # Buscar el usuario en la BD por auth0_id
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user:
            # Si no hay usuario, devolvemos lista vacía
            logger.warning(f"Usuario con Auth0 ID {auth0_id} no encontrado para read_my_events")
            return []
        
        # Obtener eventos usando caché
        events = await event_service.get_events_by_creator_cached(
            db=db,
            creator_id=user.id,  # Usar ID interno
            skip=skip,
            limit=limit,
            gym_id=current_gym.id if current_gym else None,
            redis_client=redis_client
        )
        
        process_time = (time.time() - start_time) * 1000
        logger.info(f"Endpoint read_my_events completado en {process_time:.2f}ms")
        
        return events
    
    except Exception as e:
        logger.error(f"Error obteniendo eventos del usuario {auth0_id}: {e}", exc_info=True)
        
        # Fallback a la implementación original en caso de error
        user = db.query(User).filter(User.auth0_id == auth0_id).first()
        if not user:
            return []
            
        events = event_repository.get_events_by_creator(
            db=db,
            creator_id=user.id,
            skip=skip,
            limit=limit,
            gym_id=current_gym.id if current_gym else None
        )
        
        process_time = (time.time() - start_time) * 1000
        logger.warning(f"Endpoint read_my_events completado con fallback en {process_time:.2f}ms")
        
        return events


@router.get("/{event_id}", response_model=EventDetail)
async def read_event(
    *,
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento a obtener", ge=1),
    current_gym: GymSchema = Depends(verify_gym_access_cached),
    redis_client: Redis = Depends(get_redis_client),
    current_user: Auth0User = Security(auth.get_user, scopes=["read:events"])
) -> Any:
    """
    Obtener detalles de un evento específico.
    
    Este endpoint permite a los usuarios obtener información detallada sobre un evento,
    incluyendo sus participantes, creador, y otros atributos relevantes.
    
    Permissions:
        - Requires 'read_events' scope (all authenticated users)
    """
    start_time = time.time()
    
    try:
        # Obtener evento usando caché
        event_detail = await event_service.get_event_cached(db, event_id, redis_client)
        
        if not event_detail:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        
        # Verificar que el evento pertenece al gimnasio actual
        if event_detail.gym_id != current_gym.id:
            raise HTTPException(
                status_code=403, 
                detail="El evento no pertenece al gimnasio actual"
            )
        
        process_time = (time.time() - start_time) * 1000
        logger.info(f"Endpoint read_event completado en {process_time:.2f}ms")
        
        return event_detail
    
    except HTTPException:
        # Re-lanzar excepciones HTTP
        raise
    except Exception as e:
        logger.error(f"Error obteniendo evento {event_id}: {e}", exc_info=True)
        
        # Fallback a la implementación original en caso de error
        event = event_repository.get_event(db, event_id=event_id)
        if not event:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        
        # Verificar que el evento pertenece al gimnasio actual
        if event.gym_id != current_gym.id:
            raise HTTPException(
                status_code=403, 
                detail="El evento no pertenece al gimnasio actual"
            )
        
        # Contar participantes
        participants_count = len(event.participants) if event.participants else 0
        
        # Convertir a esquema EventDetail
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
        
        process_time = (time.time() - start_time) * 1000
        logger.warning(f"Endpoint read_event completado con fallback en {process_time:.2f}ms")
        
        return event_detail


@router.put("/{event_id}", response_model=EventSchema)
async def update_event(
    *,
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    event_in: EventUpdate,
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
    current_user: Auth0User = Security(auth.get_user, scopes=["admin:events"])
) -> Any:
    """
    Update an existing event.
    
    This endpoint allows the event creator or administrators to update
    event details such as title, description, time, location, capacity,
    and status. Only the creator of the event or administrators can perform
    this operation.
    
    If the end_time is updated, a message is sent to the queue service to
    reschedule the event completion.
    
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
            
        # Si se actualizó la hora de finalización, enviar mensaje para procesar el evento
        if 'end_time' in update_data and updated_event.status == EventStatus.SCHEDULED:
            try:
                # Usar el servicio de colas para crear el chat del evento
                process_response = queue_service.publish_event_processing(
                    event_id=event_id,
                    creator_id=user_id,
                    gym_id=current_gym.id,
                    event_title=updated_event.title,
                    end_time=updated_event.end_time,
                    first_message_chat=event_in.first_message_chat if hasattr(event_in, 'first_message_chat') else None
                )
                
                # Verificar si hubo error en la respuesta
                if not process_response.get("success", False):
                    logger.error(f"Error al solicitar creación de chat: {process_response.get('error')}")
                else:
                    # Registro para creación de chat
                    if "chat_creation" in process_response and process_response["chat_creation"].get("success"):
                        logger.info(f"Solicitud de creación de chat para evento {event_id} enviada correctamente")
                    
                    logger.info(f"Solicitud de procesamiento para evento {event_id} enviada correctamente")
                    
            except Exception as e:
                logger.error(f"Excepción al solicitar procesamiento del evento: {str(e)}", exc_info=True)
                # No fallar la actualización del evento si el envío del mensaje falla
            
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
    
    # Si se actualizó la hora de finalización, enviar mensaje para procesar el evento
    if 'end_time' in update_data and updated_event.status == EventStatus.SCHEDULED:
        try:
            # Usar el servicio de colas para crear el chat del evento
            process_response = queue_service.publish_event_processing(
                event_id=event_id,
                creator_id=creator_id,
                gym_id=current_gym.id,
                event_title=updated_event.title,
                end_time=updated_event.end_time,
                first_message_chat=event_in.first_message_chat if hasattr(event_in, 'first_message_chat') else None
            )
            
            # Verificar si hubo error en la respuesta
            if not process_response.get("success", False):
                logger.error(f"Error al solicitar creación de chat: {process_response.get('error')}")
            else:
                # Registro para creación de chat
                if "chat_creation" in process_response and process_response["chat_creation"].get("success"):
                    logger.info(f"Solicitud de creación de chat para evento {event_id} enviada correctamente")
                
                logger.info(f"Solicitud de procesamiento para evento {event_id} enviada correctamente")
                
        except Exception as e:
            logger.error(f"Excepción al solicitar procesamiento del evento: {str(e)}", exc_info=True)
            # No fallar la actualización del evento si el envío del mensaje falla
    
    return updated_event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    *,
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
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
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
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
    request: Request,
    db: Session = Depends(get_db),
    participation_in: EventParticipationCreate = Body(...),
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
    current_user: Auth0User = Security(auth.get_user, scopes=["create:participations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> EventParticipationSchema:
    """
    Registrar el usuario actual como participante de un evento.
    
    Este endpoint permite a los usuarios registrarse para participar en un evento.
    Si el evento está lleno, el usuario puede ser puesto en lista de espera.
    
    Permissions:
        - Requires 'create:participations' scope (all authenticated users)
    """
    start_time = time.time()
    auth0_id = current_user.id
    
    # Verificar que el usuario existe en la BD
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado. Por favor complete su perfil primero."
        )
    
    # Verificar que el evento existe
    event = event_repository.get_event(db, event_id=participation_in.event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Evento no encontrado"
        )

    # <<< Añadir comprobación de estado >>>
    if event.status == EventStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes registrarte para un evento que ya ha finalizado."
        )
    
    # Verificar que el evento pertenece al gimnasio actual
    if event.gym_id != current_gym.id:
        raise HTTPException(
            status_code=403,
            detail="El evento no pertenece al gimnasio actual"
        )
    
    # Verificar si el usuario ya está registrado
    existing = event_participation_repository.get_participation_by_member_and_event(
        db, member_id=user.id, event_id=participation_in.event_id
    )
    if existing:
        if existing.status == EventParticipationStatus.REGISTERED:
            raise HTTPException(
                status_code=400,
                detail="Ya estás registrado para este evento"
            )
        elif existing.status == EventParticipationStatus.CANCELLED:
            # Si el usuario canceló previamente, reactivar la participación
            # Verificar capacidad de nuevo
            registered_count = db.query(EventParticipation).filter(
                EventParticipation.event_id == event.id,
                EventParticipation.status == EventParticipationStatus.REGISTERED
            ).count()

            if event.max_participants == 0 or registered_count < event.max_participants:
                existing.status = EventParticipationStatus.REGISTERED
            else:
                existing.status = EventParticipationStatus.WAITING_LIST
            
            existing.updated_at = datetime.now(timezone.utc)
            db.add(existing)
            db.commit()
            db.refresh(existing)
            participation = existing # Asignar el objeto actualizado a participation
        else:
            # Por ejemplo, si está en WAITING_LIST, no debería poder registrarse de nuevo por esta vía
            raise HTTPException(
                status_code=400,
                detail=f"No puedes registrarte de nuevo con estado actual: {existing.status}"
            )
    else:
        # Crear nueva participación
        # La lógica para determinar REGISTERED o WAITING_LIST ya está en el repositorio
        participation = event_participation_repository.create_participation(
            db, participation_in=participation_in, member_id=user.id
        )
    
    if not participation:
        raise HTTPException(
            status_code=400,
            detail="Error al registrarse para el evento"
        )
    
    # Invalidar cachés relacionadas
    if redis_client:
        try:
            await event_service.invalidate_event_caches(
                redis_client=redis_client,
                event_id=participation_in.event_id
            )
            logger.info(f"Cachés del evento {participation_in.event_id} invalidadas después del registro")
        except Exception as e:
            logger.error(f"Error invalidando cachés: {e}", exc_info=True)
    
    process_time = (time.time() - start_time) * 1000
    logger.info(f"Registro para evento completado en {process_time:.2f}ms")
    
    return participation


@router.get("/participation/me", response_model=List[EventParticipationWithEvent])
async def read_my_participations(
    *,
    request: Request,
    db: Session = Depends(get_db),
    participation_status: Optional[EventParticipationStatus] = None,
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
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
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    participation_status: Optional[EventParticipationStatus] = None,
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
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
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_gym: GymSchema = Depends(verify_gym_access),  # Usar GymSchema
    current_user: Auth0User = Security(auth.get_user, scopes=["delete:own_participations"]),
    redis_client: Redis = Depends(get_redis_client)
) -> None:
    """
    Cancelar la participación del usuario actual en un evento.
    
    Este endpoint permite a los usuarios cancelar su inscripción a un evento.
    Si hay una lista de espera, el primer usuario en la lista será promovido automáticamente.
    
    Permissions:
        - Requires 'delete:own_participations' scope (all authenticated users)
    """
    start_time = time.time()
    auth0_id = current_user.id
    
    # Verificar que el usuario existe en la BD
    user = db.query(User).filter(User.auth0_id == auth0_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail="Usuario no encontrado"
        )
    
    # Verificar que el evento existe
    event = event_repository.get_event(db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=404,
            detail="Evento no encontrado"
        )

    # <<< Añadir comprobación de estado >>>
    if event.status == EventStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes cancelar la participación en un evento que ya ha finalizado."
        )
    
    # Verificar que el evento pertenece al gimnasio actual
    if event.gym_id != current_gym.id:
        raise HTTPException(
            status_code=403,
            detail="El evento no pertenece al gimnasio actual"
        )
    
    # Cancelar participación
    result = event_participation_repository.cancel_participation(
        db, member_id=user.id, event_id=event_id
    )
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail="No se encontró participación para este evento"
        )
    
    # Invalidar cachés relacionadas
    if redis_client:
        try:
            await event_service.invalidate_event_caches(
                redis_client=redis_client,
                event_id=event_id
            )
            logger.info(f"Cachés del evento {event_id} invalidadas después de cancelar participación")
        except Exception as e:
            logger.error(f"Error invalidando cachés: {e}", exc_info=True)
    
    process_time = (time.time() - start_time) * 1000
    logger.info(f"Cancelación de participación completada en {process_time:.2f}ms")
    return None


@router.put("/participation/event/{event_id}/user/{user_id}", response_model=EventParticipationSchema)
async def update_attendance(
    *,
    request: Request,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    user_id: int = Path(..., title="Internal User ID of the participant"),
    attendance_data: EventParticipationUpdate = Body(...),
    current_gym: GymSchema = Depends(verify_gym_access),
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