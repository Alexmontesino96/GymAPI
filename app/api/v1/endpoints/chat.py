"""
Chat Module - API Endpoints

This module provides real-time chat functionality for the gym application using Stream Chat as 
the underlying service. It enables:

- Direct messaging between users (member-to-trainer communication)
- Group chats for events (event participants communication)
- Room management (creating rooms, adding/removing members)

The chat system is integrated with the user authentication system and uses Stream Chat tokens
for secure access. Each endpoint is protected with appropriate permission scopes.
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query, status, Security, Request, Header
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging # Import logging

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User, auth
from app.core.config import get_settings
from app.core.tenant import verify_gym_admin_access, verify_gym_access, verify_gym_trainer_access, get_current_gym, get_tenant_id
from app.schemas.gym import GymSchema
from app.models.user_gym import UserGym, GymRoleType
from app.models.event import Event
from app.services.chat import chat_service
from app.repositories.chat import chat_repository
from app.schemas.chat import (
    ChatRoom,
    ChatRoomCreate,
    StreamTokenResponse,
    StreamMessageSend,
    ChatHideResponse,
    ChatLeaveGroupResponse,
    ChatDeleteGroupResponse,
    DeleteConversationResponse
)
from app.models.user import User
from app.models.chat import ChatRoom as ChatRoomModel, ChatRoomStatus
from app.models.event import Event

router = APIRouter()
logger = logging.getLogger("chat_api") # Initialize logger at the module level

@router.get("/token", response_model=StreamTokenResponse)
async def get_stream_token(
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Get Stream Chat Token

    Generates a secure authentication token for the currently authenticated user
    to connect to the Stream Chat service.

    The token includes user details (name, email, picture) for display purposes
    within the chat interface. It uses the user's internal database ID for Stream identification.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).

    Permissions:
        - Requires 'use:chat' scope (granted to all authenticated users).

    Returns:
        StreamTokenResponse: An object containing:
                               - `token`: The Stream Chat user token.
                               - `api_key`: The Stream Chat application API key.
                               - `internal_user_id`: The user's internal database ID.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'use:chat' scope.
        HTTPException 404: User profile not found in the local database.
    """
    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # User data for Stream Chat profile
    user_data = {
        "name": getattr(internal_user, "display_name", f"{internal_user.first_name} {internal_user.last_name}"), # Use display_name if available
        "email": internal_user.email,
        "image": internal_user.picture # Use 'image' for Stream compatibility
    }

    # Use internal ID to generate the token with gym restriction
    token = chat_service.get_user_token(internal_user.id, user_data, gym_id=current_gym.id)

    # Call get_settings() to get the settings object
    settings_obj = get_settings()
    return {
        "token": token,
        "api_key": settings_obj.STREAM_API_KEY, # Use the object
        "internal_user_id": internal_user.id
    }

@router.post("/rooms", response_model=ChatRoom, status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_data: ChatRoomCreate,
    current_gym: GymSchema = Depends(verify_gym_trainer_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"])
):
    """
    Create Chat Room

    Creates a new group chat room. Intended for use by trainers or administrators.
    The creator is automatically added as a member and channel admin.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        room_data (ChatRoomCreate): Data for the new room, including name and initial member IDs.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).

    Permissions:
        - Requires 'create:chat_rooms' scope (typically for trainers/admins).

    Request Body (ChatRoomCreate):
        {
          "name": "string (optional)",
          "member_ids": [integer] /* List of internal user IDs */,
          "is_direct": false (optional, default: false)
        }

    Returns:
        ChatRoomSchema: The newly created chat room object, including its Stream channel ID.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'create:chat_rooms' scope.
        HTTPException 404: Creator's user profile or specified members not found.
        HTTPException 500: Internal error during room creation (e.g., Stream API error).
    """
    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    # Use internal ID (integer) directly for the service
    creator_id = internal_user.id

    # Service handles room creation in DB and Stream using internal IDs
    # Pass gym_id to ensure room is associated with correct gym
    return chat_service.create_room(db, creator_id, room_data, current_gym.id)

@router.get("/rooms/direct/{other_user_id}", response_model=ChatRoom)
async def get_direct_chat(
    request: Request,
    *,
    db: Session = Depends(get_db),
    other_user_id: int = Path(..., title="Internal user ID for direct chat"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Get or Create Direct Chat Room

    Establishes or retrieves a 1-on-1 direct message channel between the currently
    authenticated user and the specified `other_user_id`.
    If a room already exists, it returns the existing room details. Otherwise,
    a new direct message room is created.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        other_user_id (int): The internal database ID of the other user to chat with.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).

    Permissions:
        - Requires 'use:chat' scope.

    Returns:
        ChatRoomSchema: The direct chat room object.

    Raises:
        HTTPException 400: If the user attempts to create a chat with themselves (`other_user_id` matches current user's ID).
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'use:chat' scope.
        HTTPException 404: Current user's or other user's profile not found.
        HTTPException 500: Internal error during room creation/retrieval.
    """
    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current user profile not found"
        )

    if other_user_id == internal_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create a direct chat with yourself"
        )

    # Verificar que el otro usuario también pertenece al mismo gimnasio
    from app.models.user_gym import UserGym
    other_user_membership = db.query(UserGym).filter(
        UserGym.user_id == other_user_id,
        UserGym.gym_id == current_gym.id
    ).first()
    
    if not other_user_membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No puedes crear un chat directo con un usuario que no pertenece a tu gimnasio"
        )

    # Use internal IDs (integers) directly
    user1_id = internal_user.id
    user2_id = other_user_id

    return chat_service.get_or_create_direct_chat(db, user1_id, user2_id, current_gym.id)

@router.get("/rooms/event/{event_id}", response_model=ChatRoom)
async def get_event_chat(
    request: Request,
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Get or Create Event Chat Room

    Retrieves or creates the group chat room associated with a specific event.
    Users must be registered participants of the event to access or create its chat.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        event_id (int): The ID of the event.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).

    Permissions:
        - Requires 'use:chat' scope.
        - User must be a registered participant of the event.

    Returns:
        ChatRoomSchema: The event's chat room object.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: User is not registered for the event or lacks 'use:chat' scope.
        HTTPException 404: Event or User profile not found.
        HTTPException 500: Internal error during room creation/retrieval.
        HTTPException 503: Chat service timeout/latency issue.
    """
    import time
    # import logging # Already imported at module level
    # logger = logging.getLogger("chat_api") # Already initialized
    start_time = time.time()

    # Get local user from auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )

    logger.info(f"Request for event chat {event_id} by internal user {internal_user.id}")

    try:
        # Check if event exists and belongs to current gym
        from app.models.event import Event
        event = db.query(Event).filter(Event.id == event_id).first()

        if not event:
            logger.warning(f"Event {event_id} not found")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Event {event_id} not found")
        
        if event.gym_id != current_gym.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"No tienes acceso a este evento - pertenece a otro gimnasio"
            )

        # VALIDACIÓN CRÍTICA: Verificar que el usuario esté inscrito en el evento
        # EXCEPCIÓN: Trainers y admins pueden acceder sin estar inscritos
        from app.models.event import EventParticipation, EventParticipationStatus
        
        # Obtener membresía del usuario para verificar su rol
        user_membership = db.query(UserGym).filter(
            UserGym.user_id == internal_user.id,
            UserGym.gym_id == current_gym.id
        ).first()
        
        # Si es trainer, admin, o creador del evento, permitir acceso
        is_trainer_or_admin = (user_membership and 
                              user_membership.role in [GymRoleType.TRAINER, GymRoleType.ADMIN])
        is_event_creator = (event.creator_id == internal_user.id)
        
        if not (is_trainer_or_admin or is_event_creator):
            # Para miembros regulares, verificar inscripción
            participation = db.query(EventParticipation).filter(
                EventParticipation.event_id == event_id,
                EventParticipation.member_id == internal_user.id,
                EventParticipation.gym_id == current_gym.id,
                EventParticipation.status == EventParticipationStatus.REGISTERED
            ).first()
            
            if not participation:
                logger.warning(f"Member {internal_user.id} attempted to access event {event_id} chat without registration")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Debes estar inscrito en este evento para acceder a su chat"
                )
        
        logger.info(f"User {internal_user.id} granted access to event {event_id} chat")
        
        try:
            # Use internal user ID (integer) directly
            user_id = internal_user.id
            result = chat_service.get_or_create_event_chat(db, event_id, user_id, current_gym.id)

            total_time = time.time() - start_time
            logger.info(f"Event chat {event_id} processed in {total_time:.2f}s")

            return result
        except ValueError as e:
            # Catch permission errors from the service layer
            logger.warning(f"Access error for event {event_id} chat by user {internal_user.id}: {str(e)}")
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
        except Exception as e:
            logger.error(f"Error getting event chat {event_id}: {str(e)}", exc_info=True)
            total_time = time.time() - start_time
            if total_time > 5.0: # Timeout threshold
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Chat service is currently experiencing high latency, please try again later"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error processing event chat: {str(e)}"
                )

    except HTTPException:
        # Re-raise specific HTTPExceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_event_chat endpoint: {str(e)}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred")

@router.post("/rooms/{room_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def add_member_to_room(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="Local Chat room ID from DB"),
    user_id: int = Path(..., title="Internal user ID to add"),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Add Member to Chat Room

    Adds a specified user (by internal ID) to an existing chat room (identified by local DB ID).

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        room_id (int): The local database ID of the chat room.
        user_id (int): The internal database ID of the user to add.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).

    Permissions:
        - Requires 'manage:chat_rooms' scope (typically for trainers/admins).

    Returns:
        dict: Success message, e.g., `{"status": "User added successfully"}`.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'manage:chat_rooms' scope.
        HTTPException 404: Chat room or User to add not found.
        HTTPException 500: Internal error adding user (e.g., Stream API error).
    """
    try:
        # Use internal ID (integer) directly
        chat_service.add_user_to_channel(db, room_id, user_id)
        return {"status": "User added successfully"}
    except ValueError as e:
        # Catch errors like room/user not found from service
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to add user {user_id} to room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add user to room")

@router.delete("/rooms/{room_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_member_from_room(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="Local Chat room ID from DB"),
    user_id: int = Path(..., title="Internal user ID to remove"),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Remove Member from Chat Room

    Removes a specified user (by internal ID) from an existing chat room (identified by local DB ID).

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        room_id (int): The local database ID of the chat room.
        user_id (int): The internal database ID of the user to remove.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).

    Permissions:
        - Requires 'manage:chat_rooms' scope (typically for trainers/admins).

    Returns:
        dict: Success message, e.g., `{"status": "User removed successfully"}`.

    Raises:
        HTTPException 401: Invalid or missing authentication token.
        HTTPException 403: Token lacks the required 'manage:chat_rooms' scope.
        HTTPException 404: Chat room or User to remove not found.
        HTTPException 500: Internal error removing user (e.g., Stream API error).
    """
    try:
        # Use internal ID (integer) directly
        chat_service.remove_user_from_channel(db, room_id, user_id)
        return {"status": "User removed successfully"}
    except ValueError as e:
        # Catch errors like room/user not found from service
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to remove user {user_id} from room {room_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to remove user from room")


# =====================================
# ENDPOINTS DE ESTADÍSTICAS Y ANALÍTICAS
# =====================================

@router.get("/analytics/gym-summary")
async def get_gym_chat_summary(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Obtiene un resumen completo de la actividad de chat en un gimnasio.
    
    Requiere permisos de administrador del gimnasio actual (verificado por multi-tenant).
    
    Returns:
        Dict con estadísticas completas del gimnasio:
        - total_rooms: Número total de salas
        - total_members: Miembros únicos en chats
        - active_rooms: Salas con actividad reciente
        - direct_chats: Número de chats directos
        - event_chats: Número de chats de eventos
        - most_active_rooms: Top 5 salas más activas
    """
    try:
        from app.services.chat_analytics import chat_analytics_service
        
        # El gimnasio ya está verificado por la dependencia verify_gym_admin_access
        gym_id = current_gym.id
        
        summary = chat_analytics_service.get_gym_chat_summary(db, gym_id)
        return summary
        
    except Exception as e:
        logger.error(f"Error obteniendo resumen de chat para gimnasio {gym_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Error generando estadísticas")


@router.get("/analytics/user-activity")
async def get_user_chat_activity(
    request: Request,
    *,
    db: Session = Depends(get_db),
    user_id: Optional[int] = Query(None, description="ID del usuario (opcional, por defecto el usuario actual)"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Obtiene estadísticas de actividad de chat para un usuario.
    
    Si no se especifica user_id, retorna estadísticas del usuario actual.
    Para consultar otro usuario, se requiere acceso al mismo gimnasio.
    """
    try:
        from app.services.chat_analytics import chat_analytics_service
        
        # Obtener usuario actual
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
        # Determinar qué usuario consultar
        target_user_id = user_id if user_id else internal_user.id
        
        # Si consulta otro usuario, verificar que también pertenece al mismo gimnasio
        if target_user_id != internal_user.id:
            from app.models.user_gym import UserGym
            target_membership = db.query(UserGym).filter(
                UserGym.user_id == target_user_id,
                UserGym.gym_id == current_gym.id
            ).first()
            
            if not target_membership:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No puedes consultar la actividad de un usuario que no pertenece a tu gimnasio"
                )
        
        activity = chat_analytics_service.get_user_chat_activity(db, target_user_id)
        return activity
        
    except Exception as e:
        logger.error(f"Error obteniendo actividad de usuario {user_id or 'current'}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Error generando estadísticas")


@router.get("/analytics/popular-times")
async def get_popular_chat_times(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    days: int = Query(30, description="Días hacia atrás para analizar", ge=1, le=90),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Analiza los horarios más populares para chat en un gimnasio.
    
    Requiere permisos de administrador del gimnasio actual (verificado por multi-tenant).
    """
    try:
        from app.services.chat_analytics import chat_analytics_service
        
        # El gimnasio ya está verificado por la dependencia verify_gym_admin_access
        gym_id = current_gym.id
        
        analysis = chat_analytics_service.get_popular_chat_times(db, gym_id, days)
        return analysis
        
    except Exception as e:
        logger.error(f"Error analizando horarios para gimnasio {gym_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Error generando análisis")


@router.get("/analytics/event-effectiveness/{event_id}")
async def get_event_chat_effectiveness(
    request: Request,
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., description="ID del evento"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Analiza la efectividad del chat de un evento específico.
    
    El usuario debe pertenecer al mismo gimnasio que el evento para ver estas métricas.
    """
    try:
        from app.services.chat_analytics import chat_analytics_service
        
        # Verificar que el evento pertenece al gimnasio actual
        from app.models.event import Event
        event = db.query(Event).filter(Event.id == event_id).first()
        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evento no encontrado")
        
        if event.gym_id != current_gym.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes acceso a este evento - pertenece a otro gimnasio"
            )
        
        effectiveness = chat_analytics_service.get_event_chat_effectiveness(db, event_id)
        return effectiveness
        
    except Exception as e:
        logger.error(f"Error analizando efectividad de evento {event_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Error generando análisis")


@router.get("/analytics/health-metrics")
async def get_chat_health_metrics(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Genera métricas de salud general del sistema de chat.
    
    Incluye recomendaciones para mejorar el engagement y limpiar datos.
    Requiere permisos de administrador del gimnasio actual (verificado por multi-tenant).
    """
    try:
        from app.services.chat_analytics import chat_analytics_service
        
        # El gimnasio ya está verificado por la dependencia verify_gym_admin_access
        gym_id = current_gym.id
        
        metrics = chat_analytics_service.get_chat_health_metrics(db, gym_id)
        return metrics
        
    except Exception as e:
        logger.error(f"Error generando métricas de salud para gimnasio {gym_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Error generando métricas")


@router.get("/rooms/{room_id}/stats")
async def get_room_statistics(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., description="ID de la sala de chat"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Obtiene estadísticas básicas de una sala de chat específica.
    
    El usuario debe ser miembro de la sala para acceder a estas estadísticas.
    """
    try:
        # Verificar usuario
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
        
        # Verificar que la sala pertenece al gimnasio actual
        from app.models.chat import ChatMember, ChatRoom
        chat_room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        
        if not chat_room:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                              detail="Sala de chat no encontrada")
        
        if chat_room.gym_id != current_gym.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                              detail="No tienes acceso a esta sala de chat - pertenece a otro gimnasio")
        
        # Verificar que el usuario es miembro de la sala
        is_member = db.query(ChatMember).filter(
            ChatMember.room_id == room_id,
            ChatMember.user_id == internal_user.id
        ).first()
        
        if not is_member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, 
                              detail="No tienes acceso a esta sala de chat")
        
        stats = chat_service.get_chat_statistics(db, room_id)
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas de sala {room_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                          detail="Error obteniendo estadísticas")

@router.get("/general-channel/info")
async def get_general_channel_info(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Obtener información del canal general del gimnasio.
    
    Devuelve información básica del canal general incluyendo ID, nombre,
    número de miembros y fechas de creación/actualización.
    """
    from app.services.gym_chat import gym_chat_service
    
    channel_info = gym_chat_service.get_general_channel_info(db, current_gym.id)
    
    if not channel_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Canal general no encontrado para este gimnasio"
        )
    
    return channel_info

@router.post("/general-channel/join", status_code=status.HTTP_200_OK)
async def join_general_channel(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Unirse manualmente al canal general del gimnasio.
    
    Permite a un usuario unirse al canal general si no está ya incluido.
    Normalmente esto se hace automáticamente al unirse al gimnasio.
    """
    from app.services.gym_chat import gym_chat_service
    
    # Obtener usuario interno
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de usuario no encontrado"
        )
    
    success = gym_chat_service.add_user_to_general_channel(db, current_gym.id, internal_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al unirse al canal general"
        )
    
    return {"message": "Te has unido exitosamente al canal general"}

@router.delete("/general-channel/leave", status_code=status.HTTP_200_OK)
async def leave_general_channel(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Salir del canal general del gimnasio.
    
    Permite a un usuario salir del canal general si está incluido.
    Nota: Al salir del gimnasio esto se hace automáticamente.
    """
    from app.services.gym_chat import gym_chat_service
    
    # Obtener usuario interno
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Perfil de usuario no encontrado"
        )
    
    success = gym_chat_service.remove_user_from_general_channel(db, current_gym.id, internal_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al salir del canal general"
        )
    
    return {"message": "Has salido del canal general"}

@router.post("/general-channel/add-member/{user_id}", status_code=status.HTTP_200_OK)
async def add_member_to_general_channel(
    request: Request,
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., title="ID del usuario a agregar"),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Agregar un miembro al canal general (solo administradores).
    
    Permite a administradores agregar manualmente un usuario al canal general.
    """
    from app.services.gym_chat import gym_chat_service
    from app.models.user_gym import UserGym
    
    # Verificar que el usuario pertenece al gimnasio
    membership = db.query(UserGym).filter(
        UserGym.user_id == user_id,
        UserGym.gym_id == current_gym.id
    ).first()
    
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El usuario no pertenece a este gimnasio"
        )
    
    success = gym_chat_service.add_user_to_general_channel(db, current_gym.id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al agregar usuario al canal general"
        )
    
    return {"message": f"Usuario {user_id} agregado al canal general"}

@router.delete("/general-channel/remove-member/{user_id}", status_code=status.HTTP_200_OK)
async def remove_member_from_general_channel(
    request: Request,
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., title="ID del usuario a remover"),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Remover un miembro del canal general (solo administradores).
    
    Permite a administradores remover manualmente un usuario del canal general.
    """
    from app.services.gym_chat import gym_chat_service
    
    success = gym_chat_service.remove_user_from_general_channel(db, current_gym.id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error al remover usuario del canal general"
        )
    
    return {"message": f"Usuario {user_id} removido del canal general"}

@router.get("/debug/headers")
async def debug_headers(
    request: Request,
    x_gym_id_raw: Optional[str] = Header(None, alias="X-Gym-ID"),
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Endpoint de debug para diagnosticar problemas con headers multi-tenant
    """
    # Obtener todos los headers
    all_headers = dict(request.headers)
    
    # Obtener tenant_id usando la función original
    tenant_id = await get_tenant_id(x_gym_id_raw)
    
    # Intentar obtener el gym
    current_gym = await get_current_gym(db, tenant_id, None)
    
    return {
        "all_headers": all_headers,
        "x_gym_id_raw": x_gym_id_raw,
        "tenant_id": tenant_id,
        "current_gym": current_gym.dict() if current_gym else None,
        "user_auth0_id": current_user.id
    }


# =====================================
# ENDPOINTS PARA LISTAR SALAS DE CHAT
# =====================================

@router.get("/my-rooms", response_model=List[ChatRoom])
async def get_user_chat_rooms(
    request: Request,
    *,
    db: Session = Depends(get_db),
    include_hidden: bool = Query(False, description="Incluir chats ocultos"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Obtiene todas las salas de chat del usuario actual en el gimnasio.

    Devuelve una lista de salas donde el usuario es miembro dentro del gimnasio actual.
    Por defecto, excluye chats ocultos.

    Args:
        db (Session): Sesión de base de datos
        include_hidden: Si True, incluye chats ocultos (default: False)
        current_gym (GymSchema): Gimnasio actual del usuario
        current_user (Auth0User): Usuario autenticado

    Returns:
        List[ChatRoom]: Lista de salas de chat del usuario en el gimnasio

    Raises:
        HTTPException 401: Token inválido o faltante
        HTTPException 403: Usuario no pertenece al gimnasio
        HTTPException 404: Usuario no encontrado
        HTTPException 500: Error interno del servidor
    """
    try:
        # Obtener usuario interno
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )

        # Obtener salas del usuario en el gimnasio actual
        from app.models.chat import ChatRoom, ChatMember, ChatMemberHidden
        user_rooms_query = db.query(ChatRoom).join(ChatMember).filter(
            and_(
                ChatMember.user_id == internal_user.id,
                ChatRoom.gym_id == current_gym.id,
                ChatRoom.status == "ACTIVE"  # Solo salas activas
            )
        )

        # Excluir chats ocultos si no se solicitan explícitamente
        if not include_hidden:
            # Subconsulta para obtener IDs de salas ocultas
            hidden_room_ids = db.query(ChatMemberHidden.room_id).filter(
                ChatMemberHidden.user_id == internal_user.id
            ).subquery()

            user_rooms_query = user_rooms_query.filter(
                ~ChatRoom.id.in_(hidden_room_ids)
            )

        user_rooms = user_rooms_query.all()

        logger.info(
            f"Usuario {internal_user.id} tiene {len(user_rooms)} salas "
            f"{'(incluyendo ocultas)' if include_hidden else '(excluyendo ocultas)'} "
            f"en gimnasio {current_gym.id}"
        )

        return user_rooms

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo salas de chat del usuario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo salas de chat"
        )


@router.get("/user-rooms", response_model=List[ChatRoom])
async def get_all_user_chat_rooms(
    request: Request,
    *,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Obtiene todas las salas de chat activas del usuario en todos los gimnasios.
    
    Devuelve una lista completa de salas donde el usuario es miembro,
    sin filtrar por gimnasio específico. Útil para mostrar un dashboard
    global de chats del usuario.
    
    Args:
        db (Session): Sesión de base de datos
        current_user (Auth0User): Usuario autenticado
        
    Returns:
        List[ChatRoom]: Lista de todas las salas de chat activas del usuario
        
    Raises:
        HTTPException 401: Token inválido o faltante
        HTTPException 404: Usuario no encontrado
        HTTPException 500: Error interno del servidor
    """
    try:
        # Obtener usuario interno
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuario no encontrado"
            )
        
        # Obtener todas las salas del usuario usando el repositorio
        user_rooms = chat_repository.get_user_rooms(db, user_id=internal_user.id)
        
        # Filtrar solo salas activas
        active_rooms = [room for room in user_rooms if room.status == "ACTIVE"]
        
        logger.info(f"Usuario {internal_user.id} tiene {len(active_rooms)} salas activas en total")
        
        return active_rooms
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo todas las salas de chat del usuario: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error obteniendo salas de chat"
        )


@router.post("/admin/cleanup-expired-channels", response_model=Dict[str, Any])
async def cleanup_expired_event_channels_endpoint(
    hours: int = Query(48, description="Horas desde finalización del evento para considerar expirado"),
    dry_run: bool = Query(False, description="Solo mostrar canales que se eliminarían sin eliminarlos"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_admin_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:admin"])
):
    """
    Limpieza Manual de Canales de Eventos Expirados
    
    Permite a los administradores limpiar manualmente los canales de Stream Chat
    para eventos que terminaron hace más del tiempo especificado.
    
    Este endpoint es útil para:
    - Limpieza manual inmediata de canales viejos
    - Pruebas con diferentes períodos de expiración  
    - Verificar qué canales se eliminarían antes de ejecutar
    
    Args:
        hours: Número de horas desde la finalización del evento (default: 48)
        dry_run: Si es True, solo muestra los canales sin eliminarlos (default: False)
        current_gym_id: ID del gimnasio actual (automático)
        db: Sesión de base de datos (automático)
    
    Returns:
        Dict con resumen de la operación incluyendo:
        - success: Si la operación fue exitosa
        - events_processed: Número de eventos procesados
        - channels_cleaned: Número de canales eliminados
        - dry_run: Si fue una simulación
        - details: Lista detallada de acciones
    
    Raises:
        HTTPException 403: Sin permisos de administrador
        HTTPException 500: Error interno del servidor
    """
    try:
        # Importar función del scheduler
        from app.core.scheduler import delete_stream_channel
        from datetime import datetime, timedelta, timezone
        
        gym_id = current_gym.id
        logger.info(f"Starting manual cleanup of expired event channels for gym {gym_id}")
        logger.info(f"Parameters: hours={hours}, dry_run={dry_run}")
        
        # Calcular fecha límite
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        # Buscar eventos expirados con chats activos en este gimnasio
        expired_events = db.query(Event).join(ChatRoomModel).filter(
            Event.gym_id == gym_id,  # Filtrar por gimnasio
            Event.end_time < cutoff_time,
            ChatRoomModel.event_id == Event.id,
            ChatRoomModel.status == ChatRoomStatus.ACTIVE
        ).distinct().all()
        
        logger.info(f"Found {len(expired_events)} expired events with active chats in gym {gym_id}")
        
        channels_cleaned = 0
        events_processed = 0
        details = []
        errors = []
        
        for event in expired_events:
            try:
                # Obtener todas las chat_rooms del evento
                chat_rooms = db.query(ChatRoomModel).filter(
                    ChatRoomModel.event_id == event.id,
                    ChatRoomModel.status == ChatRoomStatus.ACTIVE
                ).all()
                
                event_channels = []
                event_channels_cleaned = 0
                
                for chat_room in chat_rooms:
                    channel_info = {
                        "channel_id": chat_room.stream_channel_id,
                        "channel_type": chat_room.stream_channel_type,
                        "room_name": chat_room.name
                    }
                    
                    if not dry_run:
                        try:
                            # Eliminar canal de Stream Chat
                            success = delete_stream_channel(
                                chat_room.stream_channel_type,
                                chat_room.stream_channel_id
                            )
                            
                            if success:
                                # Marcar como cerrada en nuestra DB
                                chat_room.status = ChatRoomStatus.CLOSED
                                chat_room.updated_at = datetime.utcnow()
                                channels_cleaned += 1
                                event_channels_cleaned += 1
                                channel_info["status"] = "deleted"
                            else:
                                channel_info["status"] = "failed"
                                errors.append(f"Failed to delete channel {chat_room.stream_channel_id}")
                                
                        except Exception as e:
                            channel_info["status"] = "error"
                            channel_info["error"] = str(e)
                            errors.append(f"Error deleting channel {chat_room.stream_channel_id}: {e}")
                    else:
                        channel_info["status"] = "would_delete"
                        channels_cleaned += 1
                        event_channels_cleaned += 1
                    
                    event_channels.append(channel_info)
                
                if event_channels_cleaned > 0 or dry_run:
                    events_processed += 1
                    event_detail = {
                        "event_id": event.id,
                        "event_title": event.title,
                        "end_time": event.end_time.isoformat(),
                        "channels": event_channels,
                        "channels_processed": len(event_channels)
                    }
                    details.append(event_detail)
                    
            except Exception as e:
                error_msg = f"Error processing event {event.id}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Commit cambios solo si no es dry_run
        if not dry_run:
            db.commit()
            logger.info(f"Manual cleanup completed. Events processed: {events_processed}, Channels cleaned: {channels_cleaned}")
        else:
            logger.info(f"Dry run completed. Events would be processed: {events_processed}, Channels would be cleaned: {channels_cleaned}")
        
        return {
            "success": True,
            "events_processed": events_processed,
            "channels_cleaned": channels_cleaned,
            "dry_run": dry_run,
            "hours_threshold": hours,
            "gym_id": gym_id,
            "details": details,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        logger.error(f"Error in manual cleanup endpoint: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la limpieza de canales: {str(e)}"
        )


# =====================================
# GESTIÓN DE CHATS (Hide/Leave/Delete)
# =====================================

@router.post("/rooms/{room_id}/hide", response_model=ChatHideResponse)
async def hide_chat(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="ID de la sala a ocultar"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Ocultar Chat 1-to-1 (Patrón WhatsApp)

    Solo funciona con chats directos 1-to-1. Para grupos, usa 'Leave Group'.
    """
    try:
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        result = chat_service.hide_channel_for_user(
            db=db, room_id=room_id, user_id=internal_user.id, gym_id=current_gym.id
        )
        return ChatHideResponse(**result)

    except ValueError as e:
        error_msg = str(e)
        if "Solo puedes ocultar chats directos" in error_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        elif "No eres miembro" in error_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except Exception as e:
        logger.error(f"Error ocultando chat {room_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error ocultando el chat")


@router.post("/rooms/{room_id}/show", response_model=ChatHideResponse)
async def show_chat(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="ID de la sala a mostrar"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """Mostrar Chat Oculto (Unhide)"""
    try:
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        result = chat_service.show_channel_for_user(
            db=db, room_id=room_id, user_id=internal_user.id, gym_id=current_gym.id
        )
        return ChatHideResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error mostrando chat {room_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error mostrando el chat")


@router.post("/rooms/{room_id}/leave", response_model=ChatLeaveGroupResponse)
async def leave_group(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="ID del grupo"),
    auto_hide: bool = Query(True, description="Ocultar automáticamente después de salir"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:read"])
):
    """
    Salir de Grupo (Patrón WhatsApp)

    No aplica a chats 1-to-1 ni eventos. Si eres el último miembro, el grupo se elimina.
    """
    try:
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        result = chat_service.leave_group(
            db=db, room_id=room_id, user_id=internal_user.id, gym_id=current_gym.id, auto_hide=auto_hide
        )
        return ChatLeaveGroupResponse(**result)

    except ValueError as e:
        error_msg = str(e)
        if "No puedes salir" in error_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        elif "No eres miembro" in error_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except Exception as e:
        logger.error(f"Error saliendo de grupo {room_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error saliendo del grupo")


@router.delete("/rooms/{room_id}", response_model=ChatDeleteGroupResponse)
async def delete_group(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="ID del grupo"),
    hard_delete: bool = Query(False, description="Eliminar de Stream Chat"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"])
):
    """
    Eliminar Grupo Completamente

    Solo ADMIN/OWNER pueden eliminar cualquier grupo.
    TRAINER solo puede eliminar grupos que creó.
    Debes remover TODOS los miembros antes de eliminar.
    """
    try:
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        # Obtener rol del usuario
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == internal_user.id,
            UserGym.gym_id == current_gym.id
        ).first()

        if not user_gym:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No perteneces a este gimnasio")

        result = chat_service.delete_group(
            db=db, room_id=room_id, user_id=internal_user.id,
            gym_id=current_gym.id, user_role=user_gym.role.value, hard_delete=hard_delete
        )
        return ChatDeleteGroupResponse(**result)

    except ValueError as e:
        error_msg = str(e)
        if "Debes remover a todos los miembros" in error_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        elif "No tienes permisos" in error_msg or "solo pueden eliminar" in error_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        elif "No puedes eliminar" in error_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except Exception as e:
        logger.error(f"Error eliminando grupo {room_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error eliminando el grupo")


@router.delete("/rooms/{room_id}/conversation", response_model=DeleteConversationResponse)
async def delete_conversation_for_me(
    request: Request,
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="ID de la conversación"),
    current_gym: GymSchema = Depends(verify_gym_access),
    current_user: Auth0User = Security(auth.get_user, scopes=["resource:write"])
):
    """
    Eliminar Conversación 1-to-1 (Solo Para Mí)

    Implementa el patrón "Eliminar Para Mí" de WhatsApp.

    **Comportamiento:**
    - Elimina todos los mensajes de la conversación SOLO para ti
    - El otro usuario mantiene su historial intacto
    - La conversación queda oculta automáticamente
    - Solo aplica a chats directos 1-to-1

    **Diferencias con Hide:**
    - Hide: Solo oculta, mensajes permanecen
    - Delete: Elimina mensajes + oculta chat

    **Para grupos:** Usa el endpoint `POST /rooms/{id}/leave` en su lugar.
    """
    try:
        internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
        if not internal_user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")

        result = chat_service.delete_conversation_for_user(
            db=db,
            room_id=room_id,
            user_id=internal_user.id,
            gym_id=current_gym.id
        )
        return DeleteConversationResponse(**result)

    except ValueError as e:
        error_msg = str(e)
        if "Solo puedes eliminar conversaciones 1-to-1" in error_msg:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
        elif "No eres miembro" in error_msg:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error_msg)
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=error_msg)
    except Exception as e:
        logger.error(f"Error eliminando conversación {room_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error eliminando la conversación") 