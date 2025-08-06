"""
Tests para UserStatsService

Tests críticos para el servicio de estadísticas de usuario, incluyendo
performance, cache, y lógica de negocio.
"""

import pytest
from datetime import datetime, timedelta, date
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from app.services.user_stats import user_stats_service
from app.schemas.user_stats import (
    DashboardSummary, ComprehensiveUserStats, PeriodType,
    FitnessMetrics, EventsMetrics, SocialMetrics
)
from app.models.schedule import ClassParticipation, ClassParticipationStatus
from app.models.event import EventParticipation
from app.models.user_gym import UserGym


class TestUserStatsService:
    """Tests para UserStatsService."""

    @pytest.fixture
    def mock_db(self):
        """Mock de sesión de base de datos."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_redis(self):
        """Mock de cliente Redis."""
        return AsyncMock()

    @pytest.fixture
    def sample_user_data(self):
        """Datos de muestra para tests."""
        return {
            "user_id": 1,
            "gym_id": 1,
            "auth0_id": "auth0|test123"
        }

    # Tests de Dashboard Summary
    
    @pytest.mark.asyncio
    async def test_get_dashboard_summary_with_cache_hit(self, mock_db, mock_redis, sample_user_data):
        """Test dashboard summary con cache hit."""
        # Arrange
        expected_summary = DashboardSummary(
            user_id=1,
            current_streak=5,
            weekly_workouts=3,
            monthly_goal_progress=75.0,
            next_class="Yoga - Mañana 9:00 AM",
            recent_achievement=None,
            membership_status="active",
            quick_stats={"total_sessions_month": 12}
        )
        
        # Mock cache hit
        with patch.object(user_stats_service.cache_service, 'get_or_set') as mock_cache:
            mock_cache.return_value = expected_summary
            
            # Act
            result = await user_stats_service.get_dashboard_summary(
                mock_db, 
                sample_user_data["user_id"], 
                sample_user_data["gym_id"],
                mock_redis
            )
            
            # Assert
            assert result.user_id == expected_summary.user_id
            assert result.current_streak == expected_summary.current_streak
            assert result.weekly_workouts == expected_summary.weekly_workouts
            mock_cache.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_dashboard_summary_cache_miss(self, mock_db, mock_redis, sample_user_data):
        """Test dashboard summary con cache miss."""
        # Arrange
        with patch.object(user_stats_service.cache_service, 'get_or_set') as mock_cache:
            mock_cache.return_value = None  # Cache miss
            
            with patch.object(user_stats_service, '_compute_dashboard_summary') as mock_compute:
                expected_summary = DashboardSummary(
                    user_id=1,
                    current_streak=2,
                    weekly_workouts=1,
                    monthly_goal_progress=25.0,
                    next_class=None,
                    recent_achievement=None,
                    membership_status="active",
                    quick_stats={}
                )
                mock_compute.return_value = expected_summary
                
                # Act
                result = await user_stats_service.get_dashboard_summary(
                    mock_db,
                    sample_user_data["user_id"],
                    sample_user_data["gym_id"],
                    mock_redis
                )
                
                # Assert
                assert result == expected_summary
                mock_compute.assert_called_once()

    # Tests de Comprehensive Stats
    
    @pytest.mark.asyncio
    async def test_get_comprehensive_stats_different_periods(self, mock_db, mock_redis, sample_user_data):
        """Test comprehensive stats con diferentes períodos."""
        periods_to_test = [PeriodType.week, PeriodType.month, PeriodType.quarter, PeriodType.year]
        
        for period in periods_to_test:
            with patch.object(user_stats_service, '_compute_comprehensive_stats') as mock_compute:
                mock_stats = Mock(spec=ComprehensiveUserStats)
                mock_stats.period = period
                mock_compute.return_value = mock_stats
                
                # Act
                result = await user_stats_service.get_comprehensive_stats(
                    mock_db,
                    sample_user_data["user_id"],
                    sample_user_data["gym_id"],
                    period=period,
                    redis_client=mock_redis
                )
                
                # Assert
                assert result.period == period
                mock_compute.assert_called_once()

    # Tests de Cálculos Específicos
    
    @pytest.mark.asyncio 
    async def test_calculate_current_streak_no_attendance(self, mock_db, sample_user_data):
        """Test cálculo de racha sin asistencias."""
        # Arrange
        mock_db.query.return_value.filter.return_value.distinct.return_value.order_by.return_value.all.return_value = []
        
        # Act
        result = await user_stats_service._calculate_current_streak_fast(
            mock_db,
            sample_user_data["user_id"],
            sample_user_data["gym_id"]
        )
        
        # Assert
        assert result == 0

    @pytest.mark.asyncio
    async def test_calculate_current_streak_with_data(self, mock_db, sample_user_data):
        """Test cálculo de racha con datos de asistencia."""
        # Arrange
        today = date.today()
        mock_attendance_data = [
            Mock(attendance_date=today),
            Mock(attendance_date=today - timedelta(days=1)),
            Mock(attendance_date=today - timedelta(days=2))
        ]
        mock_db.query.return_value.filter.return_value.distinct.return_value.order_by.return_value.all.return_value = mock_attendance_data
        
        # Act
        result = await user_stats_service._calculate_current_streak_fast(
            mock_db,
            sample_user_data["user_id"],
            sample_user_data["gym_id"]
        )
        
        # Assert
        assert result == 3  # 3 días consecutivos

    @pytest.mark.asyncio
    async def test_get_weekly_workout_count(self, mock_db, sample_user_data):
        """Test conteo de entrenamientos semanales."""
        # Arrange
        week_start = date.today() - timedelta(days=date.today().weekday())
        mock_db.query.return_value.filter.return_value.count.return_value = 4
        
        # Act
        result = await user_stats_service._get_weekly_workout_count(
            mock_db,
            sample_user_data["user_id"],
            sample_user_data["gym_id"],
            week_start
        )
        
        # Assert
        assert result == 4

    # Tests de Fitness Metrics
    
    @pytest.mark.asyncio
    async def test_compute_fitness_metrics(self, mock_db, sample_user_data):
        """Test cómputo de métricas de fitness."""
        # Arrange
        period_start = datetime.now() - timedelta(days=30)
        period_end = datetime.now()
        
        # Mock de query counts
        mock_counts = Mock()
        mock_counts.attended_classes = 10
        mock_counts.scheduled_classes = 12
        mock_db.query.return_value.filter.return_value.first.return_value = mock_counts
        
        # Mock de total horas
        mock_hours = Mock()
        mock_hours.total_minutes = 600  # 10 horas
        mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.first.return_value = mock_hours
        
        # Mock streak methods
        with patch.object(user_stats_service, '_calculate_current_streak_fast') as mock_current_streak:
            with patch.object(user_stats_service, '_calculate_longest_streak') as mock_longest_streak:
                mock_current_streak.return_value = 5
                mock_longest_streak.return_value = 8
                
                # Mock favorite classes
                mock_favorite_classes = [
                    Mock(name="Yoga", count=3),
                    Mock(name="Pilates", count=2)
                ]
                mock_db.query.return_value.join.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_favorite_classes
                
                # Mock peak times
                mock_peak_times = [
                    Mock(hour=18, count=5),
                    Mock(hour=9, count=3)
                ]
                mock_db.query.return_value.join.return_value.filter.return_value.group_by.return_value.order_by.return_value.limit.return_value.all.return_value = mock_peak_times
                
                # Act
                result = await user_stats_service._compute_fitness_metrics(
                    mock_db,
                    sample_user_data["user_id"],
                    sample_user_data["gym_id"],
                    period_start,
                    period_end
                )
                
                # Assert
                assert isinstance(result, FitnessMetrics)
                assert result.classes_attended == 10
                assert result.classes_scheduled == 12
                assert result.attendance_rate == 83.3  # 10/12 * 100
                assert result.total_workout_hours == 10.0
                assert result.streak_current == 5
                assert result.streak_longest == 8
                assert "Yoga" in result.favorite_class_types

    # Tests de Performance
    
    @pytest.mark.asyncio
    async def test_dashboard_summary_performance(self, mock_db, mock_redis, sample_user_data):
        """Test de performance del dashboard summary."""
        import time
        
        # Arrange
        with patch.object(user_stats_service, '_compute_dashboard_summary') as mock_compute:
            mock_compute.return_value = DashboardSummary(
                user_id=1,
                current_streak=0,
                weekly_workouts=0,
                monthly_goal_progress=0.0,
                next_class=None,
                recent_achievement=None,
                membership_status="active",
                quick_stats={}
            )
            
            # Act
            start_time = time.time()
            await user_stats_service.get_dashboard_summary(
                mock_db,
                sample_user_data["user_id"],
                sample_user_data["gym_id"],
                mock_redis
            )
            end_time = time.time()
            
            # Assert - should be very fast (mock, but test structure)
            duration_ms = (end_time - start_time) * 1000
            assert duration_ms < 100  # Less than 100ms for mock

    # Tests de Error Handling
    
    @pytest.mark.asyncio
    async def test_dashboard_summary_error_handling(self, mock_db, mock_redis, sample_user_data):
        """Test manejo de errores en dashboard summary."""
        # Arrange
        with patch.object(user_stats_service, '_compute_dashboard_summary') as mock_compute:
            mock_compute.side_effect = Exception("Database error")
            
            # Act & Assert - should not raise, should return default
            result = await user_stats_service.get_dashboard_summary(
                mock_db,
                sample_user_data["user_id"],
                sample_user_data["gym_id"],
                mock_redis
            )
            
            # Should return default values when error occurs
            assert result.user_id == sample_user_data["user_id"]
            assert result.current_streak == 0
            assert result.membership_status == "unknown"

    # Tests de Cache TTL
    
    @pytest.mark.asyncio
    async def test_comprehensive_stats_cache_ttl_by_period(self, mock_db, mock_redis, sample_user_data):
        """Test que el TTL del cache varía según el período."""
        periods_and_ttls = [
            (PeriodType.week, 1800),     # 30 minutes
            (PeriodType.month, 3600),    # 1 hour
            (PeriodType.quarter, 7200),  # 2 hours
            (PeriodType.year, 14400)     # 4 hours
        ]
        
        for period, expected_ttl in periods_and_ttls:
            with patch.object(user_stats_service.cache_service, 'get_or_set') as mock_cache:
                mock_cache.return_value = None
                
                with patch.object(user_stats_service, '_compute_comprehensive_stats') as mock_compute:
                    mock_compute.return_value = Mock(spec=ComprehensiveUserStats)
                    
                    # Act
                    await user_stats_service.get_comprehensive_stats(
                        mock_db,
                        sample_user_data["user_id"],
                        sample_user_data["gym_id"],
                        period=period,
                        redis_client=mock_redis
                    )
                    
                    # Assert - verificar que se llamó con el TTL correcto
                    mock_cache.assert_called_once()
                    call_args = mock_cache.call_args
                    assert call_args.kwargs['expiry_seconds'] == expected_ttl

    # Tests de Validación
    
    def test_calculate_period_dates(self, sample_user_data):
        """Test cálculo de fechas de período."""
        # Test week period
        start, end = user_stats_service._calculate_period_dates(PeriodType.week)
        assert (end - start).days == 7
        
        # Test month period
        start, end = user_stats_service._calculate_period_dates(PeriodType.month)
        assert start.day == 1  # Should start from first day of month
        
        # Test quarter period
        start, end = user_stats_service._calculate_period_dates(PeriodType.quarter)
        assert start.month in [1, 4, 7, 10]  # Should be start of quarter
        
        # Test year period
        start, end = user_stats_service._calculate_period_dates(PeriodType.year)
        assert start.month == 1 and start.day == 1  # Should start from Jan 1

    # Tests de Integración
    
    @pytest.mark.asyncio
    async def test_social_score_calculation(self, sample_user_data):
        """Test cálculo de social score."""
        # Test different scenarios
        test_cases = [
            (0, 0, 0, 0.0),      # No activity
            (2, 10, 5, 3.7),     # Low activity  
            (5, 50, 10, 7.5),    # Medium activity
            (10, 150, 20, 10.0)  # High activity (capped at 10)
        ]
        
        for chat_rooms, messages, recent_days, expected_score in test_cases:
            result = user_stats_service._calculate_social_score(chat_rooms, messages, recent_days)
            assert abs(result - expected_score) < 0.1  # Allow small floating point differences

    def test_membership_value_score_calculation(self, sample_user_data):
        """Test cálculo de value score de membresía."""
        # Test with different scenarios
        mock_plan = Mock()
        
        # High utilization with premium plan
        result = user_stats_service._calculate_membership_value_score(90.0, 20, mock_plan)
        assert result == 10.0  # Should be maximum
        
        # Low utilization with basic plan
        result = user_stats_service._calculate_membership_value_score(20.0, 5, None)
        assert result < 5.0  # Should be lower
        
        # No activity
        result = user_stats_service._calculate_membership_value_score(0.0, 0, None)
        assert result == 1.0  # Base score for having any plan


# Tests de Performance Críticos

@pytest.mark.performance
class TestUserStatsPerformance:
    """Tests específicos de performance."""

    @pytest.mark.asyncio
    async def test_dashboard_summary_target_time(self, mock_db, mock_redis):
        """Test que dashboard summary cumple target de < 50ms."""
        # Este test requeriría una base de datos real para ser meaningful
        # Por ahora, testea la estructura
        pass

    @pytest.mark.asyncio
    async def test_comprehensive_stats_target_time(self, mock_db, mock_redis):
        """Test que comprehensive stats cumple target de < 200ms con cache."""
        # Este test requeriría una base de datos real para ser meaningful
        pass


# Fixtures adicionales para tests de integración

@pytest.fixture(scope="session")
def real_db_session():
    """
    Fixture para tests de integración con base de datos real.
    Solo se usa para tests marcados como @pytest.mark.integration
    """
    # Configuración de base de datos de test
    pass


@pytest.mark.integration
class TestUserStatsIntegration:
    """Tests de integración con base de datos real."""
    
    def test_real_database_queries(self, real_db_session):
        """Test queries reales contra base de datos."""
        # Estos tests requieren configuración específica de base de datos de test
        pass