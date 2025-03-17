from typing import List, Optional, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path, status, Security
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, get_current_user_with_permissions, Auth0User
from app.schemas.event import (
    Event, 
    EventCreate, 
    EventUpdate, 
    EventDetail,
    EventParticipation, 
    EventParticipationCreate, 
    EventParticipationUpdate,
    EventWithParticipantCount,
    EventsSearchParams
)
from app.models.event import EventStatus, EventParticipationStatus
from app.models.user import UserRole
from app.repositories.event import event_repository, event_participation_repository


router = APIRouter()


# Endpoints para Eventos
@router.post("/", response_model=Event, status_code=status.HTTP_201_CREATED)
async def create_event(
    *,
    db: Session = Depends(get_db),
    event_in: EventCreate,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Crear un nuevo evento.
    Sólo entrenadores o administradores pueden crear eventos.
    """
    # Verificar que current_user.permissions existe antes de verificar permisos
    user_permissions = getattr(current_user, "permissions", []) or []
    
    # Verificar permisos para crear eventos (aceptar tanto singular como plural)
    has_permission = any(perm in user_permissions for perm in ["create:events", "create:event", "admin:all"])
    
    if not has_permission:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para crear eventos"
        )
    
    # Obtener el ID del usuario en la base de datos
    # Modificación: Usar el ID completo de Auth0 en lugar de intentar extraer un número
    user_id = current_user.id
    
    # Crear el evento
    event = event_repository.create_event(db=db, event_in=event_in, creator_id=user_id)
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
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Obtener lista de eventos con filtros opcionales.
    """
    events = event_repository.get_events(
        db=db,
        skip=skip,
        limit=limit,
        status=status,
        start_date=start_date,
        end_date=end_date,
        title_contains=title_contains,
        location_contains=location_contains,
        created_by=created_by,
        only_available=only_available
    )
    
    # Añadir conteo de participantes a cada evento
    result = []
    for event in events:
        # Contar participantes registrados
        participants_count = len([
            p for p in event.participants 
            if p.status == EventParticipationStatus.REGISTERED
        ])
        
        # Crear objeto con conteo
        event_dict = Event.from_orm(event).dict()
        event_dict["participants_count"] = participants_count
        result.append(EventWithParticipantCount(**event_dict))
        
    return result


@router.get("/me", response_model=List[Event])
async def read_my_events(
    *,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Obtener eventos creados por el usuario autenticado.
    """
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    events = event_repository.get_events_by_creator(
        db=db, creator_id=user_id, skip=skip, limit=limit
    )
    return events


@router.get("/{event_id}", response_model=EventDetail)
async def read_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento"),
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Obtener detalles de un evento por ID.
    """
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )
    
    # Verificar que current_user.permissions existe antes de verificar permisos
    user_permissions = getattr(current_user, "permissions", []) or []
    
    # Verificar si el usuario tiene permisos para ver los participantes
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    is_admin = "admin:all" in user_permissions
    is_creator = event.creator_id == user_id
    
    # Crear objeto detallado
    event_dict = Event.from_orm(event).dict()
    
    # Incluir participantes solo si es admin o creador
    if is_admin or is_creator:
        event_dict["participants"] = [
            EventParticipation.from_orm(p) for p in event.participants
        ]
    else:
        # Para usuarios normales, solo incluir conteo
        event_dict["participants"] = []
        event_dict["participants_count"] = len([
            p for p in event.participants 
            if p.status == EventParticipationStatus.REGISTERED
        ])
        
    return EventDetail(**event_dict)


@router.put("/{event_id}", response_model=Event)
async def update_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento"),
    event_in: EventUpdate,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Actualizar un evento.
    Solo el creador o un administrador puede actualizar el evento.
    """
    # Verificar que current_user.permissions existe antes de verificar permisos
    user_permissions = getattr(current_user, "permissions", []) or []
    
    if "update:events" not in user_permissions and "admin:all" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar eventos"
        )
    
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )
    
    # Verificar permisos
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    is_admin = "admin:all" in user_permissions
    
    # Solo el creador o un admin puede actualizar
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar este evento"
        )
    
    # Actualizar evento
    updated_event = event_repository.update_event(
        db=db, event_id=event_id, event_in=event_in
    )
    return updated_event


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento"),
    current_user: Auth0User = Depends(get_current_user)
) -> None:
    """
    Eliminar un evento.
    Solo el creador o un administrador puede eliminar el evento.
    """
    # Verificar que current_user.permissions existe antes de verificar permisos
    user_permissions = getattr(current_user, "permissions", []) or []
    
    if "delete:events" not in user_permissions and "admin:all" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar eventos"
        )
    
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )
    
    # Verificar permisos
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    is_admin = "admin:all" in user_permissions
    
    # Solo el creador o un admin puede eliminar
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para eliminar este evento"
        )
    
    # Eliminar evento
    event_repository.delete_event(db=db, event_id=event_id)


# Endpoints para Participaciones en Eventos
@router.post("/participation", response_model=EventParticipation, status_code=status.HTTP_201_CREATED)
async def register_for_event(
    *,
    db: Session = Depends(get_db),
    participation_in: EventParticipationCreate,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Registrar al usuario actual como participante en un evento.
    """
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    
    # Verificar que el evento existe
    event = event_repository.get_event(db=db, event_id=participation_in.event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )
    
    # Verificar que el evento no está cancelado o completado
    if event.status != EventStatus.SCHEDULED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No puedes registrarte a un evento con estado {event.status}"
        )
    
    # Crear participación
    participation = event_participation_repository.create_participation(
        db=db, participation_in=participation_in, member_id=user_id
    )
    
    if not participation:
        # Si ya existe una participación
        existing = event_participation_repository.get_participation_by_member_and_event(
            db=db, member_id=user_id, event_id=participation_in.event_id
        )
        
        if existing and existing.status != EventParticipationStatus.CANCELLED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ya estás registrado en este evento"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No se pudo registrar la participación"
            )
    
    return participation


@router.get("/participation/me", response_model=List[EventParticipation])
async def read_my_participations(
    *,
    db: Session = Depends(get_db),
    status: Optional[EventParticipationStatus] = None,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Obtener las participaciones del usuario autenticado.
    """
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    participations = event_participation_repository.get_member_events(
        db=db, member_id=user_id, status=status
    )
    return participations


@router.get("/participation/event/{event_id}", response_model=List[EventParticipation])
async def read_event_participations(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento"),
    status: Optional[EventParticipationStatus] = None,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Obtener participaciones de un evento.
    Solo el creador del evento o un administrador puede ver las participaciones.
    """
    # Verificar que current_user.permissions existe antes de verificar permisos
    user_permissions = getattr(current_user, "permissions", []) or []
    
    if "read:participations" not in user_permissions and "admin:all" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las participaciones de este evento"
        )
    
    # Verificar que el evento existe
    event = event_repository.get_event(db=db, event_id=event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Evento no encontrado"
        )
    
    # Verificar permisos
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    is_admin = "admin:all" in user_permissions
    
    # Solo el creador o un admin puede ver las participaciones
    if not (is_admin or event.creator_id == user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para ver las participaciones de este evento"
        )
    
    # Obtener participaciones
    participations = event_participation_repository.get_event_participants(
        db=db, event_id=event_id, status=status
    )
    return participations


@router.delete("/participation/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_participation(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento"),
    current_user: Auth0User = Depends(get_current_user)
) -> None:
    """
    Cancelar la participación del usuario actual en un evento.
    """
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    
    # Cancelar participación
    participation = event_participation_repository.cancel_participation(
        db=db, member_id=user_id, event_id=event_id
    )
    
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No tienes una participación activa en este evento"
        )


@router.put("/participation/{participation_id}", response_model=EventParticipation)
async def update_participation(
    *,
    db: Session = Depends(get_db),
    participation_id: int = Path(..., title="ID de la participación"),
    participation_in: EventParticipationUpdate,
    current_user: Auth0User = Depends(get_current_user)
) -> Any:
    """
    Actualizar una participación en un evento.
    Solo el creador del evento o un administrador puede actualizar participaciones.
    """
    # Verificar que current_user.permissions existe antes de verificar permisos
    user_permissions = getattr(current_user, "permissions", []) or []
    
    if "update:participations" not in user_permissions and "admin:all" not in user_permissions:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar participaciones"
        )
    
    # Verificar que la participación existe
    participation = event_participation_repository.get_participation(
        db=db, participation_id=participation_id
    )
    if not participation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Participación no encontrada"
        )
    
    # Verificar permisos
    # Modificación: Usar el ID completo de Auth0
    user_id = current_user.id
    is_admin = "admin:all" in user_permissions
    
    # Obtener el evento para verificar si el usuario es el creador
    event = event_repository.get_event(db=db, event_id=participation.event_id)
    
    # Solo el creador del evento o un admin puede actualizar participaciones
    if not (is_admin or (event and event.creator_id == user_id)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para actualizar esta participación"
        )
    
    # Actualizar participación
    updated_participation = event_participation_repository.update_participation(
        db=db, participation_id=participation_id, participation_in=participation_in
    )
    return updated_participation 