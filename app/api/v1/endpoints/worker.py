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
import sys
import time
import traceback

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
        room = chat_service.get_or_create_event_chat(db, request.event_id, request.creator_id)
        
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
                    
                    # Find the creator user to use their ID in the message
                    creator = db.query(User).filter(User.id == request.creator_id).first()
                    if creator and creator.auth0_id:
                        # Create message with appropriate format
                        message_response = channel.send_message({
                            "text": request.first_message_chat,
                            "user_id": creator.auth0_id  # Use auth0_id for Stream
                        })
                        logger.info(f"[DEBUG] Initial message sent to event chat {request.event_id}")
                    else:
                        logger.warning(f"[DEBUG] Could not find creator {request.creator_id} to send initial message")
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
    # Crear logger específico para este endpoint
    endpoint_logger = logging.getLogger("endpoint.events_due_completion")
    endpoint_logger.setLevel(logging.DEBUG)
    
    # Asegurar que los logs sean visibles
    if not endpoint_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        endpoint_logger.addHandler(handler)
    
    print("\n=== INICIO ENDPOINT GET_EVENTS_DUE_FOR_COMPLETION ===")
    endpoint_logger.info("Iniciando búsqueda de eventos pendientes de completar")
    
    try:
        # Obtener timestamp actual
        now_utc = datetime.now(timezone.utc)
        print(f"Timestamp actual: {now_utc.isoformat()}")
        endpoint_logger.debug(f"Timestamp actual: {now_utc.isoformat()}")
        
        # Imprimir criterios de filtrado
        search_end_time = now_utc + timedelta(days=1)
        search_criteria = {
            "status": EventStatus.SCHEDULED.value,
            "end_time_antes_de": search_end_time.isoformat(),
            "max_completion_attempts": 10,
            "limit": 100
        }
        print(f"Criterios de búsqueda: {search_criteria}")
        endpoint_logger.debug(f"Criterios de búsqueda: {search_criteria}")
        
        # Construir la consulta
        query = db.query(Event).filter(
            Event.status == EventStatus.SCHEDULED, 
            Event.end_time < search_end_time,
            Event.completion_attempts <= 10
        ).order_by(
            Event.end_time.asc()
        ).limit(100)
        
        print(f"SQL Query: {str(query)}")
        endpoint_logger.debug(f"SQL Query: {str(query)}")
        
        # Ejecutar la consulta y medir el tiempo
        start_time = time.time()
        events = query.all()
        query_time = time.time() - start_time
        
        # Registrar resultado
        event_count = len(events)
        result_msg = f"Encontrados {event_count} eventos pendientes de completar en {query_time:.4f}s"
        print(result_msg)
        endpoint_logger.info(result_msg)
        logger.info(f"Found {event_count} events with pending completion.")
        
        # Imprimir detalles de los primeros eventos para diagnóstico
        if events:
            print("Primeros eventos encontrados:")
            for i, event in enumerate(events[:5]):  # Primeros 5 eventos
                event_info = f"  {i+1}. ID={event.id}, Título={event.title}, Fin={event.end_time}, Intentos={event.completion_attempts}"
                print(event_info)
                endpoint_logger.debug(event_info)
        
        # Convertir a esquema de respuesta
        print("Convirtiendo eventos a esquema de respuesta...")
        start_conversion = time.time()
        response = [EventWorkerResponse.from_orm(event) for event in events]
        conversion_time = time.time() - start_conversion
        print(f"Conversión completada en {conversion_time:.4f}s")
        
        # Log final
        end_msg = f"Procesamiento completado con éxito: {event_count} eventos listos para completar"
        print(f"=== FIN ENDPOINT ({end_msg}) ===\n")
        endpoint_logger.info(end_msg)
        
        return response
        
    except Exception as e:
        # Capturar y registrar el error
        error_msg = f"Error al obtener eventos pendientes: {str(e)}"
        print(f"ERROR: {error_msg}")
        print(f"Traceback: {traceback.format_exc()}")
        endpoint_logger.exception(error_msg)
        logger.error(f"Error getting events pending completion: {e}", exc_info=True)
        
        print("=== FIN ENDPOINT (ERROR) ===\n")
        
        # Lanzar excepción HTTP con detalles
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