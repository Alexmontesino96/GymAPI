"""
Servicio de IA para generación de planes nutricionales usando OpenAI GPT-4o-mini.
Genera planes completos con días, comidas e ingredientes.
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


class NutritionAIService:
    """
    Servicio para generar planes nutricionales usando OpenAI GPT-4o-mini.
    Costo aproximado: $0.002 por plan generado.
    """

    def __init__(self):
        """Inicializar cliente OpenAI con API key."""
        settings = get_settings()
        # Usar CHAT_GPT_MODEL primero, luego OPENAI_API_KEY como fallback
        self.api_key = settings.CHAT_GPT_MODEL or settings.OPENAI_API_KEY
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        else:
            logger.warning("OpenAI API key not configured (CHAT_GPT_MODEL or OPENAI_API_KEY)")
            self.client = None

        self.model = "gpt-4o-mini"
        self.max_retries = 3

    def _build_system_prompt(self) -> str:
        """Construir el prompt del sistema para nutrición."""
        return """Eres un nutricionista experto que crea planes de alimentación detallados y personalizados.

        IMPORTANTE: Debes responder SOLO con un JSON válido, sin texto adicional ni explicaciones.

        El JSON debe tener exactamente esta estructura:
        {
            "title": "Nombre descriptivo del plan",
            "description": "Descripción breve del plan y sus beneficios",
            "daily_plans": [
                {
                    "day_number": 1,
                    "day_name": "Lunes",
                    "total_calories": 0,
                    "total_protein": 0,
                    "total_carbs": 0,
                    "total_fat": 0,
                    "meals": [
                        {
                            "name": "Nombre de la comida",
                            "meal_type": "breakfast|snack|lunch|dinner",
                            "description": "Descripción breve",
                            "calories": 0,
                            "protein": 0,
                            "carbs": 0,
                            "fat": 0,
                            "prep_time_minutes": 0,
                            "ingredients": [
                                {
                                    "name": "Ingrediente",
                                    "quantity": 0,
                                    "unit": "g|ml|unidad|taza|cucharada",
                                    "calories": 0,
                                    "protein": 0,
                                    "carbs": 0,
                                    "fat": 0
                                }
                            ],
                            "instructions": "Instrucciones paso a paso de preparación"
                        }
                    ]
                }
            ]
        }

        Reglas importantes:
        1. El total de calorías diarias debe estar dentro del 5% del objetivo
        2. Incluir variedad de alimentos sin repetir comidas principales en días consecutivos
        3. Los macros deben ser realistas y sumar correctamente
        4. Usar ingredientes locales y accesibles
        5. Las instrucciones deben ser claras y concisas
        6. Adaptar las porciones según el objetivo calórico
        7. Respetar todas las restricciones dietéticas indicadas
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
        if request.preferences and 'exclude_ingredients' in request.preferences:
            prompt += f"\nINGREDIENTES A EXCLUIR:\n"
            for ingredient in request.preferences['exclude_ingredients']:
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

        prompt += f"\nGenera un plan COMPLETO de {request.duration_days} días con todas las comidas, ingredientes y valores nutricionales."

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

        Returns:
            Dict con información del plan creado y metadata de la generación.
        """
        start_time = time.time()

        try:
            # Si no hay cliente OpenAI, usar generación mock
            if not self.client:
                logger.warning("Using mock generation - OpenAI not configured")
                return await self._generate_mock_plan(request, creator_id, gym_id, db)

            # Construir prompts
            system_prompt = self._build_system_prompt()
            user_prompt = self._build_user_prompt(request)

            logger.info(f"Generating nutrition plan with OpenAI for gym {gym_id}")

            # Llamar a OpenAI
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response_format={"type": "json_object"}
            )

            # Parsear respuesta JSON
            try:
                plan_data = json.loads(response.choices[0].message.content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse OpenAI response: {e}")
                # Intentar extraer JSON del texto
                import re
                json_match = re.search(r'\{.*\}', response.choices[0].message.content, re.DOTALL)
                if json_match:
                    plan_data = json.loads(json_match.group())
                else:
                    raise ValueError("No se pudo parsear la respuesta de OpenAI")

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
                created_by=creator_id,
                gym_id=gym_id,
                plan_type=PlanType.TEMPLATE,
                created_at=datetime.utcnow()
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
                    plan_id=nutrition_plan.id,
                    day_number=day_data['day_number'],
                    day_name=day_data.get('day_name', f"Día {day_data['day_number']}"),
                    total_calories=day_data.get('total_calories', 0),
                    total_protein=day_data.get('total_protein', 0),
                    total_carbs=day_data.get('total_carbs', 0),
                    total_fat=day_data.get('total_fat', 0)
                )
                db.add(daily_plan)
                db.flush()

                # Crear comidas del día
                for meal_data in day_data.get('meals', []):
                    meal = Meal(
                        day_plan_id=daily_plan.id,
                        name=meal_data['name'],
                        meal_type=MealType(meal_data.get('meal_type', 'lunch')),
                        description=meal_data.get('description', ''),
                        calories=meal_data.get('calories', 0),
                        protein=meal_data.get('protein', 0),
                        carbohydrates=meal_data.get('carbs', 0),
                        fat=meal_data.get('fat', 0),
                        fiber=meal_data.get('fiber', 0),
                        sugar=meal_data.get('sugar', 0),
                        sodium=meal_data.get('sodium', 0),
                        preparation_time_minutes=meal_data.get('prep_time_minutes', 15),
                        cooking_instructions=meal_data.get('instructions', '')
                    )
                    db.add(meal)
                    db.flush()

                    # Crear ingredientes
                    for ing_data in meal_data.get('ingredients', []):
                        ingredient = MealIngredient(
                            meal_id=meal.id,
                            name=ing_data['name'],
                            quantity=ing_data.get('quantity', 0),
                            unit=ing_data.get('unit', 'g'),
                            calories=ing_data.get('calories', 0),
                            protein=ing_data.get('protein', 0),
                            carbohydrates=ing_data.get('carbs', 0),
                            fat=ing_data.get('fat', 0)
                        )
                        db.add(ingredient)

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
            created_by=creator_id,
            gym_id=gym_id,
            plan_type=PlanType.TEMPLATE,
            created_at=datetime.utcnow()
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
            "snack": {
                "name": "Snack Saludable",
                "calories": int(request.target_calories * 0.1),
                "description": "Snack nutritivo"
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
                plan_id=nutrition_plan.id,
                day_number=day_num,
                day_name=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][day_num - 1],
                total_calories=request.target_calories,
                total_protein=nutrition_plan.target_protein_g,
                total_carbs=nutrition_plan.target_carbs_g,
                total_fat=nutrition_plan.target_fat_g
            )
            db.add(daily_plan)
            db.flush()

            # Crear comidas del día
            for meal_type, template in meal_templates.items():
                if meal_type == "snack" and request.target_calories < 1800:
                    continue  # Skip snack for low calorie plans

                meal = Meal(
                    day_plan_id=daily_plan.id,
                    name=f"{template['name']} - Día {day_num}",
                    meal_type=MealType(meal_type),
                    description=template['description'],
                    calories=template['calories'],
                    protein=template['calories'] * 0.3 / 4,
                    carbohydrates=template['calories'] * 0.4 / 4,
                    fat=template['calories'] * 0.3 / 9,
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