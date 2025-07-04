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
    NutritionGoal, DifficultyLevel, BudgetLevel, DietaryRestriction, MealType
)
from app.models.user import User
from app.models.gym import Gym
from app.schemas.nutrition import (
    NutritionPlanCreate, NutritionPlanUpdate, NutritionPlanFilters,
    DailyNutritionPlanCreate, DailyNutritionPlanUpdate,
    MealCreate, MealUpdate, MealIngredientCreate,
    NutritionPlanFollowerCreate, UserDailyProgressCreate, UserMealCompletionCreate,
    TodayMealPlan, WeeklyNutritionSummary, UserNutritionDashboard, NutritionAnalytics
)

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
            user_id=user_id
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