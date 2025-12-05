"""
AsyncOptimizedNutritionNotificationService - Servicio async optimizado para notificaciones.

Versión async optimizada con mejoras de rendimiento, seguridad y escalabilidad:
- Batch processing de notificaciones
- Cache Redis para configuraciones
- Métricas y analytics en tiempo real
- Soporte multi-tenant completo

Migrado en FASE 3 de la conversión sync → async.
"""

from datetime import datetime, date, timedelta, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
import logging
import json
import asyncio

from app.models.nutrition import (
    NutritionPlan,
    NutritionPlanFollower,
    DailyNutritionPlan,
    Meal,
    PlanType
)
from app.services.async_notification_service import async_notification_service
from app.db.redis_client import get_redis_client

logger = logging.getLogger("async_nutrition_notification_optimized")


class AsyncOptimizedNutritionNotificationService:
    """
    Servicio async optimizado de notificaciones para nutrición.

    Todos los métodos son async y utilizan AsyncSession.

    Funcionalidades:
    - Batch processing de recordatorios (lotes de 50)
    - Cache Redis para usuarios y configuraciones (TTL 5min)
    - Métricas en tiempo real guardadas en Redis
    - Analytics de notificaciones (últimos N días)
    - Cálculo optimizado de día actual según tipo de plan
    - Integración con AsyncOneSignalService

    Métodos principales:
    - send_batch_meal_reminders() - Envío batch con cache
    - track_notification_metrics() - Tracking en Redis
    - get_notification_analytics() - Analytics por gym

    Note:
        - Batch size: 50 usuarios
        - Cache TTL: 5 minutos
        - Métricas TTL: 30 días
        - Pausa de 0.1s entre batches
    """

    def __init__(self):
        """
        Inicializa el servicio optimizado.

        Note:
            - notification_service es async (AsyncOneSignalService)
            - Redis client es lazy-loaded
            - Batch size y cache TTL configurables
        """
        self.notification_service = async_notification_service
        self.redis = None
        self.batch_size = 50  # Enviar notificaciones en lotes de 50
        self.cache_ttl = 300  # 5 minutos de TTL para cache

    async def _get_redis(self):
        """
        Obtener cliente Redis de forma lazy async.

        Returns:
            Redis client o None si no está disponible
        """
        if self.redis is None:
            self.redis = await get_redis_client()
        return self.redis

    async def send_batch_meal_reminders(
        self,
        db: AsyncSession,
        gym_id: int,
        meal_type: str,
        scheduled_time: str
    ) -> Dict[str, Any]:
        """
        Enviar recordatorios de comida en batch para mejor rendimiento.

        Optimizaciones:
        - Procesa usuarios en lotes de 50
        - Usa cache Redis para configuraciones (TTL 5min)
        - Limita queries a la BD con joins optimizados
        - Pausa de 0.1s entre batches para no sobrecargar
        - Guarda métricas en Redis para dashboard

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            meal_type: Tipo de comida (breakfast, lunch, dinner)
            scheduled_time: Hora programada (formato "HH:MM")

        Returns:
            Dict con estadísticas:
            - total_users: Total de usuarios procesados
            - batches_processed: Número de batches
            - notifications_sent: Notificaciones enviadas exitosamente
            - cache_hits: Si se usó cache
            - errors: Contador de errores
            - processing_time_ms: Tiempo de procesamiento

        Note:
            - Cache key: nutrition:reminders:{gym_id}:{meal_type}:{time}
            - Batch size: 50
            - Métricas guardadas por 7 días
        """
        stats = {
            "total_users": 0,
            "batches_processed": 0,
            "notifications_sent": 0,
            "cache_hits": 0,
            "errors": 0,
            "processing_time_ms": 0
        }

        start_time = datetime.now(timezone.utc)

        try:
            # Intentar obtener usuarios de cache
            redis = await self._get_redis()
            cache_key = f"nutrition:reminders:{gym_id}:{meal_type}:{scheduled_time}"

            cached_users = None
            if redis:
                try:
                    cached_data = await redis.get(cache_key)
                    if cached_data:
                        cached_users = json.loads(cached_data)
                        stats["cache_hits"] = 1
                        logger.info(f"Cache hit for {cache_key}")
                except Exception as e:
                    logger.warning(f"Redis cache error: {e}")

            # Si no hay cache, consultar BD (async)
            if not cached_users:
                users_data = await self._get_users_for_reminder(
                    db, gym_id, meal_type, scheduled_time
                )

                # Guardar en cache para próximas ejecuciones
                if redis and users_data:
                    try:
                        await redis.setex(
                            cache_key,
                            self.cache_ttl,
                            json.dumps(users_data)
                        )
                    except Exception as e:
                        logger.warning(f"Failed to cache users data: {e}")
            else:
                users_data = cached_users

            stats["total_users"] = len(users_data)

            # Procesar en batches
            for i in range(0, len(users_data), self.batch_size):
                batch = users_data[i:i + self.batch_size]
                stats["batches_processed"] += 1

                # Preparar notificaciones del batch
                notifications = []
                for user_data in batch:
                    notifications.append({
                        "user_id": str(user_data["user_id"]),
                        "title": f"{user_data['emoji']} Hora de tu {user_data['meal_text']}",
                        "message": f"{user_data['meal_name']} - {user_data['plan_title']}",
                        "data": {
                            "type": "meal_reminder",
                            "meal_type": meal_type,
                            "plan_id": user_data["plan_id"],
                            "meal_id": user_data["meal_id"]
                        }
                    })

                # Enviar batch de notificaciones (async)
                if notifications:
                    success_count = await self._send_batch_notifications(
                        notifications, db
                    )
                    stats["notifications_sent"] += success_count

                # Pequeña pausa entre batches para no sobrecargar
                if i + self.batch_size < len(users_data):
                    await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in batch meal reminders: {str(e)}", exc_info=True)
            stats["errors"] += 1

        # Calcular tiempo de procesamiento
        processing_time = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
        stats["processing_time_ms"] = round(processing_time, 2)

        # Log métricas
        logger.info(
            f"Batch reminders completed: {stats['notifications_sent']}/{stats['total_users']} "
            f"sent in {stats['processing_time_ms']}ms ({stats['batches_processed']} batches)"
        )

        # Guardar métricas en Redis para dashboard
        if redis:
            try:
                metrics_key = f"nutrition:metrics:{gym_id}:{datetime.now(timezone.utc).strftime('%Y%m%d')}"
                await redis.hincrby(metrics_key, f"reminders_{meal_type}", stats["notifications_sent"])
                await redis.expire(metrics_key, 86400 * 7)  # 7 días
            except Exception as e:
                logger.warning(f"Failed to save metrics: {e}")

        return stats

    async def _send_batch_notifications(
        self,
        notifications: List[Dict],
        db: AsyncSession
    ) -> int:
        """
        Enviar un batch de notificaciones de forma eficiente async.

        Args:
            notifications: Lista de dicts con user_id, title, message, data
            db: Sesión async de BD (para actualizar tokens)

        Returns:
            int: Número de notificaciones enviadas exitosamente

        Note:
            - Usa send_to_users de AsyncOneSignalService
            - OneSignal soporta envío a múltiples usuarios en un solo request
        """
        try:
            # Extraer todos los user_ids
            user_ids = [n["user_id"] for n in notifications]

            # OneSignal soporta envío a múltiples usuarios (async)
            result = await self.notification_service.send_to_users(
                user_ids=user_ids,
                title=notifications[0]["title"],  # Asumiendo mismo título
                message="Revisa tu plan nutricional",  # Mensaje genérico
                data={
                    "type": "meal_reminder_batch",
                    "count": len(notifications)
                },
                db=db
            )

            if result.get("success"):
                return len(user_ids)
            return 0

        except Exception as e:
            logger.error(f"Error sending batch notifications: {e}", exc_info=True)
            return 0

    async def _get_users_for_reminder(
        self,
        db: AsyncSession,
        gym_id: int,
        meal_type: str,
        scheduled_time: str
    ) -> List[Dict]:
        """
        Obtener usuarios que necesitan recordatorio con query optimizada async.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            meal_type: Tipo de comida (breakfast, lunch, dinner)
            scheduled_time: Hora programada (formato "HH:MM")

        Returns:
            List[Dict] con datos de usuarios y sus comidas:
            - user_id, plan_id, plan_title, meal_id, meal_name
            - meal_text, emoji, current_day

        Note:
            - Query optimizada con todos los JOINs necesarios en una sola consulta
            - Filtra por gym_id, is_active, notifications_enabled
            - Calcula día actual según tipo de plan
        """
        users_data = []

        try:
            # Mapear tipo de comida a campo de horario
            time_field_map = {
                "breakfast": NutritionPlanFollower.notification_time_breakfast,
                "lunch": NutritionPlanFollower.notification_time_lunch,
                "dinner": NutritionPlanFollower.notification_time_dinner
            }

            time_field = time_field_map.get(meal_type)
            if not time_field:
                return users_data

            # Query optimizada con todos los JOINs necesarios (async)
            query = (
                select(
                    NutritionPlanFollower.user_id,
                    NutritionPlanFollower.start_date,
                    NutritionPlan.id.label("plan_id"),
                    NutritionPlan.title.label("plan_title"),
                    NutritionPlan.plan_type,
                    NutritionPlan.duration_days,
                    NutritionPlan.is_recurring,
                    NutritionPlan.live_start_date,
                    DailyNutritionPlan.day_number,
                    Meal.id.label("meal_id"),
                    Meal.name.label("meal_name")
                )
                .join(NutritionPlan)
                .outerjoin(
                    DailyNutritionPlan,
                    NutritionPlan.id == DailyNutritionPlan.nutrition_plan_id
                )
                .outerjoin(
                    Meal,
                    and_(
                        Meal.daily_plan_id == DailyNutritionPlan.id,
                        Meal.meal_type == meal_type
                    )
                )
                .filter(
                    and_(
                        NutritionPlan.gym_id == gym_id,
                        NutritionPlan.is_active == True,
                        NutritionPlanFollower.is_active == True,
                        NutritionPlanFollower.notifications_enabled == True,
                        time_field == scheduled_time
                    )
                )
            )

            result = await db.execute(query)
            results = result.all()

            # Mapeo de emojis y textos
            meal_emojis = {
                "breakfast": "🌅",
                "mid_morning": "🥤",
                "lunch": "🍽️",
                "afternoon": "☕",
                "dinner": "🌙",
                "post_workout": "💪",
                "late_snack": "🍿"
            }

            meal_texts = {
                "breakfast": "desayuno",
                "mid_morning": "snack de media mañana",
                "lunch": "almuerzo",
                "afternoon": "merienda",
                "dinner": "cena",
                "post_workout": "comida post-entreno",
                "late_snack": "snack nocturno"
            }

            # Procesar resultados
            for row in results:
                # Calcular día actual según tipo de plan
                current_day = self._calculate_current_day_optimized(
                    plan_type=row.plan_type,
                    duration_days=row.duration_days,
                    is_recurring=row.is_recurring,
                    user_start_date=row.start_date,
                    live_start_date=row.live_start_date
                )

                # Solo agregar si el día coincide y hay comida
                if current_day > 0 and row.day_number == current_day and row.meal_id:
                    users_data.append({
                        "user_id": row.user_id,
                        "plan_id": row.plan_id,
                        "plan_title": row.plan_title,
                        "meal_id": row.meal_id,
                        "meal_name": row.meal_name,
                        "meal_text": meal_texts.get(meal_type, "comida"),
                        "emoji": meal_emojis.get(meal_type, "🍽️"),
                        "current_day": current_day
                    })

        except Exception as e:
            logger.error(f"Error getting users for reminder: {e}", exc_info=True)

        return users_data

    def _calculate_current_day_optimized(
        self,
        plan_type: str,
        duration_days: int,
        is_recurring: bool,
        user_start_date: Optional[datetime],
        live_start_date: Optional[datetime]
    ) -> int:
        """
        Versión optimizada del cálculo de día actual según tipo de plan.

        Args:
            plan_type: Tipo de plan (TEMPLATE, LIVE, ARCHIVED)
            duration_days: Duración total del plan
            is_recurring: Si el plan se repite cíclicamente
            user_start_date: Fecha de inicio del usuario
            live_start_date: Fecha de inicio del plan live

        Returns:
            int: Día actual del plan (1-based) o 0 si plan terminado/no iniciado

        Note:
            - TEMPLATE/ARCHIVED: Usa user_start_date
            - LIVE: Usa live_start_date
            - Recurring: Usa módulo para ciclos infinitos
            - No recurring: Retorna 0 si plan terminó
        """
        today = date.today()

        if plan_type in [PlanType.TEMPLATE, PlanType.ARCHIVED]:
            if not user_start_date:
                return 0

            days_since_start = (today - user_start_date.date()).days

            if is_recurring:
                return (days_since_start % duration_days) + 1
            else:
                if days_since_start >= duration_days:
                    return 0
                return days_since_start + 1

        elif plan_type == PlanType.LIVE:
            if not live_start_date:
                return 0

            plan_start_date = live_start_date.date()

            if today < plan_start_date:
                return 0

            days_since_start = (today - plan_start_date).days

            if is_recurring:
                return (days_since_start % duration_days) + 1
            else:
                if days_since_start >= duration_days:
                    return 0
                return days_since_start + 1

        return 0

    async def track_notification_metrics(
        self,
        gym_id: int,
        notification_type: str,
        success: bool
    ):
        """
        Trackear métricas de notificaciones para análisis async.

        Args:
            gym_id: ID del gimnasio
            notification_type: Tipo de notificación (ej: meal_reminder_breakfast)
            success: Si la notificación fue exitosa

        Note:
            - Guarda métricas en Redis con TTL 30 días
            - Formato clave: nutrition:metrics:{gym_id}:{YYYYMMDD}
            - Campos: {type}_sent, {type}_failed, {type}_last
        """
        redis = await self._get_redis()
        if not redis:
            return

        try:
            # Clave de métricas diarias
            today = datetime.now(timezone.utc).strftime("%Y%m%d")
            metrics_key = f"nutrition:metrics:{gym_id}:{today}"

            # Incrementar contadores (async)
            if success:
                await redis.hincrby(metrics_key, f"{notification_type}_sent", 1)
            else:
                await redis.hincrby(metrics_key, f"{notification_type}_failed", 1)

            # Agregar timestamp de última notificación
            await redis.hset(
                metrics_key,
                f"{notification_type}_last",
                datetime.now(timezone.utc).isoformat()
            )

            # TTL de 30 días para métricas
            await redis.expire(metrics_key, 86400 * 30)

        except Exception as e:
            logger.warning(f"Failed to track metrics: {e}")

    async def get_notification_analytics(
        self,
        gym_id: int,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        Obtener analytics de notificaciones de los últimos N días async.

        Args:
            gym_id: ID del gimnasio
            days: Número de días hacia atrás (default: 7)

        Returns:
            Dict con analytics:
            - total_sent: Total de notificaciones enviadas
            - total_failed: Total de notificaciones fallidas
            - by_type: Dict con stats por tipo de notificación
            - daily_trend: Lista de stats por día con success_rate

        Note:
            - Itera sobre últimos N días
            - Agrega stats por tipo de notificación
            - Calcula success_rate por día
        """
        redis = await self._get_redis()
        if not redis:
            return {}

        analytics = {
            "total_sent": 0,
            "total_failed": 0,
            "by_type": {},
            "daily_trend": []
        }

        try:
            for i in range(days):
                date_str = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y%m%d")
                metrics_key = f"nutrition:metrics:{gym_id}:{date_str}"

                daily_data = await redis.hgetall(metrics_key)
                if daily_data:
                    daily_sent = 0
                    daily_failed = 0

                    for key, value in daily_data.items():
                        key_str = key.decode() if isinstance(key, bytes) else key
                        value_int = int(value.decode() if isinstance(value, bytes) else value) if not key_str.endswith("_last") else 0

                        if key_str.endswith("_sent"):
                            daily_sent += value_int
                            notification_type = key_str.replace("_sent", "")
                            if notification_type not in analytics["by_type"]:
                                analytics["by_type"][notification_type] = {"sent": 0, "failed": 0}
                            analytics["by_type"][notification_type]["sent"] += value_int

                        elif key_str.endswith("_failed"):
                            daily_failed += value_int
                            notification_type = key_str.replace("_failed", "")
                            if notification_type not in analytics["by_type"]:
                                analytics["by_type"][notification_type] = {"sent": 0, "failed": 0}
                            analytics["by_type"][notification_type]["failed"] += value_int

                    analytics["total_sent"] += daily_sent
                    analytics["total_failed"] += daily_failed

                    analytics["daily_trend"].append({
                        "date": date_str,
                        "sent": daily_sent,
                        "failed": daily_failed,
                        "success_rate": round(daily_sent / (daily_sent + daily_failed) * 100, 2) if (daily_sent + daily_failed) > 0 else 0
                    })

        except Exception as e:
            logger.error(f"Error getting notification analytics: {e}", exc_info=True)

        return analytics


# Función optimizada async para usar con APScheduler
async def send_meal_reminders_job_optimized(gym_id: int, meal_type: str, scheduled_time: str):
    """
    Job optimizado async para enviar recordatorios de comidas.

    Usa batching, cache y métricas para máximo rendimiento.

    Args:
        gym_id: ID del gimnasio
        meal_type: Tipo de comida (breakfast, lunch, dinner)
        scheduled_time: Hora programada (formato "HH:MM")

    Returns:
        Dict con estadísticas del job

    Note:
        - Usa AsyncSessionLocal para sesión async
        - Trackea métricas automáticamente
        - Cierra sesión en finally
    """
    from app.db.session import AsyncSessionLocal

    logger.info(f"Running optimized async meal reminder job for gym {gym_id}, {meal_type} at {scheduled_time}")

    async with AsyncSessionLocal() as db:
        try:
            service = AsyncOptimizedNutritionNotificationService()

            # Enviar recordatorios en batch (async)
            stats = await service.send_batch_meal_reminders(
                db=db,
                gym_id=gym_id,
                meal_type=meal_type,
                scheduled_time=scheduled_time
            )

            # Trackear métricas (async)
            await service.track_notification_metrics(
                gym_id=gym_id,
                notification_type=f"meal_reminder_{meal_type}",
                success=stats["notifications_sent"] > 0
            )

            return stats

        except Exception as e:
            logger.error(f"Error in optimized async meal reminders job: {e}", exc_info=True)
            return {"error": str(e)}


# Instancia singleton del servicio async optimizado
async_optimized_nutrition_notification_service = AsyncOptimizedNutritionNotificationService()
