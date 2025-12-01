from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DBAPIError
from datetime import datetime, timedelta, timezone
from functools import wraps
import logging
import time

from app.db.session import SessionLocal
from app.services.notification_service import notification_service
from app.repositories.notification_repository import notification_repository
from app.repositories.schedule import class_repository, class_session_repository, class_participation_repository
from app.repositories.event import EventRepository
from app.models.event import Event, EventStatus
from app.models.schedule import ClassSession, ClassSessionStatus
from app.models.chat import ChatRoom, ChatRoomStatus
from app.services.user_stats import user_stats_service
from app.db.redis_client import get_redis_client

logger = logging.getLogger(__name__)
event_repository = EventRepository()

# Variable global para mantener referencia al scheduler
_scheduler = None


def retry_on_db_error(max_retries=3, delay=2):
    """
    Decorator para reintentar operaciones en caso de errores de BD.

    Útil para scheduled tasks que pueden fallar por conexiones cerradas
    por pgbouncer o timeouts transitorios.

    Args:
        max_retries: Número máximo de reintentos (default: 3)
        delay: Tiempo base de espera entre reintentos en segundos (default: 2)
               Se aplica backoff exponencial: delay * (attempt + 1)
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OperationalError, DBAPIError) as e:
                    if attempt < max_retries - 1:
                        wait_time = delay * (attempt + 1)  # Backoff exponencial
                        logger.warning(
                            f"DB error in {func.__name__}, retry {attempt + 1}/{max_retries} "
                            f"after {wait_time}s: {str(e)}"
                        )
                        time.sleep(wait_time)
                    else:
                        logger.error(
                            f"Max retries ({max_retries}) reached for {func.__name__}: {str(e)}",
                            exc_info=True
                        )
                        raise
                except Exception as e:
                    # Para otros errores, no reintentar
                    logger.error(f"Non-DB error in {func.__name__}: {str(e)}", exc_info=True)
                    raise
        return wrapper
    return decorator

@retry_on_db_error(max_retries=3, delay=2)
def send_class_reminders():
    """
    Envía recordatorios automáticos para clases que comienzan pronto
    """
    logger.info("Running scheduled task: send_class_reminders")
    db = SessionLocal()
    try:
        # Calcular ventana de tiempo para clases próximas
        # (Clases que comienzan entre 1:45 y 2:15 horas desde ahora, en UTC)
        now_utc = datetime.now(timezone.utc)
        start_window = now_utc + timedelta(hours=1, minutes=45)
        end_window = now_utc + timedelta(hours=2, minutes=15)

        # Obtener sesiones en ese rango
        upcoming_sessions = class_session_repository.get_by_date_range(
            db, start_date=start_window, end_date=end_window
        )

        logger.info(f"Found {len(upcoming_sessions)} upcoming sessions for reminders")

        for session in upcoming_sessions:
            if session.status != ClassSessionStatus.SCHEDULED:
                continue  # Ignorar sesiones canceladas

            # Obtener la clase
            class_info = class_repository.get(db, id=session.class_id)

            # Obtener participantes
            participants = class_participation_repository.get_by_session(db, session_id=session.id)
            user_ids = [p.member_id for p in participants]

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
        db.rollback()
    finally:
        db.close()

@retry_on_db_error(max_retries=3, delay=2)
def cleanup_old_tokens():
    """
    Limpia tokens viejos e inactivos de la base de datos
    """
    logger.info("Running scheduled task: cleanup_old_tokens")
    db = SessionLocal()
    try:
        count = notification_repository.cleanup_old_tokens(db, days=90)
        logger.info(f"Cleaned up {count} old device tokens")
    except Exception as e:
        logger.error(f"Error in cleanup_old_tokens task: {str(e)}", exc_info=True)
        db.rollback()
    finally:
        db.close()

@retry_on_db_error(max_retries=3, delay=2)
def mark_completed_events():
    """
    Marca como completados los eventos cuya hora de finalización ya pasó.

    Esta función se ejecuta como respaldo para asegurar que los eventos
    se marquen como completados incluso si el worker falla.
    """
    logger.info("Running scheduled task: mark_completed_events")
    db = SessionLocal()
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
        db.rollback()
    finally:
        db.close()


def precompute_user_stats():
    """
    Precalcula estadísticas de usuario en background para mejorar performance.
    
    Se ejecuta cada 6 horas para mantener caches actualizados de usuarios activos.
    """
    logger.info("Running scheduled task: precompute_user_stats")
    
    db = None
    
    try:
        # Obtener conexión a BD
        db = SessionLocal()
        
        # Obtener usuarios activos (que han tenido actividad reciente)
        from app.models.user_gym import UserGym
        from app.models.user import User
        from sqlalchemy import and_
        from datetime import datetime, timedelta
        
        # Usuarios con actividad en los últimos 7 días
        recent_activity_date = datetime.now() - timedelta(days=7)
        
        # Query optimizada para obtener usuarios activos
        active_users = db.query(User.id, UserGym.gym_id).join(
            UserGym, User.id == UserGym.user_id
        ).filter(
            and_(
                User.is_active == True,
                User.updated_at >= recent_activity_date
            )
        ).distinct().limit(50).all()  # Limitar a 50 usuarios por ejecución
        
        logger.info(f"Found {len(active_users)} active users for stats precomputation")
        
        # Por ahora solo registrar, implementación completa pendiente
        precomputed_count = 0
        for user_id, gym_id in active_users:
            try:
                # TODO: Implementar precálculo real cuando servicio esté completo
                logger.debug(f"Would precompute stats for user {user_id}, gym {gym_id}")
                precomputed_count += 1
                
            except Exception as user_error:
                logger.error(f"Error precomputing stats for user {user_id}: {user_error}")
                continue
        
        logger.info(f"Stats precomputation job completed for {precomputed_count} users")
        
    except Exception as e:
        logger.error(f"Error in precompute_user_stats: {str(e)}", exc_info=True)
    finally:
        if db:
            db.close()


def cleanup_expired_stats_cache():
    """
    Limpia caches expirados de estadísticas de usuario.
    
    Se ejecuta diariamente para mantener Redis limpio y optimizado.
    """
    logger.info("Running scheduled task: cleanup_expired_stats_cache")
    
    try:
        # TODO: Implementar limpieza de caches cuando Redis esté disponible
        # Patrones a limpiar:
        # - dashboard_summary:*
        # - comprehensive_stats:*
        # - user_stats_temp:*
        
        logger.info("Stats cache cleanup completed (placeholder)")
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_stats_cache: {str(e)}", exc_info=True)

@retry_on_db_error(max_retries=3, delay=2)
def mark_completed_sessions():
    """
    Marca como completadas las sesiones cuya hora de finalización ya pasó.
    También actualiza sesiones a IN_PROGRESS cuando están dentro del horario.

    Esta función maneja tanto datos UTC como datos naive (hora local) para
    compatibilidad durante la migración.
    """
    logger.info("Running scheduled task: mark_completed_sessions")
    db = SessionLocal()
    try:
        from sqlalchemy import and_, or_
        from sqlalchemy.exc import SQLAlchemyError

        current_utc = datetime.now(timezone.utc)

        # Query optimizada: Una sola consulta para obtener todas las sesiones activas
        sessions_to_update = db.query(ClassSession).filter(
            ClassSession.status.in_([
                ClassSessionStatus.SCHEDULED,
                ClassSessionStatus.IN_PROGRESS
            ])
        ).all()

        progress_count = 0
        completion_count = 0

        for session in sessions_to_update:
            try:
                # Manejar tanto datos UTC como naive para compatibilidad
                session_start = session.start_time
                session_end = session.end_time

                # Si los tiempos son naive (sin timezone), asumimos que son UTC
                if session_start.tzinfo is None:
                    session_start = session_start.replace(tzinfo=timezone.utc)
                if session_end.tzinfo is None:
                    session_end = session_end.replace(tzinfo=timezone.utc)

                # Ahora podemos comparar de manera segura
                if session.status == ClassSessionStatus.SCHEDULED:
                    if session_start <= current_utc < session_end:
                        # Sesión debe estar IN_PROGRESS
                        session.status = ClassSessionStatus.IN_PROGRESS
                        db.add(session)
                        progress_count += 1
                        logger.debug(f"Session {session.id} marked as IN_PROGRESS")
                    elif session_end <= current_utc:
                        # Sesión ya terminó, directamente a COMPLETED
                        session.status = ClassSessionStatus.COMPLETED
                        db.add(session)
                        completion_count += 1
                        logger.info(f"Session {session.id} marked as COMPLETED")

                elif session.status == ClassSessionStatus.IN_PROGRESS:
                    if session_end <= current_utc:
                        # Sesión IN_PROGRESS que ya terminó
                        session.status = ClassSessionStatus.COMPLETED
                        db.add(session)
                        completion_count += 1
                        logger.info(f"Session {session.id} marked as COMPLETED")

            except Exception as session_error:
                logger.error(f"Error processing session {session.id}: {session_error}")
                continue

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
    finally:
        db.close()

def init_scheduler():
    """
    Inicializa el programador de tareas
    """
    global _scheduler
    
    logger.info("Initializing scheduler with UTC timezone")
    _scheduler = AsyncIOScheduler(timezone=timezone.utc)
    
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
    
    # Precálculo de estadísticas de usuario cada 6 horas
    # Mantiene caches actualizados para usuarios activos
    _scheduler.add_job(
        precompute_user_stats,
        trigger=CronTrigger(hour='*/6', minute=30),  # Cada 6 horas a los 30 minutos
        id='user_stats_precompute',
        replace_existing=True
    )
    
    # Limpieza de caches de estadísticas diariamente
    # Mantiene Redis optimizado eliminando caches expirados
    _scheduler.add_job(
        cleanup_expired_stats_cache,
        trigger=CronTrigger(hour=3, minute=15),  # Diariamente a las 3:15 AM
        id='stats_cache_cleanup',
        replace_existing=True
    )
    
    # Iniciar el scheduler
    _scheduler.start()
    logger.info("Scheduler started with UTC timezone - includes session completion and user stats tasks")
    
    # Limpieza de canales de eventos expirados cada 12 horas
    # Elimina canales Stream de eventos que terminaron hace más de 48h
    _scheduler.add_job(
        cleanup_expired_event_channels,
        trigger=CronTrigger(hour='*/12', minute=0),  # Cada 12 horas
        id='event_channels_cleanup',
        replace_existing=True
    )

    # ============================================================================
    # JOBS DE NUTRICIÓN (Multi-gym support)
    # ============================================================================

    # Importar funciones de nutrición
    try:
        from app.services.nutrition_notification_service import (
            send_meal_reminders_all_gyms_job,
            check_live_plan_status_job,
            check_daily_achievements_job
        )

        # Recordatorios de comidas - ejecutar cada hora para TODOS los gimnasios
        # El job itera sobre todos los gyms con nutrición activa

        # Desayuno - típicamente entre 6-10 AM
        for hour in [6, 7, 8, 9, 10]:
            _scheduler.add_job(
                lambda h=hour: send_meal_reminders_all_gyms_job("breakfast", f"{h:02d}:00"),
                trigger=CronTrigger(hour=hour, minute=0),
                id=f'nutrition_breakfast_{hour:02d}00',
                replace_existing=True
            )

        # Almuerzo - típicamente entre 12-15 PM
        for hour in [12, 13, 14, 15]:
            _scheduler.add_job(
                lambda h=hour: send_meal_reminders_all_gyms_job("lunch", f"{h:02d}:00"),
                trigger=CronTrigger(hour=hour, minute=0),
                id=f'nutrition_lunch_{hour:02d}00',
                replace_existing=True
            )

        # Cena - típicamente entre 19-22 PM
        for hour in [19, 20, 21, 22]:
            _scheduler.add_job(
                lambda h=hour: send_meal_reminders_all_gyms_job("dinner", f"{h:02d}:00"),
                trigger=CronTrigger(hour=hour, minute=0),
                id=f'nutrition_dinner_{hour:02d}00',
                replace_existing=True
            )

        # Verificar estado de planes live - ejecutar diariamente a las 6 AM UTC
        _scheduler.add_job(
            check_live_plan_status_job,
            trigger=CronTrigger(hour=6, minute=0),
            id='nutrition_live_plan_status',
            replace_existing=True
        )

        # Verificar logros diarios - ejecutar a las 23:30 UTC (final del día)
        _scheduler.add_job(
            check_daily_achievements_job,
            trigger=CronTrigger(hour=23, minute=30),
            id='nutrition_daily_achievements',
            replace_existing=True
        )

        logger.info("Nutrition notification jobs added to scheduler (multi-gym enabled)")

    except ImportError as e:
        logger.warning(f"Could not import nutrition notification jobs: {e}")

    # ============================================================================
    # JOBS DE ACTIVITY FEED
    # ============================================================================
    try:
        from app.core.activity_feed_jobs import (
            update_realtime_counters,
            generate_hourly_summary,
            update_daily_rankings,
            reset_daily_counters,
            generate_motivational_burst,
            cleanup_expired_data
        )

        # Actualizar contadores cada 5 minutos
        _scheduler.add_job(
            update_realtime_counters,
            trigger=CronTrigger(minute='*/5'),
            id='activity_feed_realtime',
            replace_existing=True
        )

        # Resumen horario
        _scheduler.add_job(
            generate_hourly_summary,
            trigger=CronTrigger(minute=0),
            id='activity_feed_hourly',
            replace_existing=True
        )

        # Rankings diarios a las 23:50
        _scheduler.add_job(
            update_daily_rankings,
            trigger=CronTrigger(hour=23, minute=50),
            id='activity_feed_rankings',
            replace_existing=True
        )

        # Reset contadores diarios a las 00:05
        _scheduler.add_job(
            reset_daily_counters,
            trigger=CronTrigger(hour=0, minute=5),
            id='activity_feed_reset',
            replace_existing=True
        )

        # Mensajes motivacionales cada 30 minutos
        _scheduler.add_job(
            generate_motivational_burst,
            trigger=CronTrigger(minute='*/30'),
            id='activity_feed_motivational',
            replace_existing=True
        )

        # Limpieza cada 2 horas
        _scheduler.add_job(
            cleanup_expired_data,
            trigger=CronTrigger(hour='*/2', minute=15),
            id='activity_feed_cleanup',
            replace_existing=True
        )

        logger.info("Activity Feed jobs added to scheduler")

    except ImportError as e:
        logger.warning(f"Could not import Activity Feed jobs: {e}")

    return _scheduler


def delete_stream_channel(channel_type: str, channel_id: str) -> bool:
    """
    Elimina un canal específico de Stream Chat completamente (mensajes + canal).
    
    Args:
        channel_type: Tipo del canal (ej: 'messaging')
        channel_id: ID del canal
        
    Returns:
        True si se eliminó correctamente, False en caso contrario
    """
    try:
        from app.core.stream_client import stream_client
        channel = stream_client.channel(channel_type, channel_id)
        
        # Paso 1: Truncar el canal para eliminar todos los mensajes
        try:
            channel.truncate()
            logger.info(f"Stream channel {channel_type}:{channel_id} truncated (messages cleared)")
        except Exception as truncate_error:
            # Si truncate falla, continuar con delete (podría ser un canal vacío)
            logger.warning(f"Could not truncate {channel_type}:{channel_id}: {truncate_error}")
        
        # Paso 2: Eliminar el canal
        channel.delete()
        logger.info(f"Successfully deleted Stream channel {channel_type}:{channel_id} completely")
        return True
    except Exception as e:
        logger.error(f"Error deleting Stream channel {channel_type}:{channel_id}: {e}")
        return False


@retry_on_db_error(max_retries=3, delay=2)
def cleanup_expired_event_channels():
    """
    Elimina canales de Stream Chat para eventos que terminaron hace más de 48h.

    Esta tarea:
    1. Busca eventos con end_time > 48h atrás
    2. Encuentra sus chat_rooms asociadas con status ACTIVE
    3. Elimina los canales de Stream Chat
    4. Marca las chat_rooms como CLOSED
    """
    logger.info("Starting cleanup of expired event channels")

    db = SessionLocal()
    try:
        # Calcular fecha límite (48 horas atrás)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=48)

        # Buscar eventos finalizados hace más de 48h con chats activos
        expired_events = db.query(Event).join(ChatRoom).filter(
            Event.end_time < cutoff_time,
            ChatRoom.event_id == Event.id,
            ChatRoom.status == ChatRoomStatus.ACTIVE
        ).distinct().all()

        logger.info(f"Found {len(expired_events)} events with active chats to cleanup")

        channels_cleaned = 0
        events_processed = 0

        for event in expired_events:
            try:
                # Obtener todas las chat_rooms del evento
                chat_rooms = db.query(ChatRoom).filter(
                    ChatRoom.event_id == event.id,
                    ChatRoom.status == ChatRoomStatus.ACTIVE
                ).all()

                event_channels_cleaned = 0

                for chat_room in chat_rooms:
                    try:
                        # Eliminar canal de Stream Chat
                        success = delete_stream_channel(
                            chat_room.stream_channel_type,
                            chat_room.stream_channel_id
                        )

                        if success:
                            # Marcar como cerrada en nuestra DB
                            chat_room.status = ChatRoomStatus.CLOSED
                            chat_room.updated_at = datetime.utcnow()
                            channels_cleaned += 1
                            event_channels_cleaned += 1

                    except Exception as e:
                        logger.error(f"Failed to cleanup channel {chat_room.stream_channel_id}: {e}")

                if event_channels_cleaned > 0:
                    events_processed += 1
                    logger.info(f"Cleaned {event_channels_cleaned} channels for event '{event.title}' (ID: {event.id})")

            except Exception as e:
                logger.error(f"Error processing event {event.id}: {e}")

        db.commit()
        logger.info(f"Expired event channels cleanup completed. Events processed: {events_processed}, Channels cleaned: {channels_cleaned}")

    except Exception as e:
        logger.error(f"Error in cleanup_expired_event_channels: {e}")
        db.rollback()
    finally:
        db.close()


# Función para obtener el scheduler (útil para pruebas y otros módulos)
def get_scheduler():
    global _scheduler
    return _scheduler 
