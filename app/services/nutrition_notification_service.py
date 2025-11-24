"""
Servicio de notificaciones para el módulo de nutrición.
Maneja recordatorios de comidas, logros y actualizaciones de challenges.

Features:
- Recordatorios de comidas con horarios personalizables
- Notificaciones de logros y rachas
- Actualizaciones de challenges grupales (planes LIVE)
- Cache con Redis para mejor rendimiento
- Rate limiting integrado
"""

from datetime import datetime, time, timedelta, date, timezone
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func
import logging
import asyncio
import json

from app.models.nutrition import (
    NutritionPlan,
    NutritionPlanFollower,
    DailyNutritionPlan,
    Meal,
    UserMealCompletion,
    UserDailyProgress,
    PlanType,
    MealType
)
from app.models.user import User
from app.services.notification_service import notification_service
from app.db.redis_client import get_redis_client
from app.services.nutrition import NutritionService

logger = logging.getLogger(__name__)

# Constantes de configuración
CACHE_TTL_USERS_FOR_REMINDER = 300  # 5 minutos
CACHE_TTL_USER_STREAK = 3600  # 1 hora
CACHE_TTL_NOTIFICATION_SENT = 86400  # 24 horas
BATCH_SIZE = 50


class NutritionNotificationService:
    """Servicio de notificaciones para nutrición con cache Redis"""

    def __init__(self, use_sqs: bool = True):
        """
        Inicializar servicio de notificaciones.

        Args:
            use_sqs: Si True, usa SQS para encolar notificaciones (recomendado para producción).
                    Si False, envía directamente via OneSignal.
        """
        self.notification_service = notification_service
        self._redis = None  # Se inicializará cuando sea necesario
        self.batch_size = BATCH_SIZE
        self.use_sqs = use_sqs
        self._sqs_service = None

    def _get_sqs_service(self):
        """Obtener servicio SQS de forma lazy"""
        if self._sqs_service is None:
            try:
                from app.services.sqs_notification_service import sqs_notification_service
                if sqs_notification_service.enabled:
                    self._sqs_service = sqs_notification_service
                else:
                    self._sqs_service = False  # Marcar como no disponible
            except ImportError:
                self._sqs_service = False
        return self._sqs_service if self._sqs_service else None

    def _get_redis_sync(self):
        """Obtener cliente Redis de forma síncrona (para uso en jobs)"""
        try:
            import redis
            from app.core.config import get_settings
            settings = get_settings()

            if settings.REDIS_URL:
                return redis.from_url(settings.REDIS_URL, decode_responses=True)
            return None
        except Exception as e:
            logger.warning(f"Could not get Redis client: {e}")
            return None

    async def _get_redis(self):
        """Obtener cliente Redis de forma async"""
        if self._redis is None:
            self._redis = await get_redis_client()
        return self._redis

    def _check_notification_already_sent(
        self,
        redis_client,
        user_id: int,
        notification_type: str,
        date_str: str
    ) -> bool:
        """
        Verificar si ya se envió esta notificación hoy (evitar duplicados).
        Usa cache Redis con TTL de 24 horas.
        """
        if not redis_client:
            return False

        try:
            cache_key = f"nutrition:notif_sent:{user_id}:{notification_type}:{date_str}"
            return redis_client.exists(cache_key) > 0
        except Exception as e:
            logger.warning(f"Redis check error: {e}")
            return False

    def _mark_notification_sent(
        self,
        redis_client,
        user_id: int,
        notification_type: str,
        date_str: str
    ):
        """Marcar notificación como enviada en cache"""
        if not redis_client:
            return

        try:
            cache_key = f"nutrition:notif_sent:{user_id}:{notification_type}:{date_str}"
            redis_client.setex(cache_key, CACHE_TTL_NOTIFICATION_SENT, "1")
        except Exception as e:
            logger.warning(f"Redis mark error: {e}")

    def _increment_metric(
        self,
        redis_client,
        gym_id: int,
        metric_name: str,
        increment: int = 1
    ):
        """Incrementar métrica en Redis"""
        if not redis_client:
            return

        try:
            today = datetime.now().strftime("%Y%m%d")
            metrics_key = f"nutrition:metrics:{gym_id}:{today}"
            redis_client.hincrby(metrics_key, metric_name, increment)
            redis_client.expire(metrics_key, 86400 * 30)  # 30 días TTL
        except Exception as e:
            logger.warning(f"Redis metrics error: {e}")

    def send_meal_reminder(
        self,
        db: Session,
        user_id: int,
        meal_type: str,
        meal_name: str,
        plan_title: str,
        gym_id: int,
        force_direct: bool = False
    ) -> bool:
        """
        Enviar recordatorio de comida a un usuario.

        Si SQS está habilitado y force_direct=False, encola el mensaje para
        procesamiento asíncrono. Si no, envía directamente via OneSignal.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            meal_type: Tipo de comida (breakfast, lunch, dinner, etc)
            meal_name: Nombre de la comida
            plan_title: Título del plan nutricional
            gym_id: ID del gimnasio
            force_direct: Si True, envía directamente sin usar SQS

        Returns:
            bool: True si se envió/encoló correctamente
        """
        try:
            # Obtener cliente Redis para cache
            redis_client = self._get_redis_sync()
            today_str = datetime.now().strftime("%Y%m%d")

            # Verificar si ya se envió esta notificación hoy (evitar duplicados)
            if self._check_notification_already_sent(
                redis_client, user_id, f"meal_{meal_type}", today_str
            ):
                logger.debug(f"Skipping duplicate meal reminder for user {user_id}")
                return False

            # Mapeo de tipos de comida a emojis y textos
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

            emoji = meal_emojis.get(meal_type, "🍽️")
            meal_text = meal_texts.get(meal_type, "comida")

            # Crear notificación
            title = f"{emoji} Hora de tu {meal_text}"
            message = f"{meal_name} - {plan_title}"

            # Intentar usar SQS si está habilitado
            sqs_service = self._get_sqs_service()
            if self.use_sqs and sqs_service and not force_direct:
                # Encolar en SQS para procesamiento asíncrono
                success = sqs_service.enqueue_meal_reminder(
                    user_id=user_id,
                    gym_id=gym_id,
                    meal_type=meal_type,
                    meal_name=meal_name,
                    plan_title=plan_title
                )

                if success:
                    # Marcar como enviada en cache (prevenir duplicados)
                    self._mark_notification_sent(
                        redis_client, user_id, f"meal_{meal_type}", today_str
                    )
                    self._increment_metric(redis_client, gym_id, f"meal_reminder_{meal_type}_queued")
                    logger.info(f"Meal reminder queued in SQS for user {user_id}, meal {meal_type}")
                    return True
                else:
                    # Si falla SQS, hacer fallback a envío directo
                    logger.warning(f"SQS enqueue failed, falling back to direct send for user {user_id}")

            # Envío directo via OneSignal (fallback o force_direct)
            result = self.notification_service.send_to_users(
                user_ids=[str(user_id)],
                title=title,
                message=message,
                data={
                    "type": "meal_reminder",
                    "meal_type": meal_type,
                    "action": "open_meal_plan"
                },
                db=db
            )

            if result.get("success"):
                # Marcar como enviada en cache
                self._mark_notification_sent(
                    redis_client, user_id, f"meal_{meal_type}", today_str
                )
                # Incrementar métrica
                self._increment_metric(redis_client, gym_id, f"meal_reminder_{meal_type}_sent")
                logger.info(f"Meal reminder sent directly to user {user_id} for {meal_type}")
                return True

            # Incrementar métrica de fallo
            self._increment_metric(redis_client, gym_id, f"meal_reminder_{meal_type}_failed")
            return False

        except Exception as e:
            logger.error(f"Error sending meal reminder: {str(e)}")
            return False

    def send_daily_plan_reminder(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """
        Enviar recordatorios del plan diario a todos los usuarios activos.

        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con estadísticas de envío
        """
        stats = {
            "total_users": 0,
            "notifications_sent": 0,
            "errors": 0
        }

        try:
            # Obtener seguidores activos con notificaciones habilitadas
            followers = db.query(NutritionPlanFollower).join(
                NutritionPlan
            ).filter(
                and_(
                    NutritionPlan.gym_id == gym_id,
                    NutritionPlan.is_active == True,
                    NutritionPlanFollower.is_active == True,
                    NutritionPlanFollower.notifications_enabled == True
                )
            ).all()

            stats["total_users"] = len(followers)

            for follower in followers:
                try:
                    # Obtener información del plan
                    plan = db.query(NutritionPlan).filter(
                        NutritionPlan.id == follower.plan_id
                    ).first()

                    if not plan:
                        continue

                    # Calcular día actual según tipo de plan
                    current_day = self._calculate_current_day(plan, follower)

                    if current_day > 0:
                        # Enviar notificación con resumen del día
                        title = "📋 Tu plan nutricional de hoy"
                        message = f"{plan.title} - Día {current_day} de {plan.duration_days}"

                        result = self.notification_service.send_to_users(
                            user_ids=[str(follower.user_id)],
                            title=title,
                            message=message,
                            data={
                                "type": "daily_plan",
                                "plan_id": follower.plan_id,
                                "current_day": current_day
                            },
                            db=db
                        )

                        if result.get("success"):
                            stats["notifications_sent"] += 1

                except Exception as e:
                    logger.error(f"Error sending daily reminder to user {follower.user_id}: {str(e)}")
                    stats["errors"] += 1

        except Exception as e:
            logger.error(f"Error in send_daily_plan_reminder: {str(e)}")

        return stats

    def send_achievement_notification(
        self,
        db: Session,
        user_id: int,
        achievement_type: str,
        gym_id: int,
        extra_data: Optional[Dict] = None
    ) -> bool:
        """
        Enviar notificación de logro desbloqueado.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            achievement_type: Tipo de logro
            gym_id: ID del gimnasio
            extra_data: Datos adicionales del logro

        Returns:
            bool: True si se envió correctamente
        """
        achievements = {
            "first_meal": {
                "title": "🎉 ¡Primera comida completada!",
                "body": "Has dado el primer paso en tu viaje nutricional"
            },
            "week_streak": {
                "title": "🔥 ¡Racha de 7 días!",
                "body": "Una semana completa siguiendo tu plan"
            },
            "month_streak": {
                "title": "🏆 ¡Racha de 30 días!",
                "body": "Un mes entero de consistencia. ¡Eres imparable!"
            },
            "perfect_day": {
                "title": "⭐ ¡Día perfecto!",
                "body": "Completaste todas las comidas del día"
            },
            "challenge_completed": {
                "title": "🥇 ¡Challenge completado!",
                "body": f"Has terminado el challenge: {extra_data.get('challenge_name', '') if extra_data else ''}"
            },
            "photo_warrior": {
                "title": "📸 ¡Guerrero visual!",
                "body": "Has subido 50 fotos de tus comidas"
            }
        }

        achievement = achievements.get(achievement_type)
        if not achievement:
            return False

        try:
            result = self.notification_service.send_to_users(
                user_ids=[str(user_id)],
                title=achievement["title"],
                message=achievement["body"],
                data={
                    "type": "achievement",
                    "achievement_type": achievement_type,
                    "extra": extra_data or {}
                },
                db=db
            )

            if result.get("success"):
                logger.info(f"Achievement notification sent to user {user_id}: {achievement_type}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error sending achievement notification: {str(e)}")
            return False

    def send_challenge_update(
        self,
        db: Session,
        plan_id: int,
        update_type: str,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Enviar actualización de challenge (plan live) a todos los participantes.

        Args:
            db: Sesión de base de datos
            plan_id: ID del plan live
            update_type: Tipo de actualización (started, ending_soon, completed, etc)
            gym_id: ID del gimnasio

        Returns:
            Dict con estadísticas de envío
        """
        stats = {
            "participants": 0,
            "notifications_sent": 0,
            "errors": 0
        }

        try:
            # Obtener plan y verificar que es LIVE
            plan = db.query(NutritionPlan).filter(
                NutritionPlan.id == plan_id
            ).first()

            if not plan or plan.plan_type != PlanType.LIVE:
                logger.warning(f"Plan {plan_id} is not a live plan")
                return stats

            # Obtener todos los participantes activos
            followers = db.query(NutritionPlanFollower).filter(
                and_(
                    NutritionPlanFollower.plan_id == plan_id,
                    NutritionPlanFollower.is_active == True
                )
            ).all()

            stats["participants"] = len(followers)

            # Preparar mensaje según tipo
            messages = {
                "started": {
                    "title": "🚀 ¡El challenge ha comenzado!",
                    "body": f"{plan.title} está en marcha. ¡A por ello!"
                },
                "halfway": {
                    "title": "🎯 ¡Mitad del challenge!",
                    "body": f"Llevas la mitad de {plan.title}. ¡Sigue así!"
                },
                "ending_soon": {
                    "title": "⏰ ¡Últimos 3 días!",
                    "body": f"{plan.title} está por terminar. ¡Sprint final!"
                },
                "completed": {
                    "title": "🎊 ¡Challenge completado!",
                    "body": f"¡Felicidades! Has completado {plan.title}"
                },
                "daily_leaderboard": {
                    "title": "📊 Actualización del challenge",
                    "body": f"Revisa tu posición en {plan.title}"
                }
            }

            message = messages.get(update_type)
            if not message:
                return stats

            # Enviar a todos los participantes
            user_ids = [str(f.user_id) for f in followers]

            if user_ids:
                result = self.notification_service.send_to_users(
                    user_ids=user_ids,
                    title=message["title"],
                    message=message["body"],
                    data={
                        "type": "challenge_update",
                        "update_type": update_type,
                        "plan_id": plan_id,
                        "plan_title": plan.title
                    },
                    db=db
                )

                if result.get("success"):
                    stats["notifications_sent"] = len(user_ids)

                logger.info(f"Challenge update sent for plan {plan_id}: {update_type}")

        except Exception as e:
            logger.error(f"Error sending challenge update: {str(e)}")
            stats["errors"] += 1

        return stats

    def check_and_send_streak_notifications(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> Optional[int]:
        """
        Verificar racha de días consecutivos y enviar notificación si corresponde.

        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio

        Returns:
            Número de días de racha si hay milestone, None si no
        """
        try:
            # Calcular racha actual
            streak = self._calculate_streak(db, user_id)

            # Milestones de racha para notificar
            milestones = [3, 7, 14, 21, 30, 60, 90, 100, 365]

            if streak in milestones:
                # Enviar notificación de milestone
                emoji_map = {
                    3: "🌱", 7: "🔥", 14: "💪", 21: "⭐",
                    30: "🏆", 60: "🥇", 90: "🎯", 100: "💯", 365: "👑"
                }

                title = f"{emoji_map.get(streak, '🎉')} ¡{streak} días de racha!"
                message = self._get_streak_message(streak)

                result = self.notification_service.send_to_users(
                    user_ids=[str(user_id)],
                    title=title,
                    message=message,
                    data={
                        "type": "streak_milestone",
                        "streak_days": streak
                    },
                    db=db
                )

                if result.get("success"):
                    logger.info(f"Streak milestone notification sent to user {user_id}: {streak} days")
                    return streak

        except Exception as e:
            logger.error(f"Error checking streak notifications: {str(e)}")

        return None

    # Métodos privados de ayuda

    def _calculate_current_day(self, plan: NutritionPlan, follower: NutritionPlanFollower) -> int:
        """
        Calcular el día actual del plan según su tipo.

        Returns:
            Número del día actual (1-N) o 0 si no ha comenzado
        """
        today = date.today()

        if plan.plan_type == PlanType.TEMPLATE or plan.plan_type == PlanType.ARCHIVED:
            # Para templates y archived, basado en fecha de inicio del usuario
            if not follower.start_date:
                return 0

            days_since_start = (today - follower.start_date.date()).days

            if plan.is_recurring:
                # Si es recurrente, calcular ciclo actual
                current_day = (days_since_start % plan.duration_days) + 1
                return current_day
            else:
                # Si no es recurrente, verificar si está en rango
                if days_since_start >= plan.duration_days:
                    return 0  # Plan terminado
                return days_since_start + 1

        elif plan.plan_type == PlanType.LIVE:
            # Para live, basado en fecha global del plan
            if not plan.live_start_date:
                return 0

            plan_start_date = plan.live_start_date.date()

            if today < plan_start_date:
                return 0  # No ha comenzado

            days_since_start = (today - plan_start_date).days

            if plan.is_recurring:
                current_day = (days_since_start % plan.duration_days) + 1
                return current_day
            else:
                if days_since_start >= plan.duration_days:
                    return 0  # Plan terminado
                return days_since_start + 1

        return 0

    def _calculate_streak(self, db: Session, user_id: int) -> int:
        """
        Calcular días consecutivos de adherencia.
        Considera que un día está completo si se completaron >= 80% de las comidas.
        """
        try:
            # Obtener progreso diario de los últimos 365 días ordenado por fecha descendente
            thirty_days_ago = datetime.now() - timedelta(days=365)

            progress_records = db.query(UserDailyProgress).filter(
                and_(
                    UserDailyProgress.user_id == user_id,
                    UserDailyProgress.date >= thirty_days_ago
                )
            ).order_by(UserDailyProgress.date.desc()).all()

            if not progress_records:
                return 0

            # Contar días consecutivos desde hoy hacia atrás
            streak = 0
            expected_date = date.today()

            for record in progress_records:
                record_date = record.date.date() if hasattr(record.date, 'date') else record.date

                # Si hay un gap en las fechas, la racha se rompe
                if record_date != expected_date:
                    break

                # Verificar si el día está completo (>= 80% de comidas)
                if record.completion_percentage >= 80:
                    streak += 1
                    expected_date = expected_date - timedelta(days=1)
                else:
                    break  # Racha rota

            return streak

        except Exception as e:
            logger.error(f"Error calculating streak: {str(e)}")
            return 0

    def _get_streak_message(self, days: int) -> str:
        """Obtener mensaje motivacional según días de racha"""
        messages = {
            3: "Excelente inicio. El hábito se está formando.",
            7: "Una semana completa. ¡Eres consistente!",
            14: "Dos semanas de disciplina. Impresionante.",
            21: "Dicen que 21 días forman un hábito. ¡Lo lograste!",
            30: "Un mes entero. Eres inspiración para otros.",
            60: "Dos meses de excelencia. Eres imparable.",
            90: "Tres meses. Has transformado tu estilo de vida.",
            100: "¡Centenario! Eres parte del 1% más disciplinado.",
            365: "Un año completo. Eres una leyenda viviente."
        }
        return messages.get(days, f"¡{days} días de consistencia pura!")


    def batch_enqueue_meal_reminders(
        self,
        db: Session,
        gym_id: int,
        meal_type: str,
        scheduled_time: str
    ) -> Dict[str, Any]:
        """
        Encolar múltiples recordatorios de comida en SQS de forma eficiente.

        Diseñado para ser llamado por el scheduler. Obtiene todos los usuarios
        que deben recibir notificación y los encola en batch.

        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            meal_type: Tipo de comida (breakfast, lunch, dinner)
            scheduled_time: Hora programada (formato HH:MM)

        Returns:
            Dict con estadísticas de encolamiento
        """
        stats = {
            "users_found": 0,
            "queued": 0,
            "skipped_duplicate": 0,
            "failed": 0,
            "method": "sqs" if self.use_sqs and self._get_sqs_service() else "direct"
        }

        try:
            redis_client = self._get_redis_sync()
            today_str = datetime.now().strftime("%Y%m%d")

            # Mapear tipo de comida a campo de horario
            time_field_map = {
                "breakfast": "notification_time_breakfast",
                "lunch": "notification_time_lunch",
                "dinner": "notification_time_dinner"
            }

            time_field = time_field_map.get(meal_type)
            if not time_field:
                logger.warning(f"Invalid meal type: {meal_type}")
                return stats

            # Obtener seguidores con esta hora configurada
            followers = db.query(NutritionPlanFollower).join(
                NutritionPlan
            ).filter(
                and_(
                    NutritionPlan.gym_id == gym_id,
                    NutritionPlan.is_active == True,
                    NutritionPlanFollower.is_active == True,
                    NutritionPlanFollower.notifications_enabled == True,
                    getattr(NutritionPlanFollower, time_field) == scheduled_time
                )
            ).all()

            stats["users_found"] = len(followers)
            logger.info(f"Found {len(followers)} users for {meal_type} at {scheduled_time}")

            # Preparar mensajes para batch
            messages_to_queue = []
            sqs_service = self._get_sqs_service()

            for follower in followers:
                try:
                    # Verificar duplicados
                    if self._check_notification_already_sent(
                        redis_client, follower.user_id, f"meal_{meal_type}", today_str
                    ):
                        stats["skipped_duplicate"] += 1
                        continue

                    # Obtener plan y día actual
                    plan = db.query(NutritionPlan).filter(
                        NutritionPlan.id == follower.plan_id
                    ).first()

                    if not plan:
                        continue

                    current_day = self._calculate_current_day(plan, follower)
                    if current_day <= 0:
                        continue

                    # Obtener comida del día
                    daily_plan = db.query(DailyNutritionPlan).filter(
                        and_(
                            DailyNutritionPlan.nutrition_plan_id == plan.id,
                            DailyNutritionPlan.day_number == current_day
                        )
                    ).first()

                    if not daily_plan:
                        continue

                    meal = db.query(Meal).filter(
                        and_(
                            Meal.daily_plan_id == daily_plan.id,
                            Meal.meal_type == meal_type
                        )
                    ).first()

                    if not meal:
                        continue

                    # Preparar mensaje
                    if self.use_sqs and sqs_service:
                        messages_to_queue.append({
                            "user_id": follower.user_id,
                            "gym_id": gym_id,
                            "meal_type": meal_type,
                            "meal_name": meal.name,
                            "plan_title": plan.title
                        })
                    else:
                        # Envío directo
                        success = self.send_meal_reminder(
                            db=db,
                            user_id=follower.user_id,
                            meal_type=meal_type,
                            meal_name=meal.name,
                            plan_title=plan.title,
                            gym_id=gym_id,
                            force_direct=True
                        )
                        if success:
                            stats["queued"] += 1
                        else:
                            stats["failed"] += 1

                except Exception as e:
                    logger.error(f"Error processing follower {follower.user_id}: {e}")
                    stats["failed"] += 1

            # Enviar batch a SQS
            if messages_to_queue and sqs_service:
                batch_results = sqs_service.enqueue_batch([
                    sqs_service._create_meal_reminder_message(
                        user_id=msg["user_id"],
                        gym_id=msg["gym_id"],
                        meal_type=msg["meal_type"],
                        meal_name=msg["meal_name"],
                        plan_title=msg["plan_title"]
                    )
                    for msg in messages_to_queue
                ])

                stats["queued"] = batch_results.get("successful", 0)
                stats["failed"] += batch_results.get("failed", 0)

                # Marcar como enviadas en cache
                for msg in messages_to_queue[:stats["queued"]]:
                    self._mark_notification_sent(
                        redis_client, msg["user_id"], f"meal_{meal_type}", today_str
                    )

                # Incrementar métricas
                self._increment_metric(
                    redis_client, gym_id,
                    f"meal_reminder_{meal_type}_queued",
                    stats["queued"]
                )

            logger.info(
                f"Batch enqueue completed: {stats['queued']} queued, "
                f"{stats['skipped_duplicate']} skipped, {stats['failed']} failed"
            )

        except Exception as e:
            logger.error(f"Error in batch_enqueue_meal_reminders: {e}")

        return stats


# Funciones para usar con APScheduler

def send_meal_reminders_job(gym_id: int, meal_type: str, scheduled_time: str):
    """
    Job para enviar recordatorios de comidas.
    Ejecutar con APScheduler a las horas configuradas.

    Usa SQS si está disponible (batch enqueue), si no envía directamente.

    Args:
        gym_id: ID del gimnasio
        meal_type: Tipo de comida (breakfast, lunch, dinner)
        scheduled_time: Hora programada (formato HH:MM)
    """
    from app.db.session import SessionLocal

    logger.info(f"Running meal reminder job for gym {gym_id}, meal {meal_type} at {scheduled_time}")

    db = SessionLocal()
    try:
        # Usar el nuevo método batch que maneja SQS automáticamente
        notification_srv = NutritionNotificationService()
        results = notification_srv.batch_enqueue_meal_reminders(
            db=db,
            gym_id=gym_id,
            meal_type=meal_type,
            scheduled_time=scheduled_time
        )

        logger.info(
            f"Meal reminders job completed for {meal_type}: "
            f"method={results['method']}, users_found={results['users_found']}, "
            f"queued={results['queued']}, skipped={results['skipped_duplicate']}, "
            f"failed={results['failed']}"
        )

    except Exception as e:
        logger.error(f"Error in send_meal_reminders_job: {str(e)}")
    finally:
        db.close()


def check_live_plan_status_job():
    """
    Job para verificar estado de planes live y enviar notificaciones.
    Ejecutar diariamente.
    """
    from app.db.session import SessionLocal

    logger.info("Running live plan status check job")

    db = SessionLocal()
    try:
        notification_srv = NutritionNotificationService()
        today = date.today()

        # Buscar planes que empiezan hoy
        starting_plans = db.query(NutritionPlan).filter(
            and_(
                NutritionPlan.plan_type == PlanType.LIVE,
                func.date(NutritionPlan.live_start_date) == today,
                NutritionPlan.is_active == True
            )
        ).all()

        for plan in starting_plans:
            # Marcar plan como activo
            plan.is_live_active = True
            db.add(plan)

            # Enviar notificación de inicio
            notification_srv.send_challenge_update(
                db=db,
                plan_id=plan.id,
                update_type="started",
                gym_id=plan.gym_id
            )

        # Buscar planes que terminan en 3 días
        ending_soon_date = today + timedelta(days=3)

        ending_plans = db.query(NutritionPlan).filter(
            and_(
                NutritionPlan.plan_type == PlanType.LIVE,
                NutritionPlan.is_live_active == True,
                func.date(NutritionPlan.live_start_date) + NutritionPlan.duration_days == ending_soon_date
            )
        ).all()

        for plan in ending_plans:
            # Enviar notificación de próximo a terminar
            notification_srv.send_challenge_update(
                db=db,
                plan_id=plan.id,
                update_type="ending_soon",
                gym_id=plan.gym_id
            )

        # Buscar planes que terminan hoy
        completed_plans = db.query(NutritionPlan).filter(
            and_(
                NutritionPlan.plan_type == PlanType.LIVE,
                NutritionPlan.is_live_active == True,
                func.date(NutritionPlan.live_start_date) + NutritionPlan.duration_days == today
            )
        ).all()

        for plan in completed_plans:
            # Marcar como completado
            plan.is_live_active = False
            db.add(plan)

            # Enviar notificación de completado
            notification_srv.send_challenge_update(
                db=db,
                plan_id=plan.id,
                update_type="completed",
                gym_id=plan.gym_id
            )

        db.commit()
        logger.info(f"Live plan status check completed. Started: {len(starting_plans)}, Ending soon: {len(ending_plans)}, Completed: {len(completed_plans)}")

    except Exception as e:
        logger.error(f"Error in check_live_plan_status_job: {str(e)}")
        db.rollback()
    finally:
        db.close()


def check_daily_achievements_job():
    """
    Job para verificar logros diarios (días perfectos, rachas).
    Ejecutar al final del día.
    """
    from app.db.session import SessionLocal

    logger.info("Running daily achievements check job")

    db = SessionLocal()
    try:
        notification_srv = NutritionNotificationService()
        today = date.today()

        # Obtener usuarios con actividad hoy
        users_with_activity = db.query(UserDailyProgress.user_id).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).filter(
            func.date(UserDailyProgress.date) == today
        ).distinct().all()

        perfect_days = 0
        streaks_checked = 0

        for (user_id,) in users_with_activity:
            try:
                # Verificar si tuvo un día perfecto (100% de comidas)
                daily_progress = db.query(UserDailyProgress).filter(
                    and_(
                        UserDailyProgress.user_id == user_id,
                        func.date(UserDailyProgress.date) == today,
                        UserDailyProgress.completion_percentage >= 100
                    )
                ).first()

                if daily_progress:
                    # Obtener gym_id desde el plan
                    gym_id = db.query(NutritionPlan.gym_id).join(
                        DailyNutritionPlan
                    ).filter(
                        DailyNutritionPlan.id == daily_progress.daily_plan_id
                    ).scalar()

                    if gym_id:
                        # Enviar notificación de día perfecto
                        notification_srv.send_achievement_notification(
                            db=db,
                            user_id=user_id,
                            achievement_type="perfect_day",
                            gym_id=gym_id
                        )
                        perfect_days += 1

                        # Verificar racha
                        streak = notification_srv.check_and_send_streak_notifications(
                            db=db,
                            user_id=user_id,
                            gym_id=gym_id
                        )
                        if streak:
                            streaks_checked += 1

            except Exception as e:
                logger.error(f"Error checking achievements for user {user_id}: {str(e)}")

        logger.info(f"Daily achievements check completed. Perfect days: {perfect_days}, Streak milestones: {streaks_checked}")

    except Exception as e:
        logger.error(f"Error in check_daily_achievements_job: {str(e)}")
    finally:
        db.close()


def get_notification_analytics(gym_id: int, days: int = 7) -> Dict[str, Any]:
    """
    Obtener analytics de notificaciones de los últimos N días desde Redis.

    Args:
        gym_id: ID del gimnasio
        days: Número de días a analizar (default 7)

    Returns:
        Dict con analytics de notificaciones
    """
    analytics = {
        "gym_id": gym_id,
        "period_days": days,
        "total_sent": 0,
        "total_failed": 0,
        "success_rate": 0,
        "by_type": {
            "breakfast": {"sent": 0, "failed": 0},
            "lunch": {"sent": 0, "failed": 0},
            "dinner": {"sent": 0, "failed": 0},
            "achievement": {"sent": 0, "failed": 0},
            "challenge": {"sent": 0, "failed": 0}
        },
        "daily_trend": [],
        "last_updated": datetime.now().isoformat()
    }

    try:
        import redis
        from app.core.config import get_settings
        settings = get_settings()

        redis_client = None
        if settings.REDIS_URL:
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

        if not redis_client:
            return analytics

        # Obtener datos de los últimos N días
        for i in range(days):
            date_str = (datetime.now() - timedelta(days=i)).strftime("%Y%m%d")
            metrics_key = f"nutrition:metrics:{gym_id}:{date_str}"

            daily_data = redis_client.hgetall(metrics_key)
            if not daily_data:
                continue

            daily_sent = 0
            daily_failed = 0

            for key, value in daily_data.items():
                value_int = int(value) if value else 0

                if "_sent" in key:
                    daily_sent += value_int

                    # Categorizar por tipo
                    if "breakfast" in key:
                        analytics["by_type"]["breakfast"]["sent"] += value_int
                    elif "lunch" in key:
                        analytics["by_type"]["lunch"]["sent"] += value_int
                    elif "dinner" in key:
                        analytics["by_type"]["dinner"]["sent"] += value_int
                    elif "achievement" in key:
                        analytics["by_type"]["achievement"]["sent"] += value_int
                    elif "challenge" in key:
                        analytics["by_type"]["challenge"]["sent"] += value_int

                elif "_failed" in key:
                    daily_failed += value_int

                    # Categorizar por tipo
                    if "breakfast" in key:
                        analytics["by_type"]["breakfast"]["failed"] += value_int
                    elif "lunch" in key:
                        analytics["by_type"]["lunch"]["failed"] += value_int
                    elif "dinner" in key:
                        analytics["by_type"]["dinner"]["failed"] += value_int
                    elif "achievement" in key:
                        analytics["by_type"]["achievement"]["failed"] += value_int
                    elif "challenge" in key:
                        analytics["by_type"]["challenge"]["failed"] += value_int

            analytics["total_sent"] += daily_sent
            analytics["total_failed"] += daily_failed

            # Calcular tasa de éxito del día
            day_total = daily_sent + daily_failed
            day_success_rate = round((daily_sent / day_total * 100), 2) if day_total > 0 else 0

            analytics["daily_trend"].append({
                "date": date_str,
                "sent": daily_sent,
                "failed": daily_failed,
                "success_rate": day_success_rate
            })

        # Calcular tasa de éxito global
        total = analytics["total_sent"] + analytics["total_failed"]
        if total > 0:
            analytics["success_rate"] = round((analytics["total_sent"] / total * 100), 2)

        # Ordenar tendencia por fecha
        analytics["daily_trend"].sort(key=lambda x: x["date"], reverse=True)

    except Exception as e:
        logger.error(f"Error getting notification analytics: {e}")

    return analytics


def get_user_notification_status(user_id: int, gym_id: int) -> Dict[str, Any]:
    """
    Obtener estado de notificaciones de un usuario específico.

    Args:
        user_id: ID del usuario
        gym_id: ID del gimnasio

    Returns:
        Dict con estado de notificaciones del usuario
    """
    status = {
        "user_id": user_id,
        "notifications_today": {
            "breakfast": False,
            "lunch": False,
            "dinner": False
        },
        "last_notification": None,
        "streak_days": 0,
        "total_notifications_received": 0
    }

    try:
        import redis
        from app.core.config import get_settings
        settings = get_settings()

        redis_client = None
        if settings.REDIS_URL:
            redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

        if not redis_client:
            return status

        today_str = datetime.now().strftime("%Y%m%d")

        # Verificar qué notificaciones se enviaron hoy
        for meal_type in ["breakfast", "lunch", "dinner"]:
            cache_key = f"nutrition:notif_sent:{user_id}:meal_{meal_type}:{today_str}"
            status["notifications_today"][meal_type] = redis_client.exists(cache_key) > 0

    except Exception as e:
        logger.error(f"Error getting user notification status: {e}")

    return status


# Instancia global del servicio
nutrition_notification_service = NutritionNotificationService()