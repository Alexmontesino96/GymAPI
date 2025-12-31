"""
Service for tracking user progress and meal completions.
Handles daily tracking, meal completions, and progress analytics.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_, or_
from datetime import datetime, date, timedelta
import logging

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal,
    NutritionPlanFollower, UserMealCompletion, UserDailyProgress,
    PlanType, MealType
)
from app.models.user import User
from app.schemas.nutrition import (
    UserMealCompletionCreate,
    UserDailyProgressCreate,
    TodayMealPlan,
    WeeklyNutritionSummary,
    PlanStatus
)
from app.repositories.nutrition import nutrition_progress_repository
from app.db.redis_client import get_redis_client
import asyncio

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class AlreadyCompletedError(Exception):
    """Raised when trying to complete an already completed meal."""
    pass


class NutritionProgressService:
    """Service for tracking nutrition progress and meal completions."""

    def __init__(self, db: Session):
        """
        Initialize the nutrition progress service.

        Args:
            db: Database session
        """
        self.db = db
        self.repository = nutrition_progress_repository

    async def get_today_meal_plan_cached(
        self,
        user_id: int,
        gym_id: int
    ) -> Optional[TodayMealPlan]:
        """
        Get today's meal plan for a user with caching support.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym

        Returns:
            Today's meal plan or None if no active plans

        Raises:
            NotFoundError: If user not found
        """
        # Use repository's cached method
        today_data = await self.repository.get_today_meals_cached(
            self.db,
            user_id,
            gym_id
        )

        if not today_data:
            return None

        # Convert to schema
        today_plan = TodayMealPlan(
            date=today_data['date'],
            plans=today_data['plans'],
            total_calories_target=sum(p.get('total_calories', 0) for p in today_data['plans']),
            total_calories_consumed=sum(p.get('completed_calories', 0) for p in today_data['plans']),
            overall_completion=sum(p.get('completion_percentage', 0) for p in today_data['plans']) / len(today_data['plans']) if today_data['plans'] else 0
        )

        return today_plan

    async def complete_meal(
        self,
        meal_id: int,
        user_id: int,
        gym_id: int
    ) -> UserMealCompletion:
        """
        Mark a meal as completed.

        Args:
            meal_id: ID of the meal to complete
            user_id: ID of the user completing the meal
            gym_id: ID of the gym

        Returns:
            Created completion record

        Raises:
            NotFoundError: If meal not found or user not following the plan
            AlreadyCompletedError: If meal already completed today
        """
        # Use repository method
        completion = self.repository.complete_meal(
            self.db,
            user_id,
            meal_id,
            gym_id
        )

        if not completion:
            raise NotFoundError(
                f"Meal {meal_id} not found or user {user_id} is not following the plan"
            )

        logger.info(f"User {user_id} completed meal {meal_id}")

        # Invalidate cache using repository method
        await self.repository.invalidate_progress_cache(user_id, gym_id)

        return completion

    async def uncomplete_meal(
        self,
        meal_id: int,
        user_id: int,
        gym_id: int
    ) -> bool:
        """
        Remove a meal completion for today.

        Args:
            meal_id: ID of the meal to uncomplete
            user_id: ID of the user
            gym_id: ID of the gym

        Returns:
            True if uncompleted successfully

        Raises:
            NotFoundError: If completion not found
        """
        today = date.today()

        # Find today's completion
        completion = self.db.query(UserMealCompletion).filter(
            UserMealCompletion.user_id == user_id,
            UserMealCompletion.meal_id == meal_id,
            func.date(UserMealCompletion.completed_at) == today,
            UserMealCompletion.gym_id == gym_id
        ).first()

        if not completion:
            raise NotFoundError(f"Completion not found for meal {meal_id} today")

        # Get meal details for updating daily progress
        meal = self.db.query(Meal).filter(Meal.id == meal_id).first()

        # Delete completion
        self.db.delete(completion)

        # Update daily progress (subtract the meal's nutrition)
        if meal:
            self._update_daily_progress_subtract(user_id, gym_id, meal)

        self.db.commit()

        logger.info(f"User {user_id} uncompleted meal {meal_id}")

        # Invalidate cache using repository method
        await self.repository.invalidate_progress_cache(user_id, gym_id)

        return True

    def get_weekly_summary(
        self,
        user_id: int,
        gym_id: int,
        week_offset: int = 0
    ) -> WeeklyNutritionSummary:
        """
        Get weekly nutrition summary for a user.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym
            week_offset: Number of weeks to offset (0 = current week, -1 = last week)

        Returns:
            Weekly nutrition summary
        """
        today = date.today()
        # Calculate week boundaries
        week_start = today - timedelta(days=today.weekday() + (week_offset * 7))
        week_end = week_start + timedelta(days=6)

        # Get daily progress for the week
        daily_progress = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.gym_id == gym_id,
            UserDailyProgress.date >= week_start,
            UserDailyProgress.date <= week_end
        ).order_by(UserDailyProgress.date).all()

        # Get user's active plans for targets
        active_plans = self.db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan)
        ).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).all()

        # Calculate average targets from active plans
        total_target_calories = sum(f.plan.target_calories or 0 for f in active_plans)
        total_target_protein = sum(f.plan.target_protein or 0 for f in active_plans)
        total_target_carbs = sum(f.plan.target_carbs or 0 for f in active_plans)
        total_target_fat = sum(f.plan.target_fat or 0 for f in active_plans)

        avg_target_calories = total_target_calories / len(active_plans) if active_plans else 0
        avg_target_protein = total_target_protein / len(active_plans) if active_plans else 0
        avg_target_carbs = total_target_carbs / len(active_plans) if active_plans else 0
        avg_target_fat = total_target_fat / len(active_plans) if active_plans else 0

        # Build daily summaries
        daily_summaries = []
        total_consumed = {
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0,
            'fiber': 0
        }

        for day_num in range(7):
            current_date = week_start + timedelta(days=day_num)
            progress = next(
                (p for p in daily_progress if p.date == current_date),
                None
            )

            if progress:
                daily_summary = {
                    'date': current_date,
                    'calories': progress.calories_consumed or 0,
                    'protein': progress.protein_consumed or 0,
                    'carbs': progress.carbs_consumed or 0,
                    'fat': progress.fat_consumed or 0,
                    'fiber': progress.fiber_consumed or 0,
                    'meals_completed': progress.meals_completed or 0,
                    'adherence_percentage': (
                        (progress.calories_consumed / avg_target_calories * 100)
                        if avg_target_calories > 0 else 0
                    )
                }

                # Add to totals
                for key in total_consumed:
                    total_consumed[key] += daily_summary.get(key, 0)
            else:
                daily_summary = {
                    'date': current_date,
                    'calories': 0,
                    'protein': 0,
                    'carbs': 0,
                    'fat': 0,
                    'fiber': 0,
                    'meals_completed': 0,
                    'adherence_percentage': 0
                }

            daily_summaries.append(daily_summary)

        # Calculate weekly averages
        days_with_data = len([d for d in daily_summaries if d['meals_completed'] > 0])

        return WeeklyNutritionSummary(
            week_start=week_start,
            week_end=week_end,
            daily_summaries=daily_summaries,
            weekly_totals=total_consumed,
            weekly_averages={
                'calories': total_consumed['calories'] / 7,
                'protein': total_consumed['protein'] / 7,
                'carbs': total_consumed['carbs'] / 7,
                'fat': total_consumed['fat'] / 7,
                'fiber': total_consumed['fiber'] / 7
            },
            target_averages={
                'calories': avg_target_calories,
                'protein': avg_target_protein,
                'carbs': avg_target_carbs,
                'fat': avg_target_fat
            },
            days_tracked=days_with_data,
            overall_adherence_percentage=(
                sum(d['adherence_percentage'] for d in daily_summaries) / 7
            )
        )

    def get_user_progress_history(
        self,
        user_id: int,
        gym_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> List[UserDailyProgress]:
        """
        Get user's daily progress history.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of daily progress records
        """
        query = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.gym_id == gym_id
        )

        if start_date:
            query = query.filter(UserDailyProgress.date >= start_date)

        if end_date:
            query = query.filter(UserDailyProgress.date <= end_date)

        return query.order_by(UserDailyProgress.date.desc()).all()

    def get_meal_completion_streak(
        self,
        user_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Calculate user's meal completion streak.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym

        Returns:
            Dictionary with streak information
        """
        today = date.today()

        # Get all daily progress records ordered by date
        progress_records = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.gym_id == gym_id,
            UserDailyProgress.meals_completed > 0
        ).order_by(UserDailyProgress.date.desc()).all()

        if not progress_records:
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'total_days_tracked': 0,
                'last_active_date': None
            }

        # Calculate current streak
        current_streak = 0
        check_date = today

        for record in progress_records:
            if record.date == check_date:
                current_streak += 1
                check_date = check_date - timedelta(days=1)
            else:
                break

        # Calculate longest streak
        longest_streak = 0
        temp_streak = 0
        last_date = None

        for record in reversed(progress_records):
            if last_date is None:
                temp_streak = 1
                last_date = record.date
            elif record.date == last_date + timedelta(days=1):
                temp_streak += 1
                last_date = record.date
            else:
                longest_streak = max(longest_streak, temp_streak)
                temp_streak = 1
                last_date = record.date

        longest_streak = max(longest_streak, temp_streak)

        return {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'total_days_tracked': len(progress_records),
            'last_active_date': progress_records[0].date if progress_records else None
        }

    def _update_daily_progress_subtract(
        self,
        user_id: int,
        gym_id: int,
        meal: Meal
    ) -> None:
        """
        Subtract meal nutrition from daily progress when uncompleting.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym
            meal: Meal that was uncompleted
        """
        today = date.today()

        progress = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.date == today,
            UserDailyProgress.gym_id == gym_id
        ).first()

        if progress:
            # Subtract meal nutrition
            progress.calories_consumed = max(0, (progress.calories_consumed or 0) - (meal.calories or 0))
            progress.protein_consumed = max(0, (progress.protein_consumed or 0) - (meal.protein or 0))
            progress.carbs_consumed = max(0, (progress.carbs_consumed or 0) - (meal.carbs or 0))
            progress.fat_consumed = max(0, (progress.fat_consumed or 0) - (meal.fat or 0))
            progress.fiber_consumed = max(0, (progress.fiber_consumed or 0) - (meal.fiber or 0))
            progress.meals_completed = max(0, (progress.meals_completed or 0) - 1)
            progress.updated_at = datetime.utcnow()