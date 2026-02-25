"""
Serialization utilities for nutrition module objects.
Handles conversion between SQLAlchemy models and JSON for Redis caching.
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime, date, time
from decimal import Decimal
from enum import Enum
import json
import logging

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal, MealIngredient,
    NutritionPlanFollower, UserMealCompletion, UserDailyProgress,
    PlanType, NutritionGoal, MealType, DifficultyLevel, BudgetLevel
)
from app.models.user import User

logger = logging.getLogger(__name__)


class NutritionEncoder(json.JSONEncoder):
    """Custom JSON encoder for nutrition module objects."""

    def default(self, obj):
        """Handle special types for JSON serialization."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, time):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, '__dict__'):
            # For SQLAlchemy models or custom objects
            return self._serialize_model(obj)
        return super().default(obj)

    def _serialize_model(self, obj):
        """Serialize SQLAlchemy model to dict."""
        result = {}

        # Get model columns
        for column in obj.__table__.columns:
            attr_name = column.name
            value = getattr(obj, attr_name, None)
            if value is not None:
                result[attr_name] = value

        return result


class NutritionSerializer:
    """Handles serialization and deserialization of nutrition objects for caching."""

    @staticmethod
    def serialize_plan(plan: NutritionPlan, include_relations: bool = True) -> str:
        """
        Serialize a nutrition plan to JSON string.

        Args:
            plan: NutritionPlan object
            include_relations: Whether to include related objects (daily_plans, meals, etc.)

        Returns:
            JSON string representation
        """
        try:
            data = {
                'id': plan.id,
                'gym_id': plan.gym_id,
                'creator_id': plan.creator_id,
                'title': plan.title,  # Fixed: was 'name'
                'description': plan.description,
                'goal': plan.goal.value if plan.goal else None,
                'target_calories': float(plan.target_calories) if plan.target_calories else None,
                'target_protein_g': float(plan.target_protein_g) if plan.target_protein_g else None,  # Fixed: was 'target_protein'
                'target_carbs_g': float(plan.target_carbs_g) if plan.target_carbs_g else None,  # Fixed: was 'target_carbs'
                'target_fat_g': float(plan.target_fat_g) if plan.target_fat_g else None,  # Fixed: was 'target_fat'
                'duration_days': plan.duration_days,
                'is_public': plan.is_public,
                'is_active': plan.is_active,
                'plan_type': plan.plan_type.value if plan.plan_type else None,
                'is_recurring': plan.is_recurring,
                'live_start_date': plan.live_start_date.isoformat() if plan.live_start_date else None,
                'tags': plan.tags,
                'created_at': plan.created_at.isoformat() if plan.created_at else None,
                'updated_at': plan.updated_at.isoformat() if plan.updated_at else None
            }

            if include_relations and hasattr(plan, 'daily_plans'):
                data['daily_plans'] = [
                    NutritionSerializer._serialize_daily_plan(dp)
                    for dp in plan.daily_plans
                ]

            return json.dumps(data, cls=NutritionEncoder)

        except Exception as e:
            logger.error(f"Error serializing nutrition plan {plan.id}: {e}")
            raise

    @staticmethod
    def _serialize_daily_plan(daily_plan: DailyNutritionPlan) -> Dict:
        """Serialize a daily nutrition plan to dict."""
        data = {
            'id': daily_plan.id,
            'nutrition_plan_id': daily_plan.nutrition_plan_id,  # Fixed: was 'plan_id'
            'day_number': daily_plan.day_number,
            'planned_date': daily_plan.planned_date.isoformat() if daily_plan.planned_date else None,
            'total_calories': daily_plan.total_calories,
            'total_protein_g': daily_plan.total_protein_g,
            'total_carbs_g': daily_plan.total_carbs_g,
            'total_fat_g': daily_plan.total_fat_g,
            'is_published': daily_plan.is_published,
            'notes': daily_plan.notes,
            'created_at': daily_plan.created_at.isoformat() if daily_plan.created_at else None,
            'updated_at': daily_plan.updated_at.isoformat() if daily_plan.updated_at else None
        }

        if hasattr(daily_plan, 'meals'):
            data['meals'] = [
                NutritionSerializer._serialize_meal(meal)
                for meal in daily_plan.meals
            ]

        return data

    @staticmethod
    def _serialize_meal(meal: Meal) -> Dict:
        """Serialize a meal to dict."""
        data = {
            'id': meal.id,
            'daily_plan_id': meal.daily_plan_id,
            'name': meal.name,
            'meal_type': meal.meal_type.value if meal.meal_type else None,
            'description': meal.description,
            'calories': float(meal.calories) if meal.calories else None,
            'protein_g': float(meal.protein_g) if meal.protein_g else None,  # Fixed: was 'protein'
            'carbs_g': float(meal.carbs_g) if meal.carbs_g else None,  # Fixed: was 'carbs'
            'fat_g': float(meal.fat_g) if meal.fat_g else None,  # Fixed: was 'fat'
            'fiber_g': float(meal.fiber_g) if meal.fiber_g else None,  # Fixed: was 'fiber'
            'order_in_day': meal.order_in_day,  # Fixed: was 'order'
            'cooking_instructions': meal.cooking_instructions,  # Fixed: was 'instructions'
            'preparation_time_minutes': meal.preparation_time_minutes,  # Fixed: was 'prep_time_minutes'
            'image_url': meal.image_url,
            'video_url': meal.video_url,
            'created_at': meal.created_at.isoformat() if meal.created_at else None,
            'updated_at': meal.updated_at.isoformat() if meal.updated_at else None
        }

        if hasattr(meal, 'ingredients'):
            data['ingredients'] = [
                NutritionSerializer._serialize_ingredient(ing)
                for ing in meal.ingredients
            ]

        return data

    @staticmethod
    def _serialize_ingredient(ingredient: MealIngredient) -> Dict:
        """Serialize a meal ingredient to dict."""
        return {
            'id': ingredient.id,
            'meal_id': ingredient.meal_id,
            'name': ingredient.name,
            'quantity': float(ingredient.quantity) if ingredient.quantity else None,  # Fixed: was 'amount'
            'unit': ingredient.unit,
            'alternatives': ingredient.alternatives,
            'is_optional': ingredient.is_optional,
            'calories_per_serving': float(ingredient.calories_per_serving) if ingredient.calories_per_serving else None,  # Fixed: was 'calories'
            'protein_per_serving': float(ingredient.protein_per_serving) if ingredient.protein_per_serving else None,  # Fixed: was 'protein'
            'carbs_per_serving': float(ingredient.carbs_per_serving) if ingredient.carbs_per_serving else None,  # Fixed: was 'carbs'
            'fat_per_serving': float(ingredient.fat_per_serving) if ingredient.fat_per_serving else None  # Fixed: was 'fat'
        }

    @staticmethod
    def serialize_follower(follower: NutritionPlanFollower) -> str:
        """Serialize a nutrition plan follower to JSON string."""
        data = {
            'id': follower.id,
            'user_id': follower.user_id,
            'plan_id': follower.plan_id,
            'gym_id': follower.gym_id,
            'start_date': follower.start_date.isoformat() if follower.start_date else None,
            'is_active': follower.is_active,
            'created_at': follower.created_at.isoformat() if follower.created_at else None,
            'updated_at': follower.updated_at.isoformat() if follower.updated_at else None
        }
        return json.dumps(data, cls=NutritionEncoder)

    @staticmethod
    def serialize_daily_progress(progress: UserDailyProgress) -> str:
        """Serialize user daily progress to JSON string."""
        data = {
            'id': progress.id,
            'user_id': progress.user_id,
            'gym_id': progress.gym_id,
            'date': progress.date.isoformat() if progress.date else None,
            'calories_consumed': float(progress.calories_consumed) if progress.calories_consumed else 0,
            'protein_consumed': float(progress.protein_consumed) if progress.protein_consumed else 0,
            'carbs_consumed': float(progress.carbs_consumed) if progress.carbs_consumed else 0,
            'fat_consumed': float(progress.fat_consumed) if progress.fat_consumed else 0,
            'fiber_consumed': float(progress.fiber_consumed) if progress.fiber_consumed else 0,
            'meals_completed': progress.meals_completed or 0,
            'notes': progress.notes,
            'created_at': progress.created_at.isoformat() if progress.created_at else None,
            'updated_at': progress.updated_at.isoformat() if progress.updated_at else None
        }
        return json.dumps(data, cls=NutritionEncoder)

    @staticmethod
    def serialize_today_meals(today_data: Dict) -> str:
        """Serialize today's meal plan data to JSON string."""
        # Today's data is already a dict, just ensure proper formatting
        return json.dumps(today_data, cls=NutritionEncoder)

    @staticmethod
    def deserialize_plan(data: Union[str, Dict]) -> Dict:
        """
        Deserialize JSON string or dict to plan data.

        Note: This returns a dict, not a SQLAlchemy object.
        The service layer should handle object reconstruction if needed.
        """
        if isinstance(data, str):
            return json.loads(data)
        return data

    @staticmethod
    def deserialize_follower(data: Union[str, Dict]) -> Dict:
        """Deserialize JSON string or dict to follower data."""
        if isinstance(data, str):
            return json.loads(data)
        return data

    @staticmethod
    def deserialize_daily_progress(data: Union[str, Dict]) -> Dict:
        """Deserialize JSON string or dict to daily progress data."""
        if isinstance(data, str):
            return json.loads(data)
        return data

    @staticmethod
    def deserialize_today_meals(data: Union[str, Dict]) -> Dict:
        """Deserialize JSON string or dict to today's meals data."""
        if isinstance(data, str):
            return json.loads(data)
        return data

    @staticmethod
    def serialize_dashboard(dashboard) -> str:
        """
        Serialize NutritionDashboardHybrid to JSON string.

        Args:
            dashboard: NutritionDashboardHybrid object

        Returns:
            JSON string representation
        """
        try:
            data = {
                'template_plans': [
                    NutritionSerializer._serialize_plan_summary(plan)
                    for plan in dashboard.template_plans
                ],
                'live_plans': [
                    NutritionSerializer._serialize_plan_summary(plan)
                    for plan in dashboard.live_plans
                ],
                'available_plans': [
                    NutritionSerializer._serialize_plan_summary(plan)
                    for plan in dashboard.available_plans
                ],
                'today_plan': dashboard.today_plan.dict() if dashboard.today_plan else None,
                'completion_streak': dashboard.completion_streak,
                'weekly_progress': dashboard.weekly_progress
            }
            return json.dumps(data, cls=NutritionEncoder)
        except Exception as e:
            logger.error(f"Error serializing dashboard: {e}")
            raise

    @staticmethod
    def _serialize_plan_summary(plan) -> Dict:
        """Serialize a plan summary (no deep relations)."""
        return {
            'id': plan.id,
            'gym_id': plan.gym_id,
            'creator_id': plan.creator_id,
            'name': getattr(plan, 'name', None),
            'title': getattr(plan, 'title', None),
            'description': plan.description,
            'goal': plan.goal.value if hasattr(plan, 'goal') and plan.goal else None,
            'plan_type': plan.plan_type.value if hasattr(plan, 'plan_type') and plan.plan_type else None,
            'duration_days': plan.duration_days,
            'is_public': plan.is_public,
            'is_live_active': getattr(plan, 'is_live_active', None),
            'live_start_date': plan.live_start_date.isoformat() if getattr(plan, 'live_start_date', None) else None,
            'current_day': getattr(plan, 'current_day', None),
            'status': getattr(plan, 'status', None),
            'days_until_start': getattr(plan, 'days_until_start', None),
            'created_at': plan.created_at.isoformat() if plan.created_at else None
        }

    @staticmethod
    def deserialize_dashboard(data: Union[str, Dict]):
        """
        Deserialize JSON string or dict to dashboard data.

        Returns a dictionary that can be used to construct NutritionDashboardHybrid
        """
        if isinstance(data, str):
            data = json.loads(data)

        # Import here to avoid circular dependency
        from app.schemas.nutrition import NutritionDashboardHybrid, TodayMealPlan

        # Reconstruct TodayMealPlan if exists
        today_plan = None
        if data.get('today_plan'):
            today_plan = TodayMealPlan(**data['today_plan'])

        # Return dashboard object
        return NutritionDashboardHybrid(
            template_plans=data.get('template_plans', []),
            live_plans=data.get('live_plans', []),
            available_plans=data.get('available_plans', []),
            today_plan=today_plan,
            completion_streak=data.get('completion_streak', 0),
            weekly_progress=data.get('weekly_progress', [])
        )

    @staticmethod
    def serialize_analytics(analytics) -> str:
        """
        Serialize NutritionAnalytics to JSON string.

        Args:
            analytics: NutritionAnalytics object

        Returns:
            JSON string representation
        """
        try:
            # Convert to dict using pydantic's dict method
            data = analytics.dict() if hasattr(analytics, 'dict') else analytics
            return json.dumps(data, cls=NutritionEncoder)
        except Exception as e:
            logger.error(f"Error serializing analytics: {e}")
            raise

    @staticmethod
    def deserialize_analytics(data: Union[str, Dict]):
        """
        Deserialize JSON string or dict to analytics data.

        Returns a NutritionAnalytics object
        """
        if isinstance(data, str):
            data = json.loads(data)

        # Import here to avoid circular dependency
        from app.schemas.nutrition import NutritionAnalytics

        # Return analytics object
        return NutritionAnalytics(**data)