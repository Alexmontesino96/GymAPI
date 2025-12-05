"""
AsyncChatAnalyticsService - Servicio async para analíticas y estadísticas de chat.

Este módulo proporciona funcionalidades async para generar métricas y estadísticas
avanzadas sobre la actividad de chat en gimnasios.

Migrado en FASE 3 de la conversión sync → async.
"""

from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, desc
from datetime import datetime, timedelta, timezone
import logging

from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.models.event import Event
from app.repositories.async_chat import async_chat_repository

logger = logging.getLogger("async_chat_analytics_service")


class AsyncChatAnalyticsService:
    """
    Servicio async para generar estadísticas y analíticas avanzadas de chat.

    Todos los métodos son async y utilizan AsyncSession.

    Analytics disponibles:
    - Resumen de actividad por gimnasio
    - Actividad por usuario
    - Horarios populares de chat
    - Efectividad de chats de eventos
    - Métricas de salud del sistema

    Métodos principales:
    - get_gym_chat_summary() - Resumen completo del gimnasio
    - get_user_chat_activity() - Actividad de usuario específico
    - get_popular_chat_times() - Análisis de horarios pico
    - get_event_chat_effectiveness() - Métricas de evento
    - get_chat_health_metrics() - Health score del sistema
    """

    async def get_gym_chat_summary(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Obtiene un resumen completo de la actividad de chat en un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con estadísticas del gimnasio:
            - total_rooms, total_members, active_rooms
            - direct_chats, event_chats
            - most_active_rooms (top 5)

        Note:
            Salas activas = con actividad en últimos 7 días
        """
        try:
            # Obtener todas las salas del gimnasio
            result = await db.execute(
                select(ChatRoom).where(ChatRoom.gym_id == gym_id)
            )
            rooms = result.scalars().all()

            if not rooms:
                return {
                    "gym_id": gym_id,
                    "total_rooms": 0,
                    "total_members": 0,
                    "active_rooms": 0,
                    "direct_chats": 0,
                    "event_chats": 0,
                    "most_active_rooms": []
                }

            # Estadísticas básicas
            total_rooms = len(rooms)
            direct_chats = sum(1 for room in rooms if room.is_direct)
            event_chats = sum(1 for room in rooms if room.event_id is not None)

            # Contar miembros únicos
            result = await db.execute(
                select(func.count(func.distinct(ChatMember.user_id))).where(
                    ChatMember.room_id.in_([room.id for room in rooms])
                )
            )
            unique_members = result.scalar() or 0

            # Salas activas (con actividad en los últimos 7 días)
            week_ago = datetime.now(timezone.utc) - timedelta(days=7)
            active_rooms = sum(1 for room in rooms if room.updated_at and room.updated_at > week_ago)

            # Top 5 salas más activas (por número de miembros)
            room_stats = []
            for room in rooms:
                result = await db.execute(
                    select(func.count(ChatMember.id)).where(
                        ChatMember.room_id == room.id
                    )
                )
                member_count = result.scalar() or 0

                room_stats.append({
                    "room_id": room.id,
                    "name": room.name,
                    "is_direct": room.is_direct,
                    "member_count": member_count,
                    "updated_at": room.updated_at.isoformat() if room.updated_at else None
                })

            # Ordenar por número de miembros y tomar top 5
            most_active_rooms = sorted(room_stats, key=lambda x: x["member_count"], reverse=True)[:5]

            return {
                "gym_id": gym_id,
                "total_rooms": total_rooms,
                "total_members": unique_members,
                "active_rooms": active_rooms,
                "direct_chats": direct_chats,
                "event_chats": event_chats,
                "most_active_rooms": most_active_rooms,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error generando resumen de chat para gimnasio {gym_id}: {str(e)}")
            return {"error": f"Error generando estadísticas: {str(e)}"}

    async def get_user_chat_activity(
        self,
        db: AsyncSession,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Obtiene estadísticas de actividad de chat para un usuario específico.

        Args:
            db: Sesión async de base de datos
            user_id: ID interno del usuario

        Returns:
            Dict con estadísticas del usuario:
            - total_chats, direct_chats, group_chats
            - gym_distribution
            - recent_activity (últimos 30 días)

        Raises:
            ValueError: Si el usuario no existe
        """
        try:
            # Obtener usuario
            result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = result.scalar_one_or_none()

            if not user:
                return {"error": "Usuario no encontrado"}

            # Obtener salas donde el usuario es miembro
            result = await db.execute(
                select(ChatRoom).join(ChatMember).where(
                    ChatMember.user_id == user_id
                )
            )
            user_rooms = result.scalars().all()

            # Estadísticas básicas
            total_chats = len(user_rooms)
            direct_chats = sum(1 for room in user_rooms if room.is_direct)
            group_chats = total_chats - direct_chats

            # Chats por gimnasio
            gym_distribution = {}
            for room in user_rooms:
                gym_id = room.gym_id
                if gym_id not in gym_distribution:
                    gym_distribution[gym_id] = 0
                gym_distribution[gym_id] += 1

            # Actividad reciente (últimos 30 días)
            month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            recent_activity = sum(1 for room in user_rooms
                                if room.updated_at and room.updated_at > month_ago)

            return {
                "user_id": user_id,
                "user_email": getattr(user, 'email', 'N/A'),
                "total_chats": total_chats,
                "direct_chats": direct_chats,
                "group_chats": group_chats,
                "gym_distribution": gym_distribution,
                "recent_activity": recent_activity,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error generando actividad de chat para usuario {user_id}: {str(e)}")
            return {"error": f"Error generando estadísticas: {str(e)}"}

    async def get_popular_chat_times(
        self,
        db: AsyncSession,
        gym_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analiza los horarios más populares para chat en un gimnasio.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio
            days: Número de días hacia atrás para analizar

        Returns:
            Dict con análisis de horarios:
            - hourly_distribution: actividad por hora del día
            - peak_hours: top 3 horas más activas
            - total_activity: actividad total

        Note:
            Basado en updated_at de salas.
            En implementación completa, requiere timestamps de mensajes.
        """
        try:
            # Análisis básico basado en updated_at de las salas
            start_date = datetime.now(timezone.utc) - timedelta(days=days)

            # Filtrar directamente por gym_id en ChatRoom
            result = await db.execute(
                select(ChatRoom).where(
                    and_(
                        ChatRoom.gym_id == gym_id,
                        ChatRoom.updated_at >= start_date
                    )
                )
            )
            rooms = result.scalars().all()

            # Agrupar por hora del día
            hourly_activity = {str(i): 0 for i in range(24)}

            for room in rooms:
                if room.updated_at:
                    hour = room.updated_at.hour
                    hourly_activity[str(hour)] += 1

            # Encontrar las horas más activas
            sorted_hours = sorted(hourly_activity.items(), key=lambda x: x[1], reverse=True)
            peak_hours = sorted_hours[:3]

            return {
                "gym_id": gym_id,
                "analysis_period_days": days,
                "hourly_distribution": hourly_activity,
                "peak_hours": [{"hour": hour, "activity": count} for hour, count in peak_hours],
                "total_activity": sum(hourly_activity.values()),
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error analizando horarios de chat para gimnasio {gym_id}: {str(e)}")
            return {"error": f"Error generando análisis: {str(e)}"}

    async def get_event_chat_effectiveness(
        self,
        db: AsyncSession,
        event_id: int
    ) -> Dict[str, Any]:
        """
        Analiza la efectividad del chat de un evento específico.

        Args:
            db: Sesión async de base de datos
            event_id: ID del evento

        Returns:
            Dict con métricas de efectividad:
            - has_chat, chat_room_id, total_members
            - participation_rate, is_active
            - chat_created_at, last_activity

        Note:
            Participation rate es una estimación basada en miembros.
            Chat activo = con actividad en últimas 24 horas.
        """
        try:
            # Obtener el evento
            result = await db.execute(
                select(Event).where(Event.id == event_id)
            )
            event = result.scalar_one_or_none()

            if not event:
                return {"error": "Evento no encontrado"}

            # Obtener la sala de chat del evento (sync - TODO: migrar a async)
            chat_room = chat_repository.get_event_room(db, event_id)
            if not chat_room:
                return {
                    "event_id": event_id,
                    "has_chat": False,
                    "message": "No se encontró chat para este evento"
                }

            # Obtener miembros del chat
            result = await db.execute(
                select(ChatMember).where(ChatMember.room_id == chat_room.id)
            )
            members = result.scalars().all()

            # Calcular métricas
            total_members = len(members)

            # Comparar con participantes del evento (estimación simple)
            participation_rate = min(total_members * 10, 100)

            return {
                "event_id": event_id,
                "event_name": getattr(event, 'name', 'N/A'),
                "has_chat": True,
                "chat_room_id": chat_room.id,
                "total_members": total_members,
                "participation_rate": participation_rate,
                "chat_created_at": chat_room.created_at.isoformat() if chat_room.created_at else None,
                "last_activity": chat_room.updated_at.isoformat() if chat_room.updated_at else None,
                "is_active": chat_room.updated_at > (datetime.now(timezone.utc) - timedelta(hours=24)) if chat_room.updated_at else False,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error analizando efectividad de chat para evento {event_id}: {str(e)}")
            return {"error": f"Error generando análisis: {str(e)}"}

    async def get_chat_health_metrics(
        self,
        db: AsyncSession,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Genera métricas de salud general del sistema de chat.

        Args:
            db: Sesión async de base de datos
            gym_id: ID del gimnasio

        Returns:
            Dict con métricas de salud:
            - total_rooms, abandoned_rooms, low_engagement_rooms
            - health_score (0-100)
            - recommendations: Lista de recomendaciones

        Note:
            Health score calculation:
            - Base: 100 puntos
            - Penalty: -30 puntos por % de salas abandonadas (>30 días)
            - Penalty: -20 puntos por % de salas con baja participación (<2 miembros)
        """
        try:
            # Obtener todas las salas del gimnasio
            result = await db.execute(
                select(ChatRoom).where(ChatRoom.gym_id == gym_id)
            )
            rooms = result.scalars().all()

            # Métricas de salud
            total_rooms = len(rooms)

            # Salas abandonadas (sin actividad en 30 días)
            month_ago = datetime.now(timezone.utc) - timedelta(days=30)
            abandoned_rooms = sum(1 for room in rooms
                                if not room.updated_at or room.updated_at < month_ago)

            # Salas con pocos miembros (menos de 2)
            low_engagement_rooms = 0
            for room in rooms:
                result = await db.execute(
                    select(func.count(ChatMember.id)).where(
                        ChatMember.room_id == room.id
                    )
                )
                member_count = result.scalar() or 0
                if member_count < 2:
                    low_engagement_rooms += 1

            # Calcular score de salud (0-100)
            health_score = 100
            if total_rooms > 0:
                abandoned_penalty = (abandoned_rooms / total_rooms) * 30
                low_engagement_penalty = (low_engagement_rooms / total_rooms) * 20
                health_score = max(0, 100 - abandoned_penalty - low_engagement_penalty)

            # Recomendaciones
            recommendations = []
            if abandoned_rooms > 0:
                recommendations.append(f"Considera limpiar {abandoned_rooms} salas abandonadas")
            if low_engagement_rooms > total_rooms * 0.3:
                recommendations.append("Muchas salas tienen baja participación, considera estrategias de engagement")
            if health_score > 80:
                recommendations.append("¡Sistema de chat en excelente estado!")

            return {
                "gym_id": gym_id,
                "total_rooms": total_rooms,
                "abandoned_rooms": abandoned_rooms,
                "low_engagement_rooms": low_engagement_rooms,
                "health_score": round(health_score, 1),
                "recommendations": recommendations,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Error generando métricas de salud para gimnasio {gym_id}: {str(e)}")
            return {"error": f"Error generando métricas: {str(e)}"}


# Instancia singleton del servicio async
async_chat_analytics_service = AsyncChatAnalyticsService()
