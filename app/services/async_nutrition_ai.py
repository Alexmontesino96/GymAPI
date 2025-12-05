"""
AsyncNutritionAIService - Servicio async de IA nutricional usando OpenAI.

Este módulo proporciona funcionalidades async para generar recetas e ingredientes
automáticamente usando ChatGPT con valores nutricionales precisos.

Migrado en FASE 3 de la conversión sync → async.
"""

import os
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
import logging

from app.core.config import get_settings
from app.schemas.nutrition_ai import (
    AIIngredientRequest,
    GeneratedIngredient,
    AIRecipeResponse,
    AIIngredientError
)

logger = logging.getLogger("async_nutrition_ai_service")


class NutritionAIError(Exception):
    """Excepción personalizada para errores de IA nutricional."""
    pass


class AsyncNutritionAIService:
    """
    Servicio async para generar ingredientes nutricionales usando OpenAI ChatGPT.

    Todos los métodos son async y utilizan AsyncOpenAI.

    Características:
    - Generación de recetas con ingredientes precisos
    - Cálculo automático de valores nutricionales
    - Validación de límites nutricionales realistas
    - Soporte para restricciones dietéticas
    - Confidence score por ingrediente y receta

    Métodos principales:
    - generate_recipe_ingredients() - Genera receta completa con IA
    - test_connection() - Verifica conexión con OpenAI
    """

    def __init__(self):
        """
        Inicializa el servicio con configuración de OpenAI.

        Raises:
            NutritionAIError: Si OPENAI_API_KEY no está configurada
        """
        self.settings = get_settings()

        # Validar que tenemos API key
        if not self.settings.OPENAI_API_KEY:
            raise NutritionAIError("OPENAI_API_KEY no configurada")

        # Inicializar cliente OpenAI
        self.client = AsyncOpenAI(
            api_key=self.settings.OPENAI_API_KEY,
            timeout=30.0  # Timeout de 30 segundos
        )

        # Configuración del modelo
        self.model = self.settings.OPENAI_MODEL
        self.max_tokens = self.settings.OPENAI_MAX_TOKENS
        self.temperature = self.settings.OPENAI_TEMPERATURE

        logger.info(f"✅ AsyncNutritionAIService inicializado con modelo: {self.model}")

    def _get_system_prompt(self) -> str:
        """
        Prompt del sistema optimizado para generar ingredientes nutricionales precisos.

        Returns:
            str: System prompt con reglas y límites nutricionales
        """
        return """
        Eres un nutricionista experto especializado en crear recetas precisas y balanceadas.
        Tu tarea es generar una lista detallada de ingredientes con valores nutricionales exactos.

        REGLAS CRÍTICAS:
        1. Usa valores nutricionales por 100g como referencia base
        2. Calcula cantidades realistas para el número de porciones especificado
        3. Incluye solo ingredientes necesarios, no extras opcionales
        4. Valores nutricionales deben ser precisos según bases de datos oficiales (USDA, BEDCA)
        5. Unidades deben ser prácticas para cocinar (gr, ml, unidades, tazas, cucharadas)
        6. Nombres de ingredientes deben ser específicos y claros
        7. Considera las restricciones dietéticas especificadas

        LÍMITES NUTRICIONALES REALISTAS:
        - Calorías por gramo: máximo 9 kcal/g (grasas puras como aceite)
        - Proteína por gramo: máximo 1g/g (proteína pura en polvo)
        - Carbohidratos por gramo: máximo 1g/g (azúcar puro)
        - Grasas por gramo: máximo 1g/g (aceite puro)
        - Fibra por gramo: máximo 1g/g (fibra pura)

        UNIDADES VÁLIDAS: gr, ml, units, cups, tbsp, tsp, oz, kg, l

        Responde ÚNICAMENTE con JSON válido usando esta estructura exacta:
        {
          "ingredients": [
            {
              "name": "Nombre específico del ingrediente",
              "quantity": número_positivo,
              "unit": "unidad_válida",
              "calories_per_unit": número_entre_0_y_9,
              "protein_g_per_unit": número_entre_0_y_1,
              "carbs_g_per_unit": número_entre_0_y_1,
              "fat_g_per_unit": número_entre_0_y_1,
              "fiber_g_per_unit": número_entre_0_y_1,
              "notes": "información adicional relevante",
              "confidence_score": número_entre_0_y_1
            }
          ],
          "recipe_instructions": "instrucciones paso a paso de preparación",
          "estimated_prep_time": minutos_de_preparación,
          "difficulty_level": "beginner|intermediate|advanced",
          "total_estimated_calories": calorías_totales_de_la_receta,
          "confidence_score": confianza_general_entre_0_y_1
        }

        NO incluyas texto adicional, explicaciones o comentarios fuera del JSON.
        """

    def _build_user_prompt(self, request: AIIngredientRequest) -> str:
        """
        Construye el prompt específico del usuario basado en su request.

        Args:
            request: Datos de la receta a generar

        Returns:
            str: User prompt con todos los parámetros
        """
        dietary_restrictions_text = "ninguna"
        if request.dietary_restrictions:
            restrictions = [r.value for r in request.dietary_restrictions]
            dietary_restrictions_text = ", ".join(restrictions)

        target_calories_text = f"{request.target_calories} kcal" if request.target_calories else "flexible"
        cuisine_text = request.cuisine_type or "general"
        notes_text = request.notes or "ninguna"

        return f"""
        RECETA A GENERAR: {request.recipe_name}

        PARÁMETROS:
        - Número de porciones: {request.servings}
        - Restricciones dietéticas: {dietary_restrictions_text}
        - Tipo de cocina: {cuisine_text}
        - Calorías objetivo por porción: {target_calories_text}
        - Notas adicionales: {notes_text}

        Genera una lista precisa de ingredientes con cantidades exactas y valores nutricionales
        realistas para preparar esta receta para {request.servings} porciones.

        Asegúrate de que los valores nutricionales sean coherentes y realistas.
        Si hay restricciones dietéticas, respétalas estrictamente.
        """

    async def generate_recipe_ingredients(self, request: AIIngredientRequest) -> AIRecipeResponse:
        """
        Genera ingredientes para una receta usando ChatGPT.

        Args:
            request: Datos de la receta a generar

        Returns:
            AIRecipeResponse: Respuesta completa con ingredientes y metadatos

        Raises:
            NutritionAIError: Si hay errores en la generación

        Note:
            - Usa OpenAI con response_format=json_object
            - Valida y limpia valores nutricionales
            - Timeout: 30 segundos
        """
        start_time = time.time()

        try:
            logger.info(f"🤖 Generando ingredientes para: '{request.recipe_name}' ({request.servings} porciones)")

            # Construir mensajes para ChatGPT
            messages = [
                {
                    "role": "system",
                    "content": self._get_system_prompt()
                },
                {
                    "role": "user",
                    "content": self._build_user_prompt(request)
                }
            ]

            # Llamada a OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                timeout=30
            )

            # Extraer contenido
            content = response.choices[0].message.content
            if not content:
                raise NutritionAIError("Respuesta vacía de OpenAI")

            # Parsear JSON
            try:
                raw_data = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"❌ Error parsing JSON: {content[:200]}...")
                raise NutritionAIError(f"Respuesta de IA en formato inválido: {str(e)}")

            # Validar estructura básica
            if not isinstance(raw_data, dict):
                raise NutritionAIError("Respuesta no es un objeto JSON válido")

            if "ingredients" not in raw_data or not raw_data["ingredients"]:
                raise NutritionAIError("No se generaron ingredientes")

            # Validar y limpiar ingredientes
            validated_ingredients = self._validate_and_clean_ingredients(raw_data["ingredients"])

            # Calcular tiempo de generación
            generation_time = int((time.time() - start_time) * 1000)

            # Construir respuesta
            response_data = AIRecipeResponse(
                success=True,
                ingredients=validated_ingredients,
                recipe_instructions=raw_data.get("recipe_instructions"),
                estimated_prep_time=raw_data.get("estimated_prep_time"),
                difficulty_level=raw_data.get("difficulty_level"),
                total_estimated_calories=raw_data.get("total_estimated_calories", 0),
                confidence_score=raw_data.get("confidence_score", 0.8),
                model_used=self.model,
                generation_time_ms=generation_time
            )

            logger.info(f"✅ Ingredientes generados exitosamente: {len(validated_ingredients)} items en {generation_time}ms")
            return response_data

        except asyncio.TimeoutError:
            logger.error("❌ Timeout en llamada a OpenAI")
            raise NutritionAIError("Timeout en generación de IA - intenta de nuevo")

        except Exception as e:
            logger.error(f"❌ Error en generación de IA: {str(e)}", exc_info=True)
            if "rate limit" in str(e).lower():
                raise NutritionAIError("Límite de rate de OpenAI alcanzado - intenta en unos minutos")
            elif "api key" in str(e).lower():
                raise NutritionAIError("Error de autenticación con OpenAI")
            else:
                raise NutritionAIError(f"Error generando ingredientes: {str(e)}")

    def _validate_and_clean_ingredients(self, raw_ingredients: List[Dict]) -> List[GeneratedIngredient]:
        """
        Valida y limpia los ingredientes generados por la IA.

        Args:
            raw_ingredients: Lista de ingredientes en formato dict

        Returns:
            List[GeneratedIngredient]: Ingredientes validados

        Raises:
            NutritionAIError: Si no se pueden validar ingredientes
        """
        validated = []

        for i, ing_data in enumerate(raw_ingredients):
            try:
                # Validar campos requeridos
                required_fields = ["name", "quantity", "unit", "calories_per_unit",
                                 "protein_g_per_unit", "carbs_g_per_unit", "fat_g_per_unit"]

                for field in required_fields:
                    if field not in ing_data:
                        logger.warning(f"Campo faltante '{field}' en ingrediente {i+1}, usando valor por defecto")
                        ing_data[field] = 0 if field != "name" and field != "unit" else "desconocido"

                # Limpiar y validar valores nutricionales
                ing_data = self._clean_nutrition_values(ing_data)

                # Crear objeto validado
                ingredient = GeneratedIngredient(**ing_data)
                validated.append(ingredient)

            except Exception as e:
                logger.warning(f"Error validando ingrediente {i+1}: {str(e)} - saltando")
                continue

        if not validated:
            raise NutritionAIError("No se pudieron validar ingredientes generados")

        return validated

    def _clean_nutrition_values(self, ing_data: Dict) -> Dict:
        """
        Limpia y valida valores nutricionales para que sean realistas.

        Args:
            ing_data: Datos del ingrediente

        Returns:
            Dict: Datos limpios con valores validados

        Note:
            Límites realistas:
            - Calorías: 0-9 kcal/g
            - Macros: 0-1 g/g
            - Coherencia calórica: proteína*4 + carbs*4 + fat*9 ≤ calorías totales
        """
        # Límites realistas por gramo/unidad
        max_calories = 9.0  # Grasas puras
        max_macro = 1.0     # Macronutrientes puros

        # Limpiar calorías
        calories = float(ing_data.get("calories_per_unit", 0))
        ing_data["calories_per_unit"] = min(max(calories, 0), max_calories)

        # Limpiar macronutrientes
        for macro in ["protein_g_per_unit", "carbs_g_per_unit", "fat_g_per_unit", "fiber_g_per_unit"]:
            value = float(ing_data.get(macro, 0))
            ing_data[macro] = min(max(value, 0), max_macro)

        # Validar coherencia: proteína + carbs + grasa no debe exceder calorías
        protein_cals = ing_data["protein_g_per_unit"] * 4
        carbs_cals = ing_data["carbs_g_per_unit"] * 4
        fat_cals = ing_data["fat_g_per_unit"] * 9
        total_macro_cals = protein_cals + carbs_cals + fat_cals

        if total_macro_cals > ing_data["calories_per_unit"] * 1.1:  # 10% de tolerancia
            # Ajustar proporcionalmente
            factor = ing_data["calories_per_unit"] / total_macro_cals
            ing_data["protein_g_per_unit"] *= factor
            ing_data["carbs_g_per_unit"] *= factor
            ing_data["fat_g_per_unit"] *= factor

        # Asegurar que quantity sea positivo
        ing_data["quantity"] = max(float(ing_data.get("quantity", 1)), 0.1)

        # Limpiar strings
        ing_data["name"] = str(ing_data.get("name", "")).strip()
        ing_data["unit"] = str(ing_data.get("unit", "gr")).strip().lower()
        ing_data["notes"] = str(ing_data.get("notes", "")).strip()

        # Confidence score por defecto
        if "confidence_score" not in ing_data:
            ing_data["confidence_score"] = 0.8

        return ing_data

    async def test_connection(self) -> bool:
        """
        Prueba la conexión con OpenAI.

        Returns:
            bool: True si la conexión es exitosa

        Note:
            Usa modelo gpt-3.5-turbo para minimizar costos.
        """
        try:
            response = await self.client.chat.completions.create(
                model="gpt-3.5-turbo",  # Modelo más barato para test
                messages=[{"role": "user", "content": "Test"}],
                max_tokens=5
            )
            return bool(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error en test de conexión OpenAI: {str(e)}")
            return False


# Instancia singleton del servicio async
_async_nutrition_ai_service: Optional[AsyncNutritionAIService] = None


def get_async_nutrition_ai_service() -> AsyncNutritionAIService:
    """
    Obtiene la instancia singleton del servicio async de IA nutricional.

    Returns:
        AsyncNutritionAIService: Instancia única del servicio
    """
    global _async_nutrition_ai_service

    if _async_nutrition_ai_service is None:
        _async_nutrition_ai_service = AsyncNutritionAIService()

    return _async_nutrition_ai_service
