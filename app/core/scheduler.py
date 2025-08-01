from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging

from app.db.session import SessionLocal
from app.services.notification_service import notification_service
from app.repositories.notification_repository import notification_repository
from app.repositories.schedule import class_repository, class_session_repository, class_participation_repository
from app.repositories.event import EventRepository
from app.models.event import EventStatus
from app.models.schedule import ClassSession, ClassSessionStatus

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
    Marca como completados los eventos cuya hora de finalización ya pasó.
    
    Esta función se ejecuta como respaldo para asegurar que los eventos
    se marquen como completados incluso si el worker falla.
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

def mark_completed_sessions():
    """
    Marca como completadas las sesiones cuya hora de finalización ya pasó.
    También actualiza sesiones a IN_PROGRESS cuando están dentro del horario.
    
    Esta función se ejecuta cada 15 minutos para mantener estados actualizados
    y proporcionar mejor experiencia de usuario.
    """
    logger.info("Running scheduled task: mark_completed_sessions")
    with SessionLocal() as db:
        try:
            from sqlalchemy import and_, or_
            from sqlalchemy.exc import SQLAlchemyError
            
            current_time = datetime.now(timezone.utc)
            
            # 1. Marcar sesiones como IN_PROGRESS
            # (Sesiones que ya empezaron pero aún no terminan)
            sessions_in_progress = db.query(ClassSession).filter(
                and_(
                    ClassSession.status == ClassSessionStatus.SCHEDULED,
                    ClassSession.start_time <= current_time,
                    ClassSession.end_time > current_time
                )
            ).all()
            
            progress_count = 0
            for session in sessions_in_progress:
                session.status = ClassSessionStatus.IN_PROGRESS
                db.add(session)
                progress_count += 1
                logger.debug(f"Session {session.id} marked as IN_PROGRESS")
            
            # 2. Marcar sesiones como COMPLETED
            # (Sesiones cuya hora de finalización ya pasó)
            sessions_to_complete = db.query(ClassSession).filter(
                and_(
                    or_(
                        ClassSession.status == ClassSessionStatus.SCHEDULED,
                        ClassSession.status == ClassSessionStatus.IN_PROGRESS
                    ),
                    ClassSession.end_time <= current_time
                )
            ).all()
            
            completion_count = 0
            for session in sessions_to_complete:
                session.status = ClassSessionStatus.COMPLETED
                db.add(session)
                completion_count += 1
                logger.info(f"Session {session.id} marked as completed")
            
            # Confirmar cambios si hay actualizaciones
            if progress_count > 0 or completion_count > 0:
                db.commit()
                logger.info(f"Session status updates: {progress_count} to IN_PROGRESS, {completion_count} to COMPLETED")
            else:
                logger.debug("No sessions needed status updates")
                
        except SQLAlchemyError as e:
            logger.error(f"SQLAlchemy error in mark_completed_sessions task: {str(e)}", exc_info=True)
            db.rollback()
        except Exception as e:
            logger.error(f"Error in mark_completed_sessions task: {str(e)}", exc_info=True)
            db.rollback()

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
    # Esta tarea ahora funciona como respaldo del worker
    _scheduler.add_job(
        mark_completed_events,
        trigger=CronTrigger(minute=0),  # Al inicio de cada hora
        id='event_completion_backup',
        replace_existing=True
    )
    
    # Marcar sesiones como completadas cada 15 minutos
    # Ejecuta más frecuentemente que eventos para mejor UX
    _scheduler.add_job(
        mark_completed_sessions,
        trigger=CronTrigger(minute='*/15'),  # Cada 15 minutos
        id='session_completion',
        replace_existing=True
    )
    
    # Iniciar el scheduler
    _scheduler.start()
    logger.info("Scheduler started with UTC timezone - includes session completion task")
    
    return _scheduler

# Función para obtener el scheduler (útil para pruebas y otros módulos)
def get_scheduler():
    global _scheduler
    return _scheduler 