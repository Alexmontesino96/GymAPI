"""
Servicio para manejar la lógica de negocio de los planes nutricionales.
"""

from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc, asc
from datetime import datetime, timedelta, date
import json
import logging

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal, MealIngredient,
    NutritionPlanFollower, UserDailyProgress, UserMealCompletion,
    NutritionGoal, DifficultyLevel, BudgetLevel, DietaryRestriction, MealType, PlanType
)
from app.models.user import User
from app.models.gym import Gym
from app.schemas.nutrition import (
    NutritionPlanCreate, NutritionPlanUpdate, NutritionPlanFilters,
    DailyNutritionPlanCreate, DailyNutritionPlanUpdate,
    MealCreate, MealUpdate, MealIngredientCreate,
    NutritionPlanFollowerCreate, UserDailyProgressCreate, UserMealCompletionCreate,
    TodayMealPlan, WeeklyNutritionSummary, UserNutritionDashboard, NutritionAnalytics,
    PlanStatus, ArchivePlanRequest, NutritionDashboardHybrid
)
from app.db.redis_client import get_redis_client
from app.utils.nutrition_serializers import NutritionSerializer

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    pass

class ValidationError(Exception):
    pass

class PermissionError(Exception):
    pass


class NutritionService:
    """Servicio principal para gestión de planes nutricionales."""
    
    def __init__(self, db: Session):
        self.db = db

    # ===== NUTRITION PLANS =====
    
    def create_nutrition_plan(
        self, 
        plan_data: NutritionPlanCreate, 
        creator_id: int, 
        gym_id: int
    ) -> NutritionPlan:
        """Crear un nuevo plan nutricional."""
        
        # Validar que el creador pertenece al gimnasio
        creator = self.db.query(User).filter(User.id == creator_id).first()
        if not creator:
            raise NotFoundError("Usuario no encontrado")
        
        # Convertir tags a JSON si es necesario
        tags_json = None
        if plan_data.tags:
            tags_json = json.dumps(plan_data.tags)
        
        db_plan = NutritionPlan(
            **plan_data.model_dump(exclude={'tags'}),
            creator_id=creator_id,
            gym_id=gym_id,
            tags=tags_json
        )
        
        self.db.add(db_plan)
        self.db.commit()
        self.db.refresh(db_plan)
        
        logger.info(f"Plan nutricional creado: {db_plan.id} por usuario {creator_id}")
        return db_plan
    
    def get_nutrition_plan(self, plan_id: int, gym_id: int) -> NutritionPlan:
        """Obtener un plan nutricional por ID."""
        plan = self.db.query(NutritionPlan).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()
        
        if not plan:
            raise NotFoundError("Plan nutricional no encontrado")
        
        return plan
    
    def get_nutrition_plan_with_details(
        self, 
        plan_id: int, 
        gym_id: int, 
        user_id: Optional[int] = None
    ) -> NutritionPlan:
        """Obtener plan con detalles completos incluyendo días y comidas."""
        plan = self.db.query(NutritionPlan).options(
            selectinload(NutritionPlan.daily_plans).selectinload(DailyNutritionPlan.meals).selectinload(Meal.ingredients),
            joinedload(NutritionPlan.creator),
            selectinload(NutritionPlan.followers)
        ).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()
        
        if not plan:
            raise NotFoundError("Plan nutricional no encontrado")
        
        # Verificar si el usuario puede ver este plan
        if not plan.is_public and user_id:
            # Solo el creador o seguidores pueden ver planes privados
            if plan.creator_id != user_id:
                is_follower = self.db.query(NutritionPlanFollower).filter(
                    NutritionPlanFollower.plan_id == plan_id,
                    NutritionPlanFollower.user_id == user_id,
                    NutritionPlanFollower.is_active == True
                ).first()
                if not is_follower:
                    raise PermissionError("No tienes permisos para ver este plan")
        
        return plan
    
    def list_nutrition_plans(
        self, 
        gym_id: int, 
        filters: Optional[NutritionPlanFilters] = None,
        page: int = 1,
        per_page: int = 20,
        user_id: Optional[int] = None
    ) -> Tuple[List[NutritionPlan], int]:
        """Listar planes nutricionales con filtros y paginación."""
        
        query = self.db.query(NutritionPlan).filter(
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.is_active == True
        )
        
        # Aplicar filtros
        if filters:
            if filters.goal:
                query = query.filter(NutritionPlan.goal == filters.goal)
            
            if filters.difficulty_level:
                query = query.filter(NutritionPlan.difficulty_level == filters.difficulty_level)
            
            if filters.budget_level:
                query = query.filter(NutritionPlan.budget_level == filters.budget_level)
            
            if filters.dietary_restrictions:
                query = query.filter(NutritionPlan.dietary_restrictions == filters.dietary_restrictions)
            
            if filters.duration_days_min:
                query = query.filter(NutritionPlan.duration_days >= filters.duration_days_min)
            
            if filters.duration_days_max:
                query = query.filter(NutritionPlan.duration_days <= filters.duration_days_max)
            
            if filters.creator_id:
                query = query.filter(NutritionPlan.creator_id == filters.creator_id)
            
            if filters.is_public is not None:
                query = query.filter(NutritionPlan.is_public == filters.is_public)
            
            # === NUEVO: Filtros del sistema híbrido ===
            if filters.plan_type:
                query = query.filter(NutritionPlan.plan_type == filters.plan_type)
            
            if filters.is_live_active is not None:
                query = query.filter(NutritionPlan.is_live_active == filters.is_live_active)
            
            if filters.status:
                # Filtrar por estado requiere lógica más compleja
                today = datetime.now()
                
                if filters.status == PlanStatus.NOT_STARTED:
                    # Planes live que no han empezado
                    query = query.filter(
                        and_(
                            NutritionPlan.plan_type == PlanType.LIVE,
                            NutritionPlan.live_start_date > today
                        )
                    )
                elif filters.status == PlanStatus.RUNNING:
                    # Planes activos (live activos o cualquier template/archived)
                    query = query.filter(
                        or_(
                            and_(
                                NutritionPlan.plan_type == PlanType.LIVE,
                                NutritionPlan.is_live_active == True
                            ),
                            NutritionPlan.plan_type.in_([PlanType.TEMPLATE, PlanType.ARCHIVED])
                        )
                    )
                elif filters.status == PlanStatus.FINISHED:
                    # Planes live terminados
                    query = query.filter(
                        and_(
                            NutritionPlan.plan_type == PlanType.LIVE,
                            NutritionPlan.is_live_active == False,
                            NutritionPlan.live_end_date.isnot(None)
                        )
                    )
            
            if filters.search_query:
                search = f"%{filters.search_query}%"
                query = query.filter(
                    or_(
                        NutritionPlan.title.ilike(search),
                        NutritionPlan.description.ilike(search)
                    )
                )
            
            if filters.tags:
                # Buscar planes que contengan al menos uno de los tags
                for tag in filters.tags:
                    query = query.filter(NutritionPlan.tags.like(f'%"{tag}"%'))
        
        # Filtrar planes públicos o del usuario
        if user_id:
            query = query.filter(
                or_(
                    NutritionPlan.is_public == True,
                    NutritionPlan.creator_id == user_id
                )
            )
        else:
            query = query.filter(NutritionPlan.is_public == True)
        
        # Contar total
        total = query.count()
        
        # Aplicar paginación y ordenamiento
        plans = query.order_by(desc(NutritionPlan.created_at)).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
        
        # === NUEVO: Agregar información calculada a cada plan ===
        for plan in plans:
            if plan.plan_type == PlanType.LIVE:
                # Actualizar estado para planes live
                self.update_live_plan_status(plan.id, gym_id)
                
            # Calcular información adicional
            current_day, status = self.get_current_plan_day(plan)
            plan.current_day = current_day
            plan.status = status
            plan.days_until_start = self.get_days_until_start(plan)
        
        return plans, total
    
    def update_nutrition_plan(
        self, 
        plan_id: int, 
        plan_data: NutritionPlanUpdate, 
        user_id: int,
        gym_id: int
    ) -> NutritionPlan:
        """Actualizar un plan nutricional."""
        plan = self.get_nutrition_plan(plan_id, gym_id)
        
        # Verificar permisos (solo el creador puede editar)
        if plan.creator_id != user_id:
            raise PermissionError("Solo el creador puede editar este plan")
        
        # Actualizar campos
        update_data = plan_data.model_dump(exclude_unset=True, exclude={'tags'})
        for field, value in update_data.items():
            setattr(plan, field, value)
        
        # Manejar tags especialmente
        if plan_data.tags is not None:
            plan.tags = json.dumps(plan_data.tags) if plan_data.tags else None
        
        plan.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(plan)
        
        return plan
    
    def delete_nutrition_plan(self, plan_id: int, user_id: int, gym_id: int) -> bool:
        """Eliminar un plan nutricional (soft delete)."""
        plan = self.get_nutrition_plan(plan_id, gym_id)
        
        # Verificar permisos
        if plan.creator_id != user_id:
            raise PermissionError("Solo el creador puede eliminar este plan")
        
        plan.is_active = False
        plan.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        logger.info(f"Plan nutricional eliminado: {plan_id} por usuario {user_id}")
        return True

    # ===== DAILY NUTRITION PLANS =====
    
    def create_daily_plan(
        self, 
        daily_plan_data: DailyNutritionPlanCreate,
        user_id: int
    ) -> DailyNutritionPlan:
        """Crear un plan diario."""
        # Verificar que el plan nutricional existe y el usuario tiene permisos
        nutrition_plan = self.db.query(NutritionPlan).filter(
            NutritionPlan.id == daily_plan_data.nutrition_plan_id
        ).first()
        
        if not nutrition_plan:
            raise NotFoundError("Plan nutricional no encontrado")
        
        if nutrition_plan.creator_id != user_id:
            raise PermissionError("Solo el creador puede añadir días al plan")
        
        db_daily_plan = DailyNutritionPlan(**daily_plan_data.model_dump())
        
        self.db.add(db_daily_plan)
        self.db.commit()
        self.db.refresh(db_daily_plan)
        
        return db_daily_plan
    
    def get_daily_plan_with_meals(
        self, 
        daily_plan_id: int, 
        gym_id: int,
        user_id: Optional[int] = None
    ) -> DailyNutritionPlan:
        """Obtener plan diario con comidas e ingredientes."""
        daily_plan = self.db.query(DailyNutritionPlan).options(
            selectinload(DailyNutritionPlan.meals).selectinload(Meal.ingredients),
            joinedload(DailyNutritionPlan.nutrition_plan)
        ).filter(
            DailyNutritionPlan.id == daily_plan_id
        ).first()
        
        if not daily_plan:
            raise NotFoundError("Plan diario no encontrado")
        
        # Verificar que pertenece al gimnasio correcto
        if daily_plan.nutrition_plan.gym_id != gym_id:
            raise NotFoundError("Plan diario no encontrado")
        
        return daily_plan
    
    def publish_daily_plan(
        self, 
        daily_plan_id: int, 
        user_id: int,
        gym_id: int
    ) -> DailyNutritionPlan:
        """Publicar un plan diario (enviar notificaciones)."""
        daily_plan = self.get_daily_plan_with_meals(daily_plan_id, gym_id)
        
        # Verificar permisos
        if daily_plan.nutrition_plan.creator_id != user_id:
            raise PermissionError("Solo el creador puede publicar el plan")
        
        daily_plan.is_published = True
        daily_plan.published_at = datetime.utcnow()
        
        self.db.commit()
        
        # TODO: Enviar notificaciones a seguidores
        self._notify_followers_new_day(daily_plan)
        
        return daily_plan

    # ===== MEALS =====
    
    def create_meal(self, meal_data: MealCreate, user_id: int) -> Meal:
        """Crear una comida."""
        # Verificar que el plan diario existe y el usuario tiene permisos
        daily_plan = self.db.query(DailyNutritionPlan).join(NutritionPlan).filter(
            DailyNutritionPlan.id == meal_data.daily_plan_id,
            NutritionPlan.creator_id == user_id
        ).first()
        
        if not daily_plan:
            raise NotFoundError("Plan diario no encontrado o sin permisos")
        
        db_meal = Meal(**meal_data.model_dump())
        
        self.db.add(db_meal)
        self.db.commit()
        self.db.refresh(db_meal)
        
        return db_meal
    
    def add_ingredient_to_meal(
        self, 
        ingredient_data: MealIngredientCreate,
        user_id: int
    ) -> MealIngredient:
        """Añadir ingrediente a una comida."""
        # Verificar permisos
        meal = self.db.query(Meal).join(DailyNutritionPlan).join(NutritionPlan).filter(
            Meal.id == ingredient_data.meal_id,
            NutritionPlan.creator_id == user_id
        ).first()
        
        if not meal:
            raise NotFoundError("Comida no encontrada o sin permisos")
        
        # Convertir alternativas a JSON si es necesario
        alternatives_json = None
        if ingredient_data.alternatives:
            alternatives_json = json.dumps(ingredient_data.alternatives)
        
        db_ingredient = MealIngredient(
            **ingredient_data.model_dump(exclude={'alternatives'}),
            alternatives=alternatives_json
        )
        
        self.db.add(db_ingredient)
        self.db.commit()
        self.db.refresh(db_ingredient)
        
        return db_ingredient

    # ===== FOLLOWING PLANS =====
    
    def follow_nutrition_plan(
        self, 
        plan_id: int,
        user_id: int,
        gym_id: int
    ) -> NutritionPlanFollower:
        """Seguir un plan nutricional."""
        # Verificar que el plan existe y es del gimnasio correcto
        plan = self.get_nutrition_plan(plan_id, gym_id)
        
        # Verificar que no está ya siguiendo el plan
        existing = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        ).first()
        
        if existing:
            raise ValidationError("Ya estás siguiendo este plan")
        
        db_follower = NutritionPlanFollower(
            plan_id=plan_id,
            user_id=user_id,
            gym_id=gym_id  # Multi-tenant support
        )
        
        self.db.add(db_follower)
        self.db.commit()
        self.db.refresh(db_follower)
        
        logger.info(f"Usuario {user_id} empezó a seguir plan {plan_id}")
        return db_follower
    
    def unfollow_nutrition_plan(self, plan_id: int, user_id: int, gym_id: int) -> bool:
        """Dejar de seguir un plan nutricional."""
        # Verificar que el plan existe
        self.get_nutrition_plan(plan_id, gym_id)
        
        follower = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        ).first()
        
        if not follower:
            raise NotFoundError("No estás siguiendo este plan")
        
        follower.is_active = False
        follower.end_date = datetime.utcnow()
        follower.updated_at = datetime.utcnow()
        
        self.db.commit()
        
        return True

    # ===== USER PROGRESS =====
    
    def complete_meal(
        self, 
        meal_id: int,
        user_id: int,
        gym_id: int,
        satisfaction_rating: Optional[int] = None,
        photo_url: Optional[str] = None,
        notes: Optional[str] = None
    ) -> UserMealCompletion:
        """Marcar una comida como completada."""
        # Verificar que la comida existe y el usuario sigue el plan
        meal = self.db.query(Meal).join(DailyNutritionPlan).join(NutritionPlan).filter(
            Meal.id == meal_id,
            NutritionPlan.gym_id == gym_id
        ).first()
        
        if not meal:
            raise NotFoundError("Comida no encontrada")
        
        # Verificar que el usuario sigue el plan
        is_following = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == meal.daily_plan.nutrition_plan_id,
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        ).first()
        
        if not is_following:
            raise ValidationError("Debes seguir el plan para marcar comidas como completadas")
        
        # Verificar que no está ya completada
        existing = self.db.query(UserMealCompletion).filter(
            UserMealCompletion.meal_id == meal_id,
            UserMealCompletion.user_id == user_id
        ).first()
        
        if existing:
            raise ValidationError("Esta comida ya está marcada como completada")
        
        db_completion = UserMealCompletion(
            meal_id=meal_id,
            user_id=user_id,
            satisfaction_rating=satisfaction_rating,
            photo_url=photo_url,
            notes=notes
        )
        
        self.db.add(db_completion)
        self.db.commit()
        self.db.refresh(db_completion)
        
        return db_completion
    
    def get_today_meal_plan(self, user_id: int, gym_id: int) -> TodayMealPlan:
        """Obtener el plan de comidas para hoy."""
        today = datetime.now().date()
        
        # Buscar planes que el usuario está siguiendo
        followed_plans = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        ).all()
        
        if not followed_plans:
            return TodayMealPlan(
                date=datetime.combine(today, datetime.min.time()),
                meals=[],
                completion_percentage=0.0
            )
        
        # TODO: Implementar lógica para determinar qué día del plan corresponde a hoy
        # Por ahora, tomar el primer plan activo y el primer día
        plan_follower = followed_plans[0]
        
        daily_plan = self.db.query(DailyNutritionPlan).options(
            selectinload(DailyNutritionPlan.meals).selectinload(Meal.ingredients)
        ).filter(
            DailyNutritionPlan.nutrition_plan_id == plan_follower.plan_id,
            DailyNutritionPlan.day_number == 1  # Simplificado por ahora
        ).first()
        
        if not daily_plan:
            return TodayMealPlan(
                date=datetime.combine(today, datetime.min.time()),
                meals=[],
                completion_percentage=0.0
            )
        
        # Obtener completaciones del usuario para hoy
        completions = self.db.query(UserMealCompletion).filter(
            UserMealCompletion.user_id == user_id,
            func.date(UserMealCompletion.completed_at) == today
        ).all()
        
        completion_ids = {c.meal_id for c in completions}
        
        # Calcular porcentaje de completación
        total_meals = len(daily_plan.meals)
        completed_meals = len([m for m in daily_plan.meals if m.id in completion_ids])
        completion_percentage = (completed_meals / total_meals * 100) if total_meals > 0 else 0
        
        return TodayMealPlan(
            date=datetime.combine(today, datetime.min.time()),
            daily_plan=daily_plan,
            meals=daily_plan.meals,
            completion_percentage=completion_percentage
        )

    # ===== NUEVO: SISTEMA HÍBRIDO =====
    
    def get_current_plan_day(self, plan: NutritionPlan, follower: Optional[NutritionPlanFollower] = None) -> Tuple[int, PlanStatus]:
        """Calcular qué día del plan está corriendo HOY según el tipo de plan"""
        today = datetime.now().date()
        
        if plan.plan_type == PlanType.TEMPLATE:
            # Lógica individual (comportamiento actual)
            if not follower:
                return 0, PlanStatus.NOT_STARTED
            
            days_since_subscription = (today - follower.start_date.date()).days
            
            if plan.is_recurring:
                current_day = (days_since_subscription % plan.duration_days) + 1
                return current_day, PlanStatus.RUNNING
            else:
                if days_since_subscription >= plan.duration_days:
                    return 0, PlanStatus.FINISHED
                return days_since_subscription + 1, PlanStatus.RUNNING
        
        elif plan.plan_type == PlanType.LIVE:
            # Lógica global (nueva)
            if not plan.live_start_date:
                return 0, PlanStatus.NOT_STARTED
            
            plan_start_date = plan.live_start_date.date()
            
            if today < plan_start_date:
                return 0, PlanStatus.NOT_STARTED
            
            days_since_live_start = (today - plan_start_date).days
            
            if plan.is_recurring:
                current_day = (days_since_live_start % plan.duration_days) + 1
                return current_day, PlanStatus.RUNNING
            else:
                if days_since_live_start >= plan.duration_days:
                    return 0, PlanStatus.FINISHED
                return days_since_live_start + 1, PlanStatus.RUNNING
        
        elif plan.plan_type == PlanType.ARCHIVED:
            # Lógica individual (como template)
            if not follower:
                return 0, PlanStatus.NOT_STARTED
            
            days_since_subscription = (today - follower.start_date.date()).days
            
            if plan.is_recurring:
                current_day = (days_since_subscription % plan.duration_days) + 1
                return current_day, PlanStatus.RUNNING
            else:
                if days_since_subscription >= plan.duration_days:
                    return 0, PlanStatus.FINISHED
                return days_since_subscription + 1, PlanStatus.RUNNING
        
        return 0, PlanStatus.NOT_STARTED
    
    def get_days_until_start(self, plan: NutritionPlan) -> Optional[int]:
        """Calcular días hasta que empiece un plan live"""
        if plan.plan_type != PlanType.LIVE or not plan.live_start_date:
            return None
        
        today = datetime.now().date()
        plan_start_date = plan.live_start_date.date()
        
        if today >= plan_start_date:
            return 0  # Ya empezó
        
        return (plan_start_date - today).days
    
    def update_live_plan_status(self, plan_id: int, gym_id: int) -> NutritionPlan:
        """Actualizar el estado de un plan live basado en fechas"""
        plan = self.get_nutrition_plan(plan_id, gym_id)
        
        if plan.plan_type != PlanType.LIVE:
            return plan
        
        today = datetime.now()
        
        # Calcular si debe estar activo
        should_be_active = False
        should_be_finished = False
        
        if plan.live_start_date:
            if today >= plan.live_start_date:
                if plan.is_recurring:
                    should_be_active = True
                else:
                    # Calcular fecha de fin
                    end_date = plan.live_start_date + timedelta(days=plan.duration_days)
                    if today >= end_date:
                        should_be_finished = True
                    else:
                        should_be_active = True
        
        # Actualizar estado si es necesario
        if should_be_finished and plan.is_live_active:
            plan.is_live_active = False
            plan.live_end_date = plan.live_start_date + timedelta(days=plan.duration_days)
            plan.updated_at = datetime.utcnow()
            self.db.commit()
            
            # Trigger archivado automático si es necesario
            self._auto_archive_finished_live_plan(plan)
            
        elif should_be_active and not plan.is_live_active:
            plan.is_live_active = True
            plan.updated_at = datetime.utcnow()
            self.db.commit()
        
        return plan

    def batch_update_live_plan_statuses(
        self,
        plan_ids: List[int],
        gym_id: int
    ) -> Dict[int, NutritionPlan]:
        """
        Actualizar múltiples planes live en UNA SOLA transacción (batch update).

        OPTIMIZATION: Reduce N queries + N commits to 1 query + 1 commit

        Args:
            plan_ids: Lista de IDs de planes live a actualizar
            gym_id: ID del gimnasio

        Returns:
            Dict mapeando plan_id → NutritionPlan actualizado
        """
        if not plan_ids:
            return {}

        # UNA QUERY para obtener todos los planes LIVE
        plans = self.db.query(NutritionPlan).filter(
            NutritionPlan.id.in_(plan_ids),
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.plan_type == PlanType.LIVE
        ).all()

        today = datetime.now()
        updated_plans = {}
        needs_commit = False

        for plan in plans:
            if not plan.live_start_date:
                updated_plans[plan.id] = plan
                continue

            should_be_active = False
            should_be_finished = False

            if today >= plan.live_start_date:
                if plan.is_recurring:
                    should_be_active = True
                else:
                    end_date = plan.live_start_date + timedelta(days=plan.duration_days)
                    if today >= end_date:
                        should_be_finished = True
                    else:
                        should_be_active = True

            # Actualizar estado si es necesario
            if should_be_finished and plan.is_live_active:
                plan.is_live_active = False
                plan.live_end_date = plan.live_start_date + timedelta(days=plan.duration_days)
                plan.updated_at = datetime.utcnow()
                needs_commit = True
                # Trigger archivado automático
                self._auto_archive_finished_live_plan(plan)

            elif should_be_active and not plan.is_live_active:
                plan.is_live_active = True
                plan.updated_at = datetime.utcnow()
                needs_commit = True

            updated_plans[plan.id] = plan

        # UN SOLO COMMIT para todos los cambios
        if needs_commit:
            self.db.commit()
            logger.info(f"Batch updated {len(updated_plans)} live plans for gym {gym_id}")

        return updated_plans

    def create_live_nutrition_plan(
        self, 
        plan_data: NutritionPlanCreate, 
        creator_id: int, 
        gym_id: int
    ) -> NutritionPlan:
        """Crear un plan nutricional tipo LIVE con validaciones especiales"""
        
        if plan_data.plan_type == PlanType.LIVE:
            if not plan_data.live_start_date:
                raise ValidationError("live_start_date es requerido para planes tipo LIVE")
            
            # Validar que la fecha de inicio es futura (opcional, según reglas de negocio)
            # if plan_data.live_start_date <= datetime.now():
            #     raise ValidationError("live_start_date debe ser en el futuro")
        
        # Crear el plan usando el método base
        return self.create_nutrition_plan(plan_data, creator_id, gym_id)
    
    def archive_live_plan(
        self, 
        plan_id: int, 
        user_id: int, 
        gym_id: int,
        archive_request: ArchivePlanRequest
    ) -> NutritionPlan:
        """Archivar manualmente un plan live terminado"""
        plan = self.get_nutrition_plan(plan_id, gym_id)
        
        # Verificar permisos
        if plan.creator_id != user_id:
            raise PermissionError("Solo el creador puede archivar este plan")
        
        if plan.plan_type != PlanType.LIVE:
            raise ValidationError("Solo se pueden archivar planes tipo LIVE")
        
        if plan.is_live_active:
            raise ValidationError("No se puede archivar un plan live que está activo")
        
        if archive_request.create_template_version:
            return self._create_archived_version(plan, archive_request.template_title)
        
        return plan
    
    def get_hybrid_today_meal_plan(self, user_id: int, gym_id: int) -> TodayMealPlan:
        """
        Obtener el plan de comidas para hoy usando lógica híbrida.

        OPTIMIZED: Batch loading to reduce queries from 11+ to 3
        """
        today = datetime.now().date()

        # OPTIMIZATION: Eager loading completo (daily_plans + meals + ingredients)
        followed_plans_query = self.db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan)
                .selectinload(NutritionPlan.daily_plans)
                .selectinload(DailyNutritionPlan.meals)
                .selectinload(Meal.ingredients)
        ).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        )

        followed_plans = followed_plans_query.all()

        if not followed_plans:
            return TodayMealPlan(
                date=datetime.combine(today, datetime.min.time()),
                meals=[],
                completion_percentage=0.0,
                current_day=0,
                status=PlanStatus.NOT_STARTED
            )

        # OPTIMIZATION: Batch update de planes LIVE (1 query + 1 commit en lugar de N)
        live_plan_ids = [f.plan_id for f in followed_plans if f.plan.plan_type == PlanType.LIVE]
        if live_plan_ids:
            updated_live_plans = self.batch_update_live_plan_statuses(live_plan_ids, gym_id)
            # Reemplazar plans con versiones actualizadas
            for follower in followed_plans:
                if follower.plan_id in updated_live_plans:
                    follower.plan = updated_live_plans[follower.plan_id]

        # OPTIMIZATION: Batch loading de completions (1 query en lugar de N)
        all_completions = self.db.query(UserMealCompletion).filter(
            UserMealCompletion.user_id == user_id,
            func.date(UserMealCompletion.completed_at) == today
        ).all()
        completion_ids = {c.meal_id for c in all_completions}

        # Encontrar el plan que tiene contenido para hoy (usando datos ya cargados)
        for plan_follower in followed_plans:
            plan = plan_follower.plan  # Ya actualizado y con eager loading

            # Calcular día actual y estado
            current_day, status = self.get_current_plan_day(plan, plan_follower)

            if current_day > 0:  # Plan tiene contenido para hoy
                # Buscar daily_plan en MEMORIA (ya cargado con selectinload)
                daily_plan = next(
                    (dp for dp in plan.daily_plans if dp.day_number == current_day),
                    None
                )

                if daily_plan:
                    # Calcular porcentaje de completación (usando completion_ids ya cargado)
                    total_meals = len(daily_plan.meals)
                    completed_meals = len([m for m in daily_plan.meals if m.id in completion_ids])
                    completion_percentage = (completed_meals / total_meals * 100) if total_meals > 0 else 0

                    return TodayMealPlan(
                        date=datetime.combine(today, datetime.min.time()),
                        daily_plan=daily_plan,
                        meals=daily_plan.meals,
                        completion_percentage=completion_percentage,
                        plan=plan,
                        current_day=current_day,
                        status=status
                    )

        # Si llegamos aquí, ningún plan tiene contenido para hoy
        # Buscar el próximo plan que va a empezar
        for plan_follower in followed_plans:
            plan = plan_follower.plan
            current_day, status = self.get_current_plan_day(plan, plan_follower)

            if status == PlanStatus.NOT_STARTED:
                days_until_start = self.get_days_until_start(plan)

                return TodayMealPlan(
                    date=datetime.combine(today, datetime.min.time()),
                    meals=[],
                    completion_percentage=0.0,
                    plan=plan,
                    current_day=0,
                    status=status,
                    days_until_start=days_until_start
                )

        # Default: sin planes activos
        return TodayMealPlan(
            date=datetime.combine(today, datetime.min.time()),
            meals=[],
            completion_percentage=0.0,
            current_day=0,
            status=PlanStatus.NOT_STARTED
        )
    
    def get_hybrid_dashboard(self, user_id: int, gym_id: int) -> NutritionDashboardHybrid:
        """
        Obtener dashboard nutricional híbrido categorizado por tipos de plan.

        OPTIMIZED: Batch loading to reduce queries from 15+ to 4
        """

        # OPTIMIZATION: Eager loading de followed plans con daily_plans
        followed_plans_query = self.db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan)
                .selectinload(NutritionPlan.daily_plans)
        ).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        )

        followed_plans = followed_plans_query.all()

        # OPTIMIZATION: Batch update de planes LIVE seguidos (1 query + 1 commit)
        live_followed_plan_ids = [f.plan_id for f in followed_plans if f.plan.plan_type == PlanType.LIVE]
        if live_followed_plan_ids:
            updated_live_plans = self.batch_update_live_plan_statuses(live_followed_plan_ids, gym_id)
            # Reemplazar plans con versiones actualizadas
            for follower in followed_plans:
                if follower.plan_id in updated_live_plans:
                    follower.plan = updated_live_plans[follower.plan_id]

        template_plans = []
        live_plans = []

        for follower in followed_plans:
            plan = follower.plan  # Ya actualizado si es LIVE

            # Calcular día actual y estado
            current_day, status = self.get_current_plan_day(plan, follower)

            # Agregar campos calculados
            plan.current_day = current_day
            plan.status = status
            plan.days_until_start = self.get_days_until_start(plan)

            # Categorizar por tipo
            if plan.plan_type == PlanType.LIVE:
                live_plans.append(plan)
            else:  # TEMPLATE o ARCHIVED
                template_plans.append(plan)

        # Obtener planes disponibles (públicos del gimnasio que no sigue)
        followed_plan_ids = [f.plan_id for f in followed_plans]

        # OPTIMIZATION: Eager loading de available plans también
        available_plans_query = self.db.query(NutritionPlan).options(
            selectinload(NutritionPlan.daily_plans)
        ).filter(
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.is_active == True,
            NutritionPlan.is_public == True,
            ~NutritionPlan.id.in_(followed_plan_ids) if followed_plan_ids else True
        ).limit(10)  # Limitar para performance

        available_plans = available_plans_query.all()

        # OPTIMIZATION: Batch update de planes LIVE disponibles (1 query + 1 commit)
        live_available_plan_ids = [p.id for p in available_plans if p.plan_type == PlanType.LIVE]
        if live_available_plan_ids:
            updated_available_live_plans = self.batch_update_live_plan_statuses(live_available_plan_ids, gym_id)
            # Reemplazar con versiones actualizadas
            for i, plan in enumerate(available_plans):
                if plan.id in updated_available_live_plans:
                    available_plans[i] = updated_available_live_plans[plan.id]

        # Calcular estado para planes disponibles (usando datos ya cargados)
        for plan in available_plans:
            if plan.plan_type == PlanType.LIVE:
                current_day, status = self.get_current_plan_day(plan)
                plan.current_day = current_day
                plan.status = status
                plan.days_until_start = self.get_days_until_start(plan)
        
        # Obtener plan de hoy
        today_plan = self.get_hybrid_today_meal_plan(user_id, gym_id)
        
        # TODO: Calcular estadísticas de progreso semanal
        weekly_progress = []  # Implementar después
        
        return NutritionDashboardHybrid(
            template_plans=template_plans,
            live_plans=live_plans,
            available_plans=available_plans,
            today_plan=today_plan,
            completion_streak=0,  # TODO: implementar
            weekly_progress=weekly_progress
        )

    async def get_hybrid_dashboard_cached(
        self,
        user_id: int,
        gym_id: int,
        redis_client = None
    ) -> NutritionDashboardHybrid:
        """
        Obtener dashboard con cache Redis.

        TTL: 600s (10 minutos) - Balance entre freshness y performance
        Cache key: gym:{gym_id}:user:{user_id}:nutrition_dashboard

        OPTIMIZATION: Reduce repeated dashboard loads from 4 queries to cache hit
        """
        cache_key = f"gym:{gym_id}:user:{user_id}:nutrition_dashboard"

        # Try to get Redis client if not provided
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                redis_client = None

        # Try cache first
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for dashboard user {user_id}")
                    return NutritionSerializer.deserialize_dashboard(cached)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # Fetch from database (usar método optimizado)
        dashboard = self.get_hybrid_dashboard(user_id, gym_id)

        # Cache the result
        if redis_client and dashboard:
            try:
                serialized = NutritionSerializer.serialize_dashboard(dashboard)
                await redis_client.setex(cache_key, 600, serialized)  # TTL 10 min
                logger.debug(f"Cached dashboard for user {user_id}")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return dashboard

    def _auto_archive_finished_live_plan(self, plan: NutritionPlan):
        """Crear automáticamente una versión archivada de un plan live terminado"""
        try:
            archived_title = f"{plan.title} (Template)"
            self._create_archived_version(plan, archived_title)
            logger.info(f"Plan live {plan.id} archivado automáticamente")
        except Exception as e:
            logger.error(f"Error archivando automáticamente plan {plan.id}: {str(e)}")
    
    def _create_archived_version(self, live_plan: NutritionPlan, template_title: Optional[str] = None) -> NutritionPlan:
        """Crear una versión archivada (template) de un plan live"""
        
        if not template_title:
            template_title = f"{live_plan.title} (Template)"
        
        # Crear plan archivado
        archived_plan = NutritionPlan(
            title=template_title,
            description=live_plan.description,
            goal=live_plan.goal,
            difficulty_level=live_plan.difficulty_level,
            budget_level=live_plan.budget_level,
            dietary_restrictions=live_plan.dietary_restrictions,
            duration_days=live_plan.duration_days,
            is_recurring=live_plan.is_recurring,
            target_calories=live_plan.target_calories,
            target_protein_g=live_plan.target_protein_g,
            target_carbs_g=live_plan.target_carbs_g,
            target_fat_g=live_plan.target_fat_g,
            is_public=True,  # Los archivados son públicos por defecto
            tags=live_plan.tags,
            
            # Campos específicos del archivado
            plan_type=PlanType.ARCHIVED,
            original_live_plan_id=live_plan.id,
            archived_at=datetime.utcnow(),
            original_participants_count=live_plan.live_participants_count,
            
            # Relaciones
            creator_id=live_plan.creator_id,
            gym_id=live_plan.gym_id
        )
        
        self.db.add(archived_plan)
        self.db.flush()  # Para obtener el ID
        
        # Copiar todos los días y comidas
        for daily_plan in live_plan.daily_plans:
            archived_daily = DailyNutritionPlan(
                nutrition_plan_id=archived_plan.id,
                day_number=daily_plan.day_number,
                total_calories=daily_plan.total_calories,
                total_protein_g=daily_plan.total_protein_g,
                total_carbs_g=daily_plan.total_carbs_g,
                total_fat_g=daily_plan.total_fat_g,
                notes=daily_plan.notes,
                is_published=True  # Los archivados están todos publicados
            )
            
            self.db.add(archived_daily)
            self.db.flush()
            
            # Copiar comidas
            for meal in daily_plan.meals:
                archived_meal = Meal(
                    daily_plan_id=archived_daily.id,
                    meal_type=meal.meal_type,
                    name=meal.name,
                    description=meal.description,
                    preparation_time_minutes=meal.preparation_time_minutes,
                    cooking_instructions=meal.cooking_instructions,
                    calories=meal.calories,
                    protein_g=meal.protein_g,
                    carbs_g=meal.carbs_g,
                    fat_g=meal.fat_g,
                    fiber_g=meal.fiber_g,
                    image_url=meal.image_url,
                    video_url=meal.video_url,
                    order_in_day=meal.order_in_day
                )
                
                self.db.add(archived_meal)
                self.db.flush()
                
                # Copiar ingredientes
                for ingredient in meal.ingredients:
                    archived_ingredient = MealIngredient(
                        meal_id=archived_meal.id,
                        name=ingredient.name,
                        quantity=ingredient.quantity,
                        unit=ingredient.unit,
                        alternatives=ingredient.alternatives,
                        is_optional=ingredient.is_optional,
                        calories_per_serving=ingredient.calories_per_serving,
                        protein_per_serving=ingredient.protein_per_serving,
                        carbs_per_serving=ingredient.carbs_per_serving,
                        fat_per_serving=ingredient.fat_per_serving
                    )
                    
                    self.db.add(archived_ingredient)
        
        self.db.commit()
        self.db.refresh(archived_plan)
        
        logger.info(f"Creada versión archivada {archived_plan.id} del plan live {live_plan.id}")
        return archived_plan

    # ===== ANALYTICS =====
    
    def get_nutrition_analytics(self, plan_id: int, user_id: int, gym_id: int) -> NutritionAnalytics:
        """Obtener analytics de un plan nutricional."""
        plan = self.get_nutrition_plan(plan_id, gym_id)
        
        # Verificar que es el creador
        if plan.creator_id != user_id:
            raise PermissionError("Solo el creador puede ver analytics del plan")
        
        # Contar seguidores
        total_followers = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan_id
        ).count()
        
        active_followers = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.is_active == True
        ).count()
        
        # Calcular tasa de completación promedio
        # TODO: Implementar cálculo más complejo
        avg_completion_rate = 0.0
        avg_satisfaction = 0.0
        
        return NutritionAnalytics(
            plan_id=plan_id,
            total_followers=total_followers,
            active_followers=active_followers,
            avg_completion_rate=avg_completion_rate,
            avg_satisfaction=avg_satisfaction,
            popular_meals=[],
            completion_trends=[]
        )

    # ===== PRIVATE METHODS =====
    
    def _update_daily_progress(self, daily_plan_id: int, user_id: int):
        """Actualizar el progreso diario del usuario."""
        today = datetime.now().date()
        
        # Buscar o crear progreso diario
        progress = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.daily_plan_id == daily_plan_id,
            UserDailyProgress.user_id == user_id,
            func.date(UserDailyProgress.date) == today
        ).first()
        
        # Contar comidas totales y completadas
        total_meals = self.db.query(Meal).filter(
            Meal.daily_plan_id == daily_plan_id
        ).count()
        
        completed_meals = self.db.query(UserMealCompletion).join(Meal).filter(
            Meal.daily_plan_id == daily_plan_id,
            UserMealCompletion.user_id == user_id,
            func.date(UserMealCompletion.completed_at) == today
        ).count()
        
        completion_percentage = (completed_meals / total_meals * 100) if total_meals > 0 else 0
        
        if progress:
            progress.meals_completed = completed_meals
            progress.completion_percentage = completion_percentage
            progress.updated_at = datetime.utcnow()
        else:
            progress = UserDailyProgress(
                user_id=user_id,
                daily_plan_id=daily_plan_id,
                date=datetime.combine(today, datetime.min.time()),
                meals_completed=completed_meals,
                total_meals=total_meals,
                completion_percentage=completion_percentage
            )
            self.db.add(progress)
    
    def _notify_followers_new_day(self, daily_plan: DailyNutritionPlan):
        """Enviar notificaciones a seguidores cuando se publica un nuevo día."""
        # TODO: Implementar sistema de notificaciones
        logger.info(f"Notificando seguidores del plan {daily_plan.nutrition_plan_id} sobre nuevo día")
        pass 