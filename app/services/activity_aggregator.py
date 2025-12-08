"""
Activity Aggregator Service - Agregación de eventos para feed anónimo.

Este servicio procesa eventos del sistema (check-ins, logros, etc.) y los
convierte en estadísticas agregadas anónimas para el Activity Feed.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
import json
import logging

from app.services.activity_feed_service import ActivityFeedService
from app.models.schedule import ClassParticipation, ClassSession
from app.models.user import User

logger = logging.getLogger(__name__)


class ActivityAggregator:
    """
    Agrega eventos del sistema en estadísticas anónimas.

    Procesa eventos individuales y los convierte en métricas agregadas
    sin exponer identidades de usuarios.
    """

    # Hitos de racha para celebrar
    STREAK_MILESTONES = [7, 14, 21, 30, 60, 90, 180, 365]

    # Umbrales para publicar actividades
    PUBLISH_THRESHOLDS = {
        "achievements": 3,      # Publicar cada 3 logros
        "check_ins": 5,         # Publicar cada 5 check-ins
        "personal_records": 3,   # Publicar cada 3 PRs
        "goals": 5,             # Publicar cada 5 metas cumplidas
    }

    def __init__(self, feed_service: ActivityFeedService, db: Session = None):
        """
        Inicializa el agregador.

        Args:
            feed_service: Servicio de Activity Feed
            db: Sesión de base de datos (opcional para queries agregadas)
        """
        self.feed_service = feed_service
        self.db = db

    async def on_class_checkin(self, event: Dict):
        """
        Procesa check-in a clase.

        Args:
            event: Datos del evento de check-in
                - gym_id: ID del gimnasio
                - class_name: Nombre de la clase
                - class_id: ID de la clase
                - session_id: ID de la sesión
        """
        gym_id = event["gym_id"]
        class_name = event.get("class_name", "Clase")

        # Incrementar contador de clase específica
        class_key = f"gym:{gym_id}:realtime:by_class:{class_name.replace(' ', '_')}"
        class_count = await self.feed_service.redis.incr(class_key)
        await self.feed_service.redis.expire(class_key, 300)  # 5 minutos

        # Incrementar contador total
        total_key = f"gym:{gym_id}:realtime:training_count"
        total_count = await self.feed_service.redis.incr(total_key)
        await self.feed_service.redis.expire(total_key, 300)

        # Incrementar contador diario de asistencia
        daily_key = f"gym:{gym_id}:daily:attendance"
        await self.feed_service.redis.incr(daily_key)
        await self.feed_service.redis.expire(daily_key, 86400)

        # Publicar si es múltiplo del umbral
        if total_count % self.PUBLISH_THRESHOLDS["check_ins"] == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="training_count",
                count=total_count,
                metadata={"source": "check_in"}
            )

        # Si la clase tiene suficientes personas, publicar como clase popular
        if class_count >= 10 and class_count % 5 == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="class_checkin",
                count=class_count,
                metadata={"class_name": class_name}
            )

        logger.info(f"Check-in procesado: gym={gym_id}, total={total_count}, {class_name}={class_count}")

    async def on_achievement_unlocked(self, event: Dict):
        """
        Procesa logro desbloqueado (sin exponer nombre del usuario).

        Args:
            event: Datos del evento de logro
                - gym_id: ID del gimnasio
                - achievement_type: Tipo de logro
                - achievement_level: Nivel del logro
        """
        gym_id = event["gym_id"]
        achievement_type = event.get("achievement_type", "general")

        # Incrementar contador diario de logros
        daily_count = await self.feed_service.update_aggregate_stats(
            gym_id=gym_id,
            stat_type="achievements_count",
            value=1,
            increment=True
        )

        # Incrementar contador por tipo
        type_key = f"gym:{gym_id}:daily:achievements:{achievement_type}"
        type_count = await self.feed_service.redis.incr(type_key)
        await self.feed_service.redis.expire(type_key, 86400)

        # Publicar cada X logros
        if daily_count % self.PUBLISH_THRESHOLDS["achievements"] == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="achievement_unlocked",
                count=daily_count,
                metadata={
                    "type": achievement_type,
                    "today_total": daily_count
                }
            )

        logger.info(f"Logro procesado: gym={gym_id}, total_hoy={daily_count}, tipo={achievement_type}")

    async def on_streak_milestone(self, event: Dict):
        """
        Procesa hito de racha (anónimo).

        Args:
            event: Datos del evento de racha
                - gym_id: ID del gimnasio
                - streak_days: Días de racha
        """
        gym_id = event["gym_id"]
        days = event.get("streak_days", 0)

        # Solo procesar hitos importantes
        if days not in self.STREAK_MILESTONES:
            return

        # Contar personas con este hito
        milestone_key = f"gym:{gym_id}:daily:streak_{days}"
        count = await self.feed_service.redis.incr(milestone_key)
        await self.feed_service.redis.expire(milestone_key, 86400 * 7)  # 7 días para hitos

        # Actualizar contador de rachas activas
        active_key = f"gym:{gym_id}:daily:active_streaks"
        await self.feed_service.redis.incr(active_key)
        await self.feed_service.redis.expire(active_key, 86400)

        # Publicar hito
        await self.feed_service.publish_realtime_activity(
            gym_id=gym_id,
            activity_type="streak_milestone",
            count=count,
            metadata={"days": days}
        )

        logger.info(f"Hito de racha: gym={gym_id}, {days} días, {count} personas")

    async def on_personal_record(self, event: Dict):
        """
        Procesa récord personal roto.

        Args:
            event: Datos del récord personal
                - gym_id: ID del gimnasio
                - record_type: Tipo de récord (weight, time, reps, etc)
        """
        gym_id = event["gym_id"]
        record_type = event.get("record_type", "general")

        # Incrementar contador diario de PRs
        pr_count = await self.feed_service.update_aggregate_stats(
            gym_id=gym_id,
            stat_type="personal_records",
            value=1,
            increment=True
        )

        # Publicar cada X PRs
        if pr_count % self.PUBLISH_THRESHOLDS["personal_records"] == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="pr_broken",
                count=pr_count,
                metadata={"type": record_type}
            )

        logger.info(f"PR procesado: gym={gym_id}, total_hoy={pr_count}")

    async def on_goal_completed(self, event: Dict):
        """
        Procesa meta completada.

        Args:
            event: Datos de la meta
                - gym_id: ID del gimnasio
                - goal_type: Tipo de meta
        """
        gym_id = event["gym_id"]
        goal_type = event.get("goal_type", "general")

        # Incrementar contador de metas
        goal_count = await self.feed_service.update_aggregate_stats(
            gym_id=gym_id,
            stat_type="goals_completed",
            value=1,
            increment=True
        )

        # Publicar cada X metas
        if goal_count % self.PUBLISH_THRESHOLDS["goals"] == 0:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="goal_completed",
                count=goal_count,
                metadata={"type": goal_type}
            )

        logger.info(f"Meta completada: gym={gym_id}, total_hoy={goal_count}")

    async def on_class_completed(self, event: Dict):
        """
        Procesa clase completada.

        Args:
            event: Datos de la clase completada
                - gym_id: ID del gimnasio
                - class_name: Nombre de la clase
                - total_participants: Total de participantes
                - duration_minutes: Duración en minutos
        """
        gym_id = event["gym_id"]
        participants = event.get("total_participants", 0)
        duration = event.get("duration_minutes", 60)

        # Incrementar contador de clases completadas
        classes_key = f"gym:{gym_id}:daily:classes_completed"
        classes_count = await self.feed_service.redis.incr(classes_key)
        await self.feed_service.redis.expire(classes_key, 86400)

        # Actualizar horas totales entrenadas (aproximado)
        hours_key = f"gym:{gym_id}:daily:total_hours"
        total_hours = participants * (duration / 60)
        current_hours = await self.feed_service.redis.get(hours_key) or 0
        new_total = float(current_hours) + total_hours
        await self.feed_service.redis.setex(hours_key, 86400, new_total)

        # Si la clase tuvo muchos participantes, publicar
        if participants >= 15:
            message = f"✅ Clase completada con {participants} guerreros"
            activity = {
                "type": "class_completed",
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "icon": "✅"
            }

            feed_key = f"gym:{gym_id}:feed:activities"
            await self.feed_service.redis.lpush(feed_key, json.dumps(activity))

        logger.info(f"Clase completada: gym={gym_id}, participantes={participants}")

    async def calculate_hourly_summary(self, gym_id: int):
        """
        Calcula resumen cada hora.

        Args:
            gym_id: ID del gimnasio
        """
        stats = await self._gather_hourly_stats(gym_id)
        messages = []

        # Generar mensajes motivacionales basados en actividad
        if stats.get("total_attendance", 0) > 50:
            messages.append(f"🔥 {stats['total_attendance']} asistencias en la última hora")

        if stats.get("new_prs", 0) > 10:
            messages.append(f"💪 {stats['new_prs']} nuevos récords personales")

        if stats.get("goals_completed", 0) > 5:
            messages.append(f"🎯 {stats['goals_completed']} metas alcanzadas")

        if stats.get("total_hours", 0) > 100:
            messages.append(f"📊 {int(stats['total_hours'])} horas de esfuerzo colectivo")

        # Publicar resumen si hay actividad significativa
        for message in messages[:3]:  # Máximo 3 mensajes
            activity = {
                "type": "hourly_summary",
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "icon": "📊"
            }

            feed_key = f"gym:{gym_id}:feed:activities"
            await self.feed_service.redis.lpush(feed_key, json.dumps(activity))
            await self.feed_service.redis.ltrim(feed_key, 0, 99)
            await self.feed_service.redis.expire(feed_key, 3600)

        logger.info(f"Resumen horario generado: gym={gym_id}, {len(messages)} insights")

    async def update_daily_rankings(self, gym_id: int):
        """
        Actualiza rankings diarios anónimos.

        Args:
            gym_id: ID del gimnasio
        """
        if not self.db:
            logger.warning("No hay sesión de BD para actualizar rankings")
            return

        try:
            # Obtener estadísticas agregadas del día
            today = datetime.now(timezone.utc).date()
            start_of_day = datetime.combine(today, datetime.min.time())

            # Top de consistencia (rachas) - solo valores
            consistency_query = self.db.query(
                func.count(User.id)
            ).filter(
                User.gym_id == gym_id,
                User.current_streak > 0
            ).group_by(User.current_streak).order_by(User.current_streak.desc()).limit(20)

            streak_values = [row[0] for row in consistency_query.all()]

            if streak_values:
                await self.feed_service.add_anonymous_ranking(
                    gym_id=gym_id,
                    ranking_type="consistency",
                    values=streak_values,
                    period="daily"
                )

            # Top de asistencia del día - solo cantidades
            attendance_query = self.db.query(
                func.count(ClassParticipation.id)
            ).join(ClassSession).filter(
                and_(
                    ClassSession.gym_id == gym_id,
                    ClassSession.scheduled_at >= start_of_day,
                    ClassParticipation.attended == True
                )
            ).group_by(ClassParticipation.member_id).all()

            attendance_values = [row[0] for row in attendance_query if row[0] > 0]

            if attendance_values:
                await self.feed_service.add_anonymous_ranking(
                    gym_id=gym_id,
                    ranking_type="attendance",
                    values=attendance_values,
                    period="daily"
                )

            logger.info(f"Rankings actualizados: gym={gym_id}")

        except Exception as e:
            logger.error(f"Error actualizando rankings: {e}")

    async def generate_motivational_burst(self, gym_id: int):
        """
        Genera ráfaga de mensajes motivacionales basados en actividad actual.

        Args:
            gym_id: ID del gimnasio
        """
        # Obtener estadísticas actuales
        stats = await self._gather_current_stats(gym_id)

        if stats["is_peak_time"]:
            await self.feed_service.publish_realtime_activity(
                gym_id=gym_id,
                activity_type="motivational",
                count=stats["active_users"],
                metadata={
                    "message": "¡Hora pico! El gimnasio está en llamas 🔥",
                    "peak": True
                }
            )

        if stats["group_training"] >= 3:
            message = f"👥 {stats['group_training']} grupos entrenando juntos"
            activity = {
                "type": "social",
                "message": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "icon": "👥"
            }

            feed_key = f"gym:{gym_id}:feed:activities"
            await self.feed_service.redis.lpush(feed_key, json.dumps(activity))

    async def _gather_hourly_stats(self, gym_id: int) -> Dict:
        """
        Recopila estadísticas de la última hora.

        Args:
            gym_id: ID del gimnasio

        Returns:
            Diccionario con estadísticas agregadas
        """
        stats = {}

        # Obtener contadores del día
        keys_to_check = [
            ("daily:attendance", "total_attendance"),
            ("daily:personal_records", "new_prs"),
            ("daily:goals_completed", "goals_completed"),
            ("daily:achievements_count", "achievements"),
            ("daily:total_hours", "total_hours"),
            ("daily:classes_completed", "classes_completed")
        ]

        for redis_key, stat_name in keys_to_check:
            key = f"gym:{gym_id}:{redis_key}"
            value = await self.feed_service.redis.get(key)
            if value:
                stats[stat_name] = float(value) if "hours" in stat_name else int(value)
            else:
                stats[stat_name] = 0

        return stats

    async def _gather_current_stats(self, gym_id: int) -> Dict:
        """
        Recopila estadísticas actuales en tiempo real.

        Args:
            gym_id: ID del gimnasio

        Returns:
            Diccionario con estadísticas actuales
        """
        stats = {
            "active_users": 0,
            "is_peak_time": False,
            "group_training": 0,
            "popular_classes": []
        }

        # Usuarios activos
        training_key = f"gym:{gym_id}:realtime:training_count"
        active = await self.feed_service.redis.get(training_key)
        if active:
            stats["active_users"] = int(active)
            stats["is_peak_time"] = int(active) > 20

        # Clases con grupos
        pattern = f"gym:{gym_id}:realtime:by_class:*"
        class_keys = await self.feed_service.redis.keys(pattern)

        for key in class_keys:
            count = await self.feed_service.redis.get(key)
            if count and int(count) >= 5:
                stats["group_training"] += 1
                class_name = key.decode().split(":")[-1] if isinstance(key, bytes) else key.split(":")[-1]
                stats["popular_classes"].append({
                    "name": class_name.replace("_", " "),
                    "count": int(count)
                })

        return stats

    async def process_batch_events(self, events: List[Dict]):
        """
        Procesa múltiples eventos en batch.

        Args:
            events: Lista de eventos para procesar
        """
        for event in events:
            event_type = event.get("type")

            handlers = {
                "class_checkin": self.on_class_checkin,
                "achievement_unlocked": self.on_achievement_unlocked,
                "streak_milestone": self.on_streak_milestone,
                "personal_record": self.on_personal_record,
                "goal_completed": self.on_goal_completed,
                "class_completed": self.on_class_completed
            }

            handler = handlers.get(event_type)
            if handler:
                try:
                    await handler(event)
                except Exception as e:
                    logger.error(f"Error procesando evento {event_type}: {e}")

        logger.info(f"Procesados {len(events)} eventos en batch")