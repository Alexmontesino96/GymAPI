"""
Servicio de IA para generación de planes nutricionales usando OpenAI GPT-4o-mini.
Genera planes completos con días, comidas e ingredientes.
Soporta tanto OpenAI directo como LangChain para mayor robustez.
"""

import os
import json
import time
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging

from openai import OpenAI
from sqlalchemy.orm import Session

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal, MealIngredient,
    NutritionGoal, DifficultyLevel, BudgetLevel, MealType, PlanType
)
from app.schemas.nutrition import AIGenerationRequest
from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Intentar importar LangChain si está disponible
try:
    from app.services.langchain_nutrition import LangChainNutritionGenerator
    LANGCHAIN_AVAILABLE = True
    logger.info("LangChain disponible para generación nutricional")
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logger.warning("LangChain no está disponible. Usando generación directa con OpenAI.")


class NutritionAIService:
    """
    Servicio para generar planes nutricionales usando OpenAI GPT-4o-mini.
    Costo aproximado: $0.002 por plan generado.
    """

    def __init__(self):
        """Inicializar cliente OpenAI con API key y opcionalmente LangChain."""
        settings = get_settings()
        # Usar CHAT_GPT_MODEL primero, luego OPENAI_API_KEY como fallback
        self.api_key = settings.CHAT_GPT_MODEL or settings.OPENAI_API_KEY
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                timeout=40.0,  # Timeout de 40 segundos para manejar variabilidad
                max_retries=1  # Solo 1 reintento para no demorar demasiado
            )

            # Inicializar LangChain si está disponible
            if LANGCHAIN_AVAILABLE:
                try:
                    self.langchain_generator = LangChainNutritionGenerator(self.api_key)
                    self.use_langchain = True
                    logger.info("LangChain generator inicializado exitosamente")
                except Exception as e:
                    logger.error(f"Error inicializando LangChain: {e}")
                    self.langchain_generator = None
                    self.use_langchain = False
            else:
                self.langchain_generator = None
                self.use_langchain = False
        else:
            logger.warning("OpenAI API key not configured (CHAT_GPT_MODEL or OPENAI_API_KEY)")
            self.client = None
            self.langchain_generator = None
            self.use_langchain = False

        self.model = "gpt-4o-mini"  # Modelo más rápido
        self.max_retries = 3

    def _build_system_prompt(self) -> str:
        """Construir el prompt del sistema para nutrición."""
        return """Eres un nutricionista experto que crea planes de alimentación personalizados.

        IMPORTANTE: Genera un JSON válido y COMPACTO, sin texto adicional.

        Estructura SIMPLIFICADA del JSON:
        {
            "title": "Nombre del plan",
            "description": "Descripción breve",
            "daily_plans": [
                {
                    "day_number": 1,
                    "day_name": "Lunes",
                    "total_calories": 2000,
                    "total_protein": 125,
                    "total_carbs": 250,
                    "total_fat": 65,
                    "meals": [
                        {
                            "name": "Nombre de la comida",
                            "meal_type": "breakfast",
                            "calories": 400,
                            "protein": 25,
                            "carbs": 50,
                            "fat": 13,
                            "prep_time_minutes": 15,
                            "ingredients": [
                                {
                                    "name": "Ingrediente principal",
                                    "quantity": 100,
                                    "unit": "g"
                                }
                            ],
                            "instructions": "Preparar y servir"
                        }
                    ]
                }
            ]
        }

        Reglas:
        1. Calorías diarias ±5% del objetivo
        2. NO repetir comidas principales
        3. Macros correctos
        4. Ingredientes simples (máx 3-5 por comida)
        5. Instrucciones breves (1 línea)
        6. Respetar restricciones

        IMPORTANTE: Mantén el JSON COMPACTO. NO incluyas valores nutricionales de cada ingrediente.
        """

    def _build_user_prompt(self, request: AIGenerationRequest) -> str:
        """Construir el prompt del usuario basado en la request."""
        # Mapear objetivo a descripción
        goal_descriptions = {
            "weight_loss": "pérdida de peso con déficit calórico controlado",
            "muscle_gain": "ganancia de masa muscular con superávit calórico",
            "definition": "definición muscular manteniendo la masa magra",
            "maintenance": "mantenimiento del peso actual",
            "performance": "optimización del rendimiento deportivo"
        }

        # Construir prompt con todos los parámetros
        prompt = f"""Crea un plan nutricional con estas características:

INFORMACIÓN BÁSICA:
- Objetivo: {goal_descriptions.get(request.goal.value, request.goal.value)}
- Calorías diarias: {request.target_calories} kcal
- Duración: {request.duration_days} días
- Comidas por día: {request.user_context.get('meals_per_day', 5) if request.user_context else 5}

PERFIL DEL USUARIO:
"""

        if request.user_context:
            if 'weight' in request.user_context:
                prompt += f"- Peso: {request.user_context['weight']} kg\n"
            if 'height' in request.user_context:
                prompt += f"- Altura: {request.user_context['height']} cm\n"
            if 'age' in request.user_context:
                prompt += f"- Edad: {request.user_context['age']} años\n"
            if 'activity_level' in request.user_context:
                prompt += f"- Nivel de actividad: {request.user_context['activity_level']}\n"
            if 'difficulty_level' in request.user_context:
                prompt += f"- Nivel de dificultad de recetas: {request.user_context['difficulty_level']}\n"
            if 'budget_level' in request.user_context:
                prompt += f"- Presupuesto: {request.user_context['budget_level']}\n"

        # Restricciones dietéticas
        if request.dietary_restrictions:
            prompt += f"\nRESTRICCIONES DIETÉTICAS:\n"
            for restriction in request.dietary_restrictions:
                prompt += f"- {restriction}\n"

        # Alergias
        if request.allergies:
            prompt += f"\nALERGIAS (EXCLUIR COMPLETAMENTE):\n"
            for allergy in request.allergies:
                prompt += f"- {allergy}\n"

        # Ingredientes a excluir
        if request.exclude_ingredients:
            prompt += f"\nINGREDIENTES A EXCLUIR:\n"
            for ingredient in request.exclude_ingredients:
                prompt += f"- {ingredient}\n"

        # Instrucciones adicionales del prompt original
        if request.prompt:
            prompt += f"\nINSTRUCCIONES ADICIONALES:\n{request.prompt}\n"

        # Distribución de macros según objetivo
        macro_distributions = {
            "weight_loss": "Proteína: 30-35%, Carbohidratos: 35-40%, Grasas: 25-30%",
            "muscle_gain": "Proteína: 25-30%, Carbohidratos: 45-50%, Grasas: 20-25%",
            "definition": "Proteína: 35-40%, Carbohidratos: 30-35%, Grasas: 25-30%",
            "maintenance": "Proteína: 20-25%, Carbohidratos: 45-50%, Grasas: 25-30%",
            "performance": "Proteína: 20-25%, Carbohidratos: 50-60%, Grasas: 20-25%"
        }

        prompt += f"\nDISTRIBUCIÓN DE MACROS RECOMENDADA:\n{macro_distributions.get(request.goal.value, macro_distributions['maintenance'])}\n"

        prompt += f"\nGenera un plan COMPLETO de {request.duration_days} días. SÉ CONCISO con los ingredientes (3-5 por comida máximo)."

        return prompt

    async def generate_nutrition_plan(
        self,
        request: AIGenerationRequest,
        creator_id: int,
        gym_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Generar un plan nutricional completo con IA y guardarlo en la base de datos.
        Usa generación incremental para evitar timeouts.

        Returns:
            Dict con información del plan creado y metadata de la generación.
        """
        start_time = time.time()

        try:
            # Si no hay cliente OpenAI, usar generación mock
            if not self.client:
                logger.warning("Using mock generation - OpenAI not configured")
                return await self._generate_mock_plan(request, creator_id, gym_id, db)

            logger.info(f"Generating nutrition plan with OpenAI for gym {gym_id}")

            # ESTRATEGIA OPTIMIZADA: Generar días en chunks pequeños
            # Generar día por día para evitar timeouts de OpenAI
            days_per_chunk = 1  # Un día a la vez para máxima velocidad

            # Primero generar estructura base del plan (sin días completos)
            plan_data = await self._generate_plan_structure(request, gym_id)

            # Luego generar días incrementalmente
            all_daily_plans = []
            days_generated = 0

            while days_generated < request.duration_days:
                chunk_size = min(days_per_chunk, request.duration_days - days_generated)
                start_day = days_generated + 1
                end_day = days_generated + chunk_size

                logger.info(f"Generating days {start_day} to {end_day} of {request.duration_days}")

                # Generar chunk de días
                daily_chunk = await self._generate_days_chunk(
                    request,
                    start_day,
                    end_day,
                    plan_data.get("title", request.title)
                )

                if daily_chunk:
                    all_daily_plans.extend(daily_chunk)
                    days_generated += chunk_size
                else:
                    # Si falla un chunk, generar días mock para completar
                    logger.warning(f"Failed to generate days {start_day}-{end_day}, using mock")
                    mock_days = self._generate_mock_days(
                        request,
                        start_day,
                        end_day
                    )
                    all_daily_plans.extend(mock_days)
                    days_generated += chunk_size

            # Combinar estructura del plan con días generados
            plan_data["daily_plans"] = all_daily_plans

            # Crear plan en base de datos
            nutrition_plan = NutritionPlan(
                title=plan_data.get('title', f'Plan {request.goal.value}'),
                description=plan_data.get('description', request.prompt[:500]),
                goal=request.goal,
                difficulty_level=DifficultyLevel(request.user_context.get('difficulty_level', 'beginner')) if request.user_context else DifficultyLevel.BEGINNER,
                budget_level=BudgetLevel(request.user_context.get('budget_level', 'medium')) if request.user_context else BudgetLevel.MEDIUM,
                duration_days=request.duration_days,
                target_calories=request.target_calories,
                is_public=True,
                creator_id=creator_id,
                gym_id=gym_id,
                plan_type=PlanType.TEMPLATE
            )

            # Calcular macros promedio del plan
            if 'daily_plans' in plan_data and plan_data['daily_plans']:
                total_protein = sum(day.get('total_protein', 0) for day in plan_data['daily_plans'])
                total_carbs = sum(day.get('total_carbs', 0) for day in plan_data['daily_plans'])
                total_fat = sum(day.get('total_fat', 0) for day in plan_data['daily_plans'])
                num_days = len(plan_data['daily_plans'])

                nutrition_plan.target_protein_g = round(total_protein / num_days, 1)
                nutrition_plan.target_carbs_g = round(total_carbs / num_days, 1)
                nutrition_plan.target_fat_g = round(total_fat / num_days, 1)

            db.add(nutrition_plan)
            db.flush()  # Para obtener el ID

            # Crear días y comidas
            for day_data in plan_data.get('daily_plans', []):
                daily_plan = DailyNutritionPlan(
                    nutrition_plan_id=nutrition_plan.id,
                    day_number=day_data['day_number'],
                    total_calories=day_data.get('total_calories', 0),
                    total_protein_g=day_data.get('total_protein', 0),
                    total_carbs_g=day_data.get('total_carbs', 0),
                    total_fat_g=day_data.get('total_fat', 0)
                )
                db.add(daily_plan)
                db.flush()

                # Crear comidas del día
                for idx, meal_data in enumerate(day_data.get('meals', [])):
                    # Mapear tipo de comida si OpenAI devuelve valores incorrectos
                    raw_meal_type = meal_data.get('meal_type', 'lunch').lower()

                    # Mapeo de tipos incorrectos a tipos válidos
                    meal_type_mapping = {
                        'snack': 'mid_morning' if idx == 1 else 'afternoon',  # Segundo snack es afternoon
                        'morning_snack': 'mid_morning',
                        'afternoon_snack': 'afternoon',
                        'evening_snack': 'late_snack',
                        'brunch': 'mid_morning',
                        'merienda': 'afternoon'
                    }

                    # Aplicar mapeo o usar valor directo si es válido
                    mapped_type = meal_type_mapping.get(raw_meal_type, raw_meal_type)

                    # Validar que el tipo sea válido
                    valid_types = ['breakfast', 'mid_morning', 'lunch', 'afternoon', 'dinner', 'late_snack', 'post_workout']
                    if mapped_type not in valid_types:
                        logger.warning(f"Tipo de comida inválido '{mapped_type}', usando 'lunch' por defecto")
                        mapped_type = 'lunch'

                    meal = Meal(
                        daily_plan_id=daily_plan.id,
                        name=meal_data['name'],
                        meal_type=MealType(mapped_type),
                        description=meal_data.get('description', ''),
                        calories=meal_data.get('calories', 0),
                        protein_g=meal_data.get('protein', 0),
                        carbs_g=meal_data.get('carbs', 0),
                        fat_g=meal_data.get('fat', 0),
                        fiber_g=meal_data.get('fiber', 0),
                        preparation_time_minutes=meal_data.get('prep_time_minutes', 15),
                        cooking_instructions=meal_data.get('instructions', '')
                    )
                    db.add(meal)
                    db.flush()

                    # Crear ingredientes (manejar tanto strings como objetos)
                    ingredients = meal_data.get('ingredients', [])
                    for idx, ing_data in enumerate(ingredients):
                        # Si el ingrediente es un string simple, convertirlo a objeto
                        if isinstance(ing_data, str):
                            ingredient_obj = {
                                'name': ing_data,
                                'quantity': 100,  # Cantidad por defecto
                                'unit': 'g'       # Unidad por defecto
                            }
                        elif isinstance(ing_data, dict):
                            ingredient_obj = ing_data
                        else:
                            logger.warning(f"Formato de ingrediente no reconocido: {type(ing_data)}")
                            continue

                        # Crear el ingrediente con manejo robusto
                        try:
                            ingredient = MealIngredient(
                                meal_id=meal.id,
                                name=ingredient_obj.get('name', f'Ingrediente {idx+1}'),
                                quantity=float(ingredient_obj.get('quantity', 100)),
                                unit=ingredient_obj.get('unit', 'g')
                            )
                            db.add(ingredient)
                        except Exception as e:
                            logger.warning(f"Error creando ingrediente: {e}, data: {ingredient_obj}")
                            continue

            # Commit todos los cambios
            db.commit()

            # Calcular métricas
            generation_time = int((time.time() - start_time) * 1000)

            # Calcular costo estimado basado en tokens
            # GPT-4o-mini: $0.15 / 1M input tokens, $0.60 / 1M output tokens
            # Estimación: ~2K input + 3K output = ~$0.002
            prompt_tokens = response.usage.prompt_tokens if response.usage else len(user_prompt) // 4
            completion_tokens = response.usage.completion_tokens if response.usage else len(str(plan_data)) // 4
            cost_estimate = (prompt_tokens * 0.00000015) + (completion_tokens * 0.0000006)

            return {
                "plan_id": nutrition_plan.id,
                "name": nutrition_plan.title,
                "description": nutrition_plan.description,
                "total_days": nutrition_plan.duration_days,
                "nutritional_goal": nutrition_plan.goal,
                "target_calories": nutrition_plan.target_calories,
                "daily_plans_count": len(plan_data.get('daily_plans', [])),
                "total_meals": sum(len(day.get('meals', [])) for day in plan_data.get('daily_plans', [])),
                "ai_metadata": {
                    "model": self.model,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                    "temperature": request.temperature
                },
                "generation_time_ms": generation_time,
                "cost_estimate_usd": round(cost_estimate, 4)
            }

        except Exception as e:
            logger.error(f"Error generating nutrition plan: {str(e)}")
            # En caso de error, generar plan mock
            return await self._generate_mock_plan(request, creator_id, gym_id, db)

    async def _generate_plan_structure(self, request: AIGenerationRequest, gym_id: int) -> Dict[str, Any]:
        """
        Genera solo la estructura base del plan (título, descripción, configuración)
        sin los días completos para reducir tokens.
        """
        try:
            if not self.client:
                return {
                    "title": request.title,
                    "description": f"Plan de {request.goal.value} con {request.target_calories} calorías diarias"
                }

            # Prompt simplificado solo para estructura
            system_prompt = """Eres un nutricionista experto.
Genera SOLO la estructura base del plan nutricional.
Responde con JSON compacto:
{
  "title": "título descriptivo",
  "description": "descripción breve del plan (máx 100 palabras)"
}"""

            user_prompt = f"""Crea estructura para:
- Objetivo: {request.goal.value}
- Calorías: {request.target_calories}/día
- Duración: {request.duration_days} días
- Restricciones: {', '.join(request.dietary_restrictions) if request.dietary_restrictions else 'ninguna'}"""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Máxima velocidad
                max_tokens=150,  # Solo necesitamos título y descripción
                response_format={"type": "json_object"},
                timeout=5.0  # 5 segundos para estructura simple
            )

            return json.loads(response.choices[0].message.content)

        except Exception as e:
            logger.warning(f"Failed to generate plan structure: {e}")
            return {
                "title": request.title,
                "description": f"Plan de {request.goal.value} con {request.target_calories} calorías diarias"
            }

    async def _generate_days_chunk(
        self,
        request: AIGenerationRequest,
        start_day: int,
        end_day: int,
        plan_title: str
    ) -> List[Dict[str, Any]]:
        """
        Genera un chunk de días usando LangChain (si disponible) o OpenAI directo.
        """
        try:
            # Intentar primero con LangChain si está disponible
            if self.use_langchain and self.langchain_generator:
                try:
                    logger.info(f"Usando LangChain para generar días {start_day}-{end_day}")
                    result = self.langchain_generator.generate_nutrition_plan(
                        request, start_day, end_day
                    )
                    return result.get('days', [])
                except Exception as e:
                    logger.warning(f"Error con LangChain, cayendo a OpenAI directo: {e}")
                    # Continuar con generación directa

            if not self.client:
                return self._generate_mock_days(request, start_day, end_day)

            # Días de la semana
            days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

            # Calcular qué días generar
            num_days = end_day - start_day + 1
            day_names = [days[(start_day - 1 + i) % 7] for i in range(num_days)]

            logger.info(f"Generando días {start_day}-{end_day} con OpenAI directo")

            # Prompt optimizado para máxima velocidad
            system_prompt = """Genera un plan nutricional en formato JSON con esta estructura exacta:
{
  "days": [
    {
      "day_number": 1,
      "day_name": "nombre del día",
      "meals": [array de 5 comidas]
    }
  ]
}
Cada comida debe tener: name, meal_type (breakfast/mid_morning/lunch/afternoon/dinner), calories, protein, carbs, fat, ingredients (máx 2), instructions.
IMPORTANTE:
- Usa estos meal_type exactos: breakfast, mid_morning, lunch, afternoon, dinner
- Los ingredientes deben ser objetos con: {"name": "ingrediente", "quantity": 100, "unit": "g"}
- NO uses ingredientes como strings simples ["ingrediente1", "ingrediente2"]
Responde SOLO con JSON válido."""

            # Determinar tipos de comidas según meals_per_day
            meal_types = self._get_meal_types(request.meals_per_day)
            calories_per_meal = request.target_calories / len(meal_types)

            user_prompt = f"""Crea el plan para el día {start_day} ({day_names[0]}).
Objetivo: {request.goal.value} con {request.target_calories} calorías diarias.
Distribuir en {len(meal_types)} comidas: {', '.join(meal_types)}."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Un poco más de variedad
                max_tokens=600,  # Suficiente para 1 día
                response_format={"type": "json_object"},  # Necesario para JSON válido
                timeout=15.0  # 15 segundos debería ser suficiente
            )

            try:
                content = response.choices[0].message.content
                result = json.loads(content)

                # Validar estructura básica
                if 'days' not in result or not isinstance(result['days'], list):
                    logger.warning(f"Respuesta sin estructura 'days' válida: {content[:200]}")
                    return self._generate_mock_days(request, start_day, end_day)

            except json.JSONDecodeError as e:
                logger.warning(f"JSON decode error for days {start_day}-{end_day}: {e}")
                # Intentar reparar JSON truncado
                content = response.choices[0].message.content
                try:
                    # Intentar cerrar JSON incompleto
                    import re
                    # Buscar el último objeto/array abierto y cerrarlo
                    if content.count('{') > content.count('}'):
                        content += '}' * (content.count('{') - content.count('}'))
                    if content.count('[') > content.count(']'):
                        content += ']' * (content.count('[') - content.count(']'))
                    result = json.loads(content)
                except:
                    # Si no se puede reparar, usar mock
                    logger.warning(f"Could not repair JSON, using mock for days {start_day}-{end_day}")
                    return self._generate_mock_days(request, start_day, end_day)

            # Validar y normalizar respuesta
            if "days" in result:
                return result["days"]
            elif "daily_plans" in result:
                return result["daily_plans"]
            else:
                # Si el formato no es el esperado, intentar extraer días
                logger.warning("Unexpected response format, attempting to extract days")
                return self._extract_days_from_response(result, start_day, end_day)

        except Exception as e:
            logger.error(f"Failed to generate days {start_day}-{end_day}: {e}")
            return self._generate_mock_days(request, start_day, end_day)

    def _get_meal_types(self, meals_per_day: int) -> List[str]:
        """Determina los tipos de comida según el número de comidas por día."""
        if meals_per_day <= 3:
            return ["breakfast", "lunch", "dinner"]
        elif meals_per_day == 4:
            return ["breakfast", "mid_morning", "lunch", "dinner"]
        elif meals_per_day == 5:
            return ["breakfast", "mid_morning", "lunch", "afternoon", "dinner"]
        else:
            return ["breakfast", "mid_morning", "lunch", "afternoon", "dinner", "late_snack"]

    def _generate_mock_days(self, request: AIGenerationRequest, start_day: int, end_day: int) -> List[Dict[str, Any]]:
        """Genera días mock cuando falla la generación con IA."""
        days = []
        day_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        meal_types = self._get_meal_types(request.meals_per_day)
        calories_per_meal = request.target_calories / len(meal_types)

        for day_num in range(start_day, end_day + 1):
            day_meals = []
            for meal_type in meal_types:
                meal = {
                    "name": f"{meal_type.title()} Día {day_num}",
                    "meal_type": meal_type,
                    "calories": int(calories_per_meal),
                    "protein": int(calories_per_meal * 0.3 / 4),
                    "carbs": int(calories_per_meal * 0.4 / 4),
                    "fat": int(calories_per_meal * 0.3 / 9),
                    "ingredients": [
                        {
                            "name": f"Ingrediente principal {meal_type}",
                            "quantity": 150,
                            "unit": "g"
                        }
                    ],
                    "instructions": f"Preparación estándar para {meal_type}"
                }
                day_meals.append(meal)

            days.append({
                "day_number": day_num,
                "day_name": day_names[(day_num - 1) % 7],
                "meals": day_meals
            })

        return days

    def _extract_days_from_response(self, response: Dict, start_day: int, end_day: int) -> List[Dict[str, Any]]:
        """Intenta extraer días de una respuesta con formato inesperado."""
        # Buscar cualquier clave que parezca contener días
        for key in ["days", "daily_plans", "plan", "daily"]:
            if key in response and isinstance(response[key], list):
                return response[key]

        # Si no encuentra nada, generar mock
        # Usar el request original, no crear uno nuevo
        return self._generate_mock_days(request, start_day, end_day)

    async def _generate_mock_plan(
        self,
        request: AIGenerationRequest,
        creator_id: int,
        gym_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Generar un plan mock cuando OpenAI no está disponible.
        Útil para desarrollo y testing.
        """
        start_time = time.time()

        # Crear plan base
        nutrition_plan = NutritionPlan(
            title=f"Plan {request.goal.value.replace('_', ' ').title()} - {request.target_calories} cal",
            description=f"Plan generado automáticamente: {request.prompt[:200] if request.prompt else 'Plan estándar'}",
            goal=request.goal,
            difficulty_level=DifficultyLevel.BEGINNER,
            budget_level=BudgetLevel.MEDIUM,
            duration_days=request.duration_days,
            target_calories=request.target_calories,
            target_protein_g=request.target_calories * 0.3 / 4,  # 30% proteína
            target_carbs_g=request.target_calories * 0.4 / 4,    # 40% carbos
            target_fat_g=request.target_calories * 0.3 / 9,      # 30% grasas
            is_public=True,
            creator_id=creator_id,
            gym_id=gym_id,
            plan_type=PlanType.TEMPLATE
        )
        db.add(nutrition_plan)
        db.flush()

        # Crear días de ejemplo
        meal_templates = {
            "breakfast": {
                "name": "Desayuno Energético",
                "calories": int(request.target_calories * 0.25),
                "description": "Desayuno balanceado para empezar el día"
            },
            "mid_morning": {
                "name": "Colación Media Mañana",
                "calories": int(request.target_calories * 0.1),
                "description": "Snack nutritivo de media mañana"
            },
            "afternoon": {
                "name": "Merienda",
                "calories": int(request.target_calories * 0.1),
                "description": "Snack de la tarde"
            },
            "lunch": {
                "name": "Almuerzo Completo",
                "calories": int(request.target_calories * 0.35),
                "description": "Almuerzo rico en proteínas y vegetales"
            },
            "dinner": {
                "name": "Cena Ligera",
                "calories": int(request.target_calories * 0.2),
                "description": "Cena digestiva y nutritiva"
            }
        }

        total_meals = 0
        for day_num in range(1, min(request.duration_days + 1, 8)):  # Max 7 días para mock
            daily_plan = DailyNutritionPlan(
                nutrition_plan_id=nutrition_plan.id,
                day_number=day_num,
                total_calories=request.target_calories,
                total_protein_g=nutrition_plan.target_protein_g,
                total_carbs_g=nutrition_plan.target_carbs_g,
                total_fat_g=nutrition_plan.target_fat_g
            )
            db.add(daily_plan)
            db.flush()

            # Crear comidas del día
            for meal_type, template in meal_templates.items():
                if (meal_type in ["mid_morning", "afternoon"]) and request.target_calories < 1800:
                    continue  # Skip snacks for low calorie plans

                meal = Meal(
                    daily_plan_id=daily_plan.id,
                    name=f"{template['name']} - Día {day_num}",
                    meal_type=MealType(meal_type),
                    description=template['description'],
                    calories=template['calories'],
                    protein_g=template['calories'] * 0.3 / 4,
                    carbs_g=template['calories'] * 0.4 / 4,
                    fat_g=template['calories'] * 0.3 / 9,
                    preparation_time_minutes=20,
                    cooking_instructions="Preparación estándar según ingredientes"
                )
                db.add(meal)
                total_meals += 1

        db.commit()

        generation_time = int((time.time() - start_time) * 1000)

        return {
            "plan_id": nutrition_plan.id,
            "name": nutrition_plan.title,
            "description": nutrition_plan.description,
            "total_days": nutrition_plan.duration_days,
            "nutritional_goal": nutrition_plan.goal,
            "target_calories": nutrition_plan.target_calories,
            "daily_plans_count": min(request.duration_days, 7),
            "total_meals": total_meals,
            "ai_metadata": {
                "model": "mock",
                "note": "Plan generado sin IA - OpenAI no configurado"
            },
            "generation_time_ms": generation_time,
            "cost_estimate_usd": 0.0
        }

    async def analyze_meal_image(
        self,
        image_data: bytes,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Analizar una imagen de comida y extraer información nutricional.

        Args:
            image_data: Bytes de la imagen
            context: Contexto adicional sobre la comida

        Returns:
            Dict con información nutricional estimada
        """
        # TODO: Implementar análisis de imagen con GPT-4-vision
        # Por ahora retornar mock
        return {
            "meal_name": "Comida detectada",
            "estimated_calories": 450,
            "macros": {
                "protein": 25,
                "carbs": 45,
                "fat": 20
            },
            "confidence_score": 0.75,
            "ingredients_detected": ["Ingrediente 1", "Ingrediente 2"]
        }