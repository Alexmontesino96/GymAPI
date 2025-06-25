from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from datetime import datetime, timedelta
import logging

from app.models.chat import ChatRoom, ChatMember
from app.models.user import User
from app.models.event import Event
from app.repositories.chat import chat_repository

logger = logging.getLogger(__name__)

class ChatAnalyticsService:
    """
    Servicio para generar estadísticas y analíticas avanzadas de chat.
    """
    
    def get_gym_chat_summary(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """
        Obtiene un resumen completo de la actividad de chat en un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Dict con estadísticas del gimnasio
        """
        try:
            # Obtener todas las salas del gimnasio a través de eventos
            from app.models.event import Event
            rooms = db.query(ChatRoom).join(Event).filter(
                Event.gym_id == gym_id
            ).all()
            
            # También incluir chats directos - para esto necesitaríamos una relación diferente
            # Por ahora, trabajamos solo con chats de eventos
            
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
            unique_members = db.query(func.count(func.distinct(ChatMember.user_id))).filter(
                ChatMember.room_id.in_([room.id for room in rooms])
            ).scalar() or 0
            
            # Salas activas (con actividad en los últimos 7 días)
            week_ago = datetime.utcnow() - timedelta(days=7)
            active_rooms = sum(1 for room in rooms if room.updated_at and room.updated_at > week_ago)
            
            # Top 5 salas más activas (por número de miembros)
            room_stats = []
            for room in rooms:
                member_count = db.query(ChatMember).filter(ChatMember.room_id == room.id).count()
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
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generando resumen de chat para gimnasio {gym_id}: {str(e)}")
            return {"error": f"Error generando estadísticas: {str(e)}"}
    
    def get_user_chat_activity(self, db: Session, user_id: int) -> Dict[str, Any]:
        """
        Obtiene estadísticas de actividad de chat para un usuario específico.
        
        Args:
            db: Sesión de base de datos
            user_id: ID interno del usuario
            
        Returns:
            Dict con estadísticas del usuario
        """
        try:
            # Obtener usuario
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return {"error": "Usuario no encontrado"}
            
            # Obtener salas donde el usuario es miembro
            user_rooms = db.query(ChatRoom).join(ChatMember).filter(
                ChatMember.user_id == user_id
            ).all()
            
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
            month_ago = datetime.utcnow() - timedelta(days=30)
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
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generando actividad de chat para usuario {user_id}: {str(e)}")
            return {"error": f"Error generando estadísticas: {str(e)}"}
    
    def get_popular_chat_times(self, db: Session, gym_id: int, days: int = 30) -> Dict[str, Any]:
        """
        Analiza los horarios más populares para chat en un gimnasio.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            days: Número de días hacia atrás para analizar
            
        Returns:
            Dict con análisis de horarios populares
        """
        try:
            # Por ahora, retornamos un análisis básico basado en updated_at de las salas
            # En una implementación completa, esto requeriría almacenar timestamps de mensajes
            
            start_date = datetime.utcnow() - timedelta(days=days)
            
            from app.models.event import Event
            rooms = db.query(ChatRoom).join(Event).filter(
                and_(
                    Event.gym_id == gym_id,
                    ChatRoom.updated_at >= start_date
                )
            ).all()
            
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
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analizando horarios de chat para gimnasio {gym_id}: {str(e)}")
            return {"error": f"Error generando análisis: {str(e)}"}
    
    def get_event_chat_effectiveness(self, db: Session, event_id: int) -> Dict[str, Any]:
        """
        Analiza la efectividad del chat de un evento específico.
        
        Args:
            db: Sesión de base de datos
            event_id: ID del evento
            
        Returns:
            Dict con métricas de efectividad del chat del evento
        """
        try:
            # Obtener el evento
            event = db.query(Event).filter(Event.id == event_id).first()
            if not event:
                return {"error": "Evento no encontrado"}
            
            # Obtener la sala de chat del evento
            chat_room = chat_repository.get_event_room(db, event_id)
            if not chat_room:
                return {
                    "event_id": event_id,
                    "has_chat": False,
                    "message": "No se encontró chat para este evento"
                }
            
            # Obtener miembros del chat
            members = db.query(ChatMember).filter(ChatMember.room_id == chat_room.id).all()
            
            # Calcular métricas
            total_members = len(members)
            
            # Comparar con participantes del evento (si existe esa relación)
            participation_rate = 0
            try:
                # Esto dependería de cómo esté modelada la relación evento-participantes
                # Por ahora usamos una métrica básica
                participation_rate = min(total_members * 10, 100)  # Estimación simple
            except:
                pass
            
            return {
                "event_id": event_id,
                "event_name": getattr(event, 'name', 'N/A'),
                "has_chat": True,
                "chat_room_id": chat_room.id,
                "total_members": total_members,
                "participation_rate": participation_rate,
                "chat_created_at": chat_room.created_at.isoformat() if chat_room.created_at else None,
                "last_activity": chat_room.updated_at.isoformat() if chat_room.updated_at else None,
                "is_active": chat_room.updated_at > (datetime.utcnow() - timedelta(hours=24)) if chat_room.updated_at else False,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analizando efectividad de chat para evento {event_id}: {str(e)}")
            return {"error": f"Error generando análisis: {str(e)}"}
    
    def get_chat_health_metrics(self, db: Session, gym_id: int) -> Dict[str, Any]:
        """
        Genera métricas de salud general del sistema de chat.
        
        Args:
            db: Sesión de base de datos
            gym_id: ID del gimnasio
            
        Returns:
            Dict con métricas de salud del sistema
        """
        try:
            # Obtener todas las salas del gimnasio a través de eventos
            from app.models.event import Event
            rooms = db.query(ChatRoom).join(Event).filter(
                Event.gym_id == gym_id
            ).all()
            
            # Métricas de salud
            total_rooms = len(rooms)
            
            # Salas abandonadas (sin actividad en 30 días)
            month_ago = datetime.utcnow() - timedelta(days=30)
            abandoned_rooms = sum(1 for room in rooms 
                                if not room.updated_at or room.updated_at < month_ago)
            
            # Salas con pocos miembros (menos de 2)
            low_engagement_rooms = 0
            for room in rooms:
                member_count = db.query(ChatMember).filter(ChatMember.room_id == room.id).count()
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
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error generando métricas de salud para gimnasio {gym_id}: {str(e)}")
            return {"error": f"Error generando métricas: {str(e)}"}


# Instancia global del servicio
chat_analytics_service = ChatAnalyticsService() 