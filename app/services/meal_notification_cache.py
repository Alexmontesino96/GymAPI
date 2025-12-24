"""
Servicio de caché de notificaciones por meal con generación IA.

Este servicio genera notificaciones personalizadas UNA VEZ por meal usando
GPT-4o-mini y las cachea en Redis. Todos los usuarios con el mismo meal
reciben la misma notificación, reduciendo el costo de ~$40/mes a ~$0.03/mes.

Estrategia:
- Cache key: meal:{meal_id}:notification:{gym_tone}
- TTL: 30 días
- Hit rate esperado: ~99%
- Costo mensual: $0.03 (vs $40 sin cache por meal)
"""

import json
import logging
from typing import Dict, Optional
from openai import AsyncOpenAI

from app.core.config import get_settings
from app.models.nutrition import Meal, NutritionPlan
from app.db.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class MealNotificationCacheService:
    """
    Servicio de cache de notificaciones por meal con generación IA.

    Genera una notificación por meal (no por usuario) para reducir costos.
    Todos los usuarios con el mismo meal reciben la misma notificación.
    """

    def __init__(self):
        """Inicializa el servicio con OpenAI y Redis."""
        self.settings = get_settings()

        # Validar API key
        if not self.settings.OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY no configurada - notificaciones AI deshabilitadas")
            self.ai_enabled = False
            self.client = None
        else:
            self.ai_enabled = True
            self.client = AsyncOpenAI(
                api_key=self.settings.OPENAI_API_KEY,
                timeout=30.0
            )

        # Configuración del modelo (usar gpt-4o-mini para bajo costo)
        self.model = "gpt-4o-mini"
        self.cache_ttl = 2592000  # 30 días en segundos

        logger.info(f"✅ MealNotificationCacheService inicializado (AI: {self.ai_enabled})")

    async def get_or_generate_notification(
        self,
        meal_id: int,
        meal: Meal,
        plan: Optional[NutritionPlan] = None,
        gym_tone: str = "motivational"
    ) -> Dict[str, str]:
        """
        Obtiene notificación de cache o genera nueva si no existe.

        Args:
            meal_id: ID del meal
            meal: Objeto Meal con datos de la comida
            plan: Plan nutricional (opcional, para contexto)
            gym_tone: Tono de la notificación (motivational/neutral/friendly)

        Returns:
            Dict con title, message, emoji

        Ejemplo:
            {
                "title": "🌅 Power Breakfast - Empieza fuerte",
                "message": "540 kcal, 35g proteína. ¡Tu cuerpo lo agradecerá!",
                "emoji": "🌅"
            }
        """
        # Cache key único por meal y tono
        cache_key = f"meal:{meal_id}:notification:{gym_tone}"

        # 1. Intentar obtener de cache
        try:
            redis_client = await get_redis_client()
            if redis_client:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache HIT para meal {meal_id} (tone: {gym_tone})")
                    return json.loads(cached)
        except Exception as e:
            logger.warning(f"Error leyendo cache: {e}")

        # 2. Cache MISS - generar con IA o fallback
        logger.info(f"Cache MISS para meal {meal_id} - generando notificación...")

        notification = await self._generate_notification(meal, plan, gym_tone)

        # 3. Guardar en cache (TTL 30 días)
        try:
            redis_client = await get_redis_client()
            if redis_client:
                await redis_client.setex(
                    cache_key,
                    self.cache_ttl,
                    json.dumps(notification)
                )
                logger.info(f"Notificación cacheada para meal {meal_id} (TTL: 30 días)")
        except Exception as e:
            logger.warning(f"Error guardando en cache: {e}")

        return notification

    async def _generate_notification(
        self,
        meal: Meal,
        plan: Optional[NutritionPlan],
        gym_tone: str
    ) -> Dict[str, str]:
        """
        Genera notificación con IA o fallback a template.

        Args:
            meal: Objeto Meal
            plan: Plan nutricional
            gym_tone: Tono de la notificación

        Returns:
            Dict con title, message, emoji
        """
        # Si IA está habilitada, intentar generar con GPT-4o-mini
        if self.ai_enabled:
            try:
                return await self._generate_with_ai(meal, plan, gym_tone)
            except Exception as e:
                logger.warning(f"Error generando con IA: {e} - usando fallback")

        # Fallback a template hardcoded
        return self._generate_fallback(meal, plan)

    async def _generate_with_ai(
        self,
        meal: Meal,
        plan: Optional[NutritionPlan],
        gym_tone: str
    ) -> Dict[str, str]:
        """
        Genera notificación usando GPT-4o-mini.

        Args:
            meal: Objeto Meal
            plan: Plan nutricional
            gym_tone: Tono de la notificación

        Returns:
            Dict con title, message, emoji

        Raises:
            Exception si hay error en la generación
        """
        # Construir prompt con contexto del meal
        prompt = self._build_prompt(meal, plan, gym_tone)

        # Llamar a OpenAI
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un asistente de nutrición que crea notificaciones "
                        "motivacionales para recordatorios de comidas. "
                        "Sé breve, específico y motivacional. "
                        "IMPORTANTE: No menciones nombres de usuarios ni rachas personales, "
                        "ya que esta notificación va a TODOS los usuarios con este meal."
                    )
                },
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7,
            response_format={"type": "json_object"}
        )

        # Parsear respuesta
        content = response.choices[0].message.content
        if not content:
            raise Exception("Respuesta vacía de OpenAI")

        data = json.loads(content)

        # Validar estructura
        if "title" not in data or "message" not in data:
            raise Exception("Respuesta no tiene estructura correcta")

        # Asegurar que emoji esté presente
        if "emoji" not in data:
            data["emoji"] = self._get_emoji_for_meal_type(meal.meal_type)

        logger.info(f"✅ Notificación generada con IA para meal {meal.id}")
        return data

    def _build_prompt(
        self,
        meal: Meal,
        plan: Optional[NutritionPlan],
        gym_tone: str
    ) -> str:
        """
        Construye prompt para OpenAI.

        Args:
            meal: Objeto Meal
            plan: Plan nutricional
            gym_tone: Tono de la notificación

        Returns:
            str: Prompt para IA
        """
        # Información del meal
        meal_info = f"""
**Comida:**
- Nombre: {meal.name}
- Tipo: {meal.meal_type} (breakfast/lunch/dinner/snack)
- Descripción: {meal.description or 'N/A'}
"""

        # Agregar info nutricional si está disponible
        if meal.calories:
            meal_info += f"- Calorías: {meal.calories} kcal\n"
        if meal.protein_g:
            meal_info += f"- Proteínas: {meal.protein_g}g\n"
        if meal.carbs_g:
            meal_info += f"- Carbohidratos: {meal.carbs_g}g\n"
        if meal.fat_g:
            meal_info += f"- Grasas: {meal.fat_g}g\n"

        # Información del plan (si existe)
        plan_info = ""
        if plan:
            plan_info = f"""
**Plan nutricional:**
- Título: {plan.title}
- Objetivo: {plan.goal or 'N/A'}
- Tipo: {plan.plan_type}
"""

        # Emojis por tipo de comida
        emoji_examples = {
            "breakfast": "🌅, ☀️, 🍳",
            "lunch": "🌮, 🥗, 🍽️",
            "dinner": "🌙, 🍲, 🥘",
            "snack": "🍎, 🥤, 🍪",
            "mid_morning": "🥤, 🍎",
            "afternoon": "☕, 🍪",
            "post_workout": "💪, 🥤",
            "late_snack": "🍿, 🥜"
        }

        emoji_suggestion = emoji_examples.get(meal.meal_type, "🍽️")

        return f"""
Genera una notificación de recordatorio para esta comida:

{meal_info}
{plan_info}

**Tono:** {gym_tone} (motivational/neutral/friendly)

**Reglas:**
1. Título: Máximo 50 caracteres, incluir emoji relevante al tipo de comida
2. Mensaje: Máximo 100 caracteres, motivacional y específico
3. Mencionar el nombre de la comida
4. Tono: {gym_tone}
5. NO mencionar nombres de usuarios (esto va a TODOS los usuarios con este meal)
6. NO mencionar rachas o logros individuales
7. Enfocarse en el meal específico y sus beneficios
8. Si hay info nutricional, mencionarla brevemente

**Emojis sugeridos para {meal.meal_type}:** {emoji_suggestion}

Retorna solo JSON (sin markdown):
{{
    "title": "...",
    "message": "...",
    "emoji": "..."
}}
"""

    def _generate_fallback(
        self,
        meal: Meal,
        plan: Optional[NutritionPlan]
    ) -> Dict[str, str]:
        """
        Genera notificación usando template hardcoded (fallback).

        Args:
            meal: Objeto Meal
            plan: Plan nutricional

        Returns:
            Dict con title, message, emoji
        """
        # Mapeo de tipos de comida a emojis y textos
        meal_config = {
            "breakfast": {"emoji": "🌅", "text": "desayuno"},
            "mid_morning": {"emoji": "🥤", "text": "snack de media mañana"},
            "lunch": {"emoji": "🍽️", "text": "almuerzo"},
            "afternoon": {"emoji": "☕", "text": "merienda"},
            "dinner": {"emoji": "🌙", "text": "cena"},
            "post_workout": {"emoji": "💪", "text": "comida post-entreno"},
            "late_snack": {"emoji": "🍿", "text": "snack nocturno"},
            "snack": {"emoji": "🍎", "text": "snack"}
        }

        config = meal_config.get(meal.meal_type, {"emoji": "🍽️", "text": "comida"})
        emoji = config["emoji"]
        meal_text = config["text"]

        # Construir mensaje
        plan_title = plan.title if plan else "Tu plan nutricional"

        # Si hay info nutricional, incluirla
        nutrition_info = ""
        if meal.calories:
            nutrition_info = f" ({meal.calories} kcal)"

        title = f"{emoji} Hora de tu {meal_text}"
        message = f"{meal.name}{nutrition_info} - {plan_title}"

        logger.info(f"Notificación generada con fallback para meal {meal.id}")

        return {
            "title": title,
            "message": message,
            "emoji": emoji
        }

    def _get_emoji_for_meal_type(self, meal_type: str) -> str:
        """Obtiene emoji para tipo de comida."""
        emojis = {
            "breakfast": "🌅",
            "mid_morning": "🥤",
            "lunch": "🍽️",
            "afternoon": "☕",
            "dinner": "🌙",
            "post_workout": "💪",
            "late_snack": "🍿",
            "snack": "🍎"
        }
        return emojis.get(meal_type, "🍽️")

    async def invalidate_meal_notification(self, meal_id: int) -> bool:
        """
        Invalida cache de notificación para un meal.

        Llamar cuando meal se actualiza para regenerar notificación.

        Args:
            meal_id: ID del meal

        Returns:
            bool: True si se invalidó correctamente
        """
        try:
            redis_client = await get_redis_client()
            if not redis_client:
                return False

            # Invalidar para todos los tonos
            tones = ["motivational", "neutral", "friendly"]
            count = 0

            for tone in tones:
                cache_key = f"meal:{meal_id}:notification:{tone}"
                deleted = await redis_client.delete(cache_key)
                count += deleted

            logger.info(f"Cache invalidado para meal {meal_id} ({count} claves eliminadas)")
            return True

        except Exception as e:
            logger.error(f"Error invalidando cache para meal {meal_id}: {e}")
            return False


# Instancia global del servicio
_meal_notification_cache: Optional[MealNotificationCacheService] = None


def get_meal_notification_cache() -> MealNotificationCacheService:
    """
    Obtiene la instancia global del servicio de cache de notificaciones.

    Returns:
        MealNotificationCacheService: Instancia del servicio
    """
    global _meal_notification_cache

    if _meal_notification_cache is None:
        _meal_notification_cache = MealNotificationCacheService()

    return _meal_notification_cache
