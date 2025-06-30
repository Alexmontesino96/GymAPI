"""
Worker Endpoints - Protected endpoints for SQS worker operations

This module defines endpoints that should only be called by the
SQS worker using API key authentication. These endpoints handle
asynchronous tasks such as creating chats for events and
processing completed events.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Body, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.worker_auth import verify_worker_api_key
from app.services.chat import chat_service
from app.repositories.event import event_repository
from app.models.event import EventStatus, Event
from app.models.chat import ChatRoom, ChatRoomStatus
from app.models.user import User
from app.schemas.event import EventWorkerResponse, Event as EventSchema
from app.services.event import event_service
from app.db.redis_client import get_redis_client
from app.core.stream_client import stream_client
from datetime import timedelta
from redis import Redis
import re
from app.core.stream_utils import get_stream_id_from_internal

# Configure logger
logger = logging.getLogger(__name__)

# Create router with prefix /worker
router = APIRouter(prefix="/worker", tags=["worker"])

# Data models for endpoints
class EventChatRequest(BaseModel):
    """Data for creating an event chat."""
    event_id: int
    creator_id: int
    gym_id: int = Field(..., gt=0)
    event_title: Optional[str] = None
    first_message_chat: Optional[str] = None

class EventCompletionRequest(BaseModel):
    """Data for processing a completed event."""
    event_id: int
    gym_id: int = Field(..., gt=0)

class WorkerResponse(BaseModel):
    """Standard response for worker endpoints."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

# Endpoints protected with authentication dependency
@router.post("/event-chat", response_model=WorkerResponse)
async def create_event_chat(
    request: EventChatRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_worker_api_key)  # Security dependency
):
    """
    Creates a chat room for an event.
    
    This endpoint should only be called by the SQS worker.
    Requires authentication via API key.
    
    Args:
        request: Event data for which to create the chat
        db: Database session
        _: Result of security verification (not used directly)
        
    Returns:
        WorkerResponse: Response indicating success or failure
    """
    try:
        # Validate that the event exists
        logger.info(f"[DEBUG] Verifying event {request.event_id}")
        event = event_repository.get_event(db, event_id=request.event_id)
        if not event:
            logger.warning(f"[DEBUG] Event {request.event_id} not found in DB")
            return WorkerResponse(
                success=False,
                message=f"Event {request.event_id} not found"
            )
        
        logger.info(f"[DEBUG] Event {request.event_id} found, gym_id={event.gym_id}, request.gym_id={request.gym_id}")
        
        # Validate that the event belongs to the specified gym
        if event.gym_id != request.gym_id:
            logger.warning(f"[DEBUG] Event {request.event_id} belongs to gym {event.gym_id}, not {request.gym_id}")
            return WorkerResponse(
                success=False,
                message=f"Event {request.event_id} does not belong to gym {request.gym_id}"
            )
        
        # Check if a room already exists for this event
        logger.info(f"[DEBUG] Checking if room exists for event {request.event_id}")
        existing_room = chat_service.get_event_room(db, request.event_id)
        
        if existing_room:
            logger.info(f"[DEBUG] Room for event {request.event_id} already exists: id={existing_room.id}")
            return WorkerResponse(
                success=True,
                message=f"Chat room for event {request.event_id} already exists",
                details={"room_id": existing_room.id, "stream_channel_id": existing_room.stream_channel_id}
            )
            
        # Call the chat service to create the room
        logger.info(f"[DEBUG] Creating chat room for event {request.event_id}, creator_id={request.creator_id}")
        room = chat_service.get_or_create_event_chat(db, request.event_id, request.creator_id, request.gym_id)
        
        # Verify the result
        logger.info(f"[DEBUG] Creation result: {room}")
        
        # Manually verify if the room was created
        verification_room = chat_service.get_event_room(db, request.event_id)
        if verification_room:
            logger.info(f"[DEBUG] Positive verification: room created with id={verification_room.id}")
            
            # Send initial message if provided
            if request.first_message_chat and verification_room.stream_channel_id:
                try:
                    # Get the Stream channel
                    channel = stream_client.channel(verification_room.stream_channel_type, verification_room.stream_channel_id)
                    
                    # Use creator_id directly as the internal ID
                    from app.core.stream_utils import get_stream_id_from_internal
                    
                    # Generate Stream-compatible ID from internal ID
                    message_sender_id = get_stream_id_from_internal(request.creator_id)
                    
                    # Verificar si el usuario existe en Stream
                    user_exists_in_stream = True
                    try:
                        # Intentar actualizar/crear el usuario en Stream
                        stream_client.update_user({
                            "id": message_sender_id,
                            "name": f"Usuario {request.creator_id}",
                        })
                        logger.info(f"[DEBUG] Usuario {message_sender_id} creado/actualizado en Stream")
                    except Exception as e:
                        logger.error(f"[DEBUG] Error creando usuario en Stream: {str(e)}")
                        # Verificar si el error es porque el usuario fue eliminado
                        if "was deleted" in str(e):
                            user_exists_in_stream = False
                            logger.warning(f"[DEBUG] Usuario {message_sender_id} fue eliminado en Stream. Usaremos system como alternativa.")
                    
                    # Si el usuario no existe, usamos "system"
                    if not user_exists_in_stream:
                        message_sender_id = "system"
                        # Asegurarse de que existe el usuario system
                        try:
                            stream_client.update_user({
                                "id": "system",
                                "name": "System Bot",
                            })
                        except:
                            # Ignorar errores, solo es un intento de creación
                            pass
                    
                    # Create message with appropriate format
                    message_response = channel.send_message({
                        "text": request.first_message_chat,
                    }, user_id=message_sender_id)
                    logger.info(f"[DEBUG] Initial message sent to event chat {request.event_id} using user {message_sender_id}")
                except Exception as msg_error:
                    logger.error(f"[DEBUG] Error sending initial message: {str(msg_error)}", exc_info=True)
                    # Don't fail room creation if message sending fails
        else:
            logger.warning(f"[DEBUG] Negative verification: room NOT found after creation")
        
        return WorkerResponse(
            success=True,
            message=f"Chat room for event {request.event_id} successfully created",
            details={"room_id": room.get("id"), "stream_channel_id": room.get("stream_channel_id")}
        )
        
    except Exception as e:
        logger.error(f"[DEBUG] Error creating chat room for event {request.event_id}: {e}", exc_info=True)
        return WorkerResponse(
            success=False,
            message=f"Error creating room: {str(e)}"
        )

@router.post("/event-completion", response_model=WorkerResponse)
async def process_event_completion(
    request: EventCompletionRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_worker_api_key)  # Security dependency
):
    """
    Processes an event as completed.
    
    This endpoint should only be called by the SQS worker.
    Requires authentication via API key.
    
    Args:
        request: Data of the event to mark as completed
        db: Database session
        _: Result of security verification (not used directly)
        
    Returns:
        WorkerResponse: Response indicating success or failure
    """
    try:
        # Validate that the event exists
        event = event_repository.get_event(db, event_id=request.event_id)
        if not event:
            return WorkerResponse(
                success=False,
                message=f"Event {request.event_id} not found"
            )
        
        # Validate that the event belongs to the specified gym
        if event.gym_id != request.gym_id:
            return WorkerResponse(
                success=False,
                message=f"Event {request.event_id} does not belong to gym {request.gym_id}"
            )
        
        # Check if the event is already completed
        if event.status == EventStatus.COMPLETED:
            logger.warning(f"Attempted to mark event {request.event_id} as completed when it's already in COMPLETED state")
            return WorkerResponse(
                success=True,
                message=f"Event {request.event_id} was already marked as completed",
                details={
                    "event_status": event.status.value,
                    "was_already_completed": True
                }
            )
        
        # Mark event as completed
        logger.info(f"Worker requesting to mark event {request.event_id} as completed")
        updated_event = event_repository.mark_event_completed(db, event_id=request.event_id)
        
        if not updated_event:
            return WorkerResponse(
                success=False,
                message=f"Could not update event {request.event_id}"
            )
        
        # Close chat room
        chat_result = chat_service.close_event_chat(db, request.event_id)
        
        return WorkerResponse(
            success=True,
            message=f"Event {request.event_id} marked as completed",
            details={
                "event_status": updated_event.status.value if updated_event else None,
                "chat_closed": chat_result
            }
        )
        
    except Exception as e:
        logger.error(f"Error processing event {request.event_id} as completed: {e}", exc_info=True)
        return WorkerResponse(
            success=False,
            message=f"Error processing event: {str(e)}"
        )

@router.get("/events/due-completion", response_model=List[EventWorkerResponse])
async def get_events_due_for_completion(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_worker_api_key)
) -> List[EventWorkerResponse]:
    """
    Gets up to 100 events whose end time has already passed.
    
    This endpoint protected by API key allows the event completion
    service to get a list of events that should be marked as completed.
    
    Excludes events that have failed more than 10 completion attempts.
    
    Args:
        db: Database session
        _: Result of security verification (not used)
        
    Returns:
        List of events (up to 100) ordered by end time (oldest first).
    """
    try:
        now_utc = datetime.now(timezone.utc)
        
        events = db.query(Event).filter(
            Event.status == EventStatus.SCHEDULED, 
            Event.end_time < now_utc + timedelta(days=1),
            Event.completion_attempts <= 10  # Exclude events with more than 10 attempts
        ).order_by(
            Event.end_time.asc()
        ).limit(100).all()
        
        logger.info(f"Found {len(events)} events with pending completion.")
        
        # Convert to Pydantic schema for response using the new schema
        return [EventWorkerResponse.from_orm(event) for event in events]
        
    except Exception as e:
        logger.error(f"Error getting events pending completion: {e}", exc_info=True)
        # Return empty list or raise exception depending on error policy
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error getting events: {str(e)}"
        )

@router.post("/events/{event_id}/complete", response_model=EventWorkerResponse)
async def process_event_completion(
    event_id: int,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    _: bool = Depends(verify_worker_api_key)
) -> EventWorkerResponse:
    """
    Marks an event as completed and closes its associated chat.
    
    This endpoint protected by API key allows the event completion
    service to process an event's completion, marking it as completed
    and closing its associated chat.
    
    If an error occurs during the process, it increments the counter
    of failed completion attempts.
    
    Args:
        event_id: ID of the event to complete
        db: Database session
        redis_client: Redis client for cache
        _: Result of security verification (not used)
        
    Returns:
        Updated event
    """
    try:
        # Get event using cache with skip_validation
        event = await event_service.get_event_cached(db, event_id, redis_client, skip_validation=True)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event with ID {event_id} not found"
            )
        
        # Update event status to completed
        # Get the real SQLAlchemy object for the update
        db_event = db.query(Event).filter(Event.id == event_id).first()
        if not db_event:
             # This shouldn't happen if get_event_cached was successful, but it's a safe check
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Event {event_id} not found in DB for update"
            )
            
        db_event.status = EventStatus.COMPLETED
        
        # Close associated chat if it exists
        if db_event.chat_room_id:
            chat_room = db.query(ChatRoom).filter(ChatRoom.id == db_event.chat_room_id).first()
            if chat_room:
                chat_room.status = ChatRoomStatus.CLOSED
                logger.info(f"Chat {chat_room.id} closed for event {event_id}")
        
        # Save changes
        db.add(db_event) # Ensure the DB object is added
        db.commit()
        logger.info(f"Event {event_id} successfully marked as completed")
        
        # Get gym_id and creator_id for cache invalidation
        event_gym_id = getattr(event, 'gym_id', db_event.gym_id) # Use db_event as fallback
        event_creator_id = getattr(event, 'creator_id', db_event.creator_id) # Use db_event as fallback
       
        # Invalidate event cache and related
        if redis_client:
            logger.info(f"Invalidating cache for event {event_id}")
            await event_service.invalidate_event_caches(
                redis_client, 
                event_id=event_id,
                gym_id=event_gym_id,
                creator_id=event_creator_id
            )
        
        # Return the updated object from the DB
        return EventWorkerResponse.from_orm(db_event)
        
    except Exception as e:
        db.rollback()
        # Increment failed attempts counter
        try:
            # Get the DB object to increment attempts
            db_event_fail = db.query(Event).filter(Event.id == event_id).first()
            if db_event_fail:
                db_event_fail.completion_attempts = db_event_fail.completion_attempts + 1
                db.add(db_event_fail)
                db.commit()
                logger.warning(f"Incremented attempts counter for event {event_id}: {db_event_fail.completion_attempts}")
        except Exception as inner_e:
            logger.error(f"Error incrementing attempts counter: {inner_e}", exc_info=True)
            db.rollback()
            
        logger.error(f"Error completing event {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal error completing event: {str(e)}"
        ) 