from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import logging

from app.db.session import SessionLocal
from app.services.notification_service import notification_service
from app.repositories.notification_repository import notification_repository
from app.repositories.schedule import class_repository, class_session_repository, class_participation_repository

logger = logging.getLogger(__name__)

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

def init_scheduler():
    """
    Inicializa el programador de tareas
    """
    logger.info("Initializing scheduler")
    scheduler = BackgroundScheduler()
    
    # Recordatorios de clase cada 30 minutos
    scheduler.add_job(
        send_class_reminders,
        trigger=CronTrigger(minute='*/30'),  # Cada 30 minutos
        id='class_reminders',
        replace_existing=True
    )
    
    # Limpieza de tokens cada semana
    scheduler.add_job(
        cleanup_old_tokens,
        trigger=CronTrigger(day_of_week=0, hour=2),  # Domingo a las 2 AM
        id='token_cleanup',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Scheduler started")
    
    return scheduler 