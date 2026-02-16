"""
Service for nutrition analytics and reporting.
Provides insights, metrics, and aggregated data for nutrition plans.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func, and_, or_, desc
from datetime import datetime, date, timedelta
import logging

from app.models.nutrition import (
    NutritionPlan, NutritionPlanFollower,
    UserDailyProgress, UserMealCompletion,
    PlanType, NutritionGoal,
    Meal, DailyNutritionPlan
)
from app.models.user import User
from app.schemas.nutrition import (
    NutritionAnalytics,
    UserNutritionDashboard
)
from app.db.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class NutritionAnalyticsService:
    """Service for nutrition analytics and reporting."""

    def __init__(self, db: Session, redis_client: Optional[Any] = None):
        """
        Initialize the nutrition analytics service.

        Args:
            db: Database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.redis_client = redis_client

    def get_plan_analytics(
        self,
        plan_id: int,
        gym_id: int
    ) -> NutritionAnalytics:
        """
        Get comprehensive analytics for a nutrition plan.

        Args:
            plan_id: ID of the nutrition plan
            gym_id: ID of the gym

        Returns:
            Nutrition analytics data

        Raises:
            NotFoundError: If plan not found
        """
        # Get plan with followers
        plan = self.db.query(NutritionPlan).options(
            joinedload(NutritionPlan.followers)
        ).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not plan:
            raise NotFoundError(f"Plan {plan_id} not found")

        # Calculate follower metrics
        total_followers = len(plan.followers)
        active_followers = len([f for f in plan.followers if f.is_active])
        inactive_followers = total_followers - active_followers

        # Calculate adherence rates
        adherence_rates = self._calculate_adherence_rates(plan_id, gym_id)

        # Get completion statistics
        completion_stats = self._get_completion_statistics(plan_id, gym_id)

        # Get trending times
        peak_times = self._get_peak_completion_times(plan_id, gym_id)

        # Get demographic breakdown
        demographics = self._get_follower_demographics(plan_id, gym_id)

        # Build analytics response
        analytics = NutritionAnalytics(
            plan_id=plan_id,
            plan_name=plan.name,
            plan_type=plan.plan_type.value,
            total_followers=total_followers,
            active_followers=active_followers,
            inactive_followers=inactive_followers,
            average_adherence_percentage=adherence_rates['average'],
            weekly_adherence_trend=adherence_rates['weekly_trend'],
            completion_by_meal_type=completion_stats['by_meal_type'],
            completion_by_day_of_week=completion_stats['by_day_of_week'],
            peak_completion_times=peak_times,
            follower_demographics=demographics,
            retention_rate=self._calculate_retention_rate(plan_id, gym_id),
            satisfaction_score=self._calculate_satisfaction_score(plan_id, gym_id)
        )

        return analytics

    def get_user_nutrition_dashboard(
        self,
        user_id: int,
        gym_id: int
    ) -> UserNutritionDashboard:
        """
        Get comprehensive nutrition dashboard for a user.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym

        Returns:
            User nutrition dashboard data
        """
        # Get user's active followed plans
        # Note: gym_id is in NutritionPlan, not in NutritionPlanFollower
        # We need to join with NutritionPlan to filter by gym_id
        followed_plans = self.db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan)
        ).join(
            NutritionPlan, NutritionPlanFollower.plan_id == NutritionPlan.id
        ).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).all()

        # Get recent progress
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        weekly_progress = self._get_user_progress_summary(
            user_id, gym_id, week_ago, today
        )

        monthly_progress = self._get_user_progress_summary(
            user_id, gym_id, month_ago, today
        )

        # Get streaks
        streak_data = self._calculate_user_streaks(user_id, gym_id)

        # Get favorite meals
        favorite_meals = self._get_user_favorite_meals(user_id, gym_id)

        # Build dashboard
        dashboard = UserNutritionDashboard(
            user_id=user_id,
            active_plans=[{
                'plan_id': f.plan_id,
                'plan_name': f.plan.title,
                'start_date': f.start_date,
                'current_day': self._calculate_current_day(f),
                'adherence_percentage': self._calculate_user_plan_adherence(f)
            } for f in followed_plans],
            weekly_summary=weekly_progress,
            monthly_summary=monthly_progress,
            current_streak=streak_data['current'],
            longest_streak=streak_data['longest'],
            total_meals_completed=self._get_total_meals_completed(user_id, gym_id),
            favorite_meals=favorite_meals,
            nutritional_goals_progress=self._calculate_goals_progress(user_id, gym_id, followed_plans)
        )

        return dashboard

    def get_gym_nutrition_overview(
        self,
        gym_id: int,
        date_range: Optional[tuple[date, date]] = None
    ) -> Dict[str, Any]:
        """
        Get gym-wide nutrition statistics.

        Args:
            gym_id: ID of the gym
            date_range: Optional date range filter

        Returns:
            Gym-wide nutrition overview
        """
        if not date_range:
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            date_range = (start_date, end_date)

        # Get all plans for the gym
        plans = self.db.query(NutritionPlan).filter(
            NutritionPlan.gym_id == gym_id
        ).all()

        # Get active followers count
        # Note: gym_id is in NutritionPlan, need to join
        active_followers = self.db.query(NutritionPlanFollower).join(
            NutritionPlan, NutritionPlanFollower.plan_id == NutritionPlan.id
        ).filter(
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).count()

        # Get meal completions in date range
        # Note: UserMealCompletion doesn't have gym_id, need to join through Meal → DailyNutritionPlan → NutritionPlan
        completions = self.db.query(
            func.count(UserMealCompletion.id).label('total'),
            func.date(UserMealCompletion.completed_at).label('date')
        ).join(
            Meal, UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan, Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan, DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            NutritionPlan.gym_id == gym_id,
            func.date(UserMealCompletion.completed_at) >= date_range[0],
            func.date(UserMealCompletion.completed_at) <= date_range[1]
        ).group_by(
            func.date(UserMealCompletion.completed_at)
        ).all()

        # Calculate daily average
        daily_avg = sum(c.total for c in completions) / len(completions) if completions else 0

        # Get plan distribution by goal
        goal_distribution = self.db.query(
            NutritionPlan.goal,
            func.count(NutritionPlan.id).label('count')
        ).filter(
            NutritionPlan.gym_id == gym_id
        ).group_by(
            NutritionPlan.goal
        ).all()

        # Get top performing plans
        top_plans = self._get_top_performing_plans(gym_id, limit=5)

        return {
            'gym_id': gym_id,
            'date_range': {
                'start': date_range[0],
                'end': date_range[1]
            },
            'total_plans': len(plans),
            'active_followers': active_followers,
            'daily_average_completions': round(daily_avg, 1),
            'plan_distribution_by_goal': [
                {'goal': goal.value if goal else 'None', 'count': count}
                for goal, count in goal_distribution
            ],
            'top_performing_plans': top_plans,
            'engagement_trend': [
                {'date': c.date, 'completions': c.total}
                for c in completions
            ]
        }

    def _calculate_adherence_rates(
        self,
        plan_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """Calculate adherence rates for a plan."""
        today = date.today()
        adherence_data = []

        # Get all active followers
        # Note: gym_id verification through join with NutritionPlan
        followers = self.db.query(NutritionPlanFollower).join(
            NutritionPlan, NutritionPlanFollower.plan_id == NutritionPlan.id
        ).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).all()

        for follower in followers:
            days_following = (today - follower.start_date.date()).days + 1
            # Note: UserDailyProgress doesn't have gym_id
            days_with_progress = self.db.query(UserDailyProgress).filter(
                UserDailyProgress.user_id == follower.user_id,
                UserDailyProgress.date >= follower.start_date.date(),
                UserDailyProgress.meals_completed > 0
            ).count()

            if days_following > 0:
                adherence = (days_with_progress / days_following * 100)
                adherence_data.append(adherence)

        # Calculate weekly trend
        weekly_trend = []
        for week_offset in range(4):  # Last 4 weeks
            week_start = today - timedelta(days=today.weekday() + (week_offset * 7))
            week_end = week_start + timedelta(days=6)

            week_adherence = []
            for follower in followers:
                if follower.start_date.date() > week_end:
                    continue

                days_in_week = 7
                # Note: UserDailyProgress doesn't have gym_id
                progress_days = self.db.query(UserDailyProgress).filter(
                    UserDailyProgress.user_id == follower.user_id,
                    UserDailyProgress.date >= week_start,
                    UserDailyProgress.date <= week_end,
                    UserDailyProgress.meals_completed > 0
                ).count()

                week_adherence.append((progress_days / days_in_week * 100))

            if week_adherence:
                weekly_trend.append({
                    'week_start': week_start,
                    'average_adherence': sum(week_adherence) / len(week_adherence)
                })

        return {
            'average': sum(adherence_data) / len(adherence_data) if adherence_data else 0,
            'weekly_trend': weekly_trend
        }

    def _get_completion_statistics(
        self,
        plan_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """Get meal completion statistics for a plan."""
        # Get completions by meal type
        # Note: UserMealCompletion doesn't have gym_id, join through NutritionPlan
        by_meal_type = self.db.query(
            Meal.meal_type,
            func.count(UserMealCompletion.id).label('count')
        ).join(
            UserMealCompletion,
            UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan,
            Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan,
            DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            DailyNutritionPlan.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).group_by(
            Meal.meal_type
        ).all()

        # Get completions by day of week
        by_day_of_week = self.db.query(
            func.extract('dow', UserMealCompletion.completed_at).label('day_of_week'),
            func.count(UserMealCompletion.id).label('count')
        ).join(
            Meal,
            UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan,
            Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan,
            DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            DailyNutritionPlan.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).group_by(
            func.extract('dow', UserMealCompletion.completed_at)
        ).all()

        return {
            'by_meal_type': [
                {'meal_type': mt.value if mt else 'Unknown', 'completions': count}
                for mt, count in by_meal_type
            ],
            'by_day_of_week': [
                {'day': int(day), 'completions': count}
                for day, count in by_day_of_week
            ]
        }

    def _get_peak_completion_times(
        self,
        plan_id: int,
        gym_id: int
    ) -> List[Dict[str, Any]]:
        """Get peak times for meal completions."""
        # Note: UserMealCompletion doesn't have gym_id, join through NutritionPlan
        peak_times = self.db.query(
            func.extract('hour', UserMealCompletion.completed_at).label('hour'),
            func.count(UserMealCompletion.id).label('count')
        ).join(
            Meal,
            UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan,
            Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan,
            DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            DailyNutritionPlan.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).group_by(
            func.extract('hour', UserMealCompletion.completed_at)
        ).order_by(
            desc('count')
        ).limit(5).all()

        return [
            {'hour': int(hour), 'completions': count}
            for hour, count in peak_times
        ]

    def _get_follower_demographics(
        self,
        plan_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """Get demographic breakdown of plan followers."""
        followers = self.db.query(User).join(
            NutritionPlanFollower,
            User.id == NutritionPlanFollower.user_id
        ).join(
            NutritionPlan,
            NutritionPlanFollower.plan_id == NutritionPlan.id
        ).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).all()

        # Analyze demographics
        # Note: This would need actual demographic fields in User model
        return {
            'total_users': len(followers),
            'by_role': self._group_users_by_role(followers),
            # Add more demographic breakdowns as needed
        }

    def _group_users_by_role(self, users: List[User]) -> List[Dict[str, Any]]:
        """Group users by role."""
        role_counts = {}
        for user in users:
            role = user.role.value if user.role else 'Unknown'
            role_counts[role] = role_counts.get(role, 0) + 1

        return [
            {'role': role, 'count': count}
            for role, count in role_counts.items()
        ]

    def _calculate_retention_rate(
        self,
        plan_id: int,
        gym_id: int
    ) -> float:
        """Calculate follower retention rate for a plan."""
        all_followers = self.db.query(NutritionPlanFollower).join(
            NutritionPlan, NutritionPlanFollower.plan_id == NutritionPlan.id
        ).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).count()

        active_followers = self.db.query(NutritionPlanFollower).join(
            NutritionPlan, NutritionPlanFollower.plan_id == NutritionPlan.id
        ).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).count()

        if all_followers == 0:
            return 0.0

        return (active_followers / all_followers * 100)

    def _calculate_satisfaction_score(
        self,
        plan_id: int,
        gym_id: int
    ) -> Optional[float]:
        """Calculate satisfaction score based on completion patterns."""
        # This would need actual satisfaction data (surveys, ratings, etc.)
        # For now, use adherence as a proxy
        adherence = self._calculate_adherence_rates(plan_id, gym_id)
        return adherence['average']

    def _get_user_progress_summary(
        self,
        user_id: int,
        gym_id: int,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """Get user's progress summary for a date range."""
        # Get nutritional data from UserMealCompletion and Meal tables
        # Since UserDailyProgress doesn't have nutritional fields
        nutrition_data = self.db.query(
            func.sum(Meal.calories).label('total_calories'),
            func.sum(Meal.protein_g).label('total_protein'),
            func.sum(Meal.carbs_g).label('total_carbs'),
            func.sum(Meal.fat_g).label('total_fat'),
            func.count(UserMealCompletion.id).label('total_meals')
        ).join(
            Meal, UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan, Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan, DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            UserMealCompletion.user_id == user_id,
            NutritionPlan.gym_id == gym_id,
            UserMealCompletion.completed_at >= start_date,
            UserMealCompletion.completed_at <= end_date
        ).first()

        # Get days tracked from UserDailyProgress
        days_tracked = self.db.query(
            func.count(UserDailyProgress.id)
        ).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.date >= start_date,
            UserDailyProgress.date <= end_date
        ).scalar() or 0

        total_calories = nutrition_data.total_calories if nutrition_data else 0
        total_protein = nutrition_data.total_protein if nutrition_data else 0
        total_carbs = nutrition_data.total_carbs if nutrition_data else 0
        total_fat = nutrition_data.total_fat if nutrition_data else 0
        total_meals = nutrition_data.total_meals if nutrition_data else 0

        return {
            'total_calories': total_calories or 0,
            'total_protein': total_protein or 0,
            'total_carbs': total_carbs or 0,
            'total_fat': total_fat or 0,
            'total_meals': total_meals or 0,
            'days_tracked': days_tracked,
            'daily_average_calories': (
                (total_calories / days_tracked) if days_tracked and total_calories else 0
            )
        }

    def _calculate_user_streaks(
        self,
        user_id: int,
        gym_id: int
    ) -> Dict[str, int]:
        """Calculate user's completion streaks."""
        # Implementation similar to ProgressService
        today = date.today()
        # Note: UserDailyProgress doesn't have gym_id, filter by user_id only
        progress_records = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.meals_completed > 0
        ).order_by(UserDailyProgress.date.desc()).all()

        if not progress_records:
            return {'current': 0, 'longest': 0}

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
        longest_streak = current_streak
        # Simplified - would need full implementation

        return {
            'current': current_streak,
            'longest': longest_streak
        }

    def _get_user_favorite_meals(
        self,
        user_id: int,
        gym_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get user's most frequently completed meals."""
        # Note: UserMealCompletion doesn't have gym_id, join through NutritionPlan
        favorites = self.db.query(
            Meal.id,
            Meal.name,
            func.count(UserMealCompletion.id).label('completion_count')
        ).join(
            UserMealCompletion,
            UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan,
            Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan,
            DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            UserMealCompletion.user_id == user_id,
            NutritionPlan.gym_id == gym_id
        ).group_by(
            Meal.id,
            Meal.name
        ).order_by(
            desc('completion_count')
        ).limit(limit).all()

        return [
            {
                'meal_id': meal_id,
                'meal_name': name,
                'completion_count': count
            }
            for meal_id, name, count in favorites
        ]

    def _get_total_meals_completed(
        self,
        user_id: int,
        gym_id: int
    ) -> int:
        """Get total meals completed by user."""
        # Note: UserMealCompletion doesn't have gym_id, join through NutritionPlan
        return self.db.query(UserMealCompletion).join(
            Meal, UserMealCompletion.meal_id == Meal.id
        ).join(
            DailyNutritionPlan, Meal.daily_plan_id == DailyNutritionPlan.id
        ).join(
            NutritionPlan, DailyNutritionPlan.nutrition_plan_id == NutritionPlan.id
        ).filter(
            UserMealCompletion.user_id == user_id,
            NutritionPlan.gym_id == gym_id
        ).count()

    def _calculate_current_day(self, follower: NutritionPlanFollower) -> int:
        """Calculate current day for a follower."""
        today = date.today()
        days_since_start = (today - follower.start_date.date()).days
        if follower.plan.is_recurring:
            return (days_since_start % follower.plan.duration_days) + 1
        else:
            return min(days_since_start + 1, follower.plan.duration_days)

    def _calculate_user_plan_adherence(self, follower: NutritionPlanFollower) -> float:
        """Calculate adherence for a specific user-plan combination."""
        today = date.today()
        days_following = (today - follower.start_date.date()).days + 1
        # Note: UserDailyProgress doesn't have gym_id field
        days_with_progress = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == follower.user_id,
            UserDailyProgress.date >= follower.start_date.date(),
            UserDailyProgress.meals_completed > 0
        ).count()

        if days_following == 0:
            return 0.0

        return (days_with_progress / days_following * 100)

    def _calculate_goals_progress(
        self,
        user_id: int,
        gym_id: int,
        followed_plans: List[NutritionPlanFollower]
    ) -> Dict[str, Any]:
        """Calculate progress towards nutritional goals."""
        if not followed_plans:
            return {}

        # Get average targets from followed plans
        avg_calories = sum(f.plan.target_calories or 0 for f in followed_plans) / len(followed_plans)
        avg_protein = sum(f.plan.target_protein_g or 0 for f in followed_plans) / len(followed_plans)

        # Get last 7 days average
        week_ago = date.today() - timedelta(days=7)
        recent_avg = self._get_user_progress_summary(
            user_id, gym_id, week_ago, date.today()
        )

        return {
            'calories_percentage': (
                (recent_avg['daily_average_calories'] / avg_calories * 100)
                if avg_calories > 0 else 0
            ),
            'protein_percentage': (
                ((recent_avg['total_protein'] / 7) / avg_protein * 100)
                if avg_protein > 0 else 0
            )
        }

    def _get_top_performing_plans(
        self,
        gym_id: int,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top performing plans by follower count and adherence."""
        plans = self.db.query(
            NutritionPlan.id,
            NutritionPlan.name,
            func.count(NutritionPlanFollower.id).label('follower_count')
        ).join(
            NutritionPlanFollower,
            NutritionPlan.id == NutritionPlanFollower.plan_id
        ).filter(
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).group_by(
            NutritionPlan.id,
            NutritionPlan.name
        ).order_by(
            desc('follower_count')
        ).limit(limit).all()

        return [
            {
                'plan_id': plan_id,
                'plan_name': name,
                'active_followers': count
            }
            for plan_id, name, count in plans
        ]