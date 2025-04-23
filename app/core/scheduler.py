from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging

from app.db.session import SessionLocal
from app.services.notification_service import notification_service
from app.repositories.notification_repository import notification_repository
from app.repositories.schedule import class_repository, class_session_repository, class_participation_repository
from app.repositories.event import EventRepository
from app.models.event import EventStatus

logger = logging.getLogger(__name__)
event_repository = EventRepository()

# Variable global para mantener referencia al scheduler
_scheduler = None

def send_class_reminders():
    """
    Envía recordatorios automáticos para clases que comienzan pronto
    """
    logger.info("Running scheduled task: send_class_reminders")
    with SessionLocal() as db:
        try:
            # Calcular ventana de tiempo para clases próximas
            # (Clases que comienzan entre 1:45 y 2:15 horas desde ahora)
            start_window = datetime.now() + timedelta(hours=1, minutes=45)
            end_window = datetime.now() + timedelta(hours=2, minutes=15)
            
            # Obtener sesiones en ese rango
            upcoming_sessions = class_session_repository.get_by_date_range(
                db, start_date=start_window, end_date=end_window
            )
            
            logger.info(f"Found {len(upcoming_sessions)} upcoming sessions for reminders")
            
            for session in upcoming_sessions:
                if session.status != "scheduled":
                    continue  # Ignorar sesiones canceladas
                
                # Obtener la clase
                class_info = class_repository.get(db, id=session.class_id)
                
                # Obtener participantes
                participants = class_participation_repository.get_by_session(db, session_id=session.id)
                user_ids = [p.user_id for p in participants]
                
                if not user_ids:
                    continue
                    
                # Formatear hora
                formatted_time = session.start_time.strftime("%H:%M")
                formatted_date = session.start_time.strftime("%d/%m/%Y")
                
                # Enviar notificación
                notification_service.send_to_users(
                    user_ids=user_ids,
                    title="Tu clase comienza pronto",
                    message=f"Tu clase de {class_info.name} comienza en 2 horas, a las {formatted_time}",
                    data={
                        "type": "session_reminder",
                        "session_id": session.id,
                        "class_id": class_info.id,
                        "start_time": session.start_time.isoformat()
                    },
                    db=db
                )
        except Exception as e:
            logger.error(f"Error in send_class_reminders task: {str(e)}", exc_info=True)

def cleanup_old_tokens():
    """
    Limpia tokens viejos e inactivos de la base de datos
    """
    logger.info("Running scheduled task: cleanup_old_tokens")
    with SessionLocal() as db:
        try:
            count = notification_repository.cleanup_old_tokens(db, days=90)
            logger.info(f"Cleaned up {count} old device tokens")
        except Exception as e:
            logger.error(f"Error in cleanup_old_tokens task: {str(e)}", exc_info=True)

def mark_completed_events():
    """
    Marca como completados los eventos cuya hora de finalización ya pasó
    
    Esta función se mantiene para compatibilidad y como backup del sistema
    de programación específica por evento.
    """
    logger.info("Running scheduled task: mark_completed_events")
    with SessionLocal() as db:
        try:
            # Obtener eventos que deberían haber finalizado pero aún están como SCHEDULED
            from app.models.event import Event, EventStatus
            from sqlalchemy import and_
            
            # Consultar todos los eventos programados cuya hora de finalización ya pasó
            current_time = datetime.now(timezone.utc)
            events_to_complete = db.query(Event).filter(
                and_(
                    Event.status == EventStatus.SCHEDULED,
                    Event.end_time < current_time
                )
            ).all()
            
            logger.info(f"Found {len(events_to_complete)} events to mark as completed")
            
            completion_count = 0
            for event in events_to_complete:
                # Marcar el evento como completado
                result = event_repository.mark_event_completed(db, event_id=event.id)
                if result:
                    completion_count += 1
                    logger.info(f"Event {event.id} ({event.title}) marked as completed")
                    
                    # Cerrar la sala de chat asociada al evento
                    try:
                        from app.services.chat import chat_service
                        closed = chat_service.close_event_chat(db, event.id)
                        if closed:
                            logger.info(f"Chat room for event {event.id} successfully closed")
                        else:
                            logger.warning(f"No chat room found or failed to close for event {event.id}")
                    except Exception as chat_error:
                        logger.error(f"Error closing chat room for event {event.id}: {chat_error}", exc_info=True)
                        # No interrumpir el flujo si falla el cierre del chat
            
            logger.info(f"Successfully marked {completion_count} events as completed")
            
        except Exception as e:
            logger.error(f"Error in mark_completed_events task: {str(e)}", exc_info=True)

def mark_single_event_completed(event_id: int):
    """
    Marca un evento específico como completado.
    Esta función es llamada automáticamente por las tareas programadas específicas.
    """
    logger.info(f"Running scheduled task: mark_single_event_completed for event_id={event_id}")
    with SessionLocal() as db:
        try:
            # Verificar que el evento siga programado antes de marcarlo como completado
            from app.models.event import Event
            
            event = db.query(Event).filter(
                Event.id == event_id,
                Event.status == EventStatus.SCHEDULED
            ).first()
            
            if not event:
                logger.warning(f"Event {event_id} not found or not in SCHEDULED status. Skipping completion.")
                return
                
            # Marcar el evento como completado
            result = event_repository.mark_event_completed(db, event_id=event_id)
            if result:
                logger.info(f"Event {event_id} ({event.title}) successfully marked as completed")
                
                # Cerrar la sala de chat asociada al evento
                try:
                    from app.services.chat import chat_service
                    closed = chat_service.close_event_chat(db, event_id)
                    if closed:
                        logger.info(f"Chat room for event {event_id} successfully closed")
                    else:
                        logger.warning(f"No chat room found or failed to close for event {event_id}")
                except Exception as chat_error:
                    logger.error(f"Error closing chat room for event {event_id}: {chat_error}", exc_info=True)
                    # No interrumpir el flujo si falla el cierre del chat
            else:
                logger.warning(f"Failed to mark event {event_id} as completed")
                
        except Exception as e:
            logger.error(f"Error marking event {event_id} as completed: {str(e)}", exc_info=True)

def schedule_event_completion(event_id: int, end_time: datetime):
    """
    Programa una tarea para marcar un evento como completado en su hora de finalización.
    
    Args:
        event_id: ID del evento a marcar como completado
        end_time: Hora de finalización del evento
    """
    global _scheduler
    
    if not _scheduler:
        logger.error("Scheduler not initialized. Cannot schedule event completion.")
        return
    
    # Asegurar que end_time tenga información de zona horaria (UTC)
    if end_time.tzinfo is None:
        logger.info(f"Converting naive datetime to UTC for event {event_id}: {end_time}")
        end_time = end_time.replace(tzinfo=timezone.utc)
    
    # Generar un ID único para la tarea
    job_id = f"event_completion_{event_id}"
    
    # Verificar si ya existe una tarea para este evento y eliminarla
    existing_job = _scheduler.get_job(job_id)
    if existing_job:
        existing_job.remove()
        logger.info(f"Removed existing completion job for event {event_id}")
    
    # Crear una nueva tarea programada para la hora exacta de finalización
    _scheduler.add_job(
        mark_single_event_completed,
        trigger=DateTrigger(run_date=end_time),
        args=[event_id],
        id=job_id,
        replace_existing=True
    )
    
    logger.info(f"Scheduled event {event_id} to be marked as completed at {end_time} (UTC)")

def initialize_event_completion_tasks():
    """
    Inicializa tareas de finalización para todos los eventos programados existentes.
    Esta función se ejecuta al iniciar el sistema.
    """
    logger.info("Initializing completion tasks for existing scheduled events")
    with SessionLocal() as db:
        try:
            # Obtener todos los eventos programados cuya hora de finalización es futura
            from app.models.event import Event
            from sqlalchemy import and_
            
            current_time = datetime.now(timezone.utc)
            future_events = db.query(Event).filter(
                and_(
                    Event.status == EventStatus.SCHEDULED,
                    Event.end_time > current_time
                )
            ).all()
            
            logger.info(f"Found {len(future_events)} future events to schedule for completion")
            
            # Programar una tarea para cada evento
            for event in future_events:
                schedule_event_completion(event.id, event.end_time)
                
        except Exception as e:
            logger.error(f"Error initializing event completion tasks: {str(e)}", exc_info=True)

def init_scheduler():
    """
    Inicializa el programador de tareas
    """
    global _scheduler
    
    logger.info("Initializing scheduler with UTC timezone")
    _scheduler = BackgroundScheduler(timezone=timezone.utc)
    
    # Recordatorios de clase cada 30 minutos
    _scheduler.add_job(
        send_class_reminders,
        trigger=CronTrigger(minute='*/30'),  # Cada 30 minutos
        id='class_reminders',
        replace_existing=True
    )
    
    # Limpieza de tokens cada semana
    _scheduler.add_job(
        cleanup_old_tokens,
        trigger=CronTrigger(day_of_week=0, hour=2),  # Domingo a las 2 AM
        id='token_cleanup',
        replace_existing=True
    )
    
    # Marcar eventos como completados cada hora (como respaldo)
    # Frecuencia reducida ya que ahora usamos tareas específicas por evento
    _scheduler.add_job(
        mark_completed_events,
        trigger=CronTrigger(minute=0),  # Al inicio de cada hora
        id='event_completion_backup',
        replace_existing=True
    )
    
    # Iniciar el scheduler
    _scheduler.start()
    logger.info("Scheduler started with UTC timezone")
    
    # Programar tareas para eventos existentes
    initialize_event_completion_tasks()
    
    return _scheduler

# Función para obtener el scheduler (útil para pruebas y otros módulos)
def get_scheduler():
    global _scheduler
    return _scheduler 