"""
Tests para Activity Feed.

Verifica:
1. Privacidad: No exposición de nombres de usuarios
2. Agregación mínima: No mostrar con menos de 3 personas
3. Performance: Respuesta en menos de 50ms
4. Funcionalidad: Publicación y recuperación de actividades
"""

import pytest
import asyncio
import json
import time
from typing import Dict, List
from datetime import datetime
from redis.asyncio import Redis
from unittest.mock import Mock, AsyncMock, patch

from app.services.activity_feed_service import ActivityFeedService
from app.services.activity_aggregator import ActivityAggregator


class TestActivityFeedPrivacy:
    """Tests de privacidad del Activity Feed."""

    @pytest.mark.asyncio
    async def test_no_user_names_in_activities(self):
        """Verifica que las actividades nunca contengan nombres de usuarios."""
        # Crear mock de Redis
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)

        # Crear servicio
        feed_service = ActivityFeedService(redis_mock)

        # Publicar actividad
        activity = await feed_service.publish_realtime_activity(
            gym_id=1,
            activity_type="training_count",
            count=15,
            metadata={"source": "test"}
        )

        # Verificar que no hay nombres
        assert activity is not None
        assert "name" not in activity
        assert "user" not in activity
        assert "user_name" not in activity
        assert "user_id" not in activity

        # Verificar que sí tiene información anónima
        assert activity["count"] == 15
        assert activity["type"] == "realtime"
        assert activity["message"] == "15 personas entrenando ahora"

    @pytest.mark.asyncio
    async def test_minimum_aggregation_threshold(self):
        """Verifica que no se publiquen actividades con menos del umbral mínimo."""
        redis_mock = AsyncMock(spec=Redis)
        feed_service = ActivityFeedService(redis_mock)

        # Intentar publicar con count < 3
        activity = await feed_service.publish_realtime_activity(
            gym_id=1,
            activity_type="training_count",
            count=2,  # Menor que el umbral
            metadata={"source": "test"}
        )

        # Debe retornar None (no publicado)
        assert activity is None

        # Verificar que no se llamó a Redis
        redis_mock.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_anonymous_rankings(self):
        """Verifica que los rankings sean completamente anónimos."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.delete = AsyncMock(return_value=True)
        redis_mock.zadd = AsyncMock(return_value=1)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.zrevrange = AsyncMock(return_value=[
            (b"anonymous_1", 45.0),
            (b"anonymous_2", 42.0),
            (b"anonymous_3", 40.0)
        ])

        feed_service = ActivityFeedService(redis_mock)

        # Crear ranking
        ranking = await feed_service.add_anonymous_ranking(
            gym_id=1,
            ranking_type="consistency",
            values=[45, 42, 40, 38, 35],
            period="weekly"
        )

        # Verificar estructura del ranking
        assert ranking["type"] == "consistency"
        assert ranking["top_values"] == [45, 42, 40, 38, 35]

        # Obtener rankings
        rankings = await feed_service.get_anonymous_rankings(
            gym_id=1,
            ranking_type="consistency",
            period="weekly"
        )

        # Verificar que son anónimos
        assert len(rankings) == 3
        for rank in rankings:
            assert "position" in rank
            assert "value" in rank
            assert "label" in rank
            assert rank["label"].startswith("Posición")
            # No debe haber información de usuario
            assert "user" not in rank
            assert "name" not in rank
            assert "user_id" not in rank

    @pytest.mark.asyncio
    async def test_aggregated_stats_only(self):
        """Verifica que solo se muestren estadísticas agregadas."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.keys = AsyncMock(return_value=[
            b"gym:1:realtime:training_count",
            b"gym:1:realtime:by_class:CrossFit"
        ])
        redis_mock.get = AsyncMock(side_effect=lambda key: {
            b"gym:1:realtime:training_count": b"25",
            "gym:1:realtime:training_count": b"25",
            b"gym:1:realtime:by_class:CrossFit": b"10",
            "gym:1:realtime:by_class:CrossFit": b"10"
        }.get(key, b"0"))

        feed_service = ActivityFeedService(redis_mock)

        # Obtener resumen
        summary = await feed_service.get_realtime_summary(gym_id=1)

        # Verificar que solo hay números agregados
        assert summary["total_training"] == 25
        assert "by_area" in summary
        assert summary["peak_time"] == True  # >20 personas

        # No debe haber información individual
        assert "users" not in summary
        assert "participants" not in summary
        assert "members" not in summary


class TestActivityFeedPerformance:
    """Tests de performance del Activity Feed."""

    @pytest.mark.asyncio
    async def test_feed_response_time(self):
        """Verifica que el feed responda en menos de 50ms."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.lrange = AsyncMock(return_value=[
            json.dumps({
                "type": "realtime",
                "count": 10,
                "message": "10 personas entrenando",
                "timestamp": datetime.utcnow().isoformat()
            }).encode()
            for _ in range(20)
        ])

        feed_service = ActivityFeedService(redis_mock)

        # Medir tiempo de respuesta
        start = time.time()
        activities = await feed_service.get_feed(gym_id=1, limit=20)
        duration = (time.time() - start) * 1000  # Convertir a ms

        # Verificar respuesta rápida
        assert duration < 50  # Menos de 50ms
        assert len(activities) == 20

    @pytest.mark.asyncio
    async def test_concurrent_requests_performance(self):
        """Verifica el rendimiento con múltiples requests concurrentes."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.lrange = AsyncMock(return_value=[])
        redis_mock.get = AsyncMock(return_value=b"10")

        feed_service = ActivityFeedService(redis_mock)

        # Crear 100 requests concurrentes
        tasks = []
        for _ in range(100):
            tasks.append(feed_service.get_feed(gym_id=1))

        start = time.time()
        results = await asyncio.gather(*tasks)
        duration = time.time() - start

        # Verificar que 100 requests se procesan en menos de 2 segundos
        assert duration < 2.0
        assert len(results) == 100
        assert all(isinstance(r, list) for r in results)

    @pytest.mark.asyncio
    async def test_memory_efficient_storage(self):
        """Verifica que el almacenamiento sea eficiente en memoria."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)

        feed_service = ActivityFeedService(redis_mock)

        # Publicar múltiples actividades
        for i in range(100):
            await feed_service.publish_realtime_activity(
                gym_id=1,
                activity_type="training_count",
                count=10 + i,
                metadata={"iteration": i}
            )

        # Verificar que se limita el tamaño del feed (ltrim a 100 items)
        assert redis_mock.ltrim.call_count == 100
        ltrim_calls = redis_mock.ltrim.call_args_list
        # Verificar que siempre se limita a 100 items
        for call in ltrim_calls:
            assert call[0][1] == 0
            assert call[0][2] == 99  # Máximo 100 items


class TestActivityAggregator:
    """Tests del agregador de actividades."""

    @pytest.mark.asyncio
    async def test_check_in_aggregation(self):
        """Verifica la agregación de check-ins."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.incr = AsyncMock(side_effect=[5, 20, 1])  # Clase, total, diario
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)

        feed_service = ActivityFeedService(redis_mock)
        aggregator = ActivityAggregator(feed_service)

        # Procesar check-in
        await aggregator.on_class_checkin({
            "gym_id": 1,
            "class_name": "CrossFit",
            "class_id": 1,
            "session_id": 1
        })

        # Verificar que se incrementaron contadores
        assert redis_mock.incr.call_count == 3  # Clase, total, diario

    @pytest.mark.asyncio
    async def test_achievement_aggregation(self):
        """Verifica la agregación de logros sin exponer usuarios."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.incr = AsyncMock(return_value=3)  # Múltiplo del umbral
        redis_mock.get = AsyncMock(return_value=b"3")
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)

        feed_service = ActivityFeedService(redis_mock)
        feed_service.update_aggregate_stats = AsyncMock(return_value=3)
        aggregator = ActivityAggregator(feed_service)

        # Procesar logro
        await aggregator.on_achievement_unlocked({
            "gym_id": 1,
            "achievement_type": "consistency",
            "achievement_level": "gold"
        })

        # Verificar que se actualizaron estadísticas
        feed_service.update_aggregate_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_streak_milestone_handling(self):
        """Verifica el manejo de hitos de racha."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.incr = AsyncMock(return_value=5)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)

        feed_service = ActivityFeedService(redis_mock)
        aggregator = ActivityAggregator(feed_service)

        # Procesar hito de 30 días (milestone válido)
        await aggregator.on_streak_milestone({
            "gym_id": 1,
            "streak_days": 30
        })

        # Verificar que se procesó
        assert redis_mock.incr.call_count >= 1

        # Resetear mocks
        redis_mock.reset_mock()

        # Procesar día no milestone (15 días)
        await aggregator.on_streak_milestone({
            "gym_id": 1,
            "streak_days": 15
        })

        # No debe procesarse (no es milestone)
        redis_mock.incr.assert_not_called()


class TestActivityFeedFunctionality:
    """Tests de funcionalidad general del Activity Feed."""

    @pytest.mark.asyncio
    async def test_motivational_insights_generation(self):
        """Verifica la generación de insights motivacionales."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.get = AsyncMock(side_effect=lambda key: {
            f"gym:1:realtime:training_count": b"25",
            f"gym:1:daily:achievements_count": b"8",
            f"gym:1:daily:personal_records": b"5",
            f"gym:1:daily:active_streaks": b"15",
            f"gym:1:daily:total_hours": b"120.5"
        }.get(key.decode() if isinstance(key, bytes) else key))

        feed_service = ActivityFeedService(redis_mock)

        # Generar insights
        insights = await feed_service.generate_motivational_insights(gym_id=1)

        # Verificar que se generaron insights
        assert len(insights) > 0
        assert all(isinstance(i, dict) for i in insights)

        # Verificar estructura de insights
        for insight in insights:
            assert "message" in insight
            assert "type" in insight
            assert "priority" in insight
            # Verificar que no hay nombres en mensajes
            assert "María" not in insight["message"]
            assert "Juan" not in insight["message"]

    @pytest.mark.asyncio
    async def test_class_occupancy_updates(self):
        """Verifica las actualizaciones de ocupación de clases."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.expire = AsyncMock(return_value=True)

        feed_service = ActivityFeedService(redis_mock)

        # Actualizar ocupación alta (>80%)
        activity = await feed_service.update_class_occupancy(
            gym_id=1,
            class_id=1,
            class_name="Spinning",
            current_occupancy=18,
            max_capacity=20
        )

        # Debe publicarse
        assert activity is not None
        assert "Spinning casi lleno (18/20)" in activity["message"]

        # Resetear mock
        redis_mock.reset_mock()

        # Actualizar ocupación baja (<80%)
        activity = await feed_service.update_class_occupancy(
            gym_id=1,
            class_id=2,
            class_name="Yoga",
            current_occupancy=5,
            max_capacity=20
        )

        # No debe publicarse
        assert activity is None
        redis_mock.lpush.assert_not_called()

    @pytest.mark.asyncio
    async def test_ttl_configuration(self):
        """Verifica que los TTLs se configuren correctamente."""
        redis_mock = AsyncMock(spec=Redis)
        redis_mock.setex = AsyncMock(return_value=True)
        redis_mock.expire = AsyncMock(return_value=True)
        redis_mock.lpush = AsyncMock(return_value=1)
        redis_mock.ltrim = AsyncMock(return_value=True)
        redis_mock.publish = AsyncMock(return_value=1)

        feed_service = ActivityFeedService(redis_mock)

        # Publicar actividad en tiempo real
        await feed_service.publish_realtime_activity(
            gym_id=1,
            activity_type="training_count",
            count=10
        )

        # Verificar que se estableció TTL correcto para tiempo real (5 minutos)
        setex_call = redis_mock.setex.call_args
        assert setex_call[0][1] == 300  # 5 minutos

        # Verificar expire del feed (1 hora)
        expire_calls = [call[0] for call in redis_mock.expire.call_args_list]
        assert any(call[1] == 3600 for call in expire_calls)  # 1 hora para feed


# Fixtures para tests

@pytest.fixture
async def redis_client():
    """Fixture para cliente Redis mock."""
    mock = AsyncMock(spec=Redis)
    mock.ping = AsyncMock(return_value=True)
    mock.info = AsyncMock(return_value={"used_memory": 50000000})
    return mock


@pytest.fixture
async def feed_service(redis_client):
    """Fixture para servicio de Activity Feed."""
    return ActivityFeedService(redis_client)


@pytest.fixture
async def aggregator(feed_service):
    """Fixture para agregador de actividades."""
    return ActivityAggregator(feed_service)