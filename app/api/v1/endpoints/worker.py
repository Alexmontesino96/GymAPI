"""
Endpoints Worker - Endpoints protegidos para operaciones del worker SQS

Este módulo define endpoints que solo deben ser llamados por el 
worker SQS mediante autenticación con clave API. Estos endpoints manejan 
tareas asincrónicas como la creación de chats para eventos y el 
procesamiento de eventos completados.
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
from app.schemas.event import EventWorkerResponse, Event as EventSchema
from app.services.event import event_service
from app.db.redis_client import get_redis_client
from redis import Redis

# Configurar logger
logger = logging.getLogger(__name__)

# Crear router con prefijo /worker
router = APIRouter(prefix="/worker", tags=["worker"])

# Modelos de datos para los endpoints
class EventChatRequest(BaseModel):
    """Datos para crear un chat de evento."""
    event_id: int
    creator_id: int
    gym_id: int = Field(..., gt=0)
    event_title: Optional[str] = None

class EventCompletionRequest(BaseModel):
    """Datos para procesar un evento completado."""
    event_id: int
    gym_id: int = Field(..., gt=0)

class WorkerResponse(BaseModel):
    """Respuesta estándar para endpoints del worker."""
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

# Endpoints protegidos con la dependencia de autenticación
@router.post("/event-chat", response_model=WorkerResponse)
async def create_event_chat(
    request: EventChatRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_worker_api_key)  # Dependencia de seguridad
):
    """
    Crea una sala de chat para un evento.
    
    Este endpoint solo debe ser llamado por el worker SQS.
    Requiere autenticación mediante clave API.
    
    Args:
        request: Datos del evento para el que crear el chat
        db: Sesión de base de datos
        _: Resultado de la verificación de seguridad (no usado directamente)
        
    Returns:
        WorkerResponse: Respuesta indicando éxito o fallo
    """
    try:
        # Validar que el evento exista
        logger.info(f"[DEBUG] Verificando evento {request.event_id}")
        event = event_repository.get_event(db, event_id=request.event_id)
        if not event:
            logger.warning(f"[DEBUG] Evento {request.event_id} no encontrado en la BD")
            return WorkerResponse(
                success=False,
                message=f"Evento {request.event_id} no encontrado"
            )
        
        logger.info(f"[DEBUG] Evento {request.event_id} encontrado, gym_id={event.gym_id}, request.gym_id={request.gym_id}")
        
        # Validar que el evento pertenezca al gimnasio especificado
        if event.gym_id != request.gym_id:
            logger.warning(f"[DEBUG] Evento {request.event_id} pertenece al gimnasio {event.gym_id}, no al {request.gym_id}")
            return WorkerResponse(
                success=False,
                message=f"Evento {request.event_id} no pertenece al gimnasio {request.gym_id}"
            )
        
        # Verificar si ya existe una sala para este evento
        logger.info(f"[DEBUG] Verificando si existe sala para evento {request.event_id}")
        existing_room = chat_service.get_event_room(db, request.event_id)
        
        if existing_room:
            logger.info(f"[DEBUG] Sala para evento {request.event_id} ya existe: id={existing_room.id}")
            return WorkerResponse(
                success=True,
                message=f"Sala de chat para evento {request.event_id} ya existe",
                details={"room_id": existing_room.id, "stream_channel_id": existing_room.stream_channel_id}
            )
            
        # Llamar al servicio de chat para crear la sala
        logger.info(f"[DEBUG] Creando sala de chat para evento {request.event_id}, creator_id={request.creator_id}")
        room = chat_service.get_or_create_event_chat(db, request.event_id, request.creator_id)
        
        # Verificar el resultado
        logger.info(f"[DEBUG] Resultado de creación: {room}")
        
        # Verificar manualmente si la sala se creó
        verification_room = chat_service.get_event_room(db, request.event_id)
        if verification_room:
            logger.info(f"[DEBUG] Verificación positiva: sala creada con id={verification_room.id}")
        else:
            logger.warning(f"[DEBUG] Verificación negativa: sala NO encontrada después de creación")
        
        return WorkerResponse(
            success=True,
            message=f"Sala de chat para evento {request.event_id} creada exitosamente",
            details={"room_id": room.get("id"), "stream_channel_id": room.get("stream_channel_id")}
        )
        
    except Exception as e:
        logger.error(f"[DEBUG] Error al crear sala de chat para evento {request.event_id}: {e}", exc_info=True)
        return WorkerResponse(
            success=False,
            message=f"Error creando sala: {str(e)}"
        )

@router.post("/event-completion", response_model=WorkerResponse)
async def process_event_completion(
    request: EventCompletionRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_worker_api_key)  # Dependencia de seguridad
):
    """
    Procesa un evento como completado.
    
    Este endpoint solo debe ser llamado por el worker SQS.
    Requiere autenticación mediante clave API.
    
    Args:
        request: Datos del evento a marcar como completado
        db: Sesión de base de datos
        _: Resultado de la verificación de seguridad (no usado directamente)
        
    Returns:
        WorkerResponse: Respuesta indicando éxito o fallo
    """
    try:
        # Validar que el evento exista
        event = event_repository.get_event(db, event_id=request.event_id)
        if not event:
            return WorkerResponse(
                success=False,
                message=f"Evento {request.event_id} no encontrado"
            )
        
        # Validar que el evento pertenezca al gimnasio especificado
        if event.gym_id != request.gym_id:
            return WorkerResponse(
                success=False,
                message=f"Evento {request.event_id} no pertenece al gimnasio {request.gym_id}"
            )
        
        # Verificar si el evento ya está completado
        if event.status == EventStatus.COMPLETED:
            logger.warning(f"Se intentó marcar como completado el evento {request.event_id} que ya está en estado COMPLETED")
            return WorkerResponse(
                success=True,
                message=f"Evento {request.event_id} ya estaba marcado como completado",
                details={
                    "event_status": event.status.value,
                    "was_already_completed": True
                }
            )
        
        # Marcar evento como completado
        logger.info(f"Worker solicitando marcar evento {request.event_id} como completado")
        updated_event = event_repository.mark_event_completed(db, event_id=request.event_id)
        
        if not updated_event:
            return WorkerResponse(
                success=False,
                message=f"No se pudo actualizar el evento {request.event_id}"
            )
        
        # Cerrar sala de chat
        chat_result = chat_service.close_event_chat(db, request.event_id)
        
        return WorkerResponse(
            success=True,
            message=f"Evento {request.event_id} marcado como completado",
            details={
                "event_status": updated_event.status.value if updated_event else None,
                "chat_closed": chat_result
            }
        )
        
    except Exception as e:
        logger.error(f"Error al procesar evento {request.event_id} como completado: {e}", exc_info=True)
        return WorkerResponse(
            success=False,
            message=f"Error procesando evento: {str(e)}"
        )

@router.get("/events/due-completion", response_model=List[EventWorkerResponse])
async def get_events_due_for_completion(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_worker_api_key)
) -> List[EventWorkerResponse]:
    """
    Obtiene hasta 100 eventos cuyo tiempo de finalización ya pasó.
    
    Este endpoint protegido por clave API permite al servicio de 
    finalización de eventos obtener una lista de eventos que deberían
    marcarse como completados.
    
    Excluye eventos que han fallado más de 10 intentos de finalización.
    
    Args:
        db: Sesión de base de datos
        _: Resultado de la verificación de seguridad (no usado)
        
    Returns:
        Lista de eventos (hasta 100) ordenados por fecha de finalización (más antigua primero).
    """
    try:
        now_utc = datetime.now(timezone.utc)
        
        events = db.query(Event).filter(
            Event.status == EventStatus.SCHEDULED, 
            Event.end_time < now_utc,
            Event.completion_attempts <= 10  # Excluir eventos con más de 10 intentos
        ).order_by(
            Event.end_time.asc()
        ).limit(100).all()
        
        logger.info(f"Encontrados {len(events)} eventos cuya finalización está pendiente.")
        
        # Convertir a esquema Pydantic para respuesta usando el nuevo esquema
        return [EventWorkerResponse.from_orm(event) for event in events]
        
    except Exception as e:
        logger.error(f"Error obteniendo eventos pendientes de finalización: {e}", exc_info=True)
        # Devolver lista vacía o lanzar excepción dependiendo de la política de errores
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al obtener eventos: {str(e)}"
        )

@router.post("/events/{event_id}/complete", response_model=EventWorkerResponse)
async def process_event_completion(
    event_id: int,
    db: Session = Depends(get_db),
    redis_client: Redis = Depends(get_redis_client),
    _: bool = Depends(verify_worker_api_key)
) -> EventWorkerResponse:
    """
    Marca un evento como completado y cierra su chat asociado.
    
    Este endpoint protegido por clave API permite al servicio de 
    finalización de eventos procesar la finalización de un evento,
    marcándolo como completado y cerrando su chat asociado.
    
    Si ocurre un error durante el proceso, incrementa el contador 
    de intentos de finalización fallidos.
    
    Args:
        event_id: ID del evento a completar
        db: Sesión de base de datos
        redis_client: Cliente Redis para caché
        _: Resultado de la verificación de seguridad (no usado)
        
    Returns:
        Evento actualizado
    """
    try:
        # Obtener evento usando caché con skip_validation
        event = await event_service.get_event_cached(db, event_id, redis_client, skip_validation=True)
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evento con ID {event_id} no encontrado"
            )
        
        # Actualizar estado del evento a completado
        # Obtener el objeto SQLAlchemy real para la actualización
        db_event = db.query(Event).filter(Event.id == event_id).first()
        if not db_event:
             # Esto no debería ocurrir si get_event_cached tuvo éxito, pero es una verificación segura
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Evento {event_id} no encontrado en BD para actualización"
            )
            
        db_event.status = EventStatus.COMPLETED
        
        # Cerrar chat asociado si existe
        if db_event.chat_room_id:
            chat_room = db.query(ChatRoom).filter(ChatRoom.id == db_event.chat_room_id).first()
            if chat_room:
                chat_room.status = ChatRoomStatus.CLOSED
                logger.info(f"Chat {chat_room.id} cerrado para el evento {event_id}")
        
        # Guardar cambios
        db.add(db_event) # Asegurar que se añade el objeto de BD
        db.commit()
        logger.info(f"Evento {event_id} marcado como completado correctamente")
        
        # Obtener gym_id y creator_id para invalidación de caché
        event_gym_id = getattr(event, 'gym_id', db_event.gym_id) # Usar db_event como fallback
        event_creator_id = getattr(event, 'creator_id', db_event.creator_id) # Usar db_event como fallback
       
        # Invalidar caché del evento y relacionados
        if redis_client:
            logger.info(f"Invalidando caché para el evento {event_id}")
            await event_service.invalidate_event_caches(
                redis_client, 
                event_id=event_id,
                gym_id=event_gym_id,
                creator_id=event_creator_id
            )
        
        # Devolver el objeto actualizado desde la BD
        return EventWorkerResponse.from_orm(db_event)
        
    except Exception as e:
        db.rollback()
        # Incrementar contador de intentos fallidos
        try:
            # Obtener el objeto de BD para incrementar intentos
            db_event_fail = db.query(Event).filter(Event.id == event_id).first()
            if db_event_fail:
                db_event_fail.completion_attempts = db_event_fail.completion_attempts + 1
                db.add(db_event_fail)
                db.commit()
                logger.warning(f"Incrementado contador de intentos para evento {event_id}: {db_event_fail.completion_attempts}")
        except Exception as inner_e:
            logger.error(f"Error al incrementar contador de intentos: {inner_e}", exc_info=True)
            db.rollback()
            
        logger.error(f"Error al completar evento {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error interno al completar evento: {str(e)}"
        ) 