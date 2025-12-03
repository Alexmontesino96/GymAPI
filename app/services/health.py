"""
Servicio de health tracking y metas de usuario.

Este servicio maneja toda la lógica de negocio relacionada con:
- Tracking de mediciones de salud (peso, grasa corporal, etc.)
- Sistema de metas y objetivos personales
- Cálculo automático de achievements y logros
- Snapshots diarios para análisis de tendencias
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc, asc
from redis.asyncio import Redis

from app.models.health import (
    UserHealthRecord, UserGoal, UserAchievement, UserHealthSnapshot,
    MeasurementType, GoalType, GoalStatus, AchievementType
)
from app.models.user import User
from app.models.schedule import ClassParticipation, ClassParticipationStatus
from app.schemas.user_stats import (
    GoalProgress, Achievement, HealthMetrics, BMICategory
)
from app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class UserHealthService:
    """
    Servicio para gestión completa de health tracking de usuarios.
    """
    
    def __init__(self):
        self.cache_service = CacheService()
    
    # === Health Records Management ===
    
    def record_measurement(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        weight: Optional[float] = None,
        body_fat_percentage: Optional[float] = None,
        muscle_mass: Optional[float] = None,
        measurement_type: MeasurementType = MeasurementType.MANUAL,
        notes: Optional[str] = None
    ) -> UserHealthRecord:
        """
        Registra una nueva medición de salud.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            weight: Peso en kg
            body_fat_percentage: Porcentaje de grasa corporal
            muscle_mass: Masa muscular en kg
            measurement_type: Tipo de medición
            notes: Notas adicionales
            
        Returns:
            UserHealthRecord: Registro creado
        """
        try:
            record = UserHealthRecord(
                user_id=user_id,
                gym_id=gym_id,
                weight=weight,
                body_fat_percentage=body_fat_percentage,
                muscle_mass=muscle_mass,
                measurement_type=measurement_type,
                notes=notes,
                recorded_at=datetime.utcnow()
            )
            
            db.add(record)
            db.commit()
            db.refresh(record)
            
            # Actualizar campos básicos en User para backward compatibility
            if weight is not None:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.weight = weight
                    db.commit()
            
            # Invalidar caches relacionadas
            self._invalidate_health_caches(user_id, gym_id)
            
            logger.info(f"Health measurement recorded for user {user_id}, gym {gym_id}")
            return record
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error recording health measurement: {e}")
            raise
    
    def get_latest_measurement(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> Optional[UserHealthRecord]:
        """Obtiene la medición más reciente del usuario."""
        return db.query(UserHealthRecord).filter(
            UserHealthRecord.user_id == user_id,
            UserHealthRecord.gym_id == gym_id
        ).order_by(desc(UserHealthRecord.recorded_at)).first()
    
    def get_weight_history(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        days: int = 90
    ) -> List[UserHealthRecord]:
        """
        Obtiene historial de peso de los últimos N días.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            days: Número de días a obtener
            
        Returns:
            Lista de registros de peso
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return db.query(UserHealthRecord).filter(
            UserHealthRecord.user_id == user_id,
            UserHealthRecord.gym_id == gym_id,
            UserHealthRecord.weight.isnot(None),
            UserHealthRecord.recorded_at >= cutoff_date
        ).order_by(asc(UserHealthRecord.recorded_at)).all()
    
    # === Goals Management ===
    
    def create_goal(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        goal_type: GoalType,
        title: str,
        target_value: float,
        unit: str,
        target_date: Optional[date] = None,
        description: Optional[str] = None,
        current_value: float = 0.0
    ) -> UserGoal:
        """
        Crea un nuevo objetivo para el usuario.
        
        Args:
            db: Sesión de base de datos
            user_id: ID del usuario
            gym_id: ID del gimnasio
            goal_type: Tipo de objetivo
            title: Título del objetivo
            target_value: Valor objetivo
            unit: Unidad de medida
            target_date: Fecha objetivo
            description: Descripción
            current_value: Valor inicial actual
            
        Returns:
            UserGoal: Objetivo creado
        """
        try:
            # Obtener valor inicial si es un objetivo de peso
            start_value = current_value
            if goal_type in [GoalType.WEIGHT_LOSS, GoalType.WEIGHT_GAIN]:
                latest_measurement = self.get_latest_measurement(db, user_id, gym_id)
                if latest_measurement and latest_measurement.weight:
                    start_value = latest_measurement.weight
                    current_value = latest_measurement.weight
            
            goal = UserGoal(
                user_id=user_id,
                gym_id=gym_id,
                goal_type=goal_type,
                title=title,
                description=description,
                target_value=target_value,
                current_value=current_value,
                start_value=start_value,
                unit=unit,
                target_date=target_date,
                status=GoalStatus.ACTIVE
            )
            
            db.add(goal)
            db.commit()
            db.refresh(goal)
            
            logger.info(f"Goal created for user {user_id}: {title}")
            return goal
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating goal: {e}")
            raise
    
    def update_goal_progress(
        self,
        db: Session,
        goal_id: int,
        current_value: float
    ) -> UserGoal:
        """
        Actualiza el progreso de un objetivo.
        
        Args:
            db: Sesión de base de datos
            goal_id: ID del objetivo
            current_value: Nuevo valor actual
            
        Returns:
            UserGoal: Objetivo actualizado
        """
        try:
            goal = db.query(UserGoal).filter(UserGoal.id == goal_id).first()
            if not goal:
                raise ValueError(f"Goal {goal_id} not found")
            
            goal.current_value = current_value
            
            # Verificar si el objetivo se completó
            if self._is_goal_completed(goal):
                goal.status = GoalStatus.COMPLETED
                goal.completed_at = datetime.utcnow()
                
                # Crear achievement automático
                self._create_goal_achievement(db, goal)
            
            db.commit()
            logger.info(f"Goal {goal_id} progress updated to {current_value}")
            return goal
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating goal progress: {e}")
            raise
    
    def get_active_goals(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> List[UserGoal]:
        """Obtiene todos los objetivos activos del usuario."""
        return db.query(UserGoal).filter(
            UserGoal.user_id == user_id,
            UserGoal.gym_id == gym_id,
            UserGoal.status == GoalStatus.ACTIVE
        ).order_by(desc(UserGoal.created_at)).all()
    
    def get_goals_progress(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> List[GoalProgress]:
        """
        Obtiene el progreso de todos los objetivos activos.
        
        Returns:
            Lista de GoalProgress para usar en schemas
        """
        goals = self.get_active_goals(db, user_id, gym_id)
        progress_list = []
        
        for goal in goals:
            progress_percentage = self._calculate_goal_progress_percentage(goal)
            status = self._determine_goal_status(goal, progress_percentage)
            
            progress = GoalProgress(
                goal_id=goal.id,
                goal_type=goal.goal_type.value,
                target_value=goal.target_value,
                current_value=goal.current_value,
                progress_percentage=progress_percentage,
                status=status
            )
            progress_list.append(progress)
        
        return progress_list
    
    # === Achievements Management ===
    
    def check_and_create_achievements(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """
        Revisa y crea achievements automáticamente basados en la actividad del usuario.
        
        Returns:
            Lista de nuevos achievements creados
        """
        new_achievements = []
        
        try:
            # Check attendance streak achievements
            streak_achievements = self._check_attendance_streak_achievements(db, user_id, gym_id)
            new_achievements.extend(streak_achievements)
            
            # Check class milestone achievements
            milestone_achievements = self._check_class_milestone_achievements(db, user_id, gym_id)
            new_achievements.extend(milestone_achievements)
            
            # Check weight goal achievements (ya manejados en update_goal_progress)
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error checking achievements for user {user_id}: {e}")
            return []
    
    def get_user_achievements(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        limit: int = 10
    ) -> List[UserAchievement]:
        """Obtiene los achievements más recientes del usuario."""
        return db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.gym_id == gym_id
        ).order_by(desc(UserAchievement.earned_at)).limit(limit).all()
    
    def get_recent_achievement(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> Optional[Achievement]:
        """
        Obtiene el achievement más reciente para usar en dashboard.
        
        Returns:
            Achievement schema o None si no hay achievements recientes
        """
        recent = db.query(UserAchievement).filter(
            UserAchievement.user_id == user_id,
            UserAchievement.gym_id == gym_id
        ).order_by(desc(UserAchievement.earned_at)).first()
        
        if not recent:
            return None
        
        return Achievement(
            id=recent.id,
            type=recent.achievement_type.value,
            name=recent.title,
            description=recent.description,
            earned_at=recent.earned_at,
            badge_icon=recent.icon
        )
    
    # === Health Metrics Calculation ===
    
    def calculate_health_metrics(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        include_goals: bool = True
    ) -> HealthMetrics:
        """
        Calcula métricas de salud reales basadas en datos del usuario.
        
        Returns:
            HealthMetrics con datos reales del usuario
        """
        try:
            # Obtener medición más reciente
            latest_measurement = self.get_latest_measurement(db, user_id, gym_id)
            
            # Obtener datos base del usuario
            user = db.query(User).filter(User.id == user_id).first()
            
            current_weight = None
            current_height = None
            bmi = None
            bmi_category = None
            
            if latest_measurement:
                current_weight = latest_measurement.weight
            elif user and user.weight:
                current_weight = user.weight
            
            if user and user.height:
                current_height = user.height
            
            # Calcular BMI si tenemos peso y altura
            if current_weight and current_height:
                # Validar rangos razonables (peso: 20-500kg, altura: 50-250cm)
                if not (20 <= current_weight <= 500):
                    logger.warning(f"Peso fuera de rango razonable para usuario {user_id}: {current_weight}kg")
                    current_weight = None
                elif not (50 <= current_height <= 250):
                    logger.warning(f"Altura fuera de rango razonable para usuario {user_id}: {current_height}cm")
                    current_height = None
                else:
                    # BMI = peso(kg) / (altura(m))^2
                    height_m = current_height / 100
                    calculated_bmi = round(current_weight / (height_m ** 2), 1)
                    # Validar BMI resultante
                    if 10 <= calculated_bmi <= 50:
                        bmi = calculated_bmi
                        bmi_category = self._calculate_bmi_category(bmi)
                    else:
                        logger.warning(f"BMI calculado fuera de rango razonable para usuario {user_id}: {calculated_bmi}")
                        bmi = None
                        bmi_category = None
            
            # Calcular cambio de peso en los últimos 30 días
            weight_change = self._calculate_weight_change(db, user_id, gym_id, days=30)
            
            # Obtener progreso de objetivos si se solicita
            goals_progress = []
            if include_goals:
                goals_progress = self.get_goals_progress(db, user_id, gym_id)
            
            return HealthMetrics(
                current_weight=current_weight,
                current_height=current_height,
                bmi=bmi,
                bmi_category=bmi_category,
                weight_change=weight_change,
                goals_progress=goals_progress
            )
            
        except Exception as e:
            logger.error(f"Error calculating health metrics for user {user_id}: {e}")
            raise
    
    # === Helper Methods ===
    
    def _invalidate_health_caches(self, user_id: int, gym_id: int):
        """Invalida caches relacionadas con health data."""
        # TODO: Implementar invalidación de caches específicas
        pass
    
    def _is_goal_completed(self, goal: UserGoal) -> bool:
        """Determina si un objetivo se ha completado."""
        if goal.goal_type == GoalType.WEIGHT_LOSS:
            return goal.current_value <= goal.target_value
        elif goal.goal_type == GoalType.WEIGHT_GAIN:
            return goal.current_value >= goal.target_value
        else:
            return goal.current_value >= goal.target_value
    
    def _calculate_goal_progress_percentage(self, goal: UserGoal) -> float:
        """Calcula el porcentaje de progreso de un objetivo."""
        if goal.start_value is None:
            return 0.0
        
        if goal.goal_type == GoalType.WEIGHT_LOSS:
            total_needed = goal.start_value - goal.target_value
            achieved = goal.start_value - goal.current_value
        elif goal.goal_type == GoalType.WEIGHT_GAIN:
            total_needed = goal.target_value - goal.start_value
            achieved = goal.current_value - goal.start_value
        else:
            total_needed = goal.target_value - goal.start_value
            achieved = goal.current_value - goal.start_value
        
        if total_needed <= 0:
            return 100.0
        
        progress = (achieved / total_needed) * 100
        return max(0.0, min(100.0, progress))
    
    def _determine_goal_status(self, goal: UserGoal, progress_percentage: float) -> str:
        """Determina el estado de un objetivo basado en su progreso."""
        if progress_percentage >= 100:
            return "completed"
        elif progress_percentage >= 75:
            return "on_track"
        elif progress_percentage >= 25:
            return "behind"
        else:
            return "behind"
    
    def _calculate_bmi_category(self, bmi: float) -> BMICategory:
        """Calcula la categoría de BMI."""
        if bmi < 18.5:
            return BMICategory.underweight
        elif bmi < 25:
            return BMICategory.normal
        elif bmi < 30:
            return BMICategory.overweight
        else:
            return BMICategory.obese
    
    def _calculate_weight_change(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        days: int = 30
    ) -> Optional[float]:
        """Calcula el cambio de peso en los últimos N días."""
        history = self.get_weight_history(db, user_id, gym_id, days)
        
        if len(history) < 2:
            return None
        
        oldest_weight = history[0].weight
        latest_weight = history[-1].weight
        
        if oldest_weight and latest_weight:
            return round(latest_weight - oldest_weight, 1)
        
        return None
    
    def _create_goal_achievement(self, db: Session, goal: UserGoal):
        """Crea un achievement automático cuando se completa un objetivo."""
        try:
            title = f"Meta Alcanzada: {goal.title}"
            description = f"¡Felicitaciones! Has completado tu objetivo de {goal.goal_type.value}"
            icon = "🎯"
            
            if goal.goal_type == GoalType.WEIGHT_LOSS:
                icon = "⚖️"
                description = f"¡Has perdido {goal.start_value - goal.current_value:.1f} {goal.unit}!"
            elif goal.goal_type == GoalType.WEIGHT_GAIN:
                icon = "💪"
                description = f"¡Has ganado {goal.current_value - goal.start_value:.1f} {goal.unit}!"
            
            achievement = UserAchievement(
                user_id=goal.user_id,
                gym_id=goal.gym_id,
                achievement_type=AchievementType.WEIGHT_GOAL,
                title=title,
                description=description,
                icon=icon,
                value=abs(goal.current_value - goal.start_value),
                unit=goal.unit,
                rarity="rare",
                is_milestone=True,
                points_awarded=50
            )
            
            db.add(achievement)
            db.commit()
            
            logger.info(f"Goal achievement created for user {goal.user_id}")
            
        except Exception as e:
            logger.error(f"Error creating goal achievement: {e}")
    
    def _check_attendance_streak_achievements(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """Verifica y crea achievements de racha de asistencia."""
        new_achievements = []
        
        try:
            # Calcular racha actual
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            attendance_dates = db.query(
                func.date(ClassParticipation.created_at).label('attendance_date')
            ).filter(
                ClassParticipation.member_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                func.date(ClassParticipation.created_at) >= thirty_days_ago
            ).distinct().order_by(
                func.date(ClassParticipation.created_at).desc()
            ).all()
            
            if not attendance_dates:
                return new_achievements
            
            # Calcular racha actual
            current_streak = 0
            today = date.today()
            
            for i, record in enumerate(attendance_dates):
                expected_date = today - timedelta(days=i)
                if record.attendance_date == expected_date:
                    current_streak += 1
                else:
                    break
            
            # Verificar achievements de racha
            streak_milestones = [7, 14, 21, 30]
            
            for milestone in streak_milestones:
                if current_streak >= milestone:
                    # Verificar si ya existe este achievement
                    existing = db.query(UserAchievement).filter(
                        UserAchievement.user_id == user_id,
                        UserAchievement.gym_id == gym_id,
                        UserAchievement.achievement_type == AchievementType.ATTENDANCE_STREAK,
                        UserAchievement.value == milestone
                    ).first()
                    
                    if not existing:
                        achievement = UserAchievement(
                            user_id=user_id,
                            gym_id=gym_id,
                            achievement_type=AchievementType.ATTENDANCE_STREAK,
                            title=f"Racha de {milestone} Días",
                            description=f"¡Has entrenado {milestone} días consecutivos!",
                            icon="🔥",
                            value=milestone,
                            unit="días",
                            rarity="common" if milestone <= 7 else "rare" if milestone <= 14 else "epic",
                            points_awarded=milestone * 2
                        )
                        
                        db.add(achievement)
                        new_achievements.append(achievement)
            
            if new_achievements:
                db.commit()
                logger.info(f"Created {len(new_achievements)} streak achievements for user {user_id}")
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error checking streak achievements: {e}")
            return []
    
    def _check_class_milestone_achievements(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """Verifica y crea achievements de hitos de clases."""
        new_achievements = []
        
        try:
            # Contar total de clases asistidas
            total_classes = db.query(ClassParticipation).filter(
                ClassParticipation.member_id == user_id,
                ClassParticipation.gym_id == gym_id,
                ClassParticipation.status == ClassParticipationStatus.ATTENDED
            ).count()
            
            # Milestones de clases
            class_milestones = [10, 25, 50, 100, 250, 500]
            
            for milestone in class_milestones:
                if total_classes >= milestone:
                    # Verificar si ya existe este achievement
                    existing = db.query(UserAchievement).filter(
                        UserAchievement.user_id == user_id,
                        UserAchievement.gym_id == gym_id,
                        UserAchievement.achievement_type == AchievementType.CLASS_MILESTONE,
                        UserAchievement.value == milestone
                    ).first()
                    
                    if not existing:
                        rarity = "common"
                        if milestone >= 100:
                            rarity = "epic"
                        elif milestone >= 50:
                            rarity = "rare"
                        
                        achievement = UserAchievement(
                            user_id=user_id,
                            gym_id=gym_id,
                            achievement_type=AchievementType.CLASS_MILESTONE,
                            title=f"{milestone} Clases Completadas",
                            description=f"¡Has completado {milestone} clases en el gimnasio!",
                            icon="🏆",
                            value=milestone,
                            unit="clases",
                            rarity=rarity,
                            points_awarded=milestone // 2
                        )
                        
                        db.add(achievement)
                        new_achievements.append(achievement)
            
            if new_achievements:
                db.commit()
                logger.info(f"Created {len(new_achievements)} class milestone achievements for user {user_id}")
            
            return new_achievements
            
        except Exception as e:
            logger.error(f"Error checking class milestone achievements: {e}")
            return []

    # ==========================================
    # MÉTODOS ASYNC (FASE 2 - SEMANA 4)
    # ==========================================

    async def record_measurement_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int,
        weight: Optional[float] = None,
        body_fat_percentage: Optional[float] = None,
        muscle_mass: Optional[float] = None,
        measurement_type: MeasurementType = MeasurementType.MANUAL,
        notes: Optional[str] = None
    ) -> UserHealthRecord:
        """Registra una nueva medición de salud (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        try:
            record = UserHealthRecord(
                user_id=user_id,
                gym_id=gym_id,
                weight=weight,
                body_fat_percentage=body_fat_percentage,
                muscle_mass=muscle_mass,
                measurement_type=measurement_type,
                notes=notes,
                recorded_at=datetime.utcnow()
            )

            db.add(record)
            await db.flush()
            await db.refresh(record)

            # Actualizar campos básicos en User para backward compatibility
            if weight is not None:
                stmt = select(User).where(User.id == user_id)
                result = await db.execute(stmt)
                user = result.scalar_one_or_none()
                if user:
                    user.weight = weight
                    await db.flush()

            # Invalidar caches relacionadas
            self._invalidate_health_caches(user_id, gym_id)

            logger.info(f"Health measurement recorded for user {user_id}, gym {gym_id}")
            return record

        except Exception as e:
            await db.rollback()
            logger.error(f"Error recording health measurement: {e}")
            raise

    async def get_latest_measurement_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> Optional[UserHealthRecord]:
        """Obtiene la medición más reciente del usuario (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        stmt = (
            select(UserHealthRecord)
            .where(
                and_(
                    UserHealthRecord.user_id == user_id,
                    UserHealthRecord.gym_id == gym_id
                )
            )
            .order_by(desc(UserHealthRecord.recorded_at))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_weight_history_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int,
        days: int = 90
    ) -> List[UserHealthRecord]:
        """Obtiene historial de peso de los últimos N días (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        stmt = (
            select(UserHealthRecord)
            .where(
                and_(
                    UserHealthRecord.user_id == user_id,
                    UserHealthRecord.gym_id == gym_id,
                    UserHealthRecord.weight.isnot(None),
                    UserHealthRecord.recorded_at >= cutoff_date
                )
            )
            .order_by(asc(UserHealthRecord.recorded_at))
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def create_goal_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int,
        goal_type: GoalType,
        title: str,
        target_value: float,
        unit: str,
        target_date: Optional[date] = None,
        description: Optional[str] = None,
        current_value: float = 0.0
    ) -> UserGoal:
        """Crea un nuevo objetivo para el usuario (async)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        try:
            # Obtener valor inicial si es un objetivo de peso
            start_value = current_value
            if goal_type in [GoalType.WEIGHT_LOSS, GoalType.WEIGHT_GAIN]:
                latest_measurement = await self.get_latest_measurement_async(db, user_id, gym_id)
                if latest_measurement and latest_measurement.weight:
                    start_value = latest_measurement.weight
                    current_value = latest_measurement.weight

            goal = UserGoal(
                user_id=user_id,
                gym_id=gym_id,
                goal_type=goal_type,
                title=title,
                description=description,
                target_value=target_value,
                current_value=current_value,
                start_value=start_value,
                unit=unit,
                target_date=target_date,
                status=GoalStatus.ACTIVE
            )

            db.add(goal)
            await db.flush()
            await db.refresh(goal)

            self._invalidate_health_caches(user_id, gym_id)
            logger.info(f"Goal created for user {user_id}: {title}")

            return goal

        except Exception as e:
            await db.rollback()
            logger.error(f"Error creating goal: {e}")
            raise

    async def update_goal_progress_async(
        self,
        db,  # AsyncSession
        goal_id: int,
        current_value: float
    ) -> UserGoal:
        """Actualiza el progreso de un objetivo (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        try:
            stmt = select(UserGoal).where(UserGoal.id == goal_id)
            result = await db.execute(stmt)
            goal = result.scalar_one_or_none()

            if not goal:
                raise ValueError(f"Goal {goal_id} not found")

            goal.current_value = current_value
            goal.updated_at = datetime.utcnow()

            # Actualizar estado del objetivo
            progress_percentage = self._calculate_goal_progress_percentage(goal)
            goal.status = self._determine_goal_status(goal, progress_percentage)

            # Si se completó, crear achievement
            if goal.status == GoalStatus.COMPLETED and goal.completed_at is None:
                goal.completed_at = datetime.utcnow()
                await self._create_goal_achievement_async(db, goal)

            await db.flush()
            await db.refresh(goal)

            self._invalidate_health_caches(goal.user_id, goal.gym_id)
            logger.info(f"Goal {goal_id} progress updated: {current_value}/{goal.target_value} {goal.unit}")

            return goal

        except Exception as e:
            await db.rollback()
            logger.error(f"Error updating goal progress: {e}")
            raise

    async def get_active_goals_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> List[UserGoal]:
        """Obtiene objetivos activos del usuario (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        stmt = (
            select(UserGoal)
            .where(
                and_(
                    UserGoal.user_id == user_id,
                    UserGoal.gym_id == gym_id,
                    UserGoal.status == GoalStatus.ACTIVE
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_goals_progress_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> List[GoalProgress]:
        """Obtiene progreso de todos los objetivos activos (async)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        goals = await self.get_active_goals_async(db, user_id, gym_id)

        progress_list = []
        for goal in goals:
            progress_percentage = self._calculate_goal_progress_percentage(goal)

            progress = GoalProgress(
                goal_id=goal.id,
                title=goal.title,
                goal_type=goal.goal_type.value,
                current_value=goal.current_value,
                target_value=goal.target_value,
                unit=goal.unit,
                progress_percentage=progress_percentage,
                status=goal.status.value,
                target_date=goal.target_date,
                created_at=goal.created_at
            )
            progress_list.append(progress)

        return progress_list

    async def check_and_create_achievements_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """Verifica y crea achievements basados en actividad reciente (async)."""
        from sqlalchemy.ext.asyncio import AsyncSession

        try:
            new_achievements = []

            # Verificar achievements de asistencia
            attendance_achievements = await self._check_attendance_streak_achievements_async(
                db, user_id, gym_id
            )
            new_achievements.extend(attendance_achievements)

            # Verificar achievements de clases completadas
            class_achievements = await self._check_class_milestone_achievements_async(
                db, user_id, gym_id
            )
            new_achievements.extend(class_achievements)

            if new_achievements:
                await db.flush()

            return new_achievements

        except Exception as e:
            logger.error(f"Error checking achievements: {e}")
            return []

    async def get_user_achievements_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """Obtiene todos los achievements del usuario (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        stmt = (
            select(UserAchievement)
            .where(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.gym_id == gym_id
                )
            )
            .order_by(desc(UserAchievement.earned_at))
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def get_recent_achievement_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int,
        hours: int = 24
    ) -> Optional[UserAchievement]:
        """Obtiene el achievement más reciente del usuario (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        stmt = (
            select(UserAchievement)
            .where(
                and_(
                    UserAchievement.user_id == user_id,
                    UserAchievement.gym_id == gym_id,
                    UserAchievement.earned_at >= cutoff_time
                )
            )
            .order_by(desc(UserAchievement.earned_at))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def calculate_health_metrics_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> HealthMetrics:
        """Calcula métricas de salud completas del usuario (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        # Obtener usuario para altura
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        # Obtener medición más reciente
        latest_measurement = await self.get_latest_measurement_async(db, user_id, gym_id)

        # Calcular BMI si hay peso y altura
        bmi = None
        bmi_category = None
        if latest_measurement and latest_measurement.weight and user and user.height:
            height_m = user.height / 100
            bmi = round(latest_measurement.weight / (height_m ** 2), 1)
            bmi_category = self._calculate_bmi_category(bmi)

        # Calcular cambio de peso
        weight_change_30d = await self._calculate_weight_change_async(
            db, user_id, gym_id, days=30
        )
        weight_change_7d = await self._calculate_weight_change_async(
            db, user_id, gym_id, days=7
        )

        # Contar asistencias del mes
        start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(func.count(ClassParticipation.id))
            .where(
                and_(
                    ClassParticipation.user_id == user_id,
                    ClassParticipation.gym_id == gym_id,
                    ClassParticipation.status == ClassParticipationStatus.ATTENDED,
                    ClassParticipation.attendance_time >= start_of_month
                )
            )
        )
        result = await db.execute(stmt)
        classes_this_month = result.scalar() or 0

        return HealthMetrics(
            current_weight=latest_measurement.weight if latest_measurement else None,
            body_fat_percentage=latest_measurement.body_fat_percentage if latest_measurement else None,
            muscle_mass=latest_measurement.muscle_mass if latest_measurement else None,
            bmi=bmi,
            bmi_category=bmi_category.value if bmi_category else None,
            weight_change_30d=weight_change_30d,
            weight_change_7d=weight_change_7d,
            classes_attended_this_month=classes_this_month
        )

    # Helper methods async
    async def _create_goal_achievement_async(
        self, db, goal: UserGoal  # AsyncSession
    ):
        """Crea un achievement cuando se completa un objetivo (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        try:
            # Verificar que no exista ya un achievement para este objetivo
            stmt = (
                select(UserAchievement)
                .where(
                    and_(
                        UserAchievement.user_id == goal.user_id,
                        UserAchievement.achievement_type == AchievementType.GOAL_COMPLETED,
                        UserAchievement.related_goal_id == goal.id
                    )
                )
            )
            result = await db.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return

            achievement = UserAchievement(
                user_id=goal.user_id,
                gym_id=goal.gym_id,
                achievement_type=AchievementType.GOAL_COMPLETED,
                title=f"Objetivo Cumplido: {goal.title}",
                description=f"Has alcanzado tu objetivo de {goal.target_value} {goal.unit}",
                icon="🎯",
                value=goal.target_value,
                unit=goal.unit,
                rarity="rare",
                points_awarded=50,
                related_goal_id=goal.id
            )

            db.add(achievement)
            await db.flush()

            logger.info(f"Created goal achievement for user {goal.user_id}")

        except Exception as e:
            logger.error(f"Error creating goal achievement: {e}")

    async def _check_attendance_streak_achievements_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """Verifica y crea achievements de rachas de asistencia (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        # Implementation similar to sync version but with async queries
        # This is a simplified version - full implementation would mirror sync logic
        return []

    async def _check_class_milestone_achievements_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int
    ) -> List[UserAchievement]:
        """Verifica y crea achievements de hitos de clases (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        # Implementation similar to sync version but with async queries
        # This is a simplified version - full implementation would mirror sync logic
        return []

    async def _calculate_weight_change_async(
        self,
        db,  # AsyncSession
        user_id: int,
        gym_id: int,
        days: int
    ) -> Optional[float]:
        """Calcula el cambio de peso en un período (async)."""
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

        history = await self.get_weight_history_async(db, user_id, gym_id, days=days)

        if len(history) < 2:
            return None

        first_weight = history[0].weight
        last_weight = history[-1].weight

        if first_weight and last_weight:
            return round(last_weight - first_weight, 1)

        return None


# Singleton instance
health_service = UserHealthService()