"""
Worker para el procesamiento de tareas asíncronas en segundo plano.

Este script ejecuta un worker que escucha mensajes de Amazon SQS
y los procesa según el tipo de tarea.
"""
import os
import json
import time
import logging
import uuid
import random
from typing import Dict, Any, Optional, List
import boto3
from botocore.exceptions import ClientError
from datetime import datetime

# Configurar el logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Crear loggers específicos
logger = logging.getLogger('gym-worker')
sqs_logger = logging.getLogger('sqs-client')

# Agregar importación de handlers
from task_handlers import (
    process_create_event_chat_task,
    process_event_completion_task,
    process_schedule_event_completion_task
)

# Configuración
AWS_REGION = 'us-east-1'
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL', 'https://sqs.us-east-1.amazonaws.com/891376974297/Gym-api-queue.fifo')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
API_BASE_URL = os.getenv('API_BASE_URL', 'https://gymapi-eh6m.onrender.com/api/v1')
WORKER_API_KEY = os.getenv('WORKER_API_KEY', '')
VISIBILITY_TIMEOUT = 180  # 3 minutos para procesar el mensaje

class Worker:
    def __init__(self):
        # Inicializar cliente SQS
        try:
            self.sqs = boto3.client(
                'sqs',
                region_name=AWS_REGION,
                aws_access_key_id=AWS_ACCESS_KEY_ID,
                aws_secret_access_key=AWS_SECRET_ACCESS_KEY
            )
            logger.info("Cliente SQS inicializado correctamente")
        except Exception as e:
            logger.error(f"Error al inicializar el cliente SQS: {str(e)}")
            raise
            
        # Estado para mantener tareas para reintentar
        self.retry_tasks = []
        
    def receive_messages(self, max_messages: int = 1) -> List[Dict[str, Any]]:
        """Recibe mensajes de SQS."""
        try:
            sqs_logger.info(f"Recibiendo mensajes de SQS: {SQS_QUEUE_URL}")
            response = self.sqs.receive_message(
                QueueUrl=SQS_QUEUE_URL,
                MaxNumberOfMessages=max_messages,
                VisibilityTimeout=VISIBILITY_TIMEOUT,
                WaitTimeSeconds=20,  # Long polling
                MessageAttributeNames=['All']
            )
            
            messages = response.get('Messages', [])
            return messages
        except ClientError as e:
            sqs_logger.error(f"Error recibiendo mensajes de SQS: {e}")
            return []
        except Exception as e:
            sqs_logger.error(f"Error inesperado recibiendo mensajes: {e}")
            return []

    def delete_message(self, receipt_handle: str) -> bool:
        """Elimina un mensaje de SQS después de procesarlo."""
        try:
            logger.info(f"Eliminando mensaje con receipt handle: {receipt_handle}")
            self.sqs.delete_message(
                QueueUrl=SQS_QUEUE_URL,
                ReceiptHandle=receipt_handle
            )
            return True
        except ClientError as e:
            logger.error(f"Error eliminando mensaje de SQS: {e}")
            return False
        except Exception as e:
            logger.error(f"Error inesperado eliminando mensaje: {e}")
            return False

    def process_message(self, message: Dict[str, Any]) -> bool:
        """Procesa un mensaje de SQS."""
        try:
            message_id = message.get('MessageId')
            body = message.get('Body', '{}')
            
            # Tarea única para este procesamiento
            task_id = f"task-{int(time.time())}"
            
            # Generar un ID para tracking de la tarea
            logger.info(f"Mensaje recibido: {message}")
            
            # Parsear el body del mensaje
            try:
                data = json.loads(body)
                logger.info(f"Cuerpo del mensaje: {data}")
            except json.JSONDecodeError:
                logger.error(f"Formato JSON inválido en el mensaje: {body}")
                return False
            
            # Procesar el mensaje según su formato
            if 'action' in data:
                action = data.get('action')
                logger.info(f"Formato directo detectado: {action} con event_data")
                
                if action == 'process_event':
                    # Para compatibilidad con el formato anterior, enviamos a schedule_event_completion
                    event_data = data.get('event_data', {})
                    logger.info(f"Procesando tarea: {task_id} - Tipo: schedule_event_completion - Datos: {event_data}")
                    result = process_schedule_event_completion_task(event_data)
                elif action == 'create_event_chat':
                    # Nuevo formato para crear chat de evento
                    event_data = data.get('event_data', {})
                    logger.info(f"Procesando tarea: {task_id} - Tipo: create_event_chat - Datos: {event_data}")
                    result = process_create_event_chat_task(event_data)
                elif action == 'event_completion':
                    # Para marcar eventos como completados (de EventBridge)
                    event_data = data.get('event_data', {})
                    logger.info(f"Procesando tarea: {task_id} - Tipo: event_completion - Datos: {event_data}")
                    result = process_event_completion_task(event_data)
                else:
                    logger.warning(f"Acción {action} no reconocida")
                    result = {"success": False, "error": f"Acción no soportada: {action}"}
            else:
                # Formato desconocido
                logger.warning(f"Formato de mensaje no reconocido: {data}")
                result = {"success": False, "error": "Formato de mensaje no reconocido"}
            
            # Verificar resultado y determinar si hay que reintentar
            if not result.get('success'):
                logger.warning(f"Tarea {task_id} fallida: {result.get('error')}")
                return False
                
            logger.info(f"Tarea {task_id} completada exitosamente")
            return True
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}", exc_info=True)
            return False

    def run(self):
        """Ejecuta el worker en un bucle continuo."""
        logger.info("==== INICIANDO WORKER DE PROCESAMIENTO DE TAREAS ====")
        logger.info("Iniciando worker de procesamiento...")
        
        while True:
            try:
                # Procesar primero tareas pendientes de reintento
                if self.retry_tasks:
                    task = self.retry_tasks.pop(0)
                    attempt = task.get('attempt', 0) + 1
                    logger.info(f"Reintentando tarea {task['id']} (intento {attempt})")
                    
                    # Procesar la tarea
                    success = self.process_message(task['message'])
                    
                    if success:
                        # Si el procesamiento fue exitoso, eliminar el mensaje de SQS
                        self.delete_message(task['message']['ReceiptHandle'])
                        logger.info(f"Tarea {task['id']} completada y mensaje eliminado de la cola")
                    else:
                        # Si falló, determinar si hay que reintentar de nuevo
                        max_retries = 3
                        if attempt < max_retries:
                            # Programar para reintento
                            task['attempt'] = attempt
                            self.retry_tasks.append(task)
                            logger.info(f"Reintentando tarea {task['id']} más tarde (intento {attempt})")
                        else:
                            # Abandonar después de máximos reintentos
                            logger.warning(f"Tarea {task['id']} abandonada después de {max_retries} intentos")
                            self.delete_message(task['message']['ReceiptHandle'])
                    
                    # Continuar al siguiente ciclo
                    continue
                
                # Consultar nuevos mensajes de SQS
                logger.info("Consultando cola SQS...")
                messages = self.receive_messages()
                
                if not messages:
                    logger.info("No hay mensajes en la cola. Esperando...")
                    time.sleep(5)  # Esperar 5 segundos antes de consultar de nuevo
                    continue
                
                logger.info(f"Recibidos {len(messages)} mensajes")
                
                # Procesar cada mensaje
                for message in messages:
                    task_id = f"task-{int(time.time())}"
                    
                    # Procesar el mensaje
                    success = self.process_message(message)
                    
                    if success:
                        # Si el procesamiento fue exitoso, eliminar el mensaje de SQS
                        self.delete_message(message['ReceiptHandle'])
                        logger.info(f"Tarea {task_id} completada y mensaje eliminado de la cola")
                    else:
                        # Si falló, programar para reintento
                        self.retry_tasks.append({
                            'id': task_id,
                            'message': message,
                            'attempt': 1,
                            'timestamp': time.time()
                        })
                        logger.info(f"Reintentando tarea {task_id} más tarde (intento 1)")
                
            except KeyboardInterrupt:
                logger.info("Interrupción de teclado. Finalizando worker...")
                break
            except Exception as e:
                logger.error(f"Error inesperado en el bucle principal: {e}", exc_info=True)
                time.sleep(5)  # Esperar antes de continuar

if __name__ == "__main__":
    worker = Worker()
    worker.run() 