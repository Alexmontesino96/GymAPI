"""
Activity Feed Service - Sistema de feed anónimo basado en cantidades.

Este servicio gestiona un feed de actividades completamente anónimo que muestra
solo cantidades y estadísticas agregadas, sin exponer nombres de usuarios.

Principio: "Números que motivan, sin nombres que comprometan"
"""

from typing import List, Dict, Any, Optional
import json
import asyncio
from datetime import datetime, timedelta
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)


class ActivityFeedService:
    """
    Servicio para gestionar Activity Feed anónimo basado en cantidades.

    Todas las actividades muestran solo números agregados sin identificar usuarios.
    Usa Redis con TTL automático para mantener datos efímeros.
    """

    # Configuración de TTLs (en segundos)
    TTL_CONFIG = {
        "realtime": 300,      # 5 minutos para datos en tiempo real
        "hourly": 3600,       # 1 hora para resúmenes horarios
        "daily": 86400,       # 24 horas para estadísticas diarias
        "weekly": 604800,     # 7 días para rankings semanales
        "feed": 3600,         # 1 hora para items del feed
    }

    # Umbrales mínimos de agregación para privacidad
    MIN_AGGREGATION_THRESHOLD = 3  # No mostrar si hay menos de 3

    # Iconos por tipo de actividad
    ACTIVITY_ICONS = {
        "training_count": "💪",
        "class_checkin": "📍",
        "achievement_unlocked": "⭐",
        "streak_milestone": "🔥",
        "pr_broken": "🏆",
        "goal_completed": "🎯",
        "social_activity": "👥",
        "class_popular": "📈",
        "hourly_summary": "📊",
        "motivational": "💫"
    }

    def __init__(self, redis: Redis):
        """
        Inicializa el servicio con conexión a Redis.

        Args:
            redis: Cliente Redis para almacenamiento efímero
        """
        self.redis = redis

    async def publish_realtime_activity(
        self,
        gym_id: int,
        activity_type: str,
        count: int,
        metadata: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        Publica actividad en tiempo real (solo cantidades).

        Args:
            gym_id: ID del gimnasio
            activity_type: Tipo de actividad
            count: Cantidad/número para mostrar
            metadata: Metadatos adicionales (opcional)

        Returns:
            Dict con la actividad publicada o None si no cumple umbral
        """
        # No publicar si está por debajo del umbral de privacidad
        if count < self.MIN_AGGREGATION_THRESHOLD and activity_type in ["training_count", "class_checkin"]:
            logger.info(f"Actividad no publicada: count={count} < threshold={self.MIN_AGGREGATION_THRESHOLD}")
            return None

        # Actualizar contador en Redis
        key = f"gym:{gym_id}:realtime:{activity_type}"
        await self.redis.setex(key, self.TTL_CONFIG["realtime"], count)

        # Crear mensaje para feed
        activity = {
            "id": f"{gym_id}_{activity_type}_{datetime.utcnow().timestamp()}",
            "type": "realtime",
            "subtype": activity_type,
            "count": count,
            "message": self._generate_message(activity_type, count, metadata),
            "timestamp": datetime.utcnow().isoformat(),
            "icon": self.ACTIVITY_ICONS.get(activity_type, "📊"),
            "ttl_minutes": self.TTL_CONFIG["realtime"] // 60
        }

        # Agregar al feed
        feed_key = f"gym:{gym_id}:feed:activities"
        await self.redis.lpush(feed_key, json.dumps(activity))
        await self.redis.ltrim(feed_key, 0, 99)  # Mantener últimas 100 actividades
        await self.redis.expire(feed_key, self.TTL_CONFIG["feed"])

        # Publicar para subscriptores real-time (WebSocket)
        channel = f"gym:{gym_id}:feed:updates"
        await self.redis.publish(channel, json.dumps(activity))

        logger.info(f"Actividad publicada: {activity_type} con count={count} para gym={gym_id}")

        return activity

    async def update_aggregate_stats(
        self,
        gym_id: int,
        stat_type: str,
        value: Any,
        increment: bool = False
    ) -> int:
        """
        Actualiza estadísticas agregadas del día.

        Args:
            gym_id: ID del gimnasio
            stat_type: Tipo de estadística
            value: Valor a establecer o incrementar
            increment: Si True, incrementa el valor actual

        Returns:
            Valor actualizado de la estadística
        """
        key = f"gym:{gym_id}:daily:{stat_type}"

        if increment:
            new_value = await self.redis.incr(key)
            await self.redis.expire(key, self.TTL_CONFIG["daily"])
        else:
            await self.redis.setex(key, self.TTL_CONFIG["daily"], value)
            new_value = value

        logger.debug(f"Estadística actualizada: {stat_type}={new_value} para gym={gym_id}")

        return new_value

    async def get_feed(
        self,
        gym_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict]:
        """
        Obtiene el feed de actividades anónimo.

        Args:
            gym_id: ID del gimnasio
            limit: Número máximo de actividades
            offset: Offset para paginación

        Returns:
            Lista de actividades del feed
        """
        feed_key = f"gym:{gym_id}:feed:activities"

        # Obtener actividades del feed
        raw_activities = await self.redis.lrange(
            feed_key,
            offset,
            offset + limit - 1
        )

        activities = []
        for raw in raw_activities:
            try:
                activity = json.loads(raw)
                # Enriquecer con tiempo relativo
                activity["time_ago"] = self._get_time_ago(activity["timestamp"])
                activities.append(activity)
            except Exception as e:
                logger.error(f"Error decodificando actividad: {e}")
                continue

        # Agregar estadísticas actuales si no hay muchas actividades
        if len(activities) < 5:
            current_stats = await self._get_current_stats_summary(gym_id)
            for stat in current_stats:
                activities.append(stat)

        return activities[:limit]

    async def get_realtime_summary(self, gym_id: int) -> Dict:
        """
        Obtiene resumen en tiempo real del gimnasio.

        Args:
            gym_id: ID del gimnasio

        Returns:
            Resumen con estadísticas actuales
        """
        # Buscar todos los contadores en tiempo real
        pattern = f"gym:{gym_id}:realtime:*"
        keys = await self.redis.keys(pattern)

        summary = {
            "total_training": 0,
            "by_area": {},
            "popular_classes": [],
            "peak_time": False,
            "last_update": datetime.utcnow().isoformat()
        }

        for key in keys:
            value = await self.redis.get(key)
            if value:
                key_str = key.decode() if isinstance(key, bytes) else key
                key_parts = key_str.split(":")

                if "training_count" in key_parts:
                    summary["total_training"] = int(value)
                elif "by_class" in key_parts:
                    class_name = key_parts[-1]
                    count = int(value)
                    summary["by_area"][class_name] = count

                    # Agregar a clases populares si tiene suficientes personas
                    if count >= 5:
                        summary["popular_classes"].append({
                            "name": class_name,
                            "count": count
                        })

        # Ordenar clases populares por cantidad
        summary["popular_classes"].sort(key=lambda x: x["count"], reverse=True)
        summary["popular_classes"] = summary["popular_classes"][:3]  # Top 3

        # Determinar si es hora pico (>20 personas)
        summary["peak_time"] = summary["total_training"] > 20

        return summary

    async def generate_motivational_insights(self, gym_id: int) -> List[Dict]:
        """
        Genera insights motivacionales basados en datos agregados.

        Args:
            gym_id: ID del gimnasio

        Returns:
            Lista de insights motivacionales
        """
        insights = []

        # Total de personas entrenando
        training_count_key = f"gym:{gym_id}:realtime:training_count"
        training_count = await self.redis.get(training_count_key)

        if training_count and int(training_count) > 10:
            insights.append({
                "message": f"🔥 ¡{training_count} guerreros activos ahora mismo!",
                "type": "realtime",
                "priority": 1
            })
        elif training_count and int(training_count) >= self.MIN_AGGREGATION_THRESHOLD:
            insights.append({
                "message": f"💪 {training_count} personas construyendo su mejor versión",
                "type": "realtime",
                "priority": 2
            })

        # Logros del día
        achievements_key = f"gym:{gym_id}:daily:achievements_count"
        achievements = await self.redis.get(achievements_key)

        if achievements and int(achievements) > 5:
            insights.append({
                "message": f"⭐ {achievements} logros desbloqueados hoy",
                "type": "achievement",
                "priority": 2
            })

        # Récords personales
        prs_key = f"gym:{gym_id}:daily:personal_records"
        prs = await self.redis.get(prs_key)

        if prs and int(prs) > 0:
            insights.append({
                "message": f"💪 {prs} récords personales superados",
                "type": "record",
                "priority": 1
            })

        # Rachas activas
        streak_key = f"gym:{gym_id}:daily:active_streaks"
        streak_count = await self.redis.get(streak_key)

        if streak_count and int(streak_count) > 10:
            insights.append({
                "message": f"🔥 {streak_count} personas con racha activa",
                "type": "consistency",
                "priority": 2
            })

        # Horas totales entrenadas
        hours_key = f"gym:{gym_id}:daily:total_hours"
        total_hours = await self.redis.get(hours_key)

        if total_hours and float(total_hours) > 100:
            insights.append({
                "message": f"📊 {int(float(total_hours))} horas de esfuerzo colectivo hoy",
                "type": "collective",
                "priority": 3
            })

        # Ordenar por prioridad
        insights.sort(key=lambda x: x["priority"])

        return insights[:5]  # Máximo 5 insights

    async def update_class_occupancy(
        self,
        gym_id: int,
        class_id: int,
        class_name: str,
        current_occupancy: int,
        max_capacity: int
    ) -> Optional[Dict]:
        """
        Actualiza ocupación de clase y publica si es relevante.

        Args:
            gym_id: ID del gimnasio
            class_id: ID de la clase
            class_name: Nombre de la clase
            current_occupancy: Ocupación actual
            max_capacity: Capacidad máxima

        Returns:
            Actividad publicada si es relevante
        """
        occupancy_percentage = (current_occupancy / max_capacity) * 100

        # Publicar solo si la clase está casi llena o es popular
        if occupancy_percentage >= 80:
            message = f"🔥 {class_name} casi lleno ({current_occupancy}/{max_capacity})"

            activity = {
                "type": "class_status",
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
                "icon": "🔥",
                "metadata": {
                    "class_name": class_name,
                    "occupancy": current_occupancy,
                    "capacity": max_capacity,
                    "percentage": round(occupancy_percentage)
                }
            }

            # Agregar al feed
            feed_key = f"gym:{gym_id}:feed:activities"
            await self.redis.lpush(feed_key, json.dumps(activity))
            await self.redis.ltrim(feed_key, 0, 99)
            await self.redis.expire(feed_key, self.TTL_CONFIG["feed"])

            return activity

        return None

    async def add_anonymous_ranking(
        self,
        gym_id: int,
        ranking_type: str,
        values: List[float],
        period: str = "weekly"
    ) -> Dict:
        """
        Agrega ranking anónimo (solo valores, sin identificadores).

        Args:
            gym_id: ID del gimnasio
            ranking_type: Tipo de ranking (consistency, attendance, etc)
            values: Lista de valores para el ranking
            period: Período del ranking

        Returns:
            Ranking creado
        """
        key = f"gym:{gym_id}:rankings:{period}:{ranking_type}"

        # Limpiar ranking anterior
        await self.redis.delete(key)

        # Agregar valores anónimos
        for i, value in enumerate(sorted(values, reverse=True)[:10]):  # Top 10
            member = f"anonymous_{i+1}"
            await self.redis.zadd(key, {member: value})

        # Establecer TTL según período
        ttl = self.TTL_CONFIG.get(period, self.TTL_CONFIG["weekly"])
        await self.redis.expire(key, ttl)

        logger.info(f"Ranking actualizado: {ranking_type} con {len(values)} valores")

        return {
            "type": ranking_type,
            "period": period,
            "top_values": values[:10] if len(values) >= 10 else values
        }

    async def get_anonymous_rankings(
        self,
        gym_id: int,
        ranking_type: str,
        period: str = "weekly",
        limit: int = 10
    ) -> List[Dict]:
        """
        Obtiene rankings anónimos.

        Args:
            gym_id: ID del gimnasio
            ranking_type: Tipo de ranking
            period: Período del ranking
            limit: Número de posiciones a mostrar

        Returns:
            Lista con las posiciones del ranking
        """
        key = f"gym:{gym_id}:rankings:{period}:{ranking_type}"

        # Obtener top scores
        top_scores = await self.redis.zrevrange(key, 0, limit - 1, withscores=True)

        rankings = []
        for i, (member, score) in enumerate(top_scores, 1):
            rankings.append({
                "position": i,
                "value": int(score) if score == int(score) else round(score, 1),
                "label": f"Posición {i}"
            })

        return rankings

    def _generate_message(
        self,
        activity_type: str,
        count: int,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Genera mensaje legible para la actividad.

        Args:
            activity_type: Tipo de actividad
            count: Cantidad
            metadata: Metadatos adicionales

        Returns:
            Mensaje formateado para mostrar
        """
        messages = {
            "training_count": f"{count} personas entrenando ahora",
            "class_checkin": f"{count} personas en {metadata.get('class_name', 'clase') if metadata else 'clase'}",
            "achievement_unlocked": f"{count} logros desbloqueados",
            "streak_milestone": f"{count} personas con racha de {metadata.get('days', '7') if metadata else '7'}+ días",
            "pr_broken": f"{count} récords personales rotos",
            "goal_completed": f"{count} metas cumplidas",
            "social_activity": f"{count} interacciones sociales",
            "new_members": f"{count} nuevos miembros esta semana",
            "classes_completed": f"{count} clases completadas hoy"
        }

        return messages.get(activity_type, f"{count} actividades")

    def _get_time_ago(self, timestamp_str: str) -> str:
        """
        Convierte timestamp a formato "hace X tiempo".

        Args:
            timestamp_str: Timestamp en formato ISO

        Returns:
            String con tiempo relativo
        """
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            now = datetime.utcnow()

            # Si timestamp tiene timezone, convertir now también
            if timestamp.tzinfo:
                from datetime import timezone
                now = now.replace(tzinfo=timezone.utc)

            diff = now - timestamp

            if diff.seconds < 60:
                return "hace momentos"
            elif diff.seconds < 3600:
                minutes = diff.seconds // 60
                return f"hace {minutes} minuto{'s' if minutes != 1 else ''}"
            elif diff.seconds < 86400:
                hours = diff.seconds // 3600
                return f"hace {hours} hora{'s' if hours != 1 else ''}"
            else:
                days = diff.days
                return f"hace {days} día{'s' if days != 1 else ''}"
        except Exception as e:
            logger.error(f"Error calculando tiempo relativo: {e}")
            return "recientemente"

    async def _get_current_stats_summary(self, gym_id: int) -> List[Dict]:
        """
        Obtiene resumen de estadísticas actuales para rellenar feed.

        Args:
            gym_id: ID del gimnasio

        Returns:
            Lista de actividades estadísticas
        """
        activities = []

        # Total entrenando hoy
        attendance_key = f"gym:{gym_id}:daily:attendance"
        attendance = await self.redis.get(attendance_key)

        if attendance and int(attendance) > 0:
            activities.append({
                "type": "daily_stat",
                "message": f"📊 {attendance} personas han entrenado hoy",
                "timestamp": datetime.utcnow().isoformat(),
                "icon": "📊"
            })

        # Clases completadas
        classes_key = f"gym:{gym_id}:daily:classes_completed"
        classes = await self.redis.get(classes_key)

        if classes and int(classes) > 0:
            activities.append({
                "type": "daily_stat",
                "message": f"✅ {classes} clases completadas hoy",
                "timestamp": datetime.utcnow().isoformat(),
                "icon": "✅"
            })

        return activities

    async def cleanup_expired_data(self, gym_id: int) -> Dict[str, int]:
        """
        Limpia datos expirados (aunque Redis TTL lo maneja automáticamente).

        Este método es principalmente para logging y monitoreo.

        Args:
            gym_id: ID del gimnasio

        Returns:
            Estadísticas de limpieza
        """
        stats = {
            "keys_checked": 0,
            "keys_expired": 0,
            "memory_before": 0,
            "memory_after": 0
        }

        # Obtener uso de memoria antes
        info = await self.redis.info("memory")
        stats["memory_before"] = info.get("used_memory", 0)

        # Redis maneja TTL automáticamente, solo verificamos
        patterns = [
            f"gym:{gym_id}:realtime:*",
            f"gym:{gym_id}:daily:*",
            f"gym:{gym_id}:feed:*"
        ]

        for pattern in patterns:
            keys = await self.redis.keys(pattern)
            stats["keys_checked"] += len(keys)

            for key in keys:
                ttl = await self.redis.ttl(key)
                if ttl == -1:  # Sin TTL establecido
                    # Establecer TTL por seguridad
                    await self.redis.expire(key, self.TTL_CONFIG["daily"])
                    stats["keys_expired"] += 1

        # Obtener uso de memoria después
        info = await self.redis.info("memory")
        stats["memory_after"] = info.get("used_memory", 0)

        logger.info(f"Limpieza completada para gym {gym_id}: {stats}")

        return stats