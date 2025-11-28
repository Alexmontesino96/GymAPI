"""
Activity Feed Scheduled Jobs.

Jobs programados para mantener el Activity Feed actualizado con
estadísticas agregadas y actividades periódicas.
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from typing import List
from datetime import datetime
import logging

from app.db.redis_client import get_redis_client
from app.db.session import get_db
from app.services.activity_feed_service import ActivityFeedService
from app.services.activity_aggregator import ActivityAggregator
from app.models.gym import Gym
from app.models.class_participation import ClassParticipation
from app.models.class_session import ClassSession
from sqlalchemy import and_, func
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

    Este job cuenta usuarios activos y actualiza estadísticas en tiempo real.
    """
    logger.info("Actualizando contadores en tiempo real...")

    try:
        redis = await get_redis_client()
        feed_service = ActivityFeedService(redis)

        # Obtener gimnasios activos
        db = next(get_db())
        gyms = db.query(Gym).filter(Gym.is_active == True).all()

        for gym in gyms:
            # Contar usuarios activos en las últimas 2 horas
            now = datetime.utcnow()
            two_hours_ago = now.replace(hour=now.hour-2 if now.hour >= 2 else 0)

            active_count = db.query(func.count(ClassParticipation.user_id.distinct())).join(
                ClassSession
            ).filter(
                and_(
                    ClassSession.gym_id == gym.id,
                    ClassSession.scheduled_at >= two_hours_ago,
                    ClassParticipation.attended == True
                )
            ).scalar() or 0

            if active_count >= 3:  # Solo publicar si hay suficientes personas
                await feed_service.publish_realtime_activity(
                    gym_id=gym.id,
                    activity_type="training_count",
                    count=active_count,
                    metadata={"source": "scheduled_update"}
                )

            logger.debug(f"Gym {gym.id}: {active_count} usuarios activos")

        db.close()
        logger.info("Contadores en tiempo real actualizados")

    except Exception as e:
        logger.error(f"Error actualizando contadores en tiempo real: {e}")


async def generate_hourly_summary():
    """
    Genera resumen horario de actividad para cada gimnasio.

    Crea insights basados en la actividad de la última hora.
    """
    logger.info("Generando resumen horario...")

    try:
        redis = await get_redis_client()
        feed_service = ActivityFeedService(redis)
        aggregator = ActivityAggregator(feed_service)

        db = next(get_db())
        gyms = db.query(Gym).filter(Gym.is_active == True).all()

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

        db.close()
        logger.info("Resúmenes horarios generados")

    except Exception as e:
        logger.error(f"Error generando resumen horario: {e}")


async def update_daily_rankings():
    """
    Actualiza rankings diarios anónimos.

    Calcula y actualiza los top performers del día sin exponer identidades.
    """
    logger.info("Actualizando rankings diarios...")

    try:
        redis = await get_redis_client()
        feed_service = ActivityFeedService(redis)

        db = next(get_db())
        gyms = db.query(Gym).filter(Gym.is_active == True).all()

        for gym in gyms:
            # Obtener valores de asistencia del día (solo números)
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0)

            # Query para obtener conteos de asistencia
            attendance_counts = db.query(
                func.count(ClassParticipation.id)
            ).join(ClassSession).filter(
                and_(
                    ClassSession.gym_id == gym.id,
                    ClassSession.scheduled_at >= today_start,
                    ClassParticipation.attended == True
                )
            ).group_by(ClassParticipation.user_id).all()

            # Extraer solo los valores (sin IDs de usuario)
            values = [count[0] for count in attendance_counts if count[0] > 0]

            if values:
                await feed_service.add_anonymous_ranking(
                    gym_id=gym.id,
                    ranking_type="attendance",
                    values=sorted(values, reverse=True)[:20],  # Top 20
                    period="daily"
                )

                # Publicar si hay suficiente actividad
                if len(values) >= 10:
                    top_3 = sorted(values, reverse=True)[:3]
                    await feed_service.publish_realtime_activity(
                        gym_id=gym.id,
                        activity_type="motivational",
                        count=len(values),
                        metadata={
                            "message": f"🥇 Top 3 del día: {top_3[0]}, {top_3[1]}, {top_3[2]} clases",
                            "type": "ranking_update"
                        }
                    )

            logger.debug(f"Rankings actualizados para gym {gym.id}")

        db.close()
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
        redis = await get_redis_client()

        # Obtener todos los keys diarios
        daily_keys = await redis.keys("gym:*:daily:*")

        deleted_count = 0
        for key in daily_keys:
            # No eliminar rankings, tienen su propio TTL
            if b"ranking" not in key and "ranking" not in str(key):
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
        redis = await get_redis_client()
        feed_service = ActivityFeedService(redis)
        aggregator = ActivityAggregator(feed_service)

        db = next(get_db())
        gyms = db.query(Gym).filter(Gym.is_active == True).all()

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
                await redis.lpush(feed_key, str(activity))
                await redis.ltrim(feed_key, 0, 99)
                await redis.expire(feed_key, 3600)

                logger.debug(f"Insight motivacional publicado para gym {gym.id}")

        db.close()
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
        redis = await get_redis_client()
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
        db = next(get_db())
        gym_ids = db.query(Gym.id).filter(Gym.is_active == True).all()
        db.close()
        return [gym_id[0] for gym_id in gym_ids]
    except Exception as e:
        logger.error(f"Error obteniendo gimnasios activos: {e}")
        return []