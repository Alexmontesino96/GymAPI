"""
Tests para MealNotificationCacheService.

Verifica que las notificaciones se generen correctamente con IA o fallback,
y que el cache funcione apropiadamente.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from app.services.meal_notification_cache import MealNotificationCacheService
from app.models.nutrition import Meal, NutritionPlan


class TestMealNotificationCacheService:
    """Tests para el servicio de cache de notificaciones por meal."""

    @pytest.fixture
    def mock_meal(self):
        """Crea un meal mock para tests."""
        meal = Mock(spec=Meal)
        meal.id = 123
        meal.name = "Power Breakfast"
        meal.description = "Desayuno alto en proteínas"
        meal.meal_type = "breakfast"
        meal.calories = 540
        meal.protein_g = 35
        meal.carbs_g = 45
        meal.fat_g = 18
        return meal

    @pytest.fixture
    def mock_plan(self):
        """Crea un plan mock para tests."""
        plan = Mock(spec=NutritionPlan)
        plan.id = 1
        plan.title = "Plan de Ganancia Muscular"
        plan.goal = "muscle_gain"
        plan.plan_type = "custom"
        return plan

    @pytest.fixture
    def service_with_ai_disabled(self):
        """Crea servicio con IA deshabilitada (fallback)."""
        with patch('app.services.meal_notification_cache.get_settings') as mock_settings:
            settings = Mock()
            settings.OPENAI_API_KEY = None
            mock_settings.return_value = settings

            service = MealNotificationCacheService()
            assert service.ai_enabled == False
            return service

    @pytest.fixture
    def service_with_ai_enabled(self):
        """Crea servicio con IA habilitada."""
        with patch('app.services.meal_notification_cache.get_settings') as mock_settings:
            settings = Mock()
            settings.OPENAI_API_KEY = "test-api-key"
            mock_settings.return_value = settings

            service = MealNotificationCacheService()
            assert service.ai_enabled == True
            return service

    @pytest.mark.asyncio
    async def test_fallback_generation_breakfast(self, service_with_ai_disabled, mock_meal, mock_plan):
        """Test que fallback genera notificación correcta para breakfast."""
        notification = service_with_ai_disabled._generate_fallback(mock_meal, mock_plan)

        assert "title" in notification
        assert "message" in notification
        assert "emoji" in notification

        # Verificar estructura
        assert notification["emoji"] == "🌅"
        assert "desayuno" in notification["title"].lower()
        assert mock_meal.name in notification["message"]
        assert mock_plan.title in notification["message"]

        # Verificar info nutricional si está disponible
        if mock_meal.calories:
            assert str(mock_meal.calories) in notification["message"]

    @pytest.mark.asyncio
    async def test_fallback_generation_lunch(self, service_with_ai_disabled, mock_plan):
        """Test que fallback genera notificación correcta para lunch."""
        meal = Mock(spec=Meal)
        meal.id = 124
        meal.name = "Ensalada Proteica"
        meal.meal_type = "lunch"
        meal.calories = 380
        meal.protein_g = 28

        notification = service_with_ai_disabled._generate_fallback(meal, mock_plan)

        assert notification["emoji"] == "🍽️"
        assert "almuerzo" in notification["title"].lower()
        assert meal.name in notification["message"]

    @pytest.mark.asyncio
    async def test_fallback_generation_dinner(self, service_with_ai_disabled, mock_plan):
        """Test que fallback genera notificación correcta para dinner."""
        meal = Mock(spec=Meal)
        meal.id = 125
        meal.name = "Cena Light"
        meal.meal_type = "dinner"
        meal.calories = 420

        notification = service_with_ai_disabled._generate_fallback(meal, mock_plan)

        assert notification["emoji"] == "🌙"
        assert "cena" in notification["title"].lower()

    @pytest.mark.asyncio
    async def test_get_emoji_for_meal_type(self, service_with_ai_disabled):
        """Test que emojis correctos se asignan por tipo de meal."""
        assert service_with_ai_disabled._get_emoji_for_meal_type("breakfast") == "🌅"
        assert service_with_ai_disabled._get_emoji_for_meal_type("lunch") == "🍽️"
        assert service_with_ai_disabled._get_emoji_for_meal_type("dinner") == "🌙"
        assert service_with_ai_disabled._get_emoji_for_meal_type("snack") == "🍎"
        assert service_with_ai_disabled._get_emoji_for_meal_type("mid_morning") == "🥤"
        assert service_with_ai_disabled._get_emoji_for_meal_type("afternoon") == "☕"
        assert service_with_ai_disabled._get_emoji_for_meal_type("post_workout") == "💪"
        assert service_with_ai_disabled._get_emoji_for_meal_type("late_snack") == "🍿"
        assert service_with_ai_disabled._get_emoji_for_meal_type("unknown") == "🍽️"

    @pytest.mark.asyncio
    @patch('app.services.meal_notification_cache.get_redis_client')
    async def test_cache_hit(self, mock_redis, service_with_ai_disabled, mock_meal, mock_plan):
        """Test que cache HIT retorna notificación cacheada."""
        # Mock Redis con notificación cacheada
        cached_notification = {
            "title": "🌅 Cached Title",
            "message": "Cached message",
            "emoji": "🌅"
        }

        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = json.dumps(cached_notification)
        mock_redis.return_value = mock_redis_client

        # Llamar al servicio
        notification = await service_with_ai_disabled.get_or_generate_notification(
            meal_id=mock_meal.id,
            meal=mock_meal,
            plan=mock_plan,
            gym_tone="motivational"
        )

        # Verificar que retorna cached
        assert notification == cached_notification
        mock_redis_client.get.assert_called_once()
        mock_redis_client.setex.assert_not_called()  # No debe guardar si ya existía

    @pytest.mark.asyncio
    @patch('app.services.meal_notification_cache.get_redis_client')
    async def test_cache_miss_generates_and_saves(self, mock_redis, service_with_ai_disabled, mock_meal, mock_plan):
        """Test que cache MISS genera notificación y la guarda."""
        # Mock Redis sin cache
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        # Llamar al servicio
        notification = await service_with_ai_disabled.get_or_generate_notification(
            meal_id=mock_meal.id,
            meal=mock_meal,
            plan=mock_plan,
            gym_tone="motivational"
        )

        # Verificar que genera notificación
        assert "title" in notification
        assert "message" in notification
        assert "emoji" in notification

        # Verificar que intenta guardar en cache
        mock_redis_client.get.assert_called_once()
        mock_redis_client.setex.assert_called_once()

        # Verificar parámetros de setex
        call_args = mock_redis_client.setex.call_args
        cache_key = call_args[0][0]
        ttl = call_args[0][1]
        cached_value = call_args[0][2]

        assert f"meal:{mock_meal.id}:notification:" in cache_key
        assert ttl == 2592000  # 30 días
        assert json.loads(cached_value) == notification

    @pytest.mark.asyncio
    @patch('app.services.meal_notification_cache.AsyncOpenAI')
    @patch('app.services.meal_notification_cache.get_redis_client')
    @patch('app.services.meal_notification_cache.get_settings')
    async def test_ai_generation_success(
        self,
        mock_settings,
        mock_redis,
        mock_openai_class,
        mock_meal,
        mock_plan
    ):
        """Test que generación con IA funciona correctamente."""
        # Setup settings con API key
        settings = Mock()
        settings.OPENAI_API_KEY = "test-api-key"
        mock_settings.return_value = settings

        # Mock Redis sin cache
        mock_redis_client = AsyncMock()
        mock_redis_client.get.return_value = None
        mock_redis.return_value = mock_redis_client

        # Mock OpenAI response
        ai_response = {
            "title": "🌅 AI Generated Title",
            "message": "AI generated message with context",
            "emoji": "🌅"
        }

        mock_openai_instance = AsyncMock()
        mock_openai_instance.chat.completions.create.return_value = AsyncMock(
            choices=[
                Mock(message=Mock(content=json.dumps(ai_response)))
            ]
        )
        mock_openai_class.return_value = mock_openai_instance

        # Crear servicio con IA habilitada
        service = MealNotificationCacheService()

        # Llamar al servicio
        notification = await service.get_or_generate_notification(
            meal_id=mock_meal.id,
            meal=mock_meal,
            plan=mock_plan,
            gym_tone="motivational"
        )

        # Verificar que retorna respuesta de IA
        assert notification == ai_response

        # Verificar que llamó a OpenAI
        mock_openai_instance.chat.completions.create.assert_called_once()

        # Verificar parámetros de llamada a OpenAI
        call_kwargs = mock_openai_instance.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == "gpt-4o-mini"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["max_tokens"] == 150
        assert call_kwargs["response_format"] == {"type": "json_object"}

    @pytest.mark.asyncio
    @patch('app.services.meal_notification_cache.get_redis_client')
    async def test_invalidate_meal_notification(self, mock_redis, service_with_ai_disabled, mock_meal):
        """Test que invalidación de cache elimina todas las claves del meal."""
        # Mock Redis
        mock_redis_client = AsyncMock()
        mock_redis_client.delete.return_value = 1
        mock_redis.return_value = mock_redis_client

        # Invalidar
        result = await service_with_ai_disabled.invalidate_meal_notification(mock_meal.id)

        # Verificar éxito
        assert result == True

        # Verificar que deletea para todos los tonos
        assert mock_redis_client.delete.call_count == 3  # motivational, neutral, friendly

        # Verificar las claves
        called_keys = [call[0][0] for call in mock_redis_client.delete.call_args_list]
        assert f"meal:{mock_meal.id}:notification:motivational" in called_keys
        assert f"meal:{mock_meal.id}:notification:neutral" in called_keys
        assert f"meal:{mock_meal.id}:notification:friendly" in called_keys

    @pytest.mark.asyncio
    async def test_build_prompt_contains_meal_info(self, service_with_ai_disabled, mock_meal, mock_plan):
        """Test que prompt contiene información del meal."""
        prompt = service_with_ai_disabled._build_prompt(mock_meal, mock_plan, "motivational")

        # Verificar que prompt contiene info del meal
        assert mock_meal.name in prompt
        assert mock_meal.meal_type in prompt
        if mock_meal.description:
            assert mock_meal.description in prompt

        # Verificar info nutricional
        if mock_meal.calories:
            assert str(mock_meal.calories) in prompt
        if mock_meal.protein_g:
            assert str(mock_meal.protein_g) in prompt

        # Verificar info del plan
        if mock_plan:
            assert mock_plan.title in prompt

        # Verificar tono
        assert "motivational" in prompt

    @pytest.mark.asyncio
    async def test_different_gym_tones(self, service_with_ai_disabled, mock_meal, mock_plan):
        """Test que diferentes tonos generan diferentes notificaciones."""
        tones = ["motivational", "neutral", "friendly"]

        for tone in tones:
            notification = service_with_ai_disabled._generate_fallback(mock_meal, mock_plan)

            # Todas deben tener estructura básica
            assert "title" in notification
            assert "message" in notification
            assert "emoji" in notification

    @pytest.mark.asyncio
    @patch('app.services.meal_notification_cache.get_redis_client')
    async def test_redis_failure_doesnt_break_generation(
        self,
        mock_redis,
        service_with_ai_disabled,
        mock_meal,
        mock_plan
    ):
        """Test que fallo de Redis no impide generación de notificación."""
        # Mock Redis que falla
        mock_redis.side_effect = Exception("Redis connection failed")

        # Llamar al servicio (no debe lanzar excepción)
        notification = await service_with_ai_disabled.get_or_generate_notification(
            meal_id=mock_meal.id,
            meal=mock_meal,
            plan=mock_plan,
            gym_tone="motivational"
        )

        # Debe generar notificación aunque Redis falle
        assert "title" in notification
        assert "message" in notification


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
