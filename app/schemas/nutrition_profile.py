"""
Schemas para perfiles nutricionales
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Literal
from datetime import datetime
from enum import Enum


class NutritionalGoal(str, Enum):
    """Objetivos nutricionales disponibles"""
    WEIGHT_LOSS = "weight_loss"
    MUSCLE_GAIN = "muscle_gain"
    MAINTAIN = "maintain"
    ENERGY = "energy"
    HEALTH = "health"
    RECOMPOSITION = "recomposition"


class ActivityLevel(str, Enum):
    """Niveles de actividad física"""
    LOW = "low"  # 0-2 días/semana
    MODERATE = "moderate"  # 3-5 días/semana
    HIGH = "high"  # 6-7 días/semana


class BudgetLevel(str, Enum):
    """Niveles de presupuesto"""
    LOW = "low"  # $30-50/semana
    MODERATE = "moderate"  # $50-100/semana
    HIGH = "high"  # $100+/semana


class DietaryRestriction(str, Enum):
    """Restricciones dietéticas principales"""
    NONE = "none"
    VEGETARIAN = "vegetarian"
    VEGAN = "vegan"
    GLUTEN_FREE = "gluten_free"
    DAIRY_FREE = "dairy_free"
    KETO = "keto"
    PALEO = "paleo"
    HALAL = "halal"
    KOSHER = "kosher"
    LOW_CARB = "low_carb"
    PESCATARIAN = "pescatarian"


class BMICategory(str, Enum):
    """Categorías de IMC"""
    UNDERWEIGHT = "underweight"  # <18.5
    NORMAL = "normal"  # 18.5-24.9
    OVERWEIGHT = "overweight"  # 25-29.9
    OBESE = "obese"  # >=30


# ==================== REQUEST SCHEMAS ====================

class NutritionProfileRequest(BaseModel):
    """Request para crear/actualizar perfil nutricional (Pasos 1-3)"""

    # PASO 1: Objetivo y datos básicos (REQUERIDOS)
    screening_id: int = Field(..., description="ID del screening de seguridad válido")
    goal: NutritionalGoal = Field(..., description="Objetivo nutricional principal")
    weight_kg: float = Field(..., gt=30, lt=300, description="Peso en kilogramos")
    height_cm: float = Field(..., gt=100, lt=250, description="Altura en centímetros")
    age: int = Field(..., ge=13, le=120, description="Edad")
    biological_sex: Literal["male", "female"] = Field(..., description="Sexo biológico")
    activity_level: ActivityLevel = Field(..., description="Nivel de actividad física")

    # PASO 2: Restricciones y preferencias (REQUERIDOS pero con defaults)
    dietary_restriction: DietaryRestriction = Field(
        DietaryRestriction.NONE,
        description="Restricción dietética principal"
    )
    allergies: List[str] = Field(
        default_factory=list,
        max_items=10,
        description="Lista de alergias alimentarias"
    )
    disliked_foods: str = Field(
        "",
        max_length=200,
        description="Hasta 5 ingredientes que no le gustan"
    )
    budget_level: BudgetLevel = Field(
        BudgetLevel.MODERATE,
        description="Nivel de presupuesto semanal"
    )
    cooking_time_minutes: int = Field(
        30,
        ge=10,
        le=120,
        description="Tiempo disponible para cocinar por comida"
    )

    # PASO 3: Opciones avanzadas (COMPLETAMENTE OPCIONALES)
    has_air_fryer: bool = Field(False, description="Tiene freidora de aire")
    has_pressure_cooker: bool = Field(False, description="Tiene olla de presión")
    has_food_processor: bool = Field(False, description="Tiene procesador de alimentos")
    preferred_cuisine: Optional[str] = Field(None, description="Tipo de cocina preferida")
    works_shifts: bool = Field(False, description="Trabaja por turnos")
    travels_frequently: bool = Field(False, description="Viaja frecuentemente")
    cooks_for_family: Optional[bool] = Field(None, description="Cocina para familia")
    additional_notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notas adicionales para la IA"
    )

    @validator('weight_kg')
    def validate_weight(cls, v):
        if v < 30 or v > 300:
            raise ValueError("Peso debe estar entre 30 y 300 kg")
        return round(v, 1)

    @validator('height_cm')
    def validate_height(cls, v):
        if v < 100 or v > 250:
            raise ValueError("Altura debe estar entre 100 y 250 cm")
        return round(v, 1)

    @validator('disliked_foods')
    def validate_disliked_foods(cls, v):
        if v and len(v.split(',')) > 10:
            raise ValueError("Máximo 10 alimentos no deseados")
        return v.strip()

    @validator('allergies')
    def clean_allergies(cls, v):
        # Limpiar y normalizar alergias
        return [allergy.strip().lower() for allergy in v if allergy.strip()]

    class Config:
        schema_extra = {
            "example": {
                "screening_id": 123,
                "goal": "weight_loss",
                "weight_kg": 75,
                "height_cm": 175,
                "age": 30,
                "biological_sex": "male",
                "activity_level": "moderate",
                "dietary_restriction": "none",
                "allergies": ["nueces", "mariscos"],
                "disliked_foods": "cilantro, brócoli, hígado",
                "budget_level": "moderate",
                "cooking_time_minutes": 30,
                "has_air_fryer": False,
                "cooks_for_family": True,
                "additional_notes": "Prefiero comidas con sabor picante"
            }
        }


class RealtimeCalculationRequest(BaseModel):
    """Request para cálculos en tiempo real (para el frontend)"""
    weight_kg: float = Field(..., gt=30, lt=300)
    height_cm: float = Field(..., gt=100, lt=250)
    age: int = Field(..., ge=13, le=120)
    biological_sex: Literal["male", "female"]
    activity_level: ActivityLevel
    goal: NutritionalGoal

    class Config:
        schema_extra = {
            "example": {
                "weight_kg": 75,
                "height_cm": 175,
                "age": 30,
                "biological_sex": "male",
                "activity_level": "moderate",
                "goal": "weight_loss"
            }
        }


# ==================== RESPONSE SCHEMAS ====================

class NutritionalCalculations(BaseModel):
    """Cálculos nutricionales automáticos"""
    bmi: float = Field(..., description="Índice de Masa Corporal")
    bmi_category: BMICategory = Field(..., description="Categoría de IMC")
    bmr: int = Field(..., description="Metabolismo basal en kcal")
    tdee: int = Field(..., description="Gasto energético diario total")
    target_calories: int = Field(..., description="Calorías objetivo")
    deficit_or_surplus: int = Field(..., description="Déficit o superávit calórico")
    target_protein_g: int = Field(..., description="Proteína objetivo en gramos")
    target_carbs_g: int = Field(..., description="Carbohidratos objetivo en gramos")
    target_fat_g: int = Field(..., description="Grasas objetivo en gramos")
    target_fiber_g: int = Field(..., description="Fibra objetivo en gramos")
    water_liters: float = Field(..., description="Agua recomendada en litros")

    class Config:
        schema_extra = {
            "example": {
                "bmi": 24.5,
                "bmi_category": "normal",
                "bmr": 1750,
                "tdee": 2400,
                "target_calories": 1900,
                "deficit_or_surplus": -500,
                "target_protein_g": 150,
                "target_carbs_g": 190,
                "target_fat_g": 63,
                "target_fiber_g": 30,
                "water_liters": 2.5
            }
        }


class NutritionProfileResponse(BaseModel):
    """Response al crear/actualizar perfil nutricional"""
    profile_id: int
    calculations: NutritionalCalculations
    warnings: List[str] = Field(default_factory=list)
    profile_completion_percentage: int
    can_generate_plan: bool
    missing_required_fields: List[str] = Field(default_factory=list)
    optimization_suggestions: List[str] = Field(default_factory=list)

    class Config:
        schema_extra = {
            "example": {
                "profile_id": 456,
                "calculations": {
                    "bmi": 24.5,
                    "bmi_category": "normal",
                    "bmr": 1750,
                    "tdee": 2400,
                    "target_calories": 1900,
                    "deficit_or_surplus": -500,
                    "target_protein_g": 150,
                    "target_carbs_g": 190,
                    "target_fat_g": 63,
                    "target_fiber_g": 30,
                    "water_liters": 2.5
                },
                "warnings": [
                    "Déficit calórico agresivo, considera empezar con -300 kcal"
                ],
                "profile_completion_percentage": 75,
                "can_generate_plan": True,
                "missing_required_fields": [],
                "optimization_suggestions": [
                    "Agregar preferencias culinarias mejorará la personalización"
                ]
            }
        }


class ProfileSummary(BaseModel):
    """Resumen del perfil para mostrar antes de generar"""
    goal: str
    target_calories: int
    dietary_restrictions: List[str]
    allergies: List[str]
    excluded_foods: List[str]
    budget: str
    cooking_time: str
    special_equipment: List[str]
    profile_strength: Literal["basic", "good", "excellent"]

    class Config:
        schema_extra = {
            "example": {
                "goal": "Pérdida de peso (-0.5 kg/semana)",
                "target_calories": 1900,
                "dietary_restrictions": ["Sin gluten"],
                "allergies": ["Nueces", "Mariscos"],
                "excluded_foods": ["Cilantro", "Brócoli"],
                "budget": "Moderado ($50-100/semana)",
                "cooking_time": "30 minutos por comida",
                "special_equipment": ["Freidora de aire"],
                "profile_strength": "good"
            }
        }


# ==================== PROGRESSIVE PROFILING SCHEMAS ====================

class ProgressiveQuestion(BaseModel):
    """Pregunta individual de progressive profiling"""
    id: str
    question: str
    type: Literal["boolean", "number", "text", "scale", "multiselect", "select"]
    required: bool = False
    options: Optional[List[str]] = None
    min_value: Optional[int] = None
    max_value: Optional[int] = None
    unit: Optional[str] = None

    class Config:
        schema_extra = {
            "example": {
                "id": "cooks_for_family",
                "question": "¿Cocinas para tu familia?",
                "type": "boolean",
                "required": False
            }
        }


class ProgressiveQuestionSet(BaseModel):
    """Conjunto de preguntas de progressive profiling"""
    question_set: str
    questions: List[ProgressiveQuestion]
    optional: bool = True
    can_skip: bool = True
    estimated_time_seconds: int = 30

    class Config:
        schema_extra = {
            "example": {
                "question_set": "day_1",
                "questions": [
                    {
                        "id": "cooks_for_family",
                        "question": "¿Cocinas para tu familia?",
                        "type": "boolean"
                    },
                    {
                        "id": "eats_out_weekly",
                        "question": "¿Cuántas veces comes fuera por semana?",
                        "type": "number",
                        "min_value": 0,
                        "max_value": 14
                    }
                ],
                "optional": True,
                "can_skip": True,
                "estimated_time_seconds": 30
            }
        }


class ProgressiveResponseRequest(BaseModel):
    """Request para guardar respuestas de progressive profiling"""
    question_set: str
    responses: Dict[str, any]

    class Config:
        schema_extra = {
            "example": {
                "question_set": "day_1",
                "responses": {
                    "cooks_for_family": True,
                    "eats_out_weekly": 4
                }
            }
        }


class ProgressiveResponseResult(BaseModel):
    """Resultado de guardar respuestas progressive"""
    success: bool
    profile_completion_percentage: int
    adjustments_suggested: bool
    adjustments: Optional[Dict] = None
    next_questions_available_in_days: Optional[int] = None

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "profile_completion_percentage": 85,
                "adjustments_suggested": False,
                "adjustments": None,
                "next_questions_available_in_days": 6
            }
        }


# ==================== DATABASE SCHEMAS ====================

class NutritionProfileDB(BaseModel):
    """Schema para almacenamiento en DB del perfil"""
    id: int
    user_id: int
    gym_id: int

    # Datos básicos
    goal: NutritionalGoal
    weight_kg: float
    height_cm: float
    age: int
    biological_sex: str
    activity_level: ActivityLevel

    # Cálculos
    bmi: float
    bmr: int
    tdee: int
    target_calories: int
    target_protein_g: int
    target_carbs_g: int
    target_fat_g: int

    # Restricciones
    dietary_restriction: DietaryRestriction
    allergies: List[str]
    disliked_foods: Optional[str]
    budget_level: BudgetLevel
    cooking_time_minutes: int

    # Progressive profiling
    cooks_for_family: Optional[bool]
    family_size: Optional[int]
    eats_out_weekly: Optional[int]
    meal_prep_experience: Optional[str]
    supplements: Optional[List[str]]
    waist_cm: Optional[float]
    body_fat_percentage: Optional[float]

    # Metadata
    profile_completion_percentage: int
    created_at: datetime
    updated_at: datetime
    last_plan_generated_at: Optional[datetime]

    class Config:
        orm_mode = True


# ==================== UTILITY FUNCTIONS ====================

def calculate_bmi(weight_kg: float, height_cm: float) -> tuple[float, BMICategory]:
    """Calcula IMC y su categoría"""
    height_m = height_cm / 100
    bmi = round(weight_kg / (height_m ** 2), 1)

    if bmi < 18.5:
        category = BMICategory.UNDERWEIGHT
    elif bmi < 25:
        category = BMICategory.NORMAL
    elif bmi < 30:
        category = BMICategory.OVERWEIGHT
    else:
        category = BMICategory.OBESE

    return bmi, category


def calculate_bmr(weight_kg: float, height_cm: float, age: int, sex: str) -> int:
    """Calcula BMR usando Mifflin-St Jeor"""
    if sex == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    return int(bmr)


def calculate_tdee(bmr: int, activity_level: ActivityLevel) -> int:
    """Calcula TDEE basado en actividad"""
    multipliers = {
        ActivityLevel.LOW: 1.2,
        ActivityLevel.MODERATE: 1.55,
        ActivityLevel.HIGH: 1.725
    }
    return int(bmr * multipliers[activity_level])


def calculate_profile_completion(profile: NutritionProfileDB) -> int:
    """Calcula el porcentaje de completitud del perfil"""
    total_fields = 25  # Total de campos posibles
    completed = 10  # Campos obligatorios siempre completos

    # Campos opcionales
    if profile.cooks_for_family is not None:
        completed += 1
    if profile.family_size is not None:
        completed += 1
    if profile.eats_out_weekly is not None:
        completed += 1
    if profile.meal_prep_experience:
        completed += 1
    if profile.supplements:
        completed += 1
    if profile.waist_cm:
        completed += 2  # Vale más
    if profile.body_fat_percentage:
        completed += 2  # Vale más

    # Campos de preferencias
    if profile.disliked_foods:
        completed += 1
    if len(profile.allergies) > 0:
        completed += 1

    return int((completed / total_fields) * 100)