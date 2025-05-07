"""
Handlers para las tareas procesadas por el worker.

Este módulo contiene la lógica para los diferentes tipos de tareas
que puede procesar el worker de colas.
"""
import logging
import os
import requests
import json
from datetime import datetime, timedelta, timezone
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Configuración
API_BASE_URL = os.getenv("API_BASE_URL", "https://gymapi-eh6m.onrender.com/api/v1")
WORKER_API_KEY = os.getenv("WORKER_API_KEY", "")

def process_create_event_chat_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa una tarea para crear un chat de evento.
    
    Args:
        task_data: Datos del evento para crear el chat
        
    Returns:
        Dict con resultado del procesamiento
    """
    logger.info(f"Procesando creación de chat para evento: {task_data}")
    
    # Extraer datos necesarios
    event_id = task_data.get('event_id')
    creator_id = task_data.get('creator_id')
    gym_id = task_data.get('gym_id')
    event_title = task_data.get('event_title', '')
    first_message_chat = task_data.get('first_message_chat')
    
    # Validar datos mínimos requeridos
    if not event_id or not creator_id or not gym_id:
        error_msg = f"Faltan datos requeridos para crear chat: event_id={event_id}, creator_id={creator_id}, gym_id={gym_id}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    # Preparar datos para la solicitud
    request_data = {
        "event_id": event_id,
        "creator_id": creator_id,
        "gym_id": gym_id,
        "event_title": event_title
    }
    
    # Añadir first_message_chat al payload si se proporcionó
    if first_message_chat:
        request_data["first_message_chat"] = first_message_chat
        logger.info(f"Se incluye mensaje inicial para el chat del evento {event_id}")
    
    # Configurar headers con API key para autenticación
    headers = {
        "Content-Type": "application/json",
        "x-api-key": WORKER_API_KEY
    }
    
    # Endpoint para crear el chat
    endpoint = f"{API_BASE_URL}/worker/event-chat"
    
    # Añadir clave API a la solicitud
    logger.info("Clave API de worker añadida a la solicitud")
    
    # Enviar solicitud al endpoint
    logger.info(f"Enviando solicitud para crear chat del evento {event_id} a {endpoint}")
    try:
        response = requests.post(
            endpoint,
            json=request_data,
            headers=headers,
            timeout=30  # Timeout extendido para Render
        )
        
        # Verificar respuesta
        logger.info(f"Respuesta recibida: Status={response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                logger.info(f"Chat para evento {event_id} creado exitosamente")
                return {
                    "success": True,
                    "message": f"Chat para evento {event_id} creado",
                    "details": result.get('details')
                }
            else:
                logger.warning(f"Respuesta indica fallo: {result.get('message')}")
                return {
                    "success": False,
                    "error": result.get('message')
                }
        else:
            error_msg = f"Error HTTP {response.status_code}: {response.text}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
    except requests.RequestException as e:
        error_msg = f"Error de conexión al crear chat: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Error inesperado al crear chat: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}

def process_event_completion_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa una tarea para marcar un evento como completado.
    
    Args:
        task_data: Datos del evento a marcar como completado
        
    Returns:
        Dict con resultado del procesamiento
    """
    logger.info(f"Procesando finalización de evento: {task_data}")
    
    # Extraer datos necesarios
    event_id = task_data.get('event_id')
    gym_id = task_data.get('gym_id')
    
    # Validar datos mínimos requeridos
    if not event_id or not gym_id:
        error_msg = f"Faltan datos requeridos para completar evento: event_id={event_id}, gym_id={gym_id}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    # Preparar datos para la solicitud
    request_data = {
        "event_id": event_id,
        "gym_id": gym_id
    }
    
    # Configurar headers con API key para autenticación
    headers = {
        "Content-Type": "application/json",
        "x-api-key": WORKER_API_KEY
    }
    
    # Endpoint para marcar el evento como completado
    endpoint = f"{API_BASE_URL}/worker/event-completion"
    
    # Añadir clave API a la solicitud
    logger.info("Clave API de worker añadida a la solicitud")
    
    # Enviar solicitud al endpoint
    logger.info(f"Enviando solicitud para marcar evento {event_id} como completado a {endpoint}")
    try:
        response = requests.post(
            endpoint,
            json=request_data,
            headers=headers,
            timeout=30  # Timeout extendido para Render
        )
        
        # Verificar respuesta
        logger.info(f"Respuesta recibida: Status={response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                logger.info(f"Evento {event_id} marcado como completado correctamente")
                return {
                    "success": True,
                    "message": f"Evento {event_id} marcado como completado",
                    "details": result.get('details')
                }
            else:
                logger.warning(f"Respuesta exitosa: {result.get('message')}")
                return result
        else:
            error_msg = f"Error HTTP {response.status_code}: {response.text}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
            
    except requests.RequestException as e:
        error_msg = f"Error de conexión al marcar evento como completado: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    except Exception as e:
        error_msg = f"Error inesperado al marcar evento como completado: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"success": False, "error": error_msg}

def process_schedule_event_completion_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Procesa una tarea para programar la finalización de un evento.
    NOTA: Este método solo se usa como compatibilidad con el formato antiguo de mensajes.
    
    Args:
        task_data: Datos del evento para programar su finalización
        
    Returns:
        Dict con resultado del procesamiento
    """
    logger.info(f"Procesando programación de finalización de evento: {task_data}")
    
    # Extraer datos necesarios
    event_id = task_data.get('event_id')
    gym_id = task_data.get('gym_id')
    end_time_str = task_data.get('end_time')
    
    # Validar datos mínimos requeridos
    if not event_id or not gym_id or not end_time_str:
        error_msg = f"Faltan datos requeridos para programar finalización: event_id={event_id}, gym_id={gym_id}, end_time={end_time_str}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    # Convertir string de fecha a objeto datetime
    try:
        # Formatos posibles: '2023-04-05T12:30:00+00:00' o '2023-04-05T12:30:00.000000+00:00'
        from dateutil import parser
        end_time = parser.parse(end_time_str)
        logger.info(f"Evento {event_id} finaliza a las {end_time}")
        
        # Calcular tiempo de espera hasta la finalización
        now = datetime.now(timezone.utc)
        
        # Programar la ejecución para 1 minuto después de la hora de finalización
        execution_time = end_time + timedelta(minutes=1)
        
        # Verificar si ya pasó el tiempo de finalización
        if execution_time <= now:
            logger.info(f"El tiempo de finalización ya pasó, ejecutando inmediatamente")
            return process_event_completion_task(task_data)
        
        logger.info(f"Programando finalización para {execution_time}")
        
        # Ejecutar directamente la función para completar el evento
        # ya que el servicio de verificación se encargará de esta funcionalidad
        return process_event_completion_task(task_data)
        
    except Exception as e:
        logger.error(f"Error al programar la finalización del evento: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)} 