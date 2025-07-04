"""
Esquemas Pydantic para el sistema de planes nutricionales.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator, model_validator
from datetime import datetime, date, time
from enum import Enum

from app.models.nutrition import (
    NutritionGoal,
    DifficultyLevel,
    BudgetLevel,
    DietaryRestriction,
    MealType
)


# ===== NUTRITION PLAN SCHEMAS =====

class NutritionPlanBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    goal: NutritionGoal
    difficulty_level: DifficultyLevel = DifficultyLevel.BEGINNER
    budget_level: BudgetLevel = BudgetLevel.MEDIUM
    dietary_restrictions: DietaryRestriction = DietaryRestriction.NONE
    duration_days: int = Field(1, ge=1, le=365)
    is_recurring: bool = False
    target_calories: Optional[int] = Field(None, ge=0)
    target_protein_g: Optional[float] = Field(None, ge=0)
    target_carbs_g: Optional[float] = Field(None, ge=0)
    target_fat_g: Optional[float] = Field(None, ge=0)
    is_public: bool = True
    tags: Optional[List[str]] = None

    @validator('tags', pre=True)
    def validate_tags(cls, v):
        if isinstance(v, str):
            # Si recibimos un string JSON, intentar parsearlo
            import json
            try:
                return json.loads(v)
            except:
                # Si no es JSON válido, dividir por comas
                return [tag.strip() for tag in v.split(',') if tag.strip()]
        return v or []


class NutritionPlanCreate(NutritionPlanBase):
    pass


class NutritionPlanUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    goal: Optional[NutritionGoal] = None
    difficulty_level: Optional[DifficultyLevel] = None
    budget_level: Optional[BudgetLevel] = None
    dietary_restrictions: Optional[DietaryRestriction] = None
    duration_days: Optional[int] = Field(None, ge=1, le=365)
    is_recurring: Optional[bool] = None
    target_calories: Optional[int] = Field(None, ge=0)
    target_protein_g: Optional[float] = Field(None, ge=0)
    target_carbs_g: Optional[float] = Field(None, ge=0)
    target_fat_g: Optional[float] = Field(None, ge=0)
    is_active: Optional[bool] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class NutritionPlan(NutritionPlanBase):
    id: int
    creator_id: int
    gym_id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Estadísticas opcionales
    total_followers: Optional[int] = None
    avg_satisfaction: Optional[float] = None

    model_config = {"from_attributes": True}


class NutritionPlanWithDetails(NutritionPlan):
    """Plan nutricional con información detallada"""
    daily_plans: List["DailyNutritionPlan"] = []
    creator_name: Optional[str] = None
    is_followed_by_user: Optional[bool] = None


# ===== DAILY NUTRITION PLAN SCHEMAS =====

class DailyNutritionPlanBase(BaseModel):
    day_number: int = Field(..., ge=1)
    planned_date: Optional[datetime] = None
    total_calories: Optional[int] = Field(None, ge=0)
    total_protein_g: Optional[float] = Field(None, ge=0)
    total_carbs_g: Optional[float] = Field(None, ge=0)
    total_fat_g: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


class DailyNutritionPlanCreate(DailyNutritionPlanBase):
    nutrition_plan_id: int


class DailyNutritionPlanUpdate(BaseModel):
    day_number: Optional[int] = Field(None, ge=1)
    planned_date: Optional[datetime] = None
    total_calories: Optional[int] = Field(None, ge=0)
    total_protein_g: Optional[float] = Field(None, ge=0)
    total_carbs_g: Optional[float] = Field(None, ge=0)
    total_fat_g: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None
    is_published: Optional[bool] = None


class DailyNutritionPlan(DailyNutritionPlanBase):
    id: int
    nutrition_plan_id: int
    is_published: bool
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DailyNutritionPlanWithMeals(DailyNutritionPlan):
    """Plan diario con comidas incluidas"""
    meals: List["Meal"] = []
    user_progress: Optional["UserDailyProgress"] = None


# ===== MEAL SCHEMAS =====

class MealBase(BaseModel):
    meal_type: MealType
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    preparation_time_minutes: Optional[int] = Field(None, ge=0)
    cooking_instructions: Optional[str] = None
    calories: Optional[int] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    fiber_g: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    order_in_day: int = Field(0, ge=0)


class MealCreate(MealBase):
    daily_plan_id: int


class MealUpdate(BaseModel):
    meal_type: Optional[MealType] = None
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    preparation_time_minutes: Optional[int] = Field(None, ge=0)
    cooking_instructions: Optional[str] = None
    calories: Optional[int] = Field(None, ge=0)
    protein_g: Optional[float] = Field(None, ge=0)
    carbs_g: Optional[float] = Field(None, ge=0)
    fat_g: Optional[float] = Field(None, ge=0)
    fiber_g: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    order_in_day: Optional[int] = Field(None, ge=0)


class Meal(MealBase):
    id: int
    daily_plan_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MealWithIngredients(Meal):
    """Comida con ingredientes incluidos"""
    ingredients: List["MealIngredient"] = []
    user_completion: Optional["UserMealCompletion"] = None


# ===== MEAL INGREDIENT SCHEMAS =====

class MealIngredientBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    quantity: float = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)
    alternatives: Optional[List[str]] = None
    is_optional: bool = False
    calories_per_serving: Optional[int] = Field(None, ge=0)
    protein_per_serving: Optional[float] = Field(None, ge=0)
    carbs_per_serving: Optional[float] = Field(None, ge=0)
    fat_per_serving: Optional[float] = Field(None, ge=0)

    @validator('alternatives', pre=True)
    def validate_alternatives(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except:
                return [alt.strip() for alt in v.split(',') if alt.strip()]
        return v or []


class MealIngredientCreate(MealIngredientBase):
    meal_id: int


class MealIngredientUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    quantity: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = Field(None, min_length=1, max_length=50)
    alternatives: Optional[List[str]] = None
    is_optional: Optional[bool] = None
    calories_per_serving: Optional[int] = Field(None, ge=0)
    protein_per_serving: Optional[float] = Field(None, ge=0)
    carbs_per_serving: Optional[float] = Field(None, ge=0)
    fat_per_serving: Optional[float] = Field(None, ge=0)


class MealIngredient(MealIngredientBase):
    id: int
    meal_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== NUTRITION PLAN FOLLOWER SCHEMAS =====

class NutritionPlanFollowerBase(BaseModel):
    notifications_enabled: bool = True
    notification_time_breakfast: str = Field("08:00", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    notification_time_lunch: str = Field("13:00", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    notification_time_dinner: str = Field("20:00", pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")


class NutritionPlanFollowerCreate(NutritionPlanFollowerBase):
    plan_id: int


class NutritionPlanFollowerUpdate(BaseModel):
    notifications_enabled: Optional[bool] = None
    notification_time_breakfast: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    notification_time_lunch: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    notification_time_dinner: Optional[str] = Field(None, pattern=r"^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$")
    is_active: Optional[bool] = None


class NutritionPlanFollower(NutritionPlanFollowerBase):
    id: int
    user_id: int
    plan_id: int
    is_active: bool
    start_date: datetime
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ===== USER PROGRESS SCHEMAS =====

class UserDailyProgressBase(BaseModel):
    date: datetime
    overall_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    difficulty_rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    weight_kg: Optional[float] = Field(None, gt=0)
    body_fat_percentage: Optional[float] = Field(None, ge=0, le=100)


class UserDailyProgressCreate(UserDailyProgressBase):
    daily_plan_id: int


class UserDailyProgressUpdate(BaseModel):
    overall_satisfaction: Optional[int] = Field(None, ge=1, le=5)
    difficulty_rating: Optional[int] = Field(None, ge=1, le=5)
    notes: Optional[str] = None
    weight_kg: Optional[float] = Field(None, gt=0)
    body_fat_percentage: Optional[float] = Field(None, ge=0, le=100)


class UserDailyProgress(UserDailyProgressBase):
    id: int
    user_id: int
    daily_plan_id: int
    meals_completed: int
    total_meals: int
    completion_percentage: float
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ===== USER MEAL COMPLETION SCHEMAS =====

class UserMealCompletionBase(BaseModel):
    satisfaction_rating: Optional[int] = Field(None, ge=1, le=5)
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    ingredients_modified: Optional[Dict[str, Any]] = None
    portion_size_modifier: float = Field(1.0, gt=0, le=3.0)


class UserMealCompletionCreate(UserMealCompletionBase):
    meal_id: int


class UserMealCompletionUpdate(BaseModel):
    satisfaction_rating: Optional[int] = Field(None, ge=1, le=5)
    photo_url: Optional[str] = None
    notes: Optional[str] = None
    ingredients_modified: Optional[Dict[str, Any]] = None
    portion_size_modifier: Optional[float] = Field(None, gt=0, le=3.0)


class UserMealCompletion(UserMealCompletionBase):
    id: int
    user_id: int
    meal_id: int
    completed_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


# ===== RESPONSE SCHEMAS =====

class NutritionPlanListResponse(BaseModel):
    """Respuesta para listado de planes nutricionales"""
    plans: List[NutritionPlan]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class UserNutritionDashboard(BaseModel):
    """Dashboard nutricional del usuario"""
    active_plans: List[NutritionPlan]
    today_meals: List[MealWithIngredients]
    completion_streak: int
    weekly_progress: List[UserDailyProgress]
    upcoming_meals: List[MealWithIngredients]


class NutritionAnalytics(BaseModel):
    """Analytics para entrenadores"""
    plan_id: int
    total_followers: int
    active_followers: int
    avg_completion_rate: float
    avg_satisfaction: float
    popular_meals: List[Dict[str, Any]]
    completion_trends: List[Dict[str, Any]]


class MealCompletionBatch(BaseModel):
    """Para completar múltiples comidas de una vez"""
    completions: List[UserMealCompletionCreate]


# ===== FILTROS Y BÚSQUEDA =====

class NutritionPlanFilters(BaseModel):
    """Filtros para búsqueda de planes nutricionales"""
    goal: Optional[NutritionGoal] = None
    difficulty_level: Optional[DifficultyLevel] = None
    budget_level: Optional[BudgetLevel] = None
    dietary_restrictions: Optional[DietaryRestriction] = None
    duration_days_min: Optional[int] = Field(None, ge=1)
    duration_days_max: Optional[int] = Field(None, ge=1)
    creator_id: Optional[int] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None
    search_query: Optional[str] = None  # Búsqueda por título/descripción


# ===== SCHEMAS ESPECÍFICOS PARA RESPUESTAS =====

class TodayMealPlan(BaseModel):
    """Plan de comidas para el día actual"""
    date: datetime
    daily_plan: Optional[DailyNutritionPlan] = None
    meals: List[MealWithIngredients] = []
    progress: Optional[UserDailyProgress] = None
    completion_percentage: float = 0.0


class WeeklyNutritionSummary(BaseModel):
    """Resumen semanal de nutrición"""
    week_start: datetime
    week_end: datetime
    total_days: int
    completed_days: int
    avg_completion_rate: float
    avg_satisfaction: float
    total_calories_consumed: int
    daily_summaries: List[UserDailyProgress]


# Update forward references
NutritionPlanWithDetails.model_rebuild()
DailyNutritionPlanWithMeals.model_rebuild()
MealWithIngredients.model_rebuild() 