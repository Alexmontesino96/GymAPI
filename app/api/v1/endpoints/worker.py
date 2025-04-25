"""
Endpoints Worker - Endpoints protegidos para operaciones del worker SQS

Este módulo define endpoints que solo deben ser llamados por el 
worker SQS mediante autenticación con clave API. Estos endpoints manejan 
tareas asincrónicas como la creación de chats para eventos y el 
procesamiento de eventos completados.
"""

import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Body, Path, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.worker_auth import verify_worker_api_key
from app.services.chat import chat_service
from app.repositories.event import event_repository

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