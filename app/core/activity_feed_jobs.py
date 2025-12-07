"""
Activity Feed Scheduled Jobs.

Jobs programados para mantener el Activity Feed actualizado con
estadísticas agregadas y actividades periódicas.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List
from datetime import datetime, timedelta
import logging

from app.db.redis_client import get_redis_for_jobs
from app.db.session import get_async_db_for_jobs
from app.services.activity_feed_service import ActivityFeedService
from app.services.activity_aggregator import ActivityAggregator
from app.models.gym import Gym
from app.models.schedule import ClassParticipation, ClassSession, ClassParticipationStatus
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def setup_activity_feed_jobs(scheduler: AsyncIOScheduler):
    """
    Configura todos los jobs del Activity Feed.

    Args:
        scheduler: Scheduler de APScheduler
    """
    logger.info("Configurando jobs del Activity Feed...")

    # Job 1: Actualizar contadores en tiempo real cada 5 minutos
    scheduler.add_job(
        update_realtime_counters,
        'interval',
        minutes=5,
        id='activity_feed_realtime_update',
        replace_existing=True,
        max_instances=1
    )

    # Job 2: Generar resumen horario
    scheduler.add_job(
        generate_hourly_summary,
        'cron',
        minute=0,  # Al inicio de cada hora
        id='activity_feed_hourly_summary',
        replace_existing=True,
        max_instances=1
    )

    # Job 3: Actualizar rankings diarios a las 23:50
    scheduler.add_job(
        update_daily_rankings,
        'cron',
        hour=23,
        minute=50,
        id='activity_feed_daily_rankings',
        replace_existing=True,
        max_instances=1
    )

    # Job 4: Resetear contadores diarios a las 00:05
    scheduler.add_job(
        reset_daily_counters,
        'cron',
        hour=0,
        minute=5,
        id='activity_feed_reset_daily',
        replace_existing=True,
        max_instances=1
    )

    # Job 5: Generar insights motivacionales cada 30 minutos
    scheduler.add_job(
        generate_motivational_burst,
        'interval',
        minutes=30,
        id='activity_feed_motivational',
        replace_existing=True,
        max_instances=1
    )

    # Job 6: Limpieza de datos expirados cada 2 horas
    scheduler.add_job(
        cleanup_expired_data,
        'interval',
        hours=2,
        id='activity_feed_cleanup',
        replace_existing=True,
        max_instances=1
    )

    logger.info("Jobs del Activity Feed configurados exitosamente")


async def update_realtime_counters():
    """
    Actualiza contadores en tiempo real basados en actividad actual.

    Este job:
    1. Escanea check-ins de los últimos 5 minutos
    2. Cuenta usuarios activos en las últimas 2 horas
    3. Publica actividades al feed con TTL de 24 horas
    """
    logger.info("Actualizando contadores en tiempo real...")

    try:
        async with get_redis_for_jobs() as redis:
            feed_service = ActivityFeedService(redis)

            async with get_async_db_for_jobs() as db:
                # ✅ MIGRADO A ASYNC: db.query() → await db.execute(select())
                result = await db.execute(select(Gym).where(Gym.is_active == True))
                gyms = result.scalars().all()

                now = datetime.utcnow()
                five_minutes_ago = now - timedelta(minutes=5)
                two_hours_ago = now - timedelta(hours=2)

                for gym in gyms:
                    # 1. Detectar nuevos check-ins en los últimos 5 minutos
                    # ✅ MIGRADO A ASYNC: Queries con joins y aggregates
                    stmt = (
                        select(ClassSession.id, func.count(ClassParticipation.id).label('count'))
                        .join(ClassParticipation, ClassParticipation.session_id == ClassSession.id)
                        .where(
                            and_(
                                ClassSession.gym_id == gym.id,
                                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                                ClassParticipation.updated_at >= five_minutes_ago
                            )
                        )
                        .group_by(ClassSession.id)
                    )
                    result = await db.execute(stmt)
                    recent_checkins = result.all()

                    # Publicar actividad por cada clase con check-ins recientes
                    for session_id, checkin_count in recent_checkins:
                        if checkin_count >= 3:  # Umbral mínimo de privacidad
                            # Obtener nombre de la clase
                            # ✅ MIGRADO A ASYNC
                            stmt_session = select(ClassSession).where(ClassSession.id == session_id)
                            result_session = await db.execute(stmt_session)
                            session = result_session.scalar_one_or_none()

                            class_name = "Clase"
                            if session and session.class_info:
                                class_name = session.class_info.name

                            await feed_service.publish_realtime_activity(
                                gym_id=gym.id,
                                activity_type="class_checkin",
                                count=checkin_count,
                                metadata={"class_name": class_name}
                            )
                            logger.debug(f"Gym {gym.id}: {checkin_count} check-ins en {class_name}")

                    # 2. Contar total de usuarios activos (últimas 2 horas)
                    # ✅ MIGRADO A ASYNC: count distinct
                    stmt_active = (
                        select(func.count(func.distinct(ClassParticipation.member_id)))
                        .select_from(ClassParticipation)
                        .join(ClassSession)
                        .where(
                            and_(
                                ClassSession.gym_id == gym.id,
                                ClassSession.start_time >= two_hours_ago,
                                ClassParticipation.status == ClassParticipationStatus.ATTENDED
                            )
                        )
                    )
                    result_active = await db.execute(stmt_active)
                    active_count = result_active.scalar() or 0

                    # 3. Actualizar contador diario de asistencia
                    daily_attendance_key = f"gym:{gym.id}:daily:attendance"
                    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

                    # ✅ MIGRADO A ASYNC
                    stmt_today = (
                        select(func.count(ClassParticipation.id))
                        .select_from(ClassParticipation)
                        .join(ClassSession)
                        .where(
                            and_(
                                ClassSession.gym_id == gym.id,
                                ClassSession.start_time >= today_start,
                                ClassParticipation.status == ClassParticipationStatus.ATTENDED
                            )
                        )
                    )
                    result_today = await db.execute(stmt_today)
                    today_attendance = result_today.scalar() or 0

                    await redis.setex(daily_attendance_key, 86400, today_attendance)

                    # 4. Publicar total activo si hay suficientes personas
                    if active_count >= 3:
                        await feed_service.publish_realtime_activity(
                            gym_id=gym.id,
                            activity_type="training_count",
                            count=active_count,
                            metadata={"source": "scheduled_update"}
                        )

                    logger.debug(f"Gym {gym.id}: {active_count} activos, {today_attendance} hoy")

            logger.info("Contadores en tiempo real actualizados")

    except Exception as e:
        logger.error(f"Error actualizando contadores en tiempo real: {e}")
        import traceback
        logger.error(traceback.format_exc())
    # Nota: no es necesario cerrar explícitamente la sesión aquí;
    # get_async_db_for_jobs() gestiona el cierre dentro del context manager.


async def generate_hourly_summary():
    """
    Genera resumen horario de actividad para cada gimnasio.

    Crea insights basados en la actividad de la última hora.
    """
    logger.info("Generando resumen horario...")

    try:
        async with get_redis_for_jobs() as redis:
            feed_service = ActivityFeedService(redis)
            aggregator = ActivityAggregator(feed_service)

            async with get_async_db_for_jobs() as db:
                # ✅ MIGRADO A ASYNC: db.query() → await db.execute(select())
                result = await db.execute(select(Gym).where(Gym.is_active == True))
                gyms = result.scalars().all()

                for gym in gyms:
                    await aggregator.calculate_hourly_summary(gym.id)

                    # Generar insight especial si es hora pico
                    summary = await feed_service.get_realtime_summary(gym.id)

                    if summary.get("peak_time"):
                        await feed_service.publish_realtime_activity(
                            gym_id=gym.id,
                            activity_type="motivational",
                            count=summary.get("total_training", 0),
                            metadata={
                                "message": "🔥 ¡Hora pico! El gimnasio está en su máximo",
                                "is_peak": True
                            }
                        )

                logger.info("Resúmenes horarios generados")

    except Exception as e:
        logger.error(f"Error generando resumen horario: {e}")


async def update_daily_rankings():
    """
    Actualiza rankings diarios con nombres de usuarios.

    Calcula y actualiza los top performers del día mostrando nombres.
    """
    logger.info("Actualizando rankings diarios...")

    try:
        async with get_redis_for_jobs() as redis:
            feed_service = ActivityFeedService(redis)

            async with get_async_db_for_jobs() as db:
                # ✅ MIGRADO A ASYNC: db.query() → await db.execute(select())
                result = await db.execute(select(Gym).where(Gym.is_active == True))
                gyms = result.scalars().all()

                for gym in gyms:
                    # Obtener valores de asistencia del día con nombres
                    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)

                    # Query para obtener conteos de asistencia con nombres de usuario
                    from app.models.user import User

                    # ✅ MIGRADO A ASYNC: Query compleja con joins, group by, order by, limit
                    stmt = (
                        select(
                            User.id.label('user_id'),
                            User.first_name,
                            User.last_name,
                            func.count(ClassParticipation.id).label('attendance_count')
                        )
                        .join(ClassParticipation, ClassParticipation.member_id == User.id)
                        .join(ClassSession, ClassSession.id == ClassParticipation.session_id)
                        .where(
                            and_(
                                ClassSession.gym_id == gym.id,
                                ClassSession.start_time >= today_start,
                                ClassParticipation.status == ClassParticipationStatus.ATTENDED
                            )
                        )
                        .group_by(User.id, User.first_name, User.last_name)
                        .order_by(func.count(ClassParticipation.id).desc())
                        .limit(20)
                    )
                    result_attendance = await db.execute(stmt)
                    attendance_data = result_attendance.all()

                    if attendance_data:
                        # Guardar ranking con nombres y user_id para foto de perfil
                        await feed_service.add_named_ranking(
                            gym_id=gym.id,
                            ranking_type="attendance",
                            entries=[
                                {
                                    "user_id": row.user_id,
                                    "name": f"{row.first_name} {row.last_name[0]}." if row.last_name else row.first_name,
                                    "value": row.attendance_count
                                }
                                for row in attendance_data
                            ],
                            period="daily"
                        )

                        # Publicar si hay suficiente actividad
                        if len(attendance_data) >= 3:
                            top_3_names = [f"{row.first_name}" for row in attendance_data[:3]]
                            await feed_service.publish_realtime_activity(
                                gym_id=gym.id,
                                activity_type="motivational",
                                count=len(attendance_data),
                                metadata={
                                    "message": f"🥇 Top 3 del día: {', '.join(top_3_names)}",
                                    "type": "ranking_update"
                                }
                            )

                    logger.debug(f"Rankings actualizados para gym {gym.id}")

                logger.info("Rankings diarios actualizados")

    except Exception as e:
        logger.error(f"Error actualizando rankings: {e}")


async def reset_daily_counters():
    """
    Resetea contadores diarios al inicio del día.

    Limpia estadísticas del día anterior y prepara para el nuevo día.
    """
    logger.info("Reseteando contadores diarios...")

    try:
        async with get_redis_for_jobs() as redis:
            # Obtener todos los keys diarios
            daily_keys = await redis.keys("gym:*:daily:*")

            deleted_count = 0
            for key in daily_keys:
                # Normalizar key a string
                key_str = key.decode() if isinstance(key, bytes) else key

                # No eliminar rankings, tienen su propio TTL
                if "ranking" not in key_str:
                    await redis.delete(key)
                    deleted_count += 1

            logger.info(f"Contadores diarios reseteados: {deleted_count} keys eliminados")

    except Exception as e:
        logger.error(f"Error reseteando contadores diarios: {e}")


async def generate_motivational_burst():
    """
    Genera ráfaga de mensajes motivacionales basados en actividad.

    Crea mensajes dinámicos para mantener el engagement.
    """
    logger.info("Generando burst motivacional...")

    try:
        async with get_redis_for_jobs() as redis:
            feed_service = ActivityFeedService(redis)
            aggregator = ActivityAggregator(feed_service)

            async with get_async_db_for_jobs() as db:
                # ✅ MIGRADO A ASYNC: db.query() → await db.execute(select())
                result = await db.execute(select(Gym).where(Gym.is_active == True))
                gyms = result.scalars().all()

                for gym in gyms:
                    # Obtener insights motivacionales
                    insights = await feed_service.generate_motivational_insights(gym.id)

                    # Publicar el más relevante si hay actividad
                    if insights and len(insights) > 0:
                        top_insight = insights[0]

                        activity = {
                            "type": "motivational",
                            "message": top_insight.get("message"),
                            "timestamp": datetime.utcnow().isoformat(),
                            "icon": "💫",
                            "priority": top_insight.get("priority", 3)
                        }

                        feed_key = f"gym:{gym.id}:feed:activities"
                        import json
                        await redis.lpush(feed_key, json.dumps(activity))
                        await redis.ltrim(feed_key, 0, 99)
                        await redis.expire(feed_key, 86400)

                        logger.debug(f"Insight motivacional publicado para gym {gym.id}")

                logger.info("Burst motivacional completado")

    except Exception as e:
        logger.error(f"Error generando burst motivacional: {e}")


async def cleanup_expired_data():
    """
    Limpia datos expirados y genera reporte de uso de memoria.

    Aunque Redis maneja TTL automáticamente, este job monitorea el estado.
    """
    logger.info("Ejecutando limpieza de datos...")

    try:
        async with get_redis_for_jobs() as redis:
            feed_service = ActivityFeedService(redis)

            # Obtener estadísticas de memoria antes de limpieza
            info_before = await redis.info("memory")
            memory_before = info_before.get("used_memory_human", "unknown")

            # Contar keys por tipo
            feed_keys = await redis.keys("gym:*:feed:*")
            realtime_keys = await redis.keys("gym:*:realtime:*")
            daily_keys = await redis.keys("gym:*:daily:*")
            ranking_keys = await redis.keys("gym:*:rankings:*")

            stats = {
                "feed_keys": len(feed_keys),
                "realtime_keys": len(realtime_keys),
                "daily_keys": len(daily_keys),
                "ranking_keys": len(ranking_keys),
                "total_keys": len(feed_keys) + len(realtime_keys) + len(daily_keys) + len(ranking_keys),
                "memory_before": memory_before
            }

            # Verificar keys sin TTL y establecer TTL por seguridad
            keys_without_ttl = 0
            for pattern in ["gym:*:feed:*", "gym:*:realtime:*", "gym:*:daily:*"]:
                keys = await redis.keys(pattern)
                for key in keys:
                    ttl = await redis.ttl(key)
                    if ttl == -1:  # Sin TTL
                        await redis.expire(key, 86400)  # 24 horas por defecto
                        keys_without_ttl += 1

            # Obtener estadísticas después
            info_after = await redis.info("memory")
            memory_after = info_after.get("used_memory_human", "unknown")

            stats["memory_after"] = memory_after
            stats["keys_without_ttl_fixed"] = keys_without_ttl

            logger.info(f"Limpieza completada - Stats: {stats}")

            # Si el uso de memoria es muy alto, alertar
            memory_mb = float(info_after.get("used_memory", 0)) / 1024 / 1024
            if memory_mb > 100:  # Más de 100MB
                logger.warning(f"Alto uso de memoria en Activity Feed: {memory_mb:.2f} MB")

    except Exception as e:
        logger.error(f"Error en limpieza de datos: {e}")


async def get_active_gyms() -> List[int]:
    """
    Obtiene lista de gimnasios activos.

    Returns:
        Lista de IDs de gimnasios activos
    """
    try:
        async with get_async_db_for_jobs() as db:
            # ✅ MIGRADO A ASYNC: db.query() → await db.execute(select())
            result = await db.execute(select(Gym.id).where(Gym.is_active == True))
            gym_ids = result.all()
            return [gym_id[0] for gym_id in gym_ids]
    except Exception as e:
        logger.error(f"Error obteniendo gimnasios activos: {e}")
        return []
