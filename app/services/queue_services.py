"""
Servicio para gestión de mensajes en colas.

Este módulo proporciona funcionalidades para publicar mensajes en colas como AWS SQS.
Permite la comunicación asíncrona entre diferentes partes del sistema.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime

from sqlalchemy.orm import Session
from app.services.aws_sqs import sqs_service

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para tipos de mensajes
EVENT_CREATED = "event_created"
CREATE_EVENT_CHAT = "create_event_chat"

class QueueService:

    
    @staticmethod
    def publish_create_event_chat(
        event_id: int,
        creator_id: int,
        gym_id: int,
        event_title: str
    ) -> Dict[str, Any]:
        """
        Publica un mensaje para crear una sala de chat para un evento.
        
        Args:
            event_id: ID del evento
            creator_id: ID del creador del evento
            gym_id: ID del gimnasio
            event_title: Título del evento
            
        Returns:
            Respuesta del servicio SQS o diccionario con error
        """
        try:
            # Crear mensaje para solicitar creación de chat
            message = {
                "action": CREATE_EVENT_CHAT,
                "timestamp": datetime.utcnow().isoformat(),
                "chat_data": {
                    "event_id": event_id,
                    "creator_id": creator_id,
                    "gym_id": gym_id,
                    "event_title": event_title
                }
            }
            
            # Convertir el mensaje a formato JSON para el cuerpo
            message_body = json.dumps(message)
            
            # Definir el MessageGroupId (usando event_id)
            message_group_id = str(event_id)
            
            # Enviar mensaje a SQS usando el nuevo método
            response = sqs_service.send_message(
                message_body=message_body,
                message_group_id=message_group_id
            )
            
            logger.info(f"Solicitud de creación de chat para evento {event_id} publicada en SQS con MessageId: {response.get('MessageId')}")
                
            return response
            
        except Exception as e:
            error_msg = f"Error inesperado al solicitar creación de chat en SQS: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

# Instancia única del servicio
queue_service = QueueService() 