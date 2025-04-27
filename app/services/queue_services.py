"""
Servicio para gestión de mensajes en colas.

Este módulo proporciona funcionalidades para publicar mensajes en colas como AWS SQS.
Permite la comunicación asíncrona entre diferentes partes del sistema.
"""
import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from app.services.aws_sqs import sqs_service
from app.services.aws_event_bridge import event_bridge_service

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para tipos de mensajes
EVENT_CREATED = "event_created"
PROCESS_EVENT = "process_event"
CREATE_EVENT_CHAT = "create_event_chat"

class QueueService:
    
    @staticmethod
    def publish_event_processing(
        event_id: int,
        creator_id: int,
        gym_id: int,
        event_title: str,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Publica un mensaje para procesar un evento (crear chat y programar finalización).
        
        Este método ahora:
        1. Envía un mensaje a SQS para crear el chat del evento
        2. Programa la finalización del evento usando EventBridge
        
        Args:
            event_id: ID del evento
            creator_id: ID del creador del evento
            gym_id: ID del gimnasio
            event_title: Título del evento
            end_time: Fecha y hora de finalización del evento
            
        Returns:
            Respuesta combinada de SQS y EventBridge
        """
        try:
            results = {}
            
            # 1. Enviar mensaje a SQS para crear el chat del evento
            chat_message = {
                "action": CREATE_EVENT_CHAT,
                "timestamp": datetime.utcnow().isoformat(),
                "event_data": {
                    "event_id": event_id,
                    "creator_id": creator_id,
                    "gym_id": gym_id,
                    "event_title": event_title
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
                results["sqs_chat_creation"] = {
                    "success": True,
                    "message_id": sqs_response.get('MessageId')
                }
            else:
                logger.error(f"Error al enviar mensaje para creación de chat: {sqs_response.get('error')}")
                results["sqs_chat_creation"] = {
                    "success": False,
                    "error": sqs_response.get('error')
                }
            
            # 2. Programar la finalización del evento usando EventBridge
            # Verificar si la fecha de finalización ya pasó
            now = datetime.utcnow()
            
            if end_time <= now:
                logger.warning(f"La fecha de finalización del evento {event_id} ya pasó, ejecutando finalización inmediata")
                
                # Para eventos ya finalizados, enviar mensaje directo a SQS sin programar en EventBridge
                completion_message = {
                    "action": "event_completion",
                    "event_data": {
                        "event_id": event_id,
                        "gym_id": gym_id
                    }
                }
                
                completion_message_body = json.dumps(completion_message)
                immediate_response = sqs_service.send_message(
                    message_body=completion_message_body,
                    message_group_id=message_group_id
                )
                
                if "error" not in immediate_response:
                    logger.info(f"Solicitud inmediata de finalización para evento {event_id} publicada en SQS")
                    results["event_completion"] = {
                        "success": True,
                        "immediate": True,
                        "message_id": immediate_response.get('MessageId')
                    }
                else:
                    logger.error(f"Error al enviar mensaje inmediato para finalización: {immediate_response.get('error')}")
                    results["event_completion"] = {
                        "success": False, 
                        "error": immediate_response.get('error')
                    }
            else:
                # Para eventos futuros, programar en EventBridge
                bridge_response = event_bridge_service.schedule_event_completion(
                    event_id=event_id,
                    gym_id=gym_id,
                    end_time=end_time
                )
                
                if "error" not in bridge_response:
                    logger.info(f"Programación de finalización para evento {event_id} configurada en EventBridge: {bridge_response.get('rule_name')}")
                    results["event_completion"] = {
                        "success": True,
                        "scheduled": True,
                        "rule_name": bridge_response.get('rule_name'),
                        "cron_expression": bridge_response.get('cron_expression')
                    }
                else:
                    logger.error(f"Error al programar finalización en EventBridge: {bridge_response.get('error')}")
                    results["event_completion"] = {
                        "success": False,
                        "error": bridge_response.get('error')
                    }
            
            return results
            
        except Exception as e:
            error_msg = f"Error inesperado al procesar evento en cola: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

# Instancia única del servicio
queue_service = QueueService() 