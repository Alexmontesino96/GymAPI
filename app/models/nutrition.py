"""
Modelos para el sistema de planes nutricionales.
Permite a entrenadores crear planes de dieta y a usuarios seguirlos.
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Float, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from typing import TYPE_CHECKING

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.gym import Gym


class NutritionGoal(str, enum.Enum):
    """Objetivos nutricionales disponibles."""
    BULK = "bulk"                    # Volumen/Ganancia de masa
    CUT = "cut"                      # Definición/Pérdida de grasa
    MAINTENANCE = "maintenance"      # Mantenimiento
    WEIGHT_LOSS = "weight_loss"      # Pérdida de peso
    MUSCLE_GAIN = "muscle_gain"      # Ganancia muscular
    PERFORMANCE = "performance"      # Rendimiento deportivo


class DifficultyLevel(str, enum.Enum):
    """Niveles de dificultad para preparación."""
    BEGINNER = "beginner"       # Principiante (recetas simples)
    INTERMEDIATE = "intermediate"  # Intermedio
    ADVANCED = "advanced"       # Avanzado (recetas complejas)


class BudgetLevel(str, enum.Enum):
    """Niveles de presupuesto para ingredientes."""
    ECONOMIC = "economic"       # Económico
    MEDIUM = "medium"          # Medio
    PREMIUM = "premium"        # Premium


class DietaryRestriction(str, enum.Enum):
    """Restricciones dietéticas."""
    NONE = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    LACTOSE_FREE = "lactose_free"
    KETO = "keto"
    PALEO = "paleo"
    MEDITERRANEAN = "mediterranean"


class MealType(str, enum.Enum):
    """Tipos de comidas del día."""
    BREAKFAST = "breakfast"         # Desayuno
    MID_MORNING = "mid_morning"     # Media mañana
    LUNCH = "lunch"                 # Almuerzo
    AFTERNOON = "afternoon"         # Merienda
    DINNER = "dinner"               # Cena
    POST_WORKOUT = "post_workout"   # Post-entreno
    LATE_SNACK = "late_snack"      # Snack nocturno


class NutritionPlan(Base):
    """
    Plan nutricional creado por un entrenador.
    """
    __tablename__ = "nutrition_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Información básica
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    goal = Column(Enum(NutritionGoal), nullable=False, index=True)
    difficulty_level = Column(Enum(DifficultyLevel), default=DifficultyLevel.BEGINNER)
    budget_level = Column(Enum(BudgetLevel), default=BudgetLevel.MEDIUM)
    dietary_restrictions = Column(Enum(DietaryRestriction), default=DietaryRestriction.NONE)
    
    # Duración y programación
    duration_days = Column(Integer, nullable=False, default=1)  # Duración del plan
    is_recurring = Column(Boolean, default=False)  # Si se repite automáticamente
    
    # Información nutricional objetivo
    target_calories = Column(Integer, nullable=True)  # Calorías objetivo por día
    target_protein_g = Column(Float, nullable=True)   # Proteína objetivo (gramos)
    target_carbs_g = Column(Float, nullable=True)     # Carbohidratos objetivo (gramos)
    target_fat_g = Column(Float, nullable=True)       # Grasas objetivo (gramos)
    
    # Metadatos
    is_active = Column(Boolean, default=True, index=True)
    is_public = Column(Boolean, default=True)  # Si otros usuarios pueden verlo
    tags = Column(Text, nullable=True)  # JSON array de tags
    
    # Relaciones
    creator_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), nullable=False, index=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones ORM
    creator = relationship("User", back_populates="created_nutrition_plans")
    gym = relationship("Gym", back_populates="nutrition_plans")
    daily_plans = relationship("DailyNutritionPlan", back_populates="nutrition_plan", cascade="all, delete-orphan")
    followers = relationship("NutritionPlanFollower", back_populates="plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<NutritionPlan(id={self.id}, title='{self.title}', goal='{self.goal}')>"


class DailyNutritionPlan(Base):
    """
    Plan nutricional para un día específico.
    """
    __tablename__ = "daily_nutrition_plans"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con plan padre
    nutrition_plan_id = Column(Integer, ForeignKey("nutrition_plans.id"), nullable=False, index=True)
    
    # Información del día
    day_number = Column(Integer, nullable=False)  # Día 1, 2, 3... del plan
    planned_date = Column(DateTime, nullable=True, index=True)  # Fecha específica (opcional)
    
    # Estado de publicación
    is_published = Column(Boolean, default=False, index=True)
    published_at = Column(DateTime, nullable=True)
    
    # Información nutricional del día
    total_calories = Column(Integer, nullable=True)
    total_protein_g = Column(Float, nullable=True)
    total_carbs_g = Column(Float, nullable=True)
    total_fat_g = Column(Float, nullable=True)
    
    # Notas del día
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones ORM
    nutrition_plan = relationship("NutritionPlan", back_populates="daily_plans")
    meals = relationship("Meal", back_populates="daily_plan", cascade="all, delete-orphan")
    user_progress = relationship("UserDailyProgress", back_populates="daily_plan", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DailyNutritionPlan(id={self.id}, day={self.day_number}, plan_id={self.nutrition_plan_id})>"


class Meal(Base):
    """
    Comida específica dentro de un día de plan nutricional.
    """
    __tablename__ = "meals"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con día
    daily_plan_id = Column(Integer, ForeignKey("daily_nutrition_plans.id"), nullable=False, index=True)
    
    # Información de la comida
    meal_type = Column(Enum(MealType), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    # Tiempo y preparación
    preparation_time_minutes = Column(Integer, nullable=True)
    cooking_instructions = Column(Text, nullable=True)
    
    # Información nutricional
    calories = Column(Integer, nullable=True)
    protein_g = Column(Float, nullable=True)
    carbs_g = Column(Float, nullable=True)
    fat_g = Column(Float, nullable=True)
    fiber_g = Column(Float, nullable=True)
    
    # Multimedia
    image_url = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    
    # Orden dentro del día
    order_in_day = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones ORM
    daily_plan = relationship("DailyNutritionPlan", back_populates="meals")
    ingredients = relationship("MealIngredient", back_populates="meal", cascade="all, delete-orphan")
    user_completions = relationship("UserMealCompletion", back_populates="meal", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Meal(id={self.id}, name='{self.name}', type='{self.meal_type}')>"


class MealIngredient(Base):
    """
    Ingrediente específico de una comida con cantidad.
    """
    __tablename__ = "meal_ingredients"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relación con comida
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False, index=True)
    
    # Información del ingrediente
    name = Column(String(200), nullable=False)
    quantity = Column(Float, nullable=False)
    unit = Column(String(50), nullable=False)  # gramos, ml, unidades, etc.
    
    # Alternativas
    alternatives = Column(Text, nullable=True)  # JSON array de alternativas
    is_optional = Column(Boolean, default=False)
    
    # Información nutricional por cantidad especificada
    calories_per_serving = Column(Integer, nullable=True)
    protein_per_serving = Column(Float, nullable=True)
    carbs_per_serving = Column(Float, nullable=True)
    fat_per_serving = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones ORM
    meal = relationship("Meal", back_populates="ingredients")
    
    def __repr__(self):
        return f"<MealIngredient(id={self.id}, name='{self.name}', quantity={self.quantity} {self.unit})>"


class NutritionPlanFollower(Base):
    """
    Relación entre usuario y plan nutricional que sigue.
    """
    __tablename__ = "nutrition_plan_followers"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relaciones
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("nutrition_plans.id"), nullable=False, index=True)
    
    # Estado del seguimiento
    is_active = Column(Boolean, default=True, index=True)
    start_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    end_date = Column(DateTime, nullable=True)
    
    # Preferencias de notificaciones
    notifications_enabled = Column(Boolean, default=True)
    notification_time_breakfast = Column(String(5), default="08:00")  # HH:MM
    notification_time_lunch = Column(String(5), default="13:00")
    notification_time_dinner = Column(String(5), default="20:00")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones ORM
    user = relationship("User", back_populates="followed_nutrition_plans")
    plan = relationship("NutritionPlan", back_populates="followers")
    
    def __repr__(self):
        return f"<NutritionPlanFollower(user_id={self.user_id}, plan_id={self.plan_id})>"


class UserDailyProgress(Base):
    """
    Progreso diario del usuario en un plan nutricional.
    """
    __tablename__ = "user_daily_progress"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relaciones
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    daily_plan_id = Column(Integer, ForeignKey("daily_nutrition_plans.id"), nullable=False, index=True)
    
    # Progreso del día
    date = Column(DateTime, nullable=False, index=True)
    meals_completed = Column(Integer, default=0)
    total_meals = Column(Integer, nullable=False)
    completion_percentage = Column(Float, default=0.0)
    
    # Feedback del usuario
    overall_satisfaction = Column(Integer, nullable=True)  # 1-5 rating
    difficulty_rating = Column(Integer, nullable=True)     # 1-5 rating
    notes = Column(Text, nullable=True)
    
    # Mediciones opcionales
    weight_kg = Column(Float, nullable=True)
    body_fat_percentage = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones ORM
    user = relationship("User", back_populates="nutrition_progress")
    daily_plan = relationship("DailyNutritionPlan", back_populates="user_progress")
    
    def __repr__(self):
        return f"<UserDailyProgress(user_id={self.user_id}, date={self.date}, completion={self.completion_percentage}%)>"


class UserMealCompletion(Base):
    """
    Registro de compleción de una comida específica por un usuario.
    """
    __tablename__ = "user_meal_completions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Relaciones
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False, index=True)
    meal_id = Column(Integer, ForeignKey("meals.id"), nullable=False, index=True)
    
    # Información de la compleción
    completed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    satisfaction_rating = Column(Integer, nullable=True)  # 1-5 rating
    
    # Evidencia opcional
    photo_url = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Modificaciones realizadas
    ingredients_modified = Column(Text, nullable=True)  # JSON de cambios
    portion_size_modifier = Column(Float, default=1.0)  # 1.0 = porción normal, 0.5 = media porción
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relaciones ORM
    user = relationship("User", back_populates="meal_completions")
    meal = relationship("Meal", back_populates="user_completions")
    
    def __repr__(self):
        return f"<UserMealCompletion(user_id={self.user_id}, meal_id={self.meal_id}, completed_at={self.completed_at})>" 