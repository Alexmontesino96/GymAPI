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

from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query, status, Security
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User, auth
from app.core.config import settings
from app.services.chat import chat_service
from app.schemas.chat import (
    ChatRoom, 
    ChatRoomCreate, 
    StreamTokenResponse,
    StreamMessageSend
)
from app.models.user import User

router = APIRouter()

@router.get("/token", response_model=StreamTokenResponse)
async def get_stream_token(
    *,
    db: Session = Depends(get_db),
    current_user: Auth0User = Security(auth.get_user, scopes=["use:chat"])
):
    """
    Generate authentication token for Stream Chat.
    
    This endpoint creates a secure token that allows the client to connect to the 
    Stream Chat service with the user's identity. The token includes user data like
    name, email, and profile picture to display in the chat interface.
    
    Permissions:
        - Requires 'use:chat' scope (all authenticated users)
        
    Returns:
        StreamTokenResponse: Contains the Stream token, API key, and internal user ID
    """
    # Obtener el usuario local a partir del auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Datos de usuario para mostrar en el chat
    user_data = {
        "name": getattr(current_user, "name", None),
        "email": current_user.email,
        "picture": getattr(current_user, "picture", None)
    }
    
    # Usar ID interno para generar el token
    token = chat_service.get_user_token(internal_user.id, user_data)
    
    return {
        "token": token,
        "api_key": settings.STREAM_API_KEY,
        "internal_user_id": internal_user.id  # Solo devolver el ID interno
    }

@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    *,
    db: Session = Depends(get_db),
    room_data: ChatRoomCreate,
    current_user: Auth0User = Security(auth.get_user, scopes=["create:chat_rooms"])
):
    """
    Create a new chat room.
    
    This endpoint allows trainers and administrators to create group chat rooms
    for specific purposes. The room creator is automatically added as a member
    and channel admin. Additional members can be specified in the request.
    
    Permissions:
        - Requires 'create:chat_rooms' scope (trainers and administrators)
        
    Args:
        db: Database session
        room_data: Room details including name and member IDs
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        ChatRoom: The newly created chat room
    """
    # Obtener el usuario local a partir del auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    return chat_service.create_room(db, internal_user.id, room_data)

@router.get("/rooms/direct/{user_id}")
async def get_direct_chat(
    *,
    db: Session = Depends(get_db),
    user_id: int = Path(..., title="Internal user ID for direct chat"),
    current_user: Auth0User = Security(auth.get_user, scopes=["use:chat"])
):
    """
    Get or create a direct chat with another user.
    
    This endpoint establishes a 1-on-1 chat channel between the current user and
    the specified user. If a direct chat already exists, it returns the existing
    channel; otherwise, it creates a new one.
    
    Permissions:
        - Requires 'use:chat' scope (all authenticated users)
        
    Args:
        db: Database session
        user_id: The internal ID of the user to chat with
        current_user: Authenticated user
        
    Returns:
        ChatRoom: The direct chat room between the two users
        
    Raises:
        HTTPException: 400 if attempting to create a chat with oneself
    """
    # Obtener el usuario local a partir del auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    if user_id == internal_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot create a chat with yourself"
        )
    
    return chat_service.get_or_create_direct_chat(db, internal_user.id, user_id)

@router.get("/rooms/event/{event_id}")
async def get_event_chat(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="Event ID"),
    current_user: Auth0User = Security(auth.get_user, scopes=["use:chat"])
):
    """
    Get or create the chat for an event.
    
    This endpoint retrieves or creates a group chat associated with a specific event.
    Event chats are accessible to all event participants and allow for group 
    communication before, during, and after the event.
    
    Permissions:
        - Requires 'use:chat' scope (all authenticated users)
        - User must be registered for the event to access its chat
        
    Args:
        db: Database session
        event_id: ID of the event
        current_user: Authenticated user
        
    Returns:
        ChatRoom: The event's chat room
    """
    # Monitoreo de rendimiento
    import time
    import logging
    logger = logging.getLogger("chat_api")
    start_time = time.time()
    
    # Obtener el usuario local a partir del auth0_id
    internal_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not internal_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    logger.info(f"Solicitud de chat para evento {event_id} por usuario interno {internal_user.id}")
    
    try:
        # Verificación rápida si el evento existe
        from app.models.event import Event
        event_exists = db.query(Event.id).filter(Event.id == event_id).first() is not None
        
        if not event_exists:
            logger.warning(f"Evento {event_id} no encontrado")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found"
            )
        
        # Intento crear/obtener la sala con tiempo de respuesta limitado
        try:
            result = chat_service.get_or_create_event_chat(db, event_id, internal_user.id)
            
            total_time = time.time() - start_time
            logger.info(f"Chat del evento {event_id} procesado en {total_time:.2f}s")
            
            return result
        except ValueError as e:
            logger.warning(f"Error de acceso: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(e)
            )
        except Exception as e:
            logger.error(f"Error obteniendo chat de evento: {str(e)}", exc_info=True)
            # Si tarda demasiado, responder con error específico
            total_time = time.time() - start_time
            if total_time > 5.0:  # Si tardó más de 5 segundos, probablemente hay un problema
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
        raise
    except Exception as e:
        # Capturar otros errores inesperados
        logger.error(f"Error inesperado: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred"
        )

@router.post("/rooms/{room_id}/members/{user_id}")
async def add_member_to_room(
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="Chat room ID"),
    user_id: int = Path(..., title="Internal user ID to add"),
    current_user: Auth0User = Security(auth.get_user, scopes=["manage:chat_rooms"])
):
    """
    Add a member to a chat room.
    
    This endpoint allows administrators and trainers to add a user to an existing
    chat room. This is useful for bringing new members into group discussions
    or for adding users to event chats when they register for an event.
    
    Permissions:
        - Requires 'manage:chat_rooms' scope (trainers and administrators)
        
    Args:
        db: Database session
        room_id: ID of the chat room
        user_id: Internal ID of the user to add
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        dict: Status of the operation with user and room details
        
    Raises:
        HTTPException: 404 if room or user not found
    """
    try:
        return chat_service.add_user_to_channel(db, room_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.delete("/rooms/{room_id}/members/{user_id}")
async def remove_member_from_room(
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="Chat room ID"),
    user_id: int = Path(..., title="Internal user ID to remove"),
    current_user: Auth0User = Security(auth.get_user, scopes=["manage:chat_rooms"])
):
    """
    Remove a member from a chat room.
    
    This endpoint allows administrators and trainers to remove a user from a chat room.
    This is useful when a user is no longer participating in an event or when
    moderation is needed.
    
    Permissions:
        - Requires 'manage:chat_rooms' scope (trainers and administrators)
        
    Args:
        db: Database session
        room_id: ID of the chat room
        user_id: Internal ID of the user to remove
        current_user: Authenticated user with appropriate permissions
        
    Returns:
        dict: Status of the operation with user and room details
        
    Raises:
        HTTPException: 404 if room or user not found
    """
    try:
        return chat_service.remove_user_from_channel(db, room_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) 