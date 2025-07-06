"""
Endpoints para el sistema de planes nutricionales.
"""

from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Path, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.auth0_fastapi import get_current_user, Auth0User
from app.core.tenant import verify_gym_access
from app.models.user import User
from app.models.gym import Gym
from app.schemas.nutrition import (
    NutritionPlan, NutritionPlanCreate, NutritionPlanUpdate, NutritionPlanFilters,
    NutritionPlanListResponse, NutritionPlanWithDetails, NutritionPlanListResponseHybrid,
    DailyNutritionPlan, DailyNutritionPlanCreate, DailyNutritionPlanWithMeals,
    Meal, MealCreate, MealWithIngredients, MealIngredient, MealIngredientCreate,
    NutritionPlanFollower, NutritionPlanFollowerCreate,
    UserMealCompletion, UserMealCompletionCreate,
    TodayMealPlan, UserNutritionDashboard, NutritionAnalytics, NutritionDashboardHybrid,
    NutritionGoal, DifficultyLevel, BudgetLevel, DietaryRestriction, MealType, PlanType, PlanStatus,
    ArchivePlanRequest, LivePlanStatusUpdate
)
from app.services.nutrition import NutritionService, NotFoundError, ValidationError, PermissionError
from app.services.user import user_service

router = APIRouter()


@router.get("/plans", response_model=NutritionPlanListResponse)
def list_nutrition_plans(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    goal: Optional[NutritionGoal] = Query(None),
    difficulty_level: Optional[DifficultyLevel] = Query(None),
    budget_level: Optional[BudgetLevel] = Query(None),
    dietary_restrictions: Optional[DietaryRestriction] = Query(None),
    search_query: Optional[str] = Query(None),
    creator_id: Optional[int] = Query(None),
    plan_type: Optional[PlanType] = Query(None, description="Filtrar por tipo de plan"),
    status: Optional[PlanStatus] = Query(None, description="Filtrar por estado del plan"),
    is_live_active: Optional[bool] = Query(None, description="Filtrar planes live activos"),
):
    """
    Listar planes nutricionales con filtros (incluyendo sistema híbrido).
    """
    service = NutritionService(db)
    
    # Crear filtros
    filters = NutritionPlanFilters(
        goal=goal,
        difficulty_level=difficulty_level,
        budget_level=budget_level,
        dietary_restrictions=dietary_restrictions,
        search_query=search_query,
        creator_id=creator_id,
        plan_type=plan_type,
        status=status,
        is_live_active=is_live_active
    )
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    plans, total = service.list_nutrition_plans(
        gym_id=current_gym.id,
        filters=filters,
        page=page,
        per_page=per_page,
        user_id=db_user.id
    )
    
    return NutritionPlanListResponse(
        plans=plans,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


@router.post("/plans", response_model=NutritionPlan)
def create_nutrition_plan(
    plan_data: NutritionPlanCreate,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Crear un nuevo plan nutricional (template, live o archived).
    Solo entrenadores y administradores pueden crear planes.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        # Usar el método específico para planes live o el método base
        if plan_data.plan_type == PlanType.LIVE:
            plan = service.create_live_nutrition_plan(
                plan_data=plan_data,
                creator_id=db_user.id,
                gym_id=current_gym.id
            )
        else:
            plan = service.create_nutrition_plan(
                plan_data=plan_data,
                creator_id=db_user.id,
                gym_id=current_gym.id
            )
        return plan
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/plans/{plan_id}", response_model=NutritionPlanWithDetails)
def get_nutrition_plan(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener un plan nutricional con todos sus detalles.
    """
    service = NutritionService(db)
    
    try:
        plan = service.get_nutrition_plan(plan_id, current_gym.id)
        return plan
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/plans/{plan_id}/follow", response_model=NutritionPlanFollower)
def follow_nutrition_plan(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Seguir un plan nutricional.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        follower = service.follow_nutrition_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return follower
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/plans/{plan_id}/follow")
def unfollow_nutrition_plan(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Dejar de seguir un plan nutricional.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        success = service.unfollow_nutrition_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return {"success": success}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/meals/{meal_id}/complete", response_model=UserMealCompletion)
def complete_meal(
    completion_data: UserMealCompletionCreate,
    meal_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Marcar una comida como completada.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        completion = service.complete_meal(
            meal_id=meal_id,
            user_id=db_user.id,
            gym_id=current_gym.id,
            satisfaction_rating=completion_data.satisfaction_rating,
            photo_url=completion_data.photo_url,
            notes=completion_data.notes
        )
        return completion
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/today", response_model=TodayMealPlan)
def get_today_meal_plan(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener el plan de comidas para el día de hoy (con lógica híbrida).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Usar la nueva lógica híbrida
    meal_plan = service.get_hybrid_today_meal_plan(
        user_id=db_user.id,
        gym_id=current_gym.id
    )
    
    return meal_plan


@router.get("/dashboard", response_model=NutritionDashboardHybrid)
def get_nutrition_dashboard(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener dashboard nutricional híbrido del usuario.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    dashboard = service.get_hybrid_dashboard(
        user_id=db_user.id,
        gym_id=current_gym.id
    )
    
    return dashboard


# ===== ENDPOINTS PARA CREADORES DE CONTENIDO =====

@router.post("/plans/{plan_id}/days", response_model=DailyNutritionPlan)
def create_daily_plan(
    daily_plan_data: DailyNutritionPlanCreate,
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Crear un plan diario dentro de un plan nutricional.
    Solo el creador del plan puede añadir días.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el plan_id coincide
    if daily_plan_data.nutrition_plan_id != plan_id:
        raise HTTPException(status_code=400, detail="El plan_id no coincide")
    
    try:
        daily_plan = service.create_daily_plan(
            daily_plan_data=daily_plan_data,
            user_id=db_user.id
        )
        return daily_plan
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/days/{daily_plan_id}/meals", response_model=Meal)
def create_meal(
    meal_data: MealCreate,
    daily_plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Crear una comida dentro de un plan diario.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el daily_plan_id coincide
    if meal_data.daily_plan_id != daily_plan_id:
        raise HTTPException(status_code=400, detail="El daily_plan_id no coincide")
    
    try:
        meal = service.create_meal(
            meal_data=meal_data,
            user_id=db_user.id
        )
        return meal
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post("/meals/{meal_id}/ingredients", response_model=MealIngredient)
def add_ingredient_to_meal(
    ingredient_data: MealIngredientCreate,
    meal_id: int = Path(...),
    db: Session = Depends(get_db),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Añadir un ingrediente a una comida.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Verificar que el meal_id coincide
    if ingredient_data.meal_id != meal_id:
        raise HTTPException(status_code=400, detail="El meal_id no coincide")
    
    try:
        ingredient = service.add_ingredient_to_meal(
            ingredient_data=ingredient_data,
            user_id=db_user.id
        )
        return ingredient
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ===== ENDPOINTS DE ANALYTICS =====

@router.get("/plans/{plan_id}/analytics", response_model=NutritionAnalytics)
def get_plan_analytics(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener analytics de un plan nutricional.
    Solo el creador puede ver los analytics.
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        analytics = service.get_nutrition_analytics(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id
        )
        return analytics
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


# ===== ENDPOINTS DE UTILIDAD =====

@router.get("/enums/goals")
def get_nutrition_goals():
    """Obtener lista de objetivos nutricionales disponibles."""
    return [{"value": goal.value, "label": goal.value.replace("_", " ").title()} 
            for goal in NutritionGoal]


@router.get("/enums/difficulty-levels")
def get_difficulty_levels():
    """Obtener lista de niveles de dificultad disponibles."""
    return [{"value": level.value, "label": level.value.title()} 
            for level in DifficultyLevel]


@router.get("/enums/budget-levels")
def get_budget_levels():
    """Obtener lista de niveles de presupuesto disponibles."""
    return [{"value": level.value, "label": level.value.title()} 
            for level in BudgetLevel]


@router.get("/enums/dietary-restrictions")
def get_dietary_restrictions():
    """Obtener lista de restricciones dietéticas disponibles."""
    return [{"value": restriction.value, "label": restriction.value.replace("_", " ").title()} 
            for restriction in DietaryRestriction]


@router.get("/enums/meal-types")
def get_meal_types():
    """Obtener lista de tipos de comidas disponibles."""
    return [{"value": meal_type.value, "label": meal_type.value.replace("_", " ").title()} 
            for meal_type in MealType]


@router.get("/enums/plan-types")
def get_plan_types():
    """Obtener lista de tipos de planes disponibles."""
    return [{"value": plan_type.value, "label": plan_type.value.title()} 
            for plan_type in PlanType]


@router.get("/enums/plan-statuses")
def get_plan_statuses():
    """Obtener lista de estados de planes disponibles."""
    return [{"value": status.value, "label": status.value.replace("_", " ").title()} 
            for status in PlanStatus]


# ===== NUEVOS ENDPOINTS DEL SISTEMA HÍBRIDO =====

@router.get("/plans/hybrid", response_model=NutritionPlanListResponseHybrid)
def list_plans_by_type(
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Listar planes categorizados por tipo (live, template, archived).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    # Obtener planes por tipo
    live_filters = NutritionPlanFilters(plan_type=PlanType.LIVE)
    template_filters = NutritionPlanFilters(plan_type=PlanType.TEMPLATE)
    archived_filters = NutritionPlanFilters(plan_type=PlanType.ARCHIVED)
    
    live_plans, live_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=live_filters, page=1, per_page=50, user_id=db_user.id
    )
    
    template_plans, template_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=template_filters, page=1, per_page=50, user_id=db_user.id
    )
    
    archived_plans, archived_total = service.list_nutrition_plans(
        gym_id=current_gym.id, filters=archived_filters, page=1, per_page=50, user_id=db_user.id
    )
    
    total = live_total + template_total + archived_total
    
    return NutritionPlanListResponseHybrid(
        live_plans=live_plans,
        template_plans=template_plans,
        archived_plans=archived_plans,
        total=total,
        page=page,
        per_page=per_page,
        has_next=(page * per_page) < total,
        has_prev=page > 1
    )


@router.put("/plans/{plan_id}/live-status", response_model=NutritionPlan)
def update_live_plan_status(
    plan_id: int = Path(...),
    status_update: LivePlanStatusUpdate = ...,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Actualizar el estado de un plan live (solo creadores).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        # Verificar permisos
        plan = service.get_nutrition_plan(plan_id, current_gym.id)
        if plan.creator_id != db_user.id:
            raise HTTPException(status_code=403, detail="Solo el creador puede actualizar el estado del plan")
        
        if plan.plan_type != PlanType.LIVE:
            raise HTTPException(status_code=400, detail="Solo se puede actualizar el estado de planes live")
        
        # Actualizar estado
        plan.is_live_active = status_update.is_live_active
        if status_update.live_participants_count is not None:
            plan.live_participants_count = status_update.live_participants_count
        
        service.db.commit()
        service.db.refresh(plan)
        
        return plan
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/plans/{plan_id}/archive", response_model=NutritionPlan)
def archive_live_plan(
    plan_id: int = Path(...),
    archive_request: ArchivePlanRequest = ...,
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Archivar un plan live terminado (solo creadores).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        archived_plan = service.archive_live_plan(
            plan_id=plan_id,
            user_id=db_user.id,
            gym_id=current_gym.id,
            archive_request=archive_request
        )
        return archived_plan
        
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.get("/plans/{plan_id}/status")
def get_plan_status(
    plan_id: int = Path(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user)
):
    """
    Obtener el estado actual de un plan (day, status, etc.).
    """
    service = NutritionService(db)
    
    # Obtener usuario local
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=current_user.id)
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    try:
        plan = service.get_nutrition_plan(plan_id, current_gym.id)
        
        # Obtener información de seguimiento del usuario
        follower = None
        if db_user.id != plan.creator_id:
            from app.models.nutrition import NutritionPlanFollower
            follower = service.db.query(NutritionPlanFollower).filter(
                NutritionPlanFollower.plan_id == plan_id,
                NutritionPlanFollower.user_id == db_user.id,
                NutritionPlanFollower.is_active == True
            ).first()
        
        # Calcular estado
        current_day, status = service.get_current_plan_day(plan, follower)
        days_until_start = service.get_days_until_start(plan)
        
        # Actualizar estado de planes live
        if plan.plan_type == PlanType.LIVE:
            plan = service.update_live_plan_status(plan.id, current_gym.id)
        
        return {
            "plan_id": plan.id,
            "plan_type": plan.plan_type,
            "current_day": current_day,
            "status": status,
            "days_until_start": days_until_start,
            "is_live_active": plan.is_live_active,
            "live_participants_count": plan.live_participants_count,
            "is_following": follower is not None
        }
        
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) 