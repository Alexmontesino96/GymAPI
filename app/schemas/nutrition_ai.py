"""
Schemas para la funcionalidad de IA nutricional.
Maneja requests y responses para la generación automática de ingredientes.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Optional
from app.models.nutrition import DietaryRestriction


class AIIngredientRequest(BaseModel):
    """Request para generar ingredientes con IA"""
    recipe_name: str = Field(
        ..., 
        min_length=3, 
        max_length=200,
        description="Nombre de la receta (ej: 'Paella de mariscos')"
    )
    servings: int = Field(
        4, 
        ge=1, 
        le=20,
        description="Número de porciones"
    )
    dietary_restrictions: Optional[List[DietaryRestriction]] = Field(
        default=[],
        description="Restricciones dietéticas"
    )
    cuisine_type: Optional[str] = Field(
        None,
        max_length=50,
        description="Tipo de cocina (española, italiana, mexicana, etc.)"
    )
    target_calories: Optional[int] = Field(
        None, 
        ge=100, 
        le=2000,
        description="Calorías objetivo por porción"
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Notas adicionales o preferencias"
    )

    @validator('recipe_name')
    def validate_recipe_name(cls, v):
        if not v or v.strip() == "":
            raise ValueError('El nombre de la receta no puede estar vacío')
        return v.strip()

    @validator('cuisine_type')
    def validate_cuisine_type(cls, v):
        if v:
            return v.strip().lower()
        return v


class GeneratedIngredient(BaseModel):
    """Ingrediente generado por IA"""
    name: str = Field(..., description="Nombre específico del ingrediente")
    quantity: float = Field(..., gt=0, description="Cantidad numérica")
    unit: str = Field(..., description="Unidad de medida (gr, ml, units, cups, tbsp)")
    calories_per_unit: float = Field(..., ge=0, le=9, description="Calorías por unidad")
    protein_g_per_unit: float = Field(..., ge=0, le=1, description="Proteína por unidad (gramos)")
    carbs_g_per_unit: float = Field(..., ge=0, le=1, description="Carbohidratos por unidad (gramos)")
    fat_g_per_unit: float = Field(..., ge=0, le=1, description="Grasas por unidad (gramos)")
    fiber_g_per_unit: float = Field(..., ge=0, le=1, description="Fibra por unidad (gramos)")
    notes: Optional[str] = Field(None, description="Notas adicionales del ingrediente")
    confidence_score: float = Field(0.8, ge=0, le=1, description="Confianza de la IA (0-1)")

    @validator('unit')
    def validate_unit(cls, v):
        valid_units = ['gr', 'ml', 'units', 'cups', 'tbsp', 'tsp', 'oz', 'kg', 'l']
        if v.lower() not in valid_units:
            raise ValueError(f'Unidad debe ser una de: {", ".join(valid_units)}')
        return v.lower()

    @validator('name')
    def validate_ingredient_name(cls, v):
        if len(v.strip()) < 2:
            raise ValueError('El nombre del ingrediente debe tener al menos 2 caracteres')
        return v.strip()


class AIRecipeResponse(BaseModel):
    """Response completa de la generación de receta con IA"""
    model_config = {"protected_namespaces": ()}  # Permitir campos que empiecen con "model_"
    
    success: bool = Field(..., description="Si la generación fue exitosa")
    ingredients: List[GeneratedIngredient] = Field(
        ..., 
        min_items=1, 
        max_items=25,
        description="Lista de ingredientes generados"
    )
    recipe_instructions: Optional[str] = Field(
        None, 
        description="Instrucciones paso a paso de preparación"
    )
    estimated_prep_time: Optional[int] = Field(
        None, 
        ge=1, 
        le=300,
        description="Tiempo estimado de preparación en minutos"
    )
    difficulty_level: Optional[str] = Field(
        None,
        description="Nivel de dificultad: beginner, intermediate, advanced"
    )
    total_estimated_calories: int = Field(
        ..., 
        ge=0,
        description="Calorías totales estimadas de la receta"
    )
    confidence_score: float = Field(
        0.8, 
        ge=0, 
        le=1,
        description="Confianza general de la IA en la respuesta"
    )
    model_used: str = Field(
        "gpt-4o-mini",
        description="Modelo de IA utilizado"
    )
    generation_time_ms: Optional[int] = Field(
        None,
        description="Tiempo de generación en milisegundos"
    )

    @validator('ingredients')
    def validate_ingredients_count(cls, v):
        if len(v) < 1:
            raise ValueError('Debe haber al menos 1 ingrediente')
        if len(v) > 25:
            raise ValueError('Máximo 25 ingredientes permitidos')
        return v

    @validator('difficulty_level')
    def validate_difficulty(cls, v):
        if v and v not in ['beginner', 'intermediate', 'advanced']:
            raise ValueError('Dificultad debe ser: beginner, intermediate o advanced')
        return v


class AIIngredientError(BaseModel):
    """Error en la generación de ingredientes"""
    success: bool = False
    error_type: str = Field(..., description="Tipo de error")
    error_message: str = Field(..., description="Mensaje de error")
    retry_suggested: bool = Field(False, description="Si se sugiere reintentar")
    model_used: Optional[str] = Field(None, description="Modelo que causó el error")


# Schema para aplicar ingredientes generados a una comida
class ApplyGeneratedIngredientsRequest(BaseModel):
    """Request para aplicar ingredientes generados a una comida"""
    ingredients: List[GeneratedIngredient] = Field(
        ...,
        min_items=1,
        description="Ingredientes a aplicar a la comida"
    )
    replace_existing: bool = Field(
        False,
        description="Si reemplazar ingredientes existentes o agregar"
    )
    update_meal_nutrition: bool = Field(
        True,
        description="Si actualizar automáticamente los valores nutricionales de la comida"
    )


class ApplyIngredientsResponse(BaseModel):
    """Response al aplicar ingredientes a una comida"""
    success: bool = Field(..., description="Si la aplicación fue exitosa")
    ingredients_added: int = Field(..., description="Número de ingredientes agregados")
    ingredients_replaced: int = Field(0, description="Número de ingredientes reemplazados")
    meal_updated: bool = Field(..., description="Si la comida fue actualizada")
    total_calories: Optional[float] = Field(None, description="Calorías totales actualizadas")
    total_protein: Optional[float] = Field(None, description="Proteína total actualizada")
    total_carbs: Optional[float] = Field(None, description="Carbohidratos totales actualizados")
    total_fat: Optional[float] = Field(None, description="Grasas totales actualizadas") 