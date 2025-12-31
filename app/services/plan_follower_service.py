"""
Service for managing users following nutrition plans.
Handles the relationship between users and the plans they follow.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from datetime import datetime, date, timedelta
import logging

from app.models.nutrition import (
    NutritionPlan, NutritionPlanFollower, PlanType,
    UserDailyProgress
)
from app.models.user import User
from app.schemas.nutrition import (
    NutritionPlanFollowerCreate,
    PlanStatus
)
from app.repositories.nutrition import plan_follower_repository
from app.db.redis_client import get_redis_client
import asyncio

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class AlreadyExistsError(Exception):
    """Raised when trying to create a duplicate resource."""
    pass


class PlanFollowerService:
    """Service for managing plan followers (users following nutrition plans)."""

    def __init__(self, db: Session):
        """
        Initialize the plan follower service.

        Args:
            db: Database session
        """
        self.db = db
        self.repository = plan_follower_repository

    async def follow_nutrition_plan(
        self,
        plan_id: int,
        user_id: int,
        gym_id: int,
        start_date: Optional[datetime] = None
    ) -> NutritionPlanFollower:
        """
        Follow a nutrition plan.

        Args:
            plan_id: ID of the plan to follow
            user_id: ID of the user following the plan
            gym_id: ID of the gym
            start_date: Optional start date (defaults to now)

        Returns:
            Created or reactivated follower relationship

        Raises:
            NotFoundError: If plan not found
            ValidationError: If validation fails
        """
        # Use repository method which handles all logic
        follower = self.repository.follow_plan(
            self.db,
            user_id,
            plan_id,
            gym_id,
            start_date
        )

        if not follower:
            raise NotFoundError(f"Plan {plan_id} not found in gym {gym_id}")

        logger.info(f"User {user_id} started following plan {plan_id}")

        # Invalidate cache using repository method
        await self.repository.invalidate_follower_cache(user_id, plan_id, gym_id)

        return follower

    async def unfollow_nutrition_plan(
        self,
        plan_id: int,
        user_id: int,
        gym_id: int
    ) -> bool:
        """
        Unfollow a nutrition plan.

        Args:
            plan_id: ID of the plan to unfollow
            user_id: ID of the user unfollowing the plan
            gym_id: ID of the gym

        Returns:
            True if unfollowed successfully

        Raises:
            NotFoundError: If follower relationship not found
        """
        success = self.repository.unfollow_plan(
            self.db,
            user_id,
            plan_id,
            gym_id
        )

        if not success:
            raise NotFoundError(
                f"User {user_id} is not following plan {plan_id}"
            )

        logger.info(f"User {user_id} unfollowed plan {plan_id}")

        # Invalidate cache using repository method
        await self.repository.invalidate_follower_cache(user_id, plan_id, gym_id)

        return True

    def get_user_followed_plans(
        self,
        user_id: int,
        gym_id: int,
        include_archived: bool = False
    ) -> List[NutritionPlanFollower]:
        """
        Get all plans a user is following.

        Args:
            user_id: ID of the user
            gym_id: ID of the gym
            include_archived: Whether to include inactive follows

        Returns:
            List of followed plans with plan details
        """
        return self.repository.get_user_followed_plans(
            self.db,
            user_id,
            gym_id,
            include_archived
        )

    def get_plan_followers(
        self,
        plan_id: int,
        gym_id: int,
        active_only: bool = True
    ) -> List[NutritionPlanFollower]:
        """
        Get all users following a specific plan.

        Args:
            plan_id: ID of the nutrition plan
            gym_id: ID of the gym
            active_only: Whether to only include active followers

        Returns:
            List of followers with user details
        """
        return self.repository.get_plan_followers(
            self.db,
            plan_id,
            gym_id,
            active_only
        )

    def get_current_plan_day(
        self,
        plan: NutritionPlan,
        follower: NutritionPlanFollower
    ) -> tuple[int, PlanStatus]:
        """
        Calculate the current day number for a user following a plan.

        Args:
            plan: The nutrition plan
            follower: The follower relationship

        Returns:
            Tuple of (current_day_number, plan_status)
        """
        today = date.today()

        # For TEMPLATE plans
        if plan.plan_type == PlanType.TEMPLATE:
            if not follower:
                # Not following, show day 1 preview
                return 1, PlanStatus.NOT_STARTED

            days_since_start = (today - follower.start_date.date()).days

            # Check if plan has ended (non-recurring)
            if not plan.is_recurring and days_since_start >= plan.duration_days:
                return plan.duration_days, PlanStatus.COMPLETED

            # Calculate current day
            if plan.is_recurring:
                # Recurring plan: cycle through days
                current_day = (days_since_start % plan.duration_days) + 1
                return current_day, PlanStatus.RUNNING
            else:
                # Non-recurring: linear progression
                current_day = min(days_since_start + 1, plan.duration_days)
                return current_day, PlanStatus.RUNNING

        # For LIVE plans
        elif plan.plan_type == PlanType.LIVE:
            if not plan.live_start_date:
                return 1, PlanStatus.NOT_STARTED

            # Check if plan hasn't started yet
            if plan.live_start_date.date() > today:
                days_until = (plan.live_start_date.date() - today).days
                return 1, PlanStatus.NOT_STARTED

            # Calculate days since live start
            days_since_start = (today - plan.live_start_date.date()).days

            # Check if plan has ended
            if days_since_start >= plan.duration_days:
                return plan.duration_days, PlanStatus.COMPLETED

            current_day = days_since_start + 1
            return current_day, PlanStatus.RUNNING

        return 1, PlanStatus.NOT_STARTED

    def get_follower_progress(
        self,
        follower_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Get detailed progress for a follower.

        Args:
            follower_id: ID of the follower relationship
            gym_id: ID of the gym

        Returns:
            Dictionary with progress information
        """
        # Get follower with plan details
        follower = self.db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan),
            joinedload(NutritionPlanFollower.user)
        ).filter(
            NutritionPlanFollower.id == follower_id,
            NutritionPlanFollower.gym_id == gym_id
        ).first()

        if not follower:
            raise NotFoundError(f"Follower relationship {follower_id} not found")

        # Calculate current day and status
        current_day, status = self.get_current_plan_day(
            follower.plan,
            follower
        )

        # Get completion statistics
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        # Get this week's progress
        weekly_progress = self.db.query(
            func.sum(UserDailyProgress.calories_consumed).label('total_calories'),
            func.sum(UserDailyProgress.protein_consumed).label('total_protein'),
            func.sum(UserDailyProgress.carbs_consumed).label('total_carbs'),
            func.sum(UserDailyProgress.fat_consumed).label('total_fat'),
            func.sum(UserDailyProgress.meals_completed).label('total_meals')
        ).filter(
            UserDailyProgress.user_id == follower.user_id,
            UserDailyProgress.gym_id == gym_id,
            UserDailyProgress.date >= week_start,
            UserDailyProgress.date <= today
        ).first()

        # Calculate adherence percentage
        days_following = (today - follower.start_date.date()).days + 1
        days_with_progress = self.db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == follower.user_id,
            UserDailyProgress.gym_id == gym_id,
            UserDailyProgress.date >= follower.start_date.date()
        ).count()

        adherence_percentage = (
            (days_with_progress / days_following * 100) if days_following > 0 else 0
        )

        return {
            'follower_id': follower_id,
            'user_id': follower.user_id,
            'user_name': follower.user.name if follower.user else None,
            'plan_id': follower.plan_id,
            'plan_name': follower.plan.name,
            'start_date': follower.start_date,
            'current_day': current_day,
            'status': status.value,
            'is_active': follower.is_active,
            'weekly_totals': {
                'calories': weekly_progress.total_calories or 0 if weekly_progress else 0,
                'protein': weekly_progress.total_protein or 0 if weekly_progress else 0,
                'carbs': weekly_progress.total_carbs or 0 if weekly_progress else 0,
                'fat': weekly_progress.total_fat or 0 if weekly_progress else 0,
                'meals_completed': weekly_progress.total_meals or 0 if weekly_progress else 0
            },
            'adherence_percentage': round(adherence_percentage, 1),
            'days_following': days_following,
            'days_with_activity': days_with_progress
        }

    def update_follower_start_date(
        self,
        plan_id: int,
        user_id: int,
        gym_id: int,
        new_start_date: datetime
    ) -> NutritionPlanFollower:
        """
        Update the start date for a follower (restart plan).

        Args:
            plan_id: ID of the plan
            user_id: ID of the user
            gym_id: ID of the gym
            new_start_date: New start date

        Returns:
            Updated follower relationship

        Raises:
            NotFoundError: If follower relationship not found
            ValidationError: If new start date is invalid
        """
        # Validate new start date
        if new_start_date.date() > date.today():
            raise ValidationError("Start date cannot be in the future")

        # Get follower
        follower = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.gym_id == gym_id
        ).first()

        if not follower:
            raise NotFoundError(
                f"User {user_id} is not following plan {plan_id}"
            )

        # Update start date
        follower.start_date = new_start_date
        follower.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(follower)

        logger.info(f"Updated start date for user {user_id} following plan {plan_id}")

        # Invalidate cache
        if self.redis_client:
            cache_key = f"gym:{gym_id}:user:{user_id}:today_meals"
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Cache invalidation error: {e}")

        return follower

    def get_plan_analytics(
        self,
        plan_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Get analytics for a nutrition plan's followers.

        Args:
            plan_id: ID of the plan
            gym_id: ID of the gym

        Returns:
            Dictionary with analytics data
        """
        # Get all followers
        followers = self.get_plan_followers(plan_id, gym_id, active_only=False)

        # Calculate statistics
        total_followers = len(followers)
        active_followers = len([f for f in followers if f.is_active])

        # Get completion rates
        today = date.today()
        week_start = today - timedelta(days=today.weekday())

        # Average adherence for active followers
        adherence_data = []
        for follower in followers:
            if not follower.is_active:
                continue

            days_following = (today - follower.start_date.date()).days + 1
            days_with_progress = self.db.query(UserDailyProgress).filter(
                UserDailyProgress.user_id == follower.user_id,
                UserDailyProgress.gym_id == gym_id,
                UserDailyProgress.date >= follower.start_date.date()
            ).count()

            if days_following > 0:
                adherence = (days_with_progress / days_following * 100)
                adherence_data.append(adherence)

        avg_adherence = sum(adherence_data) / len(adherence_data) if adherence_data else 0

        return {
            'plan_id': plan_id,
            'total_followers': total_followers,
            'active_followers': active_followers,
            'inactive_followers': total_followers - active_followers,
            'average_adherence_percentage': round(avg_adherence, 1),
            'follower_retention_rate': (
                (active_followers / total_followers * 100) if total_followers > 0 else 0
            )
        }