"""
Servicio para interactuar con Amazon EventBridge.

Este módulo proporciona funcionalidades para programar eventos en Amazon EventBridge.
"""
import boto3
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from botocore.exceptions import ClientError

from app.core.config import get_settings

# Configurar logger
logger = logging.getLogger(__name__)

# Constantes para nombres de reglas
EVENT_COMPLETION_PREFIX = "event-completion-"

class EventBridgeService:
    """
    Servicio para interactuar con Amazon EventBridge.
    Proporciona métodos para programar tareas basadas en tiempo.
    """
    
    def __init__(self):
        """Inicializa el cliente de EventBridge."""
        self.initialized = False
        self.client = None
        settings = get_settings()
        
        # Bus de eventos por defecto
        self.event_bus_name = 'default'
        
        # ARN del destino SQS (cola estándar para completar eventos)
        self.sqs_target_arn = "arn:aws:sqs:us-east-1:891376974297:MarkComplete"
        
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                self.client = boto3.client(
                    'events',
                    region_name=settings.AWS_REGION,
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
                )
                self.initialized = True
                logger.info("Servicio EventBridge inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar el cliente EventBridge: {str(e)}", exc_info=True)
        else:
            logger.warning("No se pudo inicializar el servicio EventBridge: faltan credenciales")
    
    def schedule_event_completion(
        self,
        event_id: int,
        gym_id: int,
        end_time: datetime
    ) -> Dict[str, Any]:
        """
        Programa una regla en EventBridge para marcar un evento como completado cuando llegue su hora de finalización.

        Args:
            event_id: ID del evento a marcar como completado
            gym_id: ID del gimnasio al que pertenece el evento
            end_time: Fecha y hora de finalización del evento (en UTC)

        Returns:
            Dict: Resultado de la operación con información de la regla creada
        """
        if not self.initialized or not self.client:
            error_msg = "El servicio EventBridge no está inicializado correctamente"
            logger.error(error_msg)
            return {"error": error_msg}
        
        try:
            # Nombre de la regla basado en el ID del evento
            rule_name = f"{EVENT_COMPLETION_PREFIX}{event_id}"
            
            # Crear la expresión cron (EventBridge utiliza UTC)
            # Formato: minutes hours day-of-month month day-of-week year
            cron_expression = f"cron({end_time.minute} {end_time.hour} {end_time.day} {end_time.month} ? {end_time.year})"
            
            logger.info(f"Programando regla EventBridge para evento {event_id} con cron: {cron_expression}")
            
            # Crear o actualizar la regla
            rule_response = self.client.put_rule(
                Name=rule_name,
                ScheduleExpression=cron_expression,
                State='ENABLED',
                Description=f"Regla para marcar evento {event_id} como completado",
            )
            
            # Preparar el payload que se enviará al destino SQS
            event_payload = {
                "action": "event_completion",
                "event_data": {
                    "event_id": event_id,
                    "gym_id": gym_id
                }
            }
            
            # Configurar el destino (SQS - cola estándar)
            target_response = self.client.put_targets(
                Rule=rule_name,
                Targets=[
                    {
                        'Id': f'sqs-{event_id}',
                        'Arn': self.sqs_target_arn,
                        'Input': json.dumps(event_payload)
                    }
                ]
            )
            
            logger.info(f"Regla EventBridge {rule_name} creada/actualizada con éxito para evento {event_id}")
            
            return {
                "success": True,
                "rule_name": rule_name,
                "rule_arn": rule_response.get('RuleArn'),
                "cron_expression": cron_expression,
                "failed_target_count": target_response.get('FailedEntryCount', 0)
            }
            
        except ClientError as e:
            error_msg = f"Error de boto3 al programar regla en EventBridge: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error inesperado al programar regla en EventBridge: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
    
    def delete_event_completion_rule(self, event_id: int) -> Dict[str, Any]:
        """
        Elimina una regla de finalización de evento previamente programada.

        Args:
            event_id: ID del evento cuya regla se debe eliminar

        Returns:
            Dict: Resultado de la operación
        """
        if not self.initialized or not self.client:
            error_msg = "El servicio EventBridge no está inicializado correctamente"
            logger.error(error_msg)
            return {"error": error_msg}
        
        rule_name = f"{EVENT_COMPLETION_PREFIX}{event_id}"
        
        try:
            # Primero eliminamos los destinos asociados a la regla
            self.client.remove_targets(
                Rule=rule_name,
                Ids=[f'sqs-{event_id}']
            )
            
            # Luego eliminamos la regla
            self.client.delete_rule(
                Name=rule_name
            )
            
            logger.info(f"Regla EventBridge {rule_name} eliminada con éxito para evento {event_id}")
            
            return {
                "success": True,
                "rule_name": rule_name
            }
            
        except ClientError as e:
            error_msg = f"Error de boto3 al eliminar regla en EventBridge: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}
        except Exception as e:
            error_msg = f"Error inesperado al eliminar regla en EventBridge: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

# Instancia única del servicio
event_bridge_service = EventBridgeService() 