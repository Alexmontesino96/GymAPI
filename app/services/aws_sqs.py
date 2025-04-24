"""
Servicio para interactuar con Amazon SQS.

Este módulo proporciona funcionalidades para publicar mensajes en colas de SQS.
"""
import boto3
import json
import logging
from typing import Dict, Any, List, Optional, Union
from botocore.exceptions import ClientError

from app.core.config import get_settings

# Configurar logger
logger = logging.getLogger(__name__)

class SQSService:
    """
    Servicio para interactuar con Amazon SQS (Simple Queue Service).
    Proporciona métodos para enviar mensajes a una cola de SQS.
    """
    
    def __init__(self):
        """Inicializa el cliente de SQS."""
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
                logger.info("Servicio SQS inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar el cliente SQS: {str(e)}", exc_info=True)
        else:
            logger.warning("No se pudo inicializar el servicio SQS: faltan credenciales o URL de cola")
    
    def send_message(
        self,
        message_body: str,
        message_attributes: Optional[Dict[str, Dict[str, Any]]] = None,
        delay_seconds: int = 0,
        message_group_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Envía un mensaje a la cola SQS configurada.

        Args:
            message_body: El cuerpo del mensaje (string).
            message_attributes: Atributos del mensaje (opcional).
            delay_seconds: Retraso en segundos para la entrega del mensaje (opcional).
            message_group_id: El ID del grupo de mensajes, REQUERIDO para colas FIFO.

        Returns:
            Dict: La respuesta de SQS si tiene éxito.

        Raises:
            SQSError: Si ocurre un error al enviar el mensaje.
            ValueError: Si message_group_id es None y la cola es FIFO.
        """
        if not self.client or not self.queue_url:
            raise SQSError("Cliente SQS o URL de la cola no configurados.")

        # Validar si se necesita MessageGroupId (para colas FIFO)
        is_fifo = self.queue_url.endswith('.fifo')
        if is_fifo and message_group_id is None:
            logger.error("Error: MessageGroupId es requerido para colas FIFO pero no se proporcionó.")
            # Puedes lanzar un error o asignar un valor por defecto si tiene sentido
            # Por ahora, lanzaremos un error para asegurar que se corrija en el origen
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
    
    def send_batch_messages(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Envía múltiples mensajes a la cola de SQS en una sola operación.
        
        Args:
            messages: Lista de diccionarios con los mensajes a enviar
            
        Returns:
            Respuesta de SQS o diccionario con error
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

# Instancia única del servicio
sqs_service = SQSService() 