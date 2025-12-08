"""
AsyncQueueService - Servicio async para gestión de mensajes en colas.

Este módulo proporciona funcionalidades para publicar mensajes en colas como AWS SQS.
Permite la comunicación asíncrona entre diferentes partes del sistema.

Migrado en FASE 3 de la conversión sync → async.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from app.services.async_aws_sqs import AsyncSQSService

# Instancia singleton del servicio SQS async
async_sqs_service = AsyncSQSService()

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para tipos de mensajes
CREATE_EVENT_CHAT = "create_event_chat"
# Acción utilizada para identificar mensajes de creación de chat que deben eliminarse
CANCEL_EVENT_CHAT = "cancel_event_chat"  # Alias interno, no se envía a SQS (solo filtro interno)


class AsyncQueueService:
    """
    Servicio async para publicación de mensajes en AWS SQS.

    Todos los métodos son async aunque SQS SDK es sync.

    Operaciones soportadas:
    - Publicar solicitud de creación de chat para eventos
    - Cancelar mensajes pendientes de eventos eliminados

    Métodos principales:
    - publish_event_processing() - Publicar mensaje de creación de chat
    - cancel_event_processing() - Eliminar mensajes pendientes de evento
    """

    @staticmethod
    async def publish_event_processing(
        event_id: int,
        creator_id: int,
        gym_id: int,
        event_title: str,
        end_time: datetime,
        first_message_chat: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Publica un mensaje para crear el chat de un evento en AWS SQS.

        Args:
            event_id: ID del evento
            creator_id: ID del creador del evento
            gym_id: ID del gimnasio
            event_title: Título del evento
            end_time: Fecha y hora de finalización del evento (referencia)
            first_message_chat: Mensaje inicial opcional para el chat

        Returns:
            Dict con resultado del envío:
            - success: bool
            - chat_creation: Dict con message_id o error

        Note:
            El mensaje se envía con MessageGroupId = event_id para garantizar
            procesamiento ordenado en SQS FIFO.
            La finalización del evento se maneja por servicio externo.
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
            sqs_response = await async_sqs_service.send_message(
                message_body=chat_message_body,
                message_group_id=message_group_id
            )

            if "error" not in sqs_response:
                logger.info(
                    f"Solicitud de creación de chat para evento {event_id} "
                    f"publicada en SQS con MessageId: {sqs_response.get('MessageId')}"
                )
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

    @staticmethod
    async def cancel_event_processing(event_id: int) -> Dict[str, Any]:
        """
        Elimina mensajes pendientes de SQS relacionados con el evento.

        Args:
            event_id: ID del evento a cancelar

        Returns:
            Dict con resultado:
            - success: bool
            - removed: Cantidad de mensajes eliminados (si success=True)
            - error: Mensaje de error (si success=False)

        Note:
            Elimina mensajes cuya acción sea CREATE_EVENT_CHAT
            y cuyo event_id coincida.
            Útil para limpiar mensajes pendientes cuando se elimina un evento.
        """
        try:
            removed = await async_sqs_service.delete_event_messages(
                event_id=event_id,
                actions=[CREATE_EVENT_CHAT]
            )

            logger.info(
                f"Se eliminaron {removed} mensajes pendientes de SQS para event_id={event_id}"
            )
            return {"success": True, "removed": removed}
        except Exception as e:
            logger.error(
                f"Error al intentar eliminar mensajes de SQS para evento {event_id}: {e}",
                exc_info=True,
            )
            return {"success": False, "error": str(e)}


# Instancia singleton del servicio async
async_queue_service = AsyncQueueService()
