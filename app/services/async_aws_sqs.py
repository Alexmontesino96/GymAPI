"""
AsyncSQSService - Servicio async para interactuar con Amazon SQS.

Este módulo proporciona funcionalidades async para publicar mensajes en colas de SQS.

Nota: boto3 SDK es sync por diseño de AWS. Los métodos son async para consistencia
pero internamente usan boto3 sync. Para operaciones I/O intensivas considerar aioboto3.

Migrado en FASE 3 de la conversión sync → async.
"""
import boto3
import json
import logging
from typing import Dict, Any, List, Optional, Union
from botocore.exceptions import ClientError

from app.core.config import get_settings

# Configurar logger
logger = logging.getLogger("async_sqs_service")


class SQSError(Exception):
    """Excepción personalizada para errores de SQS."""
    pass


class AsyncSQSService:
    """
    Servicio async para interactuar con Amazon SQS (Simple Queue Service).

    Todos los métodos son async aunque boto3 SDK es sync.

    Nota técnica:
    - boto3 es el SDK oficial de AWS y no tiene versión async nativa
    - Las operaciones SQS son típicamente rápidas (< 100ms)
    - Para alto throughput considerar aioboto3 o thread pool executor

    Métodos principales:
    - send_message() - Envía mensaje individual a cola
    - send_batch_messages() - Envía hasta 10 mensajes en batch
    - delete_event_messages() - Elimina mensajes por event_id
    """

    def __init__(self):
        """
        Inicializa el cliente de SQS.

        Raises:
            SQSError: Si las credenciales no están configuradas
        """
        self.initialized = False
        self.client = None
        settings = get_settings()
        self.queue_url = settings.SQS_QUEUE_URL

        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY and settings.SQS_QUEUE_URL:
            try:
                self.client = boto3.client(
                    'sqs',
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                self.initialized = True
                logger.info("Servicio SQS async inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar el cliente SQS: {str(e)}", exc_info=True)
        else:
            logger.warning("No se pudo inicializar el servicio SQS: faltan credenciales o URL de cola")

    async def send_message(
        self,
        message_body: str,
        message_attributes: Optional[Dict[str, Dict[str, Any]]] = None,
        delay_seconds: int = 0,
        message_group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía un mensaje a la cola SQS configurada.

        Args:
            message_body: El cuerpo del mensaje (string o JSON serializado)
            message_attributes: Atributos del mensaje (opcional)
            delay_seconds: Retraso en segundos para la entrega (0-900)
            message_group_id: ID del grupo de mensajes (REQUERIDO para colas FIFO)

        Returns:
            Dict con respuesta de SQS si tiene éxito:
            - MessageId: ID del mensaje enviado
            - MD5OfMessageBody: Hash MD5 del cuerpo
            - SequenceNumber: Número de secuencia (FIFO only)

        Raises:
            SQSError: Si cliente SQS no está configurado
            ValueError: Si message_group_id es None y la cola es FIFO

        Note:
            Colas FIFO requieren MessageGroupId obligatorio.
            Delay máximo: 15 minutos (900 segundos).
        """
        if not self.client or not self.queue_url:
            raise SQSError("Cliente SQS o URL de la cola no configurados.")

        # Validar si se necesita MessageGroupId (para colas FIFO)
        is_fifo = self.queue_url.endswith('.fifo')
        if is_fifo and message_group_id is None:
            logger.error("Error: MessageGroupId es requerido para colas FIFO pero no se proporcionó.")
            raise ValueError("MessageGroupId es requerido para colas FIFO.")

        try:
            params = {
                'QueueUrl': self.queue_url,
                'MessageBody': message_body,
                'DelaySeconds': delay_seconds
            }
            if message_attributes:
                params['MessageAttributes'] = message_attributes

            # Añadir MessageGroupId si es una cola FIFO
            if is_fifo:
                params['MessageGroupId'] = message_group_id
                # Opcional: Añadir MessageDeduplicationId si no usas deduplicación basada en contenido
                # import hashlib
                # params['MessageDeduplicationId'] = hashlib.sha256(message_body.encode()).hexdigest()

            logger.debug(f"Enviando mensaje a SQS con parámetros: {params}")
            response = self.client.send_message(**params)
            logger.info(f"Mensaje enviado a SQS exitosamente. MessageId: {response.get('MessageId')}")
            return response
        except ClientError as e:
            error_msg = f"Error de boto3 al enviar mensaje a SQS: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error inesperado al enviar mensaje a SQS: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    async def send_batch_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Envía múltiples mensajes a la cola de SQS en una sola operación.

        Args:
            messages: Lista de diccionarios con los mensajes a enviar

        Returns:
            Dict con respuesta de SQS:
            - Successful: Lista de mensajes enviados exitosamente
            - Failed: Lista de mensajes fallidos con error

        Note:
            SQS permite hasta 10 mensajes por operación batch.
            Si se proporcionan más de 10, solo se enviarán los primeros 10.
        """
        if not self.initialized:
            error_msg = "El servicio SQS no está inicializado correctamente"
            logger.error(error_msg)
            return {"error": error_msg}

        if not self.queue_url:
            error_msg = "URL de cola SQS no configurada"
            logger.error(error_msg)
            return {"error": error_msg}

        if not messages:
            return {"error": "No hay mensajes para enviar"}

        try:
            # Preparar los mensajes en el formato esperado por SQS
            entries = []
            for i, message in enumerate(messages):
                entries.append({
                    'Id': str(i),  # ID único para cada mensaje en el batch
                    'MessageBody': json.dumps(message)
                })

            # SQS permite hasta 10 mensajes en una operación de batch
            if len(entries) > 10:
                logger.warning(f"Se han proporcionado {len(entries)} mensajes, pero SQS solo permite 10 en batch. Se enviarán los primeros 10.")
                entries = entries[:10]

            # Enviar los mensajes en batch
            response = self.client.send_message_batch(
                QueueUrl=self.queue_url,
                Entries=entries
            )

            logger.info(f"Batch de {len(entries)} mensajes enviados a SQS")
            return response
        except ClientError as e:
            error_msg = f"Error de boto3 al enviar mensajes batch a SQS: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error inesperado al enviar mensajes batch a SQS: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    async def delete_event_messages(
        self,
        *,
        event_id: int,
        actions: Optional[List[str]] = None,
        max_iterations: int = 50,
        messages_per_request: int = 10
    ) -> int:
        """
        Elimina mensajes de la cola relacionados con un evento específico.

        Este método escanea la cola en lotes (long polling deshabilitado) y
        elimina los mensajes cuyo cuerpo contiene un campo ``action`` dentro
        del conjunto ``actions`` (si se proporciona) y cuyo ``event_id`` del
        ``event_data`` coincide con el proporcionado.

        Args:
            event_id: ID del evento a filtrar
            actions: Lista de acciones a considerar (e.g. ["create_event_chat"]).
                     Si es None se evaluarán todas
            max_iterations: Máximo de ciclos de lectura de la cola
            messages_per_request: Máximo de mensajes por solicitud receive_message

        Returns:
            int: Número de mensajes eliminados

        Note:
            SQS no permite buscar por contenido, por lo que el proceso consiste en
            recibir mensajes y eliminarlos condicionalmente. Para minimizar el
            impacto, se limita el número de iteraciones y el tamaño de cada lote.
        """
        if not self.initialized or not self.client or not self.queue_url:
            logger.warning("delete_event_messages: Cliente SQS no inicializado correctamente")
            return 0

        deleted_count = 0
        iterations = 0

        try:
            while iterations < max_iterations:
                iterations += 1

                response = self.client.receive_message(
                    QueueUrl=self.queue_url,
                    MaxNumberOfMessages=messages_per_request,
                    VisibilityTimeout=0,
                    WaitTimeSeconds=0,
                    MessageAttributeNames=['All']
                )

                messages = response.get('Messages', [])
                if not messages:
                    break  # No hay más mensajes que procesar

                for msg in messages:
                    try:
                        body = msg.get('Body', '{}')
                        data = json.loads(body)

                        # Validar si el mensaje corresponde al evento
                        event_data = data.get('event_data', {}) if isinstance(data, dict) else {}
                        matches_event = event_data.get('event_id') == event_id

                        # Validar acción si se proporcionó filtro
                        action = data.get('action') if isinstance(data, dict) else None
                        matches_action = True if actions is None else action in actions

                        if matches_event and matches_action:
                            # Eliminar el mensaje de la cola
                            self.client.delete_message(
                                QueueUrl=self.queue_url,
                                ReceiptHandle=msg['ReceiptHandle']
                            )
                            deleted_count += 1
                            logger.info(f"Mensaje {msg.get('MessageId')} eliminado (evento {event_id}, acción {action})")
                        else:
                            # Devolver la visibilidad inmediatamente (no cambiar visibility)
                            pass
                    except Exception as inner_e:
                        logger.error(f"Error analizando mensaje para eliminación condicional: {inner_e}")
                        continue

                # Si en este lote no se eliminaron mensajes, podríamos suponer que no hay más
                # pero seguimos hasta max_iterations o hasta que no haya más mensajes.

        except Exception as e:
            logger.error(f"Error al eliminar mensajes de evento {event_id}: {e}", exc_info=True)

        logger.info(f"Total de mensajes eliminados para evento {event_id}: {deleted_count}")
        return deleted_count


# Instancia única del servicio async
async_sqs_service = AsyncSQSService()
