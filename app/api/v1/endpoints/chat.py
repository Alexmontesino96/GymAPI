from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body, Path, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User
from app.core.config import settings
from app.services.chat import chat_service
from app.schemas.chat import (
    ChatRoom, 
    ChatRoomCreate, 
    StreamTokenResponse,
    StreamMessageSend
)

router = APIRouter()

@router.get("/token", response_model=StreamTokenResponse)
async def get_stream_token(
    current_user: Auth0User = Depends(get_current_user)
):
    """Generar token de autenticación para Stream Chat"""
    user_id = current_user.id
    user_data = {
        "name": getattr(current_user, "name", None),
        "email": current_user.email,
        "picture": getattr(current_user, "picture", None)
    }
    
    token = chat_service.get_user_token(user_id, user_data)
    
    return {
        "token": token,
        "api_key": settings.STREAM_API_KEY,
        "user_id": user_id
    }

@router.post("/rooms", status_code=status.HTTP_201_CREATED)
async def create_chat_room(
    *,
    db: Session = Depends(get_db),
    room_data: ChatRoomCreate,
    current_user: Auth0User = Depends(get_current_user)
):
    """Crear una nueva sala de chat"""
    return chat_service.create_room(db, current_user.id, room_data)

@router.get("/rooms/direct/{user_id}")
async def get_direct_chat(
    *,
    db: Session = Depends(get_db),
    user_id: str = Path(..., title="ID del usuario para chat directo"),
    current_user: Auth0User = Depends(get_current_user)
):
    """Obtener o crear un chat directo con otro usuario"""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes crear un chat contigo mismo"
        )
    
    return chat_service.get_or_create_direct_chat(db, current_user.id, user_id)

@router.get("/rooms/event/{event_id}")
async def get_event_chat(
    *,
    db: Session = Depends(get_db),
    event_id: int = Path(..., title="ID del evento"),
    current_user: Auth0User = Depends(get_current_user)
):
    """Obtener o crear el chat para un evento"""
    return chat_service.get_or_create_event_chat(db, event_id, current_user.id)

@router.post("/rooms/{room_id}/members/{user_id}")
async def add_member_to_room(
    *,
    db: Session = Depends(get_db),
    room_id: int = Path(..., title="ID de la sala de chat"),
    user_id: str = Path(..., title="ID del usuario a añadir"),
    current_user: Auth0User = Depends(get_current_user)
):
    """Añadir un miembro a una sala de chat"""
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
    room_id: int = Path(..., title="ID de la sala de chat"),
    user_id: str = Path(..., title="ID del usuario a eliminar"),
    current_user: Auth0User = Depends(get_current_user)
):
    """Eliminar un miembro de una sala de chat"""
    try:
        return chat_service.remove_user_from_channel(db, room_id, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        ) 