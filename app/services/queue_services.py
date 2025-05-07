"""
Servicio para gestión de mensajes en colas.

Este módulo proporciona funcionalidades para publicar mensajes en colas como AWS SQS.
Permite la comunicación asíncrona entre diferentes partes del sistema.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from app.services.aws_sqs import sqs_service

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para tipos de mensajes
CREATE_EVENT_CHAT = "create_event_chat"

class QueueService:
    
    @staticmethod
    def publish_event_processing(
        event_id: int,
        creator_id: int,
        gym_id: int,
        event_title: str,
        end_time: datetime,
        first_message_chat: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publica un mensaje para crear el chat de un evento.
        
        Este método:
        1. Envía un mensaje a SQS para crear el chat del evento
        
        La finalización del evento se maneja por un servicio externo
        que ejecuta verificaciones periódicas.
        
        Args:
            event_id: ID del evento
            creator_id: ID del creador del evento
            gym_id: ID del gimnasio
            event_title: Título del evento
            end_time: Fecha y hora de finalización del evento (solo para referencia)
            first_message_chat: Mensaje inicial opcional que se enviará al crear la sala de chat
            
        Returns:
            Resultado del envío del mensaje a SQS
        """
        try:
            # Enviar mensaje a SQS para crear el chat del evento
            chat_message = {
                "action": CREATE_EVENT_CHAT,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event_data": {
                    "event_id": event_id,
                    "creator_id": creator_id,
                    "gym_id": gym_id,
                    "event_title": event_title,
                    "first_message_chat": first_message_chat
                }
            }
            
            # Convertir el mensaje a formato JSON para el cuerpo
            chat_message_body = json.dumps(chat_message)
            
            # Definir el MessageGroupId (usando event_id)
            message_group_id = str(event_id)
            
            # Enviar mensaje a SQS para crear el chat
            sqs_response = sqs_service.send_message(
                message_body=chat_message_body,
                message_group_id=message_group_id
            )
            
            if "error" not in sqs_response:
                logger.info(f"Solicitud de creación de chat para evento {event_id} publicada en SQS con MessageId: {sqs_response.get('MessageId')}")
                return {
                    "success": True,
                    "chat_creation": {
                        "success": True,
                        "message_id": sqs_response.get('MessageId')
                    }
                }
            else:
                logger.error(f"Error al enviar mensaje para creación de chat: {sqs_response.get('error')}")
                return {
                    "success": False,
                    "chat_creation": {
                        "success": False,
                        "error": sqs_response.get('error')
                    }
                }
            
        except Exception as e:
            error_msg = f"Error inesperado al procesar evento en cola: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "error": error_msg}

# Instancia única del servicio
queue_service = QueueService() 