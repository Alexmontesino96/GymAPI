"""
Custom Prometheus collectors for GymAPI modules.
"""
from typing import Dict, List, Any
from prometheus_client import Gauge, Counter
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, REGISTRY
from datetime import datetime, timedelta
import logging
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

# ============================================================================
# BASE COLLECTOR
# ============================================================================

class BaseGymAPICollector:
    """Base collector para métricas de GymAPI."""

    def __init__(self, db_session_factory=None):
        self.db_session_factory = db_session_factory
        self._last_collection = datetime.now()

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos de métricas (implementar en subclases)."""
        raise NotImplementedError

    def describe(self):
        """Describir las métricas (requerido por Prometheus)."""
        return []

    def collect(self):
        """Colectar métricas (requerido por Prometheus)."""
        try:
            # Ejecutar en el loop de eventos
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            metrics_data = loop.run_until_complete(self.get_metrics_data())
            loop.close()

            # Generar métricas
            for metric in self._generate_metrics(metrics_data):
                yield metric

        except Exception as e:
            logger.error(f"Error collecting metrics in {self.__class__.__name__}: {e}")

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar objetos de métricas desde los datos."""
        return []

# ============================================================================
# NUTRITION COLLECTOR
# ============================================================================

class NutritionCollector(BaseGymAPICollector):
    """Collector para métricas del módulo de nutrición."""

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos de nutrición."""
        data = {
            'active_plans': {},
            'meals_logged': {},
            'calories_tracked': {},
            'notifications_sent': {}
        }

        if not self.db_session_factory:
            return data

        try:
            async with self.db_session_factory() as session:
                from app.models import NutritionPlan, Meal

                # Planes activos por gimnasio
                result = await session.execute(
                    select(
                        NutritionPlan.gym_id,
                        func.count(NutritionPlan.id)
                    ).where(NutritionPlan.is_active == True)
                    .group_by(NutritionPlan.gym_id)
                )
                for gym_id, count in result:
                    data['active_plans'][str(gym_id)] = count

                # Comidas registradas hoy por gimnasio
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                result = await session.execute(
                    select(
                        Meal.gym_id,
                        func.count(Meal.id),
                        func.sum(Meal.calories)
                    ).where(Meal.consumed_at >= today_start)
                    .group_by(Meal.gym_id)
                )
                for gym_id, meal_count, total_calories in result:
                    data['meals_logged'][str(gym_id)] = meal_count
                    data['calories_tracked'][str(gym_id)] = total_calories or 0

        except Exception as e:
            logger.error(f"Error getting nutrition metrics: {e}")

        return data

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar métricas de nutrición."""
        # Planes activos
        plans_metric = GaugeMetricFamily(
            'gymapi_nutrition_active_plans',
            'Active nutrition plans per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('active_plans', {}).items():
            plans_metric.add_metric([gym_id], count)
        yield plans_metric

        # Comidas registradas
        meals_metric = GaugeMetricFamily(
            'gymapi_nutrition_meals_logged_today',
            'Meals logged today per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('meals_logged', {}).items():
            meals_metric.add_metric([gym_id], count)
        yield meals_metric

        # Calorías trackeadas
        calories_metric = GaugeMetricFamily(
            'gymapi_nutrition_calories_tracked_today',
            'Total calories tracked today per gym',
            labels=['gym_id']
        )
        for gym_id, calories in data.get('calories_tracked', {}).items():
            calories_metric.add_metric([gym_id], calories)
        yield calories_metric

# ============================================================================
# EVENT COLLECTOR
# ============================================================================

class EventCollector(BaseGymAPICollector):
    """Collector para métricas del módulo de eventos."""

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos de eventos."""
        data = {
            'active_events': {},
            'participants': {},
            'upcoming_events': {}
        }

        if not self.db_session_factory:
            return data

        try:
            async with self.db_session_factory() as session:
                from app.models import Event, EventParticipant

                now = datetime.now()

                # Eventos activos por gimnasio
                result = await session.execute(
                    select(
                        Event.gym_id,
                        func.count(Event.id)
                    ).where(
                        Event.start_datetime <= now,
                        Event.end_datetime >= now
                    ).group_by(Event.gym_id)
                )
                for gym_id, count in result:
                    data['active_events'][str(gym_id)] = count

                # Total de participantes por gimnasio
                result = await session.execute(
                    select(
                        Event.gym_id,
                        func.count(EventParticipant.id)
                    ).join(Event, EventParticipant.event_id == Event.id)
                    .where(EventParticipant.status == 'confirmed')
                    .group_by(Event.gym_id)
                )
                for gym_id, count in result:
                    data['participants'][str(gym_id)] = count

                # Eventos próximos (próximas 24h)
                tomorrow = now + timedelta(days=1)
                result = await session.execute(
                    select(
                        Event.gym_id,
                        func.count(Event.id)
                    ).where(
                        Event.start_datetime >= now,
                        Event.start_datetime <= tomorrow
                    ).group_by(Event.gym_id)
                )
                for gym_id, count in result:
                    data['upcoming_events'][str(gym_id)] = count

        except Exception as e:
            logger.error(f"Error getting event metrics: {e}")

        return data

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar métricas de eventos."""
        # Eventos activos
        active_metric = GaugeMetricFamily(
            'gymapi_events_active',
            'Currently active events per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('active_events', {}).items():
            active_metric.add_metric([gym_id], count)
        yield active_metric

        # Participantes confirmados
        participants_metric = GaugeMetricFamily(
            'gymapi_events_confirmed_participants',
            'Total confirmed participants per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('participants', {}).items():
            participants_metric.add_metric([gym_id], count)
        yield participants_metric

        # Eventos próximos
        upcoming_metric = GaugeMetricFamily(
            'gymapi_events_upcoming_24h',
            'Events starting in next 24 hours per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('upcoming_events', {}).items():
            upcoming_metric.add_metric([gym_id], count)
        yield upcoming_metric

# ============================================================================
# BILLING COLLECTOR
# ============================================================================

class BillingCollector(BaseGymAPICollector):
    """Collector para métricas del módulo de billing."""

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos de billing."""
        data = {
            'active_subscriptions': {},
            'revenue_monthly': {},
            'pending_payments': {}
        }

        if not self.db_session_factory:
            return data

        try:
            async with self.db_session_factory() as session:
                from app.models import Membership, Payment

                # Suscripciones activas por gimnasio
                result = await session.execute(
                    select(
                        Membership.gym_id,
                        func.count(Membership.id)
                    ).where(Membership.status == 'active')
                    .group_by(Membership.gym_id)
                )
                for gym_id, count in result:
                    data['active_subscriptions'][str(gym_id)] = count

                # Revenue mensual por gimnasio
                month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                result = await session.execute(
                    select(
                        Payment.gym_id,
                        func.sum(Payment.amount)
                    ).where(
                        Payment.created_at >= month_start,
                        Payment.status == 'completed'
                    ).group_by(Payment.gym_id)
                )
                for gym_id, revenue in result:
                    data['revenue_monthly'][str(gym_id)] = float(revenue) if revenue else 0

                # Pagos pendientes
                result = await session.execute(
                    select(
                        Payment.gym_id,
                        func.count(Payment.id)
                    ).where(Payment.status == 'pending')
                    .group_by(Payment.gym_id)
                )
                for gym_id, count in result:
                    data['pending_payments'][str(gym_id)] = count

        except Exception as e:
            logger.error(f"Error getting billing metrics: {e}")

        return data

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar métricas de billing."""
        # Suscripciones activas
        subs_metric = GaugeMetricFamily(
            'gymapi_billing_active_subscriptions',
            'Active subscriptions per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('active_subscriptions', {}).items():
            subs_metric.add_metric([gym_id], count)
        yield subs_metric

        # Revenue mensual
        revenue_metric = GaugeMetricFamily(
            'gymapi_billing_monthly_revenue',
            'Monthly revenue per gym',
            labels=['gym_id']
        )
        for gym_id, revenue in data.get('revenue_monthly', {}).items():
            revenue_metric.add_metric([gym_id], revenue)
        yield revenue_metric

        # Pagos pendientes
        pending_metric = GaugeMetricFamily(
            'gymapi_billing_pending_payments',
            'Pending payments per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('pending_payments', {}).items():
            pending_metric.add_metric([gym_id], count)
        yield pending_metric

# ============================================================================
# CHAT COLLECTOR
# ============================================================================

class ChatCollector(BaseGymAPICollector):
    """Collector para métricas del módulo de chat."""

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos de chat."""
        data = {
            'active_channels': {},
            'messages_today': {},
            'active_users': {}
        }

        # Stream Chat metrics would require Stream API calls
        # For now, return basic structure
        # In production, integrate with Stream Analytics API

        return data

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar métricas de chat."""
        # Canales activos
        channels_metric = GaugeMetricFamily(
            'gymapi_chat_active_channels',
            'Active chat channels per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('active_channels', {}).items():
            channels_metric.add_metric([gym_id], count)
        yield channels_metric

        # Mensajes hoy
        messages_metric = GaugeMetricFamily(
            'gymapi_chat_messages_today',
            'Messages sent today per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('messages_today', {}).items():
            messages_metric.add_metric([gym_id], count)
        yield messages_metric

# ============================================================================
# SCHEDULE COLLECTOR
# ============================================================================

class ScheduleCollector(BaseGymAPICollector):
    """Collector para métricas del módulo de schedule."""

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos de schedule."""
        data = {
            'scheduled_classes': {},
            'bookings_today': {},
            'attendance_rate': {}
        }

        if not self.db_session_factory:
            return data

        try:
            async with self.db_session_factory() as session:
                from app.models import ScheduleSession, Booking

                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                today_end = today_start + timedelta(days=1)

                # Clases programadas hoy
                result = await session.execute(
                    select(
                        ScheduleSession.gym_id,
                        func.count(ScheduleSession.id)
                    ).where(
                        ScheduleSession.start_time >= today_start,
                        ScheduleSession.start_time < today_end
                    ).group_by(ScheduleSession.gym_id)
                )
                for gym_id, count in result:
                    data['scheduled_classes'][str(gym_id)] = count

                # Reservas hoy
                result = await session.execute(
                    select(
                        ScheduleSession.gym_id,
                        func.count(Booking.id)
                    ).join(ScheduleSession, Booking.session_id == ScheduleSession.id)
                    .where(
                        ScheduleSession.start_time >= today_start,
                        ScheduleSession.start_time < today_end,
                        Booking.status == 'confirmed'
                    ).group_by(ScheduleSession.gym_id)
                )
                for gym_id, count in result:
                    data['bookings_today'][str(gym_id)] = count

        except Exception as e:
            logger.error(f"Error getting schedule metrics: {e}")

        return data

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar métricas de schedule."""
        # Clases programadas
        classes_metric = GaugeMetricFamily(
            'gymapi_schedule_classes_today',
            'Scheduled classes today per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('scheduled_classes', {}).items():
            classes_metric.add_metric([gym_id], count)
        yield classes_metric

        # Reservas hoy
        bookings_metric = GaugeMetricFamily(
            'gymapi_schedule_bookings_today',
            'Bookings today per gym',
            labels=['gym_id']
        )
        for gym_id, count in data.get('bookings_today', {}).items():
            bookings_metric.add_metric([gym_id], count)
        yield bookings_metric

# ============================================================================
# MAIN COLLECTOR
# ============================================================================

class GymAPICollector(BaseGymAPICollector):
    """Collector principal para métricas generales de GymAPI."""

    async def get_metrics_data(self) -> Dict[str, Any]:
        """Obtener datos generales."""
        data = {
            'total_gyms': 0,
            'total_users': {},
            'active_sessions': {}
        }

        if not self.db_session_factory:
            return data

        try:
            async with self.db_session_factory() as session:
                from app.models import Gym, User

                # Total de gimnasios
                result = await session.execute(
                    select(func.count(Gym.id)).where(Gym.is_active == True)
                )
                data['total_gyms'] = result.scalar() or 0

                # Usuarios por tipo y gimnasio
                result = await session.execute(
                    select(
                        User.gym_id,
                        User.role,
                        func.count(User.id)
                    ).where(User.is_active == True)
                    .group_by(User.gym_id, User.role)
                )
                for gym_id, role, count in result:
                    gym_key = str(gym_id)
                    if gym_key not in data['total_users']:
                        data['total_users'][gym_key] = {}
                    data['total_users'][gym_key][role] = count

        except Exception as e:
            logger.error(f"Error getting general metrics: {e}")

        return data

    def _generate_metrics(self, data: Dict[str, Any]):
        """Generar métricas generales."""
        # Total de gimnasios
        gyms_metric = GaugeMetricFamily(
            'gymapi_total_gyms',
            'Total active gyms'
        )
        gyms_metric.add_metric([], data.get('total_gyms', 0))
        yield gyms_metric

        # Usuarios por tipo
        users_metric = GaugeMetricFamily(
            'gymapi_total_users',
            'Total users per gym and role',
            labels=['gym_id', 'role']
        )
        for gym_id, roles in data.get('total_users', {}).items():
            for role, count in roles.items():
                users_metric.add_metric([gym_id, role], count)
        yield users_metric