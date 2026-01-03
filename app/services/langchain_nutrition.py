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
            temperature=0.2,
            max_tokens=1200,
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

            # Instrucción breve para limitar a JSON válido
            full_user_prompt = f"{user_prompt}\n\nDevuelve SOLO JSON válido con la estructura indicada."

            # Crear mensajes para el LLM
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=full_user_prompt)
            ]

            # Generar respuesta
            logger.info(f"Generando días {start_day} a {end_day} con LangChain...")
            response = self.llm.invoke(messages)

            # LOG: Respuesta de LangChain/OpenAI
            logger.info(f"LangChain response for days {start_day}-{end_day}:")
            logger.info(f"  - Response length: {len(response.content)} chars")
            logger.debug(f"  - Raw response (first 500 chars): {response.content[:500]}...")
            if len(response.content) > 500:
                logger.debug(f"  - Raw response (last 200 chars): ...{response.content[-200:]}")

            # Parsear y validar respuesta
            try:
                # Intentar parsear con Pydantic
                parsed_response = self.parser.parse(response.content)
                logger.info(f"  ✅ Respuesta parseada y validada exitosamente con Pydantic")
                logger.info(f"  ✅ Days generated: {len(parsed_response.days)}")

                # Convertir a diccionario
                return parsed_response.dict()

            except Exception as parse_error:
                logger.warning(f"Error al parsear con Pydantic, intentando reparación: {parse_error}")
                # Intentar reparar el JSON y parsear nuevamente
                repaired_json = self._repair_json(response.content)
                if repaired_json:
                    try:
                        parsed_response = NutritionPlanResponse.parse_obj(repaired_json)
                        return parsed_response.dict()
                    except Exception:
                        pass
                # Fallback mínimo: devolver estructura simple si no se puede reparar
                return {"days": []}

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
        - Proteína: {getattr(request, 'target_protein_g', None) or 0}g
        - Carbohidratos: {getattr(request, 'target_carbs_g', None) or 0}g
        - Grasas: {getattr(request, 'target_fat_g', None) or 0}g

DISTRIBUCIÓN:
{meal_distribution}

CONSIDERACIONES:
        - Dificultad: {request.difficulty_level.value if hasattr(request, 'difficulty_level') else 'beginner'}
        - Presupuesto: {request.budget_level.value if hasattr(request, 'budget_level') else 'medium'}
        - Restricciones: {', '.join(request.dietary_restrictions) if getattr(request, 'dietary_restrictions', None) else 'none'}

Genera el plan completo en JSON válido."""

    def _repair_json(self, content: str) -> Optional[Dict]:
        """Intenta reparar JSON malformado con varias estrategias no destructivas."""
        import re

        if not content:
            return None

        # 1) Limpieza básica
        s = content.strip()
        # Remover fences ```json ... ``` o ``` ... ```
        if s.startswith('```'):
            parts = s.split('```')
            # elegir el bloque más largo probable de JSON
            s = max(parts, key=len)
            if s.startswith('json'):
                s = s[4:]
        # Remover caracteres de control
        s = ''.join(ch for ch in s if ord(ch) >= 32 or ch in '\n\r\t')

        # 2) Intento directo
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass

        # 3) Extraer desde la primera '{' hasta la última '}' y balancear
        start = s.find('{')
        end = s.rfind('}')
        if start != -1 and end != -1 and end > start:
            candidate = s[start:end+1]
            # Balanceo simple de llaves y corchetes
            def balance_text(txt: str) -> str:
                open_brace = close_brace = 0
                open_bracket = close_bracket = 0
                last_balanced = 0
                for i, ch in enumerate(txt):
                    if ch == '{':
                        open_brace += 1
                    elif ch == '}':
                        close_brace += 1
                    elif ch == '[':
                        open_bracket += 1
                    elif ch == ']':
                        close_bracket += 1
                    if open_brace == close_brace and open_bracket == close_bracket:
                        last_balanced = i
                # Cortar en el último punto balanceado
                cut = txt[:last_balanced+1]
                # Reparar comas colgantes
                cut = re.sub(r',\s*([}\]])', r'\1', cut)
                # Cerrar si faltan
                if cut.count('{') > cut.count('}'):
                    cut += '}' * (cut.count('{') - cut.count('}'))
                if cut.count('[') > cut.count(']'):
                    cut += ']' * (cut.count('[') - cut.count(']'))
                return cut

            balanced = balance_text(candidate)
            try:
                return json.loads(balanced)
            except json.JSONDecodeError:
                pass

        # 4) Regex: tomar el mayor bloque que empiece en '{' y termine en '}'
        matches = re.findall(r'\{[\s\S]*?\}', s)
        for m in reversed(matches):  # probar del más largo al más corto
            try:
                return json.loads(m)
            except Exception:
                continue

        return None

    def _generate_fallback_days(self, request: AIGenerationRequest, start_day: int, end_day: int) -> Dict:
        """Genera días de respaldo cuando falla la generación con IA."""
        days = []
        days_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

        # Calcular macros objetivo si faltan en la request
        protein_g = getattr(request, 'target_protein_g', None)
        carbs_g = getattr(request, 'target_carbs_g', None)
        fat_g = getattr(request, 'target_fat_g', None)

        if protein_g is None or carbs_g is None or fat_g is None:
            goal = request.goal.value if hasattr(request.goal, 'value') else str(request.goal)
            distributions = {
                'weight_loss': (0.30, 0.40, 0.30),
                'muscle_gain': (0.25, 0.50, 0.25),
                'definition': (0.35, 0.35, 0.30),
                'maintenance': (0.20, 0.50, 0.30),
                'performance': (0.20, 0.55, 0.25),
                'bulk': (0.25, 0.50, 0.25),
                'cut': (0.35, 0.35, 0.30),
            }
            p_pct, c_pct, f_pct = distributions.get(goal, (0.30, 0.40, 0.30))
            calories = max(getattr(request, 'target_calories', 0) or 0, 0)
            protein_g = round((calories * p_pct) / 4, 1)
            carbs_g = round((calories * c_pct) / 4, 1)
            fat_g = round((calories * f_pct) / 9, 1)

        for day_num in range(start_day, end_day + 1):
            day_name = days_names[(day_num - 1) % 7]

            meals = [
                MealSchema(
                    name=f"Desayuno Día {day_num}",
                    meal_type="breakfast",
                    calories=int(request.target_calories * 0.25),
                    protein=protein_g * 0.25,
                    carbs=carbs_g * 0.25,
                    fat=fat_g * 0.25,
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
                    protein=protein_g * 0.1,
                    carbs=carbs_g * 0.1,
                    fat=fat_g * 0.1,
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
                    protein=protein_g * 0.35,
                    carbs=carbs_g * 0.35,
                    fat=fat_g * 0.35,
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
                    protein=protein_g * 0.1,
                    carbs=carbs_g * 0.1,
                    fat=fat_g * 0.1,
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
                    protein=protein_g * 0.2,
                    carbs=carbs_g * 0.2,
                    fat=fat_g * 0.2,
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
