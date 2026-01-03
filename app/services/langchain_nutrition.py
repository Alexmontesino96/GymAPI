"""
Generador de planes nutricionales usando LangChain para mayor robustez.
Proporciona validación estricta de tipos y mejor manejo de errores.
"""

from typing import List, Dict, Any, Literal, Optional
from pydantic import BaseModel, Field, validator
from langchain.schema import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
import json
import logging
from datetime import datetime

from app.schemas.nutrition import AIGenerationRequest
from app.models.nutrition import MealType

logger = logging.getLogger(__name__)


class IngredientSchema(BaseModel):
    """Schema para un ingrediente con validación."""
    name: str = Field(..., description="Nombre del ingrediente")
    quantity: float = Field(ge=0, description="Cantidad del ingrediente")
    unit: str = Field(..., description="Unidad de medida (g, ml, unidad, etc)")


class MealSchema(BaseModel):
    """Schema para una comida con validación estricta."""
    name: str = Field(..., min_length=3, max_length=200)
    meal_type: Literal["breakfast", "mid_morning", "lunch", "afternoon", "dinner", "late_snack", "post_workout"]
    calories: int = Field(ge=50, le=2000, description="Calorías de la comida")
    protein: float = Field(ge=0, le=200, description="Proteína en gramos")
    carbs: float = Field(ge=0, le=300, description="Carbohidratos en gramos")
    fat: float = Field(ge=0, le=100, description="Grasa en gramos")
    ingredients: List[IngredientSchema] = Field(min_items=1, max_items=5)
    instructions: str = Field(..., min_length=10, max_length=500)

    @validator('meal_type', pre=True)
    def map_meal_type(cls, v):
        """Mapea tipos incorrectos a tipos válidos."""
        if isinstance(v, str):
            v = v.lower().strip()

        # Mapeo de tipos comunes incorrectos
        mapping = {
            'snack': 'mid_morning',
            'morning_snack': 'mid_morning',
            'morning snack': 'mid_morning',
            'afternoon_snack': 'afternoon',
            'afternoon snack': 'afternoon',
            'evening_snack': 'late_snack',
            'evening snack': 'late_snack',
            'night_snack': 'late_snack',
            'brunch': 'mid_morning',
            'merienda': 'afternoon',
            'colación': 'mid_morning',
            'tentempié': 'mid_morning'
        }

        return mapping.get(v, v)

    @validator('calories', 'protein', 'carbs', 'fat')
    def validate_macros(cls, v):
        """Asegura que los macros sean números positivos."""
        return max(0, v) if v else 0


class DayPlanSchema(BaseModel):
    """Schema para un día del plan nutricional."""
    day_number: int = Field(ge=1, le=30)
    day_name: str = Field(..., min_length=3, max_length=20)
    meals: List[MealSchema] = Field(..., min_items=3, max_items=6)

    @validator('meals')
    def validate_meals_order(cls, meals):
        """Valida que las comidas estén en orden lógico."""
        # Orden esperado de comidas
        meal_order = {
            'breakfast': 1,
            'mid_morning': 2,
            'lunch': 3,
            'afternoon': 4,
            'dinner': 5,
            'late_snack': 6,
            'post_workout': 7  # Puede estar en cualquier momento
        }

        # Ordenar comidas según el orden lógico
        sorted_meals = sorted(meals, key=lambda m: meal_order.get(m.meal_type, 99))
        return sorted_meals

    @property
    def total_calories(self) -> int:
        """Calcula las calorías totales del día."""
        return sum(meal.calories for meal in self.meals)

    @property
    def total_protein(self) -> float:
        """Calcula la proteína total del día."""
        return sum(meal.protein for meal in self.meals)

    @property
    def total_carbs(self) -> float:
        """Calcula los carbohidratos totales del día."""
        return sum(meal.carbs for meal in self.meals)

    @property
    def total_fat(self) -> float:
        """Calcula la grasa total del día."""
        return sum(meal.fat for meal in self.meals)


class NutritionPlanResponse(BaseModel):
    """Schema para la respuesta completa del plan nutricional."""
    days: List[DayPlanSchema] = Field(..., min_items=1, max_items=30)


class LangChainNutritionGenerator:
    """Generador de planes nutricionales usando LangChain con validación robusta."""

    def __init__(self, api_key: str):
        """Inicializa el generador con la clave API de OpenAI."""
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.3,
            max_tokens=800,
            api_key=api_key,
            model_kwargs={
                "response_format": {"type": "json_object"}
            }
        )
        self.parser = PydanticOutputParser(pydantic_object=NutritionPlanResponse)

    def generate_nutrition_plan(self, request: AIGenerationRequest, start_day: int, end_day: int) -> Dict[str, Any]:
        """
        Genera un plan nutricional usando LangChain con validación estricta.

        Args:
            request: Solicitud con los parámetros del plan
            start_day: Día de inicio (1-based)
            end_day: Día final (inclusive)

        Returns:
            Dict con los días generados y validados
        """
        try:
            # Construir el prompt del sistema
            system_prompt = self._build_system_prompt()

            # Construir el prompt del usuario
            user_prompt = self._build_user_prompt(request, start_day, end_day)

            # Agregar instrucciones del parser
            format_instructions = self.parser.get_format_instructions()
            full_user_prompt = f"{user_prompt}\n\n{format_instructions}"

            # Crear mensajes para el LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=full_user_prompt)
            ]

            # Generar respuesta
            logger.info(f"Generando días {start_day} a {end_day} con LangChain...")
            response = self.llm.invoke(messages)

            # Parsear y validar respuesta
            try:
                # Intentar parsear con Pydantic
                parsed_response = self.parser.parse(response.content)
                logger.info(f"Respuesta parseada y validada exitosamente")

                # Convertir a diccionario
                return parsed_response.dict()

            except Exception as parse_error:
                logger.warning(f"Error al parsear con Pydantic, intentando reparación: {parse_error}")

                # Intentar reparar el JSON
                repaired_json = self._repair_json(response.content)
                parsed_response = NutritionPlanResponse.parse_obj(repaired_json)
                return parsed_response.dict()

        except Exception as e:
            logger.error(f"Error generando plan con LangChain: {e}")
            # Generar respuesta mock como fallback
            return self._generate_fallback_days(request, start_day, end_day)

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema optimizado."""
        return """Eres un nutricionista experto que crea planes alimenticios personalizados.

IMPORTANTE: Genera un plan nutricional en formato JSON válido siguiendo EXACTAMENTE esta estructura:

{
  "days": [
    {
      "day_number": 1,
      "day_name": "Lunes",
      "meals": [
        {
          "name": "Nombre descriptivo de la comida",
          "meal_type": "breakfast|mid_morning|lunch|afternoon|dinner",
          "calories": 400,
          "protein": 30.0,
          "carbs": 45.0,
          "fat": 12.0,
          "ingredients": [
            {"name": "ingrediente1", "quantity": 100, "unit": "g"},
            {"name": "ingrediente2", "quantity": 200, "unit": "ml"}
          ],
          "instructions": "Instrucciones breves de preparación"
        }
      ]
    }
  ]
}

TIPOS DE COMIDA VÁLIDOS (usa SOLO estos):
- breakfast: Desayuno
- mid_morning: Colación media mañana
- lunch: Almuerzo
- afternoon: Merienda/colación tarde
- dinner: Cena

REGLAS CRÍTICAS:
1. Usa EXACTAMENTE los meal_type especificados arriba
2. NUNCA uses "snack" - usa "mid_morning" o "afternoon"
3. Incluye 3-5 ingredientes máximo por comida
4. Las calorías deben sumar el objetivo diario ±5%
5. Instrucciones concisas (máximo 2 líneas)
6. Varía las comidas entre días"""

    def _build_user_prompt(self, request: AIGenerationRequest, start_day: int, end_day: int) -> str:
        """Construye el prompt del usuario con los parámetros específicos."""
        days_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        days_to_generate = []
        for day in range(start_day, end_day + 1):
            day_name = days_names[(day - 1) % 7]
            days_to_generate.append(f"día {day} ({day_name})")

        # Determinar distribución de comidas
        meals_per_day = request.meals_per_day if hasattr(request, 'meals_per_day') else 5

        if meals_per_day == 3:
            meal_distribution = "3 comidas: breakfast, lunch, dinner"
        elif meals_per_day == 4:
            meal_distribution = "4 comidas: breakfast, mid_morning, lunch, dinner"
        elif meals_per_day == 5:
            meal_distribution = "5 comidas: breakfast, mid_morning, lunch, afternoon, dinner"
        else:
            meal_distribution = "5 comidas: breakfast, mid_morning, lunch, afternoon, dinner"

        return f"""Genera un plan nutricional para {', '.join(days_to_generate)}.

OBJETIVOS NUTRICIONALES:
- Objetivo: {request.goal.value}
- Calorías diarias: {request.target_calories} kcal
- Proteína: {request.target_protein_g}g
- Carbohidratos: {request.target_carbs_g}g
- Grasas: {request.target_fat_g}g

DISTRIBUCIÓN:
{meal_distribution}

CONSIDERACIONES:
- Dificultad: {request.difficulty_level.value if hasattr(request, 'difficulty_level') else 'beginner'}
- Presupuesto: {request.budget_level.value if hasattr(request, 'budget_level') else 'medium'}
- Restricciones: {request.dietary_restrictions.value if hasattr(request, 'dietary_restrictions') else 'none'}

Genera el plan completo en JSON válido."""

    def _repair_json(self, json_str: str) -> Dict:
        """Intenta reparar JSON malformado."""
        try:
            # Intentar parsear directamente
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Intentar limpiar y reparar
            json_str = json_str.strip()

            # Remover posibles caracteres de control
            json_str = ''.join(char for char in json_str if ord(char) >= 32 or char == '\n')

            # Si empieza con ``` quitarlo
            if json_str.startswith('```'):
                json_str = json_str.split('```')[1]
                if json_str.startswith('json'):
                    json_str = json_str[4:]

            # Intentar de nuevo
            try:
                return json.loads(json_str)
            except:
                # Último intento: extraer JSON del texto
                import re
                json_match = re.search(r'\{[\s\S]*\}', json_str)
                if json_match:
                    return json.loads(json_match.group())
                raise

    def _generate_fallback_days(self, request: AIGenerationRequest, start_day: int, end_day: int) -> Dict:
        """Genera días de respaldo cuando falla la generación con IA."""
        days = []
        days_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        for day_num in range(start_day, end_day + 1):
            day_name = days_names[(day_num - 1) % 7]

            meals = [
                MealSchema(
                    name=f"Desayuno Día {day_num}",
                    meal_type="breakfast",
                    calories=int(request.target_calories * 0.25),
                    protein=request.target_protein_g * 0.25,
                    carbs=request.target_carbs_g * 0.25,
                    fat=request.target_fat_g * 0.25,
                    ingredients=[
                        IngredientSchema(name="Avena", quantity=60, unit="g"),
                        IngredientSchema(name="Plátano", quantity=1, unit="unidad")
                    ],
                    instructions="Cocinar la avena y agregar el plátano en rodajas"
                ),
                MealSchema(
                    name=f"Colación Día {day_num}",
                    meal_type="mid_morning",
                    calories=int(request.target_calories * 0.1),
                    protein=request.target_protein_g * 0.1,
                    carbs=request.target_carbs_g * 0.1,
                    fat=request.target_fat_g * 0.1,
                    ingredients=[
                        IngredientSchema(name="Yogur griego", quantity=150, unit="g"),
                        IngredientSchema(name="Frutos secos", quantity=30, unit="g")
                    ],
                    instructions="Mezclar el yogur con los frutos secos"
                ),
                MealSchema(
                    name=f"Almuerzo Día {day_num}",
                    meal_type="lunch",
                    calories=int(request.target_calories * 0.35),
                    protein=request.target_protein_g * 0.35,
                    carbs=request.target_carbs_g * 0.35,
                    fat=request.target_fat_g * 0.35,
                    ingredients=[
                        IngredientSchema(name="Pechuga de pollo", quantity=150, unit="g"),
                        IngredientSchema(name="Arroz integral", quantity=80, unit="g"),
                        IngredientSchema(name="Vegetales mixtos", quantity=200, unit="g")
                    ],
                    instructions="Cocinar el pollo a la plancha y servir con arroz y vegetales"
                ),
                MealSchema(
                    name=f"Merienda Día {day_num}",
                    meal_type="afternoon",
                    calories=int(request.target_calories * 0.1),
                    protein=request.target_protein_g * 0.1,
                    carbs=request.target_carbs_g * 0.1,
                    fat=request.target_fat_g * 0.1,
                    ingredients=[
                        IngredientSchema(name="Manzana", quantity=1, unit="unidad"),
                        IngredientSchema(name="Mantequilla de maní", quantity=20, unit="g")
                    ],
                    instructions="Cortar la manzana y servir con mantequilla de maní"
                ),
                MealSchema(
                    name=f"Cena Día {day_num}",
                    meal_type="dinner",
                    calories=int(request.target_calories * 0.2),
                    protein=request.target_protein_g * 0.2,
                    carbs=request.target_carbs_g * 0.2,
                    fat=request.target_fat_g * 0.2,
                    ingredients=[
                        IngredientSchema(name="Salmón", quantity=120, unit="g"),
                        IngredientSchema(name="Quinoa", quantity=60, unit="g"),
                        IngredientSchema(name="Espárragos", quantity=150, unit="g")
                    ],
                    instructions="Hornear el salmón y servir con quinoa y espárragos al vapor"
                )
            ]

            day_plan = DayPlanSchema(
                day_number=day_num,
                day_name=day_name,
                meals=meals
            )

            days.append(day_plan.dict())

        return {"days": days}