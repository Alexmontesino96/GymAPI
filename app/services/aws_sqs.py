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
    
    def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Envía un mensaje a la cola de SQS.
        
        Args:
            message: Diccionario con el mensaje a enviar
            
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
        
        try:
            # Convertir el mensaje a formato JSON
            message_body = json.dumps(message)
            
            # Enviar el mensaje a SQS
            response = self.client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
            
            logger.info(f"Mensaje enviado a SQS con MessageId: {response.get('MessageId')}")
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