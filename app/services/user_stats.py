"""
Servicio para estadísticas comprehensivas de usuario.

Este servicio agrega datos de múltiples fuentes (clases, eventos, membresías, chat)
para generar estadísticas comprehensivas del usuario con optimizaciones de rendimiento
mediante caché inteligente y cálculos en background.
"""

import logging
from typing import Optional, Dict, List, Any, Union
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session
from redis.asyncio import Redis

from app.schemas.user_stats import (
    ComprehensiveUserStats, DashboardSummary, WeeklySummary, MonthlyTrends,
    FitnessMetrics, EventsMetrics, SocialMetrics, HealthMetrics,
    MembershipUtilization, Achievement, TrendAnalysis,
    PeriodType, TrendDirection, GoalStatus, BMICategory
)
from app.services.cache_service import CacheService
from app.core.profiling import time_db_query, register_cache_hit, register_cache_miss
from app.repositories.schedule import class_participation_repository
from app.repositories.event import event_participation_repository
from app.services.user import user_service
from app.services.membership import membership_service
from app.services.chat_analytics import chat_analytics_service
from app.models.user import User

logger = logging.getLogger(__name__)


class UserStatsService:
    """
    Servicio para generar estadísticas comprehensivas de usuario con optimizaciones avanzadas.
    """

    def __init__(self):
        self.cache_service = CacheService()
        
    async def get_dashboard_summary(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int,
        redis_client: Optional[Redis] = None
    ) -> DashboardSummary:
        """
        Obtiene resumen ultra rápido para dashboard principal.
        
        Optimizado para ser < 50ms con cache agresivo.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            redis_client: Cliente Redis para cache
            
        Returns:
            DashboardSummary: Resumen optimizado para dashboard
        """
        cache_key = f"dashboard_summary:{user_id}:{gym_id}"
        
        if redis_client:
            # Intentar obtener desde cache (TTL: 15 minutos)
            try:
                cached_data = await self.cache_service.get_or_set(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=lambda: self._compute_dashboard_summary(db, user_id, gym_id),
                    model_class=DashboardSummary,
                    expiry_seconds=900,  # 15 minutos
                    is_list=False
                )
                if cached_data:
                    register_cache_hit(cache_key)
                    return cached_data
            except Exception as e:
                logger.error(f"Error accessing cache for dashboard summary: {e}")
                register_cache_miss(cache_key)
        
        # Fallback: calcular directamente (con datos mínimos)
        return await self._compute_dashboard_summary(db, user_id, gym_id)
    
    async def get_comprehensive_stats(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period: PeriodType = PeriodType.month,
        include_goals: bool = True,
        redis_client: Optional[Redis] = None
    ) -> ComprehensiveUserStats:
        """
        Obtiene estadísticas comprehensivas del usuario.
        
        Optimizado con cache inteligente y background jobs.
        
        Args:
            db: Sesión de base de datos  
            user_id: ID del usuario
            gym_id: ID del gimnasio
            period: Período de análisis
            include_goals: Incluir progreso de objetivos
            redis_client: Cliente Redis para cache
            
        Returns:
            ComprehensiveUserStats: Estadísticas completas
        """
        cache_key = f"comprehensive_stats:{user_id}:{gym_id}:{period.value}:{include_goals}"
        
        if redis_client:
            try:
                # Cache con TTL diferenciado según período
                ttl_mapping = {
                    PeriodType.week: 1800,     # 30 minutos
                    PeriodType.month: 3600,    # 1 hora
                    PeriodType.quarter: 7200,  # 2 horas  
                    PeriodType.year: 14400     # 4 horas
                }
                
                cached_data = await self.cache_service.get_or_set(
                    redis_client=redis_client,
                    cache_key=cache_key,
                    db_fetch_func=lambda: self._compute_comprehensive_stats(
                        db, user_id, gym_id, period, include_goals
                    ),
                    model_class=ComprehensiveUserStats,
                    expiry_seconds=ttl_mapping.get(period, 3600),
                    is_list=False
                )
                if cached_data:
                    register_cache_hit(cache_key)
                    return cached_data
                    
            except Exception as e:
                logger.error(f"Error accessing cache for comprehensive stats: {e}")
                register_cache_miss(cache_key)
        
        # Calcular directamente si no hay cache
        return await self._compute_comprehensive_stats(db, user_id, gym_id, period, include_goals)
    
    async def _compute_dashboard_summary(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> DashboardSummary:
        """
        Calcula resumen de dashboard optimizado para velocidad.
        
        Solo obtiene datos esenciales para el dashboard principal.
        """
        logger.info(f"Computing dashboard summary for user {user_id}, gym {gym_id}")
        
        try:
            from app.models.user_gym import UserGym
            
            # Obtener datos básicos del usuario
            user = user_service.get_user(db, user_id=user_id)
            if not user:
                raise ValueError(f"Usuario {user_id} no encontrado")
            
            # Calcular fechas para análisis semanal rápido
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            
            # Obtener métricas básicas (queries optimizadas)
            with time_db_query("dashboard_summary_queries"):
                # Racha actual (simplificado)
                current_streak = await self._calculate_current_streak_fast(db, user_id, gym_id)
                
                # Entrenamientos esta semana
                weekly_workouts = await self._get_weekly_workout_count(db, user_id, gym_id, week_start)
                
                # Progreso mensual (basado en objetivo de 12 clases por mes)
                monthly_target = 12
                monthly_progress = min((weekly_workouts * 4 / monthly_target) * 100, 100.0)
                
                # Estado de membresía
                user_gym = db.query(UserGym).filter(
                    UserGym.user_id == user_id,
                    UserGym.gym_id == gym_id
                ).first()
                membership_status = "active" if user_gym else "inactive"
                
                # Próxima clase (query rápida)
                next_class = await self._get_next_scheduled_class(db, user_id, gym_id)
                
                # Logro más reciente (simplificado)
                recent_achievement = None  # TODO: Implementar sistema de achievements
            
            return DashboardSummary(
                user_id=user_id,
                current_streak=current_streak,
                weekly_workouts=weekly_workouts,
                monthly_goal_progress=monthly_progress,
                next_class=next_class,
                recent_achievement=recent_achievement,
                membership_status=membership_status,
                quick_stats={
                    "total_sessions_month": weekly_workouts * 4,  # Estimación rápida
                    "favorite_class": "Yoga",  # TODO: Calcular real
                    "avg_duration": 90,  # TODO: Calcular real
                    "social_score": 7.5  # TODO: Calcular real
                }
            )
            
        except Exception as e:
            logger.error(f"Error computing dashboard summary for user {user_id}: {e}", exc_info=True)
            # Retornar datos por defecto en caso de error
            return DashboardSummary(
                user_id=user_id,
                current_streak=0,
                weekly_workouts=0,
                monthly_goal_progress=0.0,
                next_class=None,
                recent_achievement=None,
                membership_status="unknown",
                quick_stats={}
            )
    
    async def _compute_comprehensive_stats(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period: PeriodType,
        include_goals: bool
    ) -> ComprehensiveUserStats:
        """
        Calcula estadísticas comprehensivas completas.
        
        Este método hace el trabajo pesado de agregación de todas las fuentes.
        """
        logger.info(f"Computing comprehensive stats for user {user_id}, period {period.value}")
        
        # Calcular fechas del período
        period_start, period_end = self._calculate_period_dates(period)
        
        try:
            with time_db_query("comprehensive_stats_computation"):
                # Obtener todas las métricas en paralelo (donde sea posible)
                fitness_metrics = await self._compute_fitness_metrics(
                    db, user_id, gym_id, period_start, period_end
                )
                
                events_metrics = await self._compute_events_metrics(
                    db, user_id, gym_id, period_start, period_end
                )
                
                social_metrics = await self._compute_social_metrics(
                    db, user_id, gym_id, period_start, period_end
                )
                
                health_metrics = await self._compute_health_metrics(
                    db, user_id, gym_id, period_start, period_end, include_goals
                )
                
                membership_util = await self._compute_membership_utilization(
                    db, user_id, gym_id, period_start, period_end
                )
                
                achievements = await self._get_recent_achievements(
                    db, user_id, gym_id, period_start, period_end
                )
                
                trends = await self._analyze_trends(
                    db, user_id, gym_id, period_start, period_end
                )
                
                recommendations = await self._generate_recommendations(
                    fitness_metrics, events_metrics, social_metrics, health_metrics
                )
            
            return ComprehensiveUserStats(
                user_id=user_id,
                period=period,
                period_start=period_start,
                period_end=period_end,
                fitness_metrics=fitness_metrics,
                events_metrics=events_metrics,
                social_metrics=social_metrics,
                health_metrics=health_metrics,
                membership_utilization=membership_util,
                achievements=achievements,
                trends=trends,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error computing comprehensive stats for user {user_id}: {e}", exc_info=True)
            raise
    
    # === Métodos de Cálculo Específicos ===
    
    async def _calculate_current_streak_fast(self, db: Session, user_id: int, gym_id: int) -> int:
        """Cálculo rápido de racha actual de días activos."""
        try:
            from datetime import date, timedelta
            from app.models.schedule import ClassParticipation, ClassParticipationStatus
            
            # Obtener los últimos 30 días de participaciones exitosas
            thirty_days_ago = date.today() - timedelta(days=30)
            
            # Query optimizada: obtener solo fechas únicas de asistencia
            # Usar índice compuesto en (user_id, gym_id, status, created_at)
            attendance_dates = db.query(
                func.date(ClassParticipation.created_at).label('attendance_date')
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                func.date(ClassParticipation.created_at) >= thirty_days_ago
            ).distinct().order_by(
                func.date(ClassParticipation.created_at).desc()
            ).all()
            
            if not attendance_dates:
                return 0
            
            # Calcular racha actual (días consecutivos desde hoy hacia atrás)
            current_streak = 0
            current_date = date.today()
            
            for attendance_record in attendance_dates:
                attendance_date = attendance_record.attendance_date
                
                # Si es el primer día o es consecutivo al anterior
                if current_streak == 0 and attendance_date == current_date:
                    current_streak = 1
                elif attendance_date == current_date - timedelta(days=current_streak):
                    current_streak += 1
                else:
                    # Se rompió la racha
                    break
                    
            return current_streak
            
        except Exception as e:
            logger.error(f"Error calculating streak for user {user_id}: {e}")
            return 0
    
    async def _calculate_longest_streak(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int, 
        start_date: datetime, 
        end_date: datetime
    ) -> int:
        """Calcula la racha más larga en un período determinado."""
        try:
            from datetime import date, timedelta
            from app.models.schedule import ClassParticipation, ClassParticipationStatus
            
            # Obtener todas las fechas de asistencia en el período
            attendance_dates = db.query(
                func.date(ClassParticipation.created_at).label('attendance_date')
            ).join(
                ClassParticipation.class_session
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                ClassParticipation.created_at >= start_date,
                ClassParticipation.created_at <= end_date
            ).distinct().order_by(
                func.date(ClassParticipation.created_at).asc()
            ).all()
            
            if not attendance_dates:
                return 0
            
            # Calcular la racha más larga
            max_streak = 0
            current_streak = 1
            
            prev_date = attendance_dates[0].attendance_date
            
            for i in range(1, len(attendance_dates)):
                current_date = attendance_dates[i].attendance_date
                
                # Si es consecutivo al día anterior
                if current_date == prev_date + timedelta(days=1):
                    current_streak += 1
                else:
                    # Se rompió la racha, actualizar máximo si es necesario
                    max_streak = max(max_streak, current_streak)
                    current_streak = 1
                
                prev_date = current_date
            
            # No olvidar la última racha
            max_streak = max(max_streak, current_streak)
            
            return max_streak
            
        except Exception as e:
            logger.error(f"Error calculating longest streak for user {user_id}: {e}")
            return 0
    
    async def _get_weekly_workout_count(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int, 
        week_start: date
    ) -> int:
        """Obtiene conteo de entrenamientos de la semana actual."""
        try:
            from app.models.schedule import ClassParticipation, ClassParticipationStatus
            
            week_end = week_start + timedelta(days=6)
            
            # Query optimizada: contar clases asistidas en la semana
            workout_count = db.query(ClassParticipation).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                func.date(ClassParticipation.created_at) >= week_start,
                func.date(ClassParticipation.created_at) <= week_end
            ).count()
            
            return workout_count
            
        except Exception as e:
            logger.error(f"Error getting weekly workout count for user {user_id}: {e}")
            return 0
    
    async def _get_next_scheduled_class(
        self, 
        db: Session, 
        user_id: int, 
        gym_id: int
    ) -> Optional[str]:
        """Obtiene la próxima clase programada del usuario."""
        try:
            from app.models.schedule import ClassParticipation, ClassSession, Class, ClassParticipationStatus, ClassSessionStatus
            
            now = datetime.now()
            
            # Query para obtener la próxima clase registrada
            next_class = db.query(
                Class.name,
                ClassSession.start_time
            ).join(
                ClassSession, Class.id == ClassSession.class_id
            ).join(
                ClassParticipation, ClassSession.id == ClassParticipation.class_session_id
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.REGISTERED,
                ClassSession.status == ClassSessionStatus.SCHEDULED,
                ClassSession.start_time > now
            ).order_by(
                ClassSession.start_time.asc()
            ).first()
            
            if next_class:
                class_name = next_class.name
                start_time = next_class.start_time
                
                # Formatear fecha de manera amigable
                if start_time.date() == now.date():
                    time_str = f"Hoy {start_time.strftime('%H:%M')}"
                elif start_time.date() == (now.date() + timedelta(days=1)):
                    time_str = f"Mañana {start_time.strftime('%H:%M')}"
                else:
                    time_str = start_time.strftime("%d/%m %H:%M")
                
                return f"{class_name} - {time_str}"
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting next class for user {user_id}: {e}")
            return None
    
    async def _compute_fitness_metrics(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> FitnessMetrics:
        """Computa métricas de fitness completas."""
        try:
            from app.models.schedule import ClassParticipation, ClassSession, Class, ClassParticipationStatus
            
            # Query optimizada usando índices compuestos
            # Contar clases asistidas y programadas en una sola query usando agregaciones
            class_counts = db.query(
                func.count(
                    func.case(
                        [(ClassParticipation.status == ClassParticipationStatus.ATTENDED, 1)], 
                        else_=None
                    )
                ).label('attended_classes'),
                func.count(
                    func.case(
                        [(ClassParticipation.status.in_([
                            ClassParticipationStatus.REGISTERED,
                            ClassParticipationStatus.ATTENDED
                        ]), 1)], 
                        else_=None
                    )
                ).label('scheduled_classes')
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.created_at >= period_start,
                ClassParticipation.created_at <= period_end
            ).first()
            
            attended_classes = class_counts.attended_classes or 0
            scheduled_classes = class_counts.scheduled_classes or 0
            
            # Tasa de asistencia
            attendance_rate = (attended_classes / scheduled_classes * 100) if scheduled_classes > 0 else 0.0
            
            # Total de horas de entrenamiento (estimado por duración promedio de clases)
            total_hours_result = db.query(
                func.sum(Class.duration).label('total_minutes')
            ).join(
                ClassSession
            ).join(
                ClassParticipation
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                ClassParticipation.created_at >= period_start,
                ClassParticipation.created_at <= period_end
            ).first()
            
            total_minutes = total_hours_result.total_minutes or 0
            total_workout_hours = total_minutes / 60.0
            
            # Duración promedio de sesión
            avg_duration = (total_minutes / attended_classes) if attended_classes > 0 else 0.0
            
            # Racha actual (calculada anteriormente)
            current_streak = await self._calculate_current_streak_fast(db, user_id, gym_id)
            
            # Racha más larga (simplificado - obtener de los últimos 6 meses)
            six_months_ago = period_end - timedelta(days=180)
            longest_streak = await self._calculate_longest_streak(db, user_id, gym_id, six_months_ago, period_end)
            
            # Tipos de clase favoritos
            favorite_classes_result = db.query(
                Class.name,
                func.count(ClassParticipation.id).label('count')
            ).join(
                ClassSession
            ).join(
                ClassParticipation
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                ClassParticipation.created_at >= period_start,
                ClassParticipation.created_at <= period_end
            ).group_by(
                Class.name
            ).order_by(
                func.count(ClassParticipation.id).desc()
            ).limit(3).all()
            
            favorite_class_types = [result.name for result in favorite_classes_result]
            
            # Horarios pico (simplificado - análisis básico)
            peak_times_result = db.query(
                func.extract('hour', ClassSession.start_time).label('hour'),
                func.count(ClassParticipation.id).label('count')
            ).join(
                ClassParticipation
            ).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                ClassParticipation.created_at >= period_start,
                ClassParticipation.created_at <= period_end
            ).group_by(
                func.extract('hour', ClassSession.start_time)
            ).order_by(
                func.count(ClassParticipation.id).desc()
            ).limit(2).all()
            
            peak_workout_times = []
            for result in peak_times_result:
                hour = int(result.hour)
                time_range = f"{hour:02d}:00-{(hour+1):02d}:00"
                peak_workout_times.append(time_range)
            
            # Estimación de calorías (fórmula básica: ~8 calorías por minuto de ejercicio)
            calories_burned_estimate = int(total_minutes * 8) if total_minutes > 0 else 0
            
            return FitnessMetrics(
                classes_attended=attended_classes,
                classes_scheduled=scheduled_classes,
                attendance_rate=round(attendance_rate, 1),
                total_workout_hours=round(total_workout_hours, 1),
                average_session_duration=round(avg_duration, 1),
                streak_current=current_streak,
                streak_longest=longest_streak,
                favorite_class_types=favorite_class_types,
                peak_workout_times=peak_workout_times,
                calories_burned_estimate=calories_burned_estimate
            )
            
        except Exception as e:
            logger.error(f"Error computing fitness metrics: {e}")
            raise
    
    async def _compute_events_metrics(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> EventsMetrics:
        """Computa métricas de eventos."""
        try:
            from app.models.event import EventParticipation, Event, EventParticipationStatus
            from app.models.user import User
            
            # Query base para participaciones en eventos del período
            base_query = db.query(EventParticipation).join(
                Event
            ).filter(
                EventParticipation.member_id == user_id,
                EventParticipation.gym_id == gym_id,
                Event.start_time >= period_start,
                Event.start_time <= period_end
            )
            
            # Eventos asistidos (marcados como asistidos)
            events_attended = base_query.filter(
                EventParticipation.attended == True
            ).count()
            
            # Eventos registrados (incluyendo asistidos)
            events_registered = base_query.filter(
                EventParticipation.status == EventParticipationStatus.REGISTERED
            ).count()
            
            # Tasa de asistencia
            attendance_rate = (events_attended / events_registered * 100) if events_registered > 0 else 0.0
            
            # Eventos creados (si el usuario es trainer/admin)
            events_created = db.query(Event).filter(
                Event.creator_id == user_id,
                Event.gym_id == gym_id,
                Event.start_time >= period_start,
                Event.start_time <= period_end
            ).count()
            
            # Tipos de evento favoritos (basado en la descripción del evento)
            # Simplificado: análisis de palabras clave en títulos
            favorite_events_result = db.query(
                Event.title,
                func.count(EventParticipation.id).label('count')
            ).join(
                EventParticipation
            ).filter(
                EventParticipation.member_id == user_id,
                EventParticipation.gym_id == gym_id,
                EventParticipation.attended == True,
                Event.start_time >= period_start,
                Event.start_time <= period_end
            ).group_by(
                Event.title
            ).order_by(
                func.count(EventParticipation.id).desc()
            ).limit(5).all()
            
            # Extraer tipos de eventos de los títulos (análisis básico)
            favorite_event_types = []
            for result in favorite_events_result:
                title = result.title.lower()
                if 'workshop' in title or 'taller' in title:
                    favorite_event_types.append("Workshop")
                elif 'competition' in title or 'competencia' in title:
                    favorite_event_types.append("Competition")
                elif 'training' in title or 'entrenamiento' in title:
                    favorite_event_types.append("Training")
                elif 'social' in title:
                    favorite_event_types.append("Social")
                else:
                    # Usar primera palabra del título como tipo
                    first_word = title.split()[0].capitalize() if title.split() else "Event"
                    favorite_event_types.append(first_word)
            
            # Remover duplicados y mantener orden
            favorite_event_types = list(dict.fromkeys(favorite_event_types))[:3]
            
            return EventsMetrics(
                events_attended=events_attended,
                events_registered=events_registered,
                events_created=events_created,
                attendance_rate=round(attendance_rate, 1),
                favorite_event_types=favorite_event_types
            )
            
        except Exception as e:
            logger.error(f"Error computing events metrics: {e}")
            raise
    
    async def _compute_social_metrics(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> SocialMetrics:
        """Computa métricas sociales y de chat."""
        try:
            from app.models.chat import ChatMember, ChatRoom
            from app.models.user import User, UserRole
            
            # Usar el servicio de chat analytics existente
            user_chat_activity = chat_analytics_service.get_user_chat_activity(db, user_id)
            
            # Extraer métricas del resultado del servicio
            if "error" not in user_chat_activity:
                chat_rooms_active = user_chat_activity.get("total_rooms", 0)
                
                # Calcular mensajes enviados (estimación basada en actividad)
                # En un sistema real, esto vendría de Stream Chat API
                chat_messages_sent = max(0, chat_rooms_active * 5)  # Estimación conservadora
                
                # Calcular social score basado en varios factores
                social_score = self._calculate_social_score(
                    chat_rooms_active, 
                    chat_messages_sent, 
                    user_chat_activity.get("recent_activity_days", 0)
                )
            else:
                # Fallback si hay error en chat analytics
                chat_rooms_active = 0
                chat_messages_sent = 0
                social_score = 0.0
            
            # Interacciones con entrenadores (basado en membresías de salas de chat)
            # Contar salas donde hay entrenadores o admins
            trainer_interactions = db.query(ChatMember).join(
                ChatRoom
            ).join(
                User, ChatMember.user_id == User.id
            ).filter(
                ChatRoom.gym_id == gym_id,
                ChatMember.user_id == user_id,
                # Buscar otras membresías en las mismas salas que incluyan trainers/admins
                ChatMember.room_id.in_(
                    db.query(ChatMember.room_id).join(
                        User, ChatMember.user_id == User.id
                    ).join(
                        User.user_gyms
                    ).filter(
                        User.user_gyms.any(
                            and_(
                                User.user_gyms.property.mapper.class_.gym_id == gym_id,
                                User.user_gyms.property.mapper.class_.role.in_([
                                    UserRole.TRAINER, UserRole.ADMIN
                                ])
                            )
                        )
                    ).distinct()
                )
            ).count()
            
            return SocialMetrics(
                chat_messages_sent=chat_messages_sent,
                chat_rooms_active=chat_rooms_active,
                social_score=round(social_score, 1),
                trainer_interactions=trainer_interactions
            )
            
        except Exception as e:
            logger.error(f"Error computing social metrics: {e}")
            # Fallback con métricas por defecto
            return SocialMetrics(
                chat_messages_sent=0,
                chat_rooms_active=0,
                social_score=0.0,
                trainer_interactions=0
            )
    
    def _calculate_social_score(self, chat_rooms: int, messages: int, recent_days: int) -> float:
        """Calcula un score social basado en actividad de chat."""
        try:
            # Algoritmo básico para social score (0-10)
            # Factores: número de salas, mensajes, días de actividad reciente
            
            rooms_score = min(chat_rooms * 0.5, 4.0)  # Máximo 4 puntos por salas
            messages_score = min(messages * 0.02, 3.0)  # Máximo 3 puntos por mensajes
            activity_score = min(recent_days * 0.5, 3.0)  # Máximo 3 puntos por actividad
            
            total_score = rooms_score + messages_score + activity_score
            return min(total_score, 10.0)  # Cap at 10
            
        except Exception as e:
            logger.error(f"Error calculating social score: {e}")
            return 0.0
    
    async def _compute_health_metrics(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime,
        include_goals: bool
    ) -> HealthMetrics:
        """Computa métricas de salud."""
        try:
            # TODO: Obtener desde user profile y goals system
            goals_progress = []
            if include_goals:
                goals_progress = [
                    {
                        "goal_id": 1,
                        "goal_type": "weight_loss",
                        "target_value": 70,
                        "current_value": 75.5,
                        "progress_percentage": 45.0,
                        "status": GoalStatus.on_track
                    }
                ]
            
            return HealthMetrics(
                current_weight=75.5,
                current_height=175,
                bmi=24.6,
                bmi_category=BMICategory.normal,
                weight_change=-2.1,
                goals_progress=goals_progress
            )
        except Exception as e:
            logger.error(f"Error computing health metrics: {e}")
            raise
    
    async def _compute_membership_utilization(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> MembershipUtilization:
        """Computa utilización de membresía."""
        try:
            from app.models.user_gym import UserGym
            from app.models.membership import MembershipPlan
            from app.models.schedule import ClassParticipation, ClassParticipationStatus
            
            # Obtener la membresía del usuario en este gimnasio
            user_gym = db.query(UserGym).filter(
                UserGym.user_id == user_id,
                UserGym.gym_id == gym_id
            ).first()
            
            if not user_gym:
                # Usuario no tiene membresía en este gimnasio
                return MembershipUtilization(
                    plan_name="No Membership",
                    utilization_rate=0.0,
                    value_score=0.0,
                    days_until_renewal=None,
                    recommended_actions=["Consider getting a membership plan"]
                )
            
            # Obtener el plan de membresía si existe
            membership_plan = None
            if hasattr(user_gym, 'membership_plan_id') and user_gym.membership_plan_id:
                membership_plan = db.query(MembershipPlan).filter(
                    MembershipPlan.id == user_gym.membership_plan_id
                ).first()
            
            plan_name = membership_plan.name if membership_plan else "Basic"
            
            # Calcular utilización basada en clases asistidas vs disponibles
            classes_attended_count = db.query(ClassParticipation).filter(
                ClassParticipation.user_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                ClassParticipation.created_at >= period_start,
                ClassParticipation.created_at <= period_end
            ).count()
            
            # Estimación de clases disponibles (basado en días del período)
            period_days = (period_end - period_start).days
            estimated_available_classes = max(period_days * 2, 1)  # Promedio 2 clases por día disponibles
            
            # Calcular tasa de utilización
            utilization_rate = min((classes_attended_count / estimated_available_classes) * 100, 100.0)
            
            # Calcular value score (0-10) basado en varios factores
            value_score = self._calculate_membership_value_score(
                utilization_rate, 
                classes_attended_count,
                membership_plan
            )
            
            # Calcular días hasta renovación (simplificado)
            days_until_renewal = None
            if user_gym.created_at:
                # Asumir renovación mensual
                next_renewal = user_gym.created_at.replace(day=1) + timedelta(days=32)
                next_renewal = next_renewal.replace(day=1)  # Primer día del siguiente mes
                days_until_renewal = (next_renewal.date() - datetime.now().date()).days
                days_until_renewal = max(days_until_renewal, 0)
            
            # Generar recomendaciones basadas en utilización
            recommended_actions = self._generate_membership_recommendations(
                utilization_rate, 
                classes_attended_count, 
                plan_name
            )
            
            return MembershipUtilization(
                plan_name=plan_name,
                utilization_rate=round(utilization_rate, 1),
                value_score=round(value_score, 1),
                days_until_renewal=days_until_renewal,
                recommended_actions=recommended_actions
            )
            
        except Exception as e:
            logger.error(f"Error computing membership utilization: {e}")
            raise
    
    def _calculate_membership_value_score(self, utilization_rate: float, classes_count: int, plan) -> float:
        """Calcula el value score de la membresía (0-10)."""
        try:
            # Factores para el value score
            utilization_score = min(utilization_rate / 10, 5.0)  # Max 5 puntos por utilización
            activity_score = min(classes_count * 0.1, 3.0)  # Max 3 puntos por actividad
            plan_score = 2.0 if plan else 1.0  # 2 puntos si tiene plan premium, 1 si es básico
            
            total_score = utilization_score + activity_score + plan_score
            return min(total_score, 10.0)
            
        except Exception as e:
            logger.error(f"Error calculating membership value score: {e}")
            return 0.0
    
    def _generate_membership_recommendations(self, utilization_rate: float, classes_count: int, plan_name: str) -> List[str]:
        """Genera recomendaciones para mejorar utilización de membresía."""
        recommendations = []
        
        try:
            if utilization_rate < 30:
                recommendations.append("Try attending more classes to get better value from your membership")
                recommendations.append("Consider scheduling regular workout times")
            elif utilization_rate < 60:
                recommendations.append("You're doing well! Try to attend 1-2 more classes per week")
            elif utilization_rate < 90:
                recommendations.append("Great utilization! Consider trying new class types")
            else:
                recommendations.append("Excellent membership utilization! Keep up the great work")
            
            if classes_count == 0:
                recommendations.append("Book your first class to start your fitness journey")
            elif classes_count < 5:
                recommendations.append("Try to maintain consistency with at least 2-3 classes per week")
            
            if plan_name == "Basic":
                recommendations.append("Consider upgrading to Premium for access to more classes")
            
            return recommendations[:3]  # Máximo 3 recomendaciones
            
        except Exception as e:
            logger.error(f"Error generating membership recommendations: {e}")
            return ["Keep up the great work with your fitness journey!"]
    
    async def _get_recent_achievements(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> List[Achievement]:
        """Obtiene logros recientes."""
        try:
            # TODO: Implementar sistema de achievements
            return [
                Achievement(
                    id=5,
                    type="attendance_streak",
                    name="5 Day Streak",
                    description="Attended classes 5 days in a row",
                    earned_at=datetime(2025, 1, 15, 10, 30),
                    badge_icon="🔥"
                )
            ]
        except Exception as e:
            logger.error(f"Error getting achievements: {e}")
            return []
    
    async def _analyze_trends(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        period_start: datetime,
        period_end: datetime
    ) -> TrendAnalysis:
        """Analiza tendencias del usuario."""
        try:
            # TODO: Implementar análisis real de tendencias
            return TrendAnalysis(
                attendance_trend=TrendDirection.increasing,
                workout_intensity_trend=TrendDirection.stable,
                social_engagement_trend=TrendDirection.increasing
            )
        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            raise
    
    async def _generate_recommendations(
        self,
        fitness: FitnessMetrics,
        events: EventsMetrics,
        social: SocialMetrics,
        health: HealthMetrics
    ) -> List[str]:
        """Genera recomendaciones personalizadas basadas en métricas."""
        recommendations = []
        
        try:
            # Lógica de recomendaciones basada en datos
            if fitness.attendance_rate < 70:
                recommendations.append("Try scheduling classes in advance to improve attendance")
            
            if len(fitness.favorite_class_types) < 3:
                recommendations.append("Try a new class type to improve variety score")
            
            if social.social_score < 5:
                recommendations.append("Join community chats to connect with other members")
            
            if events.attendance_rate < 50:
                recommendations.append("Consider attending more gym events to meet fitness goals")
            
            # Recomendaciones por defecto si no hay datos suficientes
            if not recommendations:
                recommendations = [
                    "Keep up the great work!",
                    "Consider setting new fitness goals",
                    "Try connecting with other members"
                ]
                
        except Exception as e:
            logger.error(f"Error generating recommendations: {e}")
            recommendations = ["Keep up the great work!"]
        
        return recommendations
    
    def _calculate_period_dates(self, period: PeriodType) -> tuple[datetime, datetime]:
        """Calcula fechas de inicio y fin para el período especificado."""
        now = datetime.now()
        
        if period == PeriodType.week:
            start = now - timedelta(days=7)
            end = now
        elif period == PeriodType.month:
            start = now.replace(day=1)
            end = now
        elif period == PeriodType.quarter:
            # Calcular inicio del trimestre
            quarter_start_month = ((now.month - 1) // 3) * 3 + 1
            start = now.replace(month=quarter_start_month, day=1)
            end = now
        elif period == PeriodType.year:
            start = now.replace(month=1, day=1)
            end = now
        else:
            # Default a mes
            start = now.replace(day=1)
            end = now
        
        return start, end


# Instancia global del servicio
user_stats_service = UserStatsService()