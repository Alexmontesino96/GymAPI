"""
Repository pattern implementation for nutrition module.
Handles all database operations related to nutrition plans, meals, and followers.
"""

from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta, date
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import func, and_, or_, select, exists
import json
import logging
import asyncio

from app.repositories.base import BaseRepository
from app.models.nutrition import (
    NutritionPlan,
    DailyNutritionPlan,
    Meal,
    MealIngredient,
    NutritionPlanFollower,
    UserMealCompletion,
    UserDailyProgress,
    PlanType
)
from app.models.user import User
from app.schemas.nutrition import (
    NutritionPlanCreate,
    NutritionPlanUpdate,
    MealCreate,
    MealUpdate
)
from app.db.redis_client import get_redis_client
from app.utils.nutrition_serializers import NutritionSerializer

logger = logging.getLogger(__name__)


class NutritionPlanRepository(BaseRepository):
    """Repository for NutritionPlan operations with caching support."""

    def __init__(self):
        super().__init__(NutritionPlan)
        self.cache_ttl = 3600  # 1 hour default cache

    async def get_with_cache(
        self,
        db: Session,
        plan_id: int,
        gym_id: int,
        redis_client = None
    ) -> Optional[NutritionPlan]:
        """
        Get nutrition plan with Redis cache support.

        Args:
            db: Database session
            plan_id: ID of the nutrition plan
            gym_id: Gym ID for multi-tenant validation
            redis_client: Optional Redis client for caching

        Returns:
            NutritionPlan object or None if not found
        """
        cache_key = f"gym:{gym_id}:nutrition:plan:{plan_id}"

        # Try to get Redis client if not provided
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                redis_client = None

        # Try cache first if Redis is available
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for plan {plan_id}")
                    # Note: We return the dict from cache, service layer handles object reconstruction
                    cached_data = NutritionSerializer.deserialize_plan(cached)

                    # Validate gym_id for security
                    if cached_data.get('gym_id') != gym_id:
                        logger.warning(f"Cache gym_id mismatch for plan {plan_id}")
                        await redis_client.delete(cache_key)
                    else:
                        return cached_data
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # Fetch from database with eager loading for performance
        plan = db.query(NutritionPlan).options(
            selectinload(NutritionPlan.daily_plans).selectinload(DailyNutritionPlan.meals).selectinload(Meal.ingredients),
            selectinload(NutritionPlan.followers)
        ).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        # Cache the result if Redis is available
        if redis_client and plan:
            try:
                # Serialize and cache
                serialized = NutritionSerializer.serialize_plan(plan, include_relations=True)
                await redis_client.setex(cache_key, self.cache_ttl, serialized)
                logger.debug(f"Cached plan {plan_id} with TTL {self.cache_ttl}s")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return plan

    def get_public_plans(
        self,
        db: Session,
        gym_id: int,
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 20
    ) -> List[NutritionPlan]:
        """
        Get public nutrition plans for a gym with filters.

        Args:
            db: Database session
            gym_id: Gym ID
            filters: Optional filters (goal, plan_type, etc.)
            skip: Pagination offset
            limit: Maximum results (capped at 100)

        Returns:
            List of public nutrition plans
        """
        # Cap limit to prevent excessive queries
        limit = min(limit, 100)

        query = db.query(NutritionPlan).filter(
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.is_public == True
        )

        # Apply filters
        if filters:
            if 'goal' in filters and filters['goal']:
                query = query.filter(NutritionPlan.goal == filters['goal'])

            if 'plan_type' in filters and filters['plan_type']:
                query = query.filter(NutritionPlan.plan_type == filters['plan_type'])

            if 'min_calories' in filters:
                query = query.filter(NutritionPlan.target_calories >= filters['min_calories'])

            if 'max_calories' in filters:
                query = query.filter(NutritionPlan.target_calories <= filters['max_calories'])

        # Order by most recently created/updated
        query = query.order_by(NutritionPlan.updated_at.desc())

        return query.offset(skip).limit(limit).all()

    def get_plans_by_creator(
        self,
        db: Session,
        creator_id: int,
        gym_id: int,
        include_private: bool = True
    ) -> List[NutritionPlan]:
        """
        Get all plans created by a specific user (nutritionist/trainer).

        Args:
            db: Database session
            creator_id: User ID of the creator
            gym_id: Gym ID for multi-tenant validation
            include_private: Whether to include private plans

        Returns:
            List of nutrition plans created by the user
        """
        query = db.query(NutritionPlan).filter(
            NutritionPlan.creator_id == creator_id,
            NutritionPlan.gym_id == gym_id
        )

        if not include_private:
            query = query.filter(NutritionPlan.is_public == True)

        return query.order_by(NutritionPlan.created_at.desc()).all()

    async def invalidate_cache(
        self,
        plan_id: int,
        gym_id: int,
        redis_client = None
    ) -> None:
        """
        Invalidate cache for a specific plan and related keys.

        Args:
            plan_id: ID of the plan to invalidate
            gym_id: Gym ID
            redis_client: Redis client for cache operations
        """
        # Try to get Redis client if not provided
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client for cache invalidation: {e}")
                return

        try:
            # List of cache keys to invalidate
            keys_to_delete = [
                f"gym:{gym_id}:nutrition:plan:{plan_id}",
                f"gym:{gym_id}:nutrition:plan:{plan_id}:followers",
                f"gym:{gym_id}:nutrition:plan:{plan_id}:meals",
                f"gym:{gym_id}:nutrition:public_plans",  # Invalidate public plans list
            ]

            # Delete all keys
            for key in keys_to_delete:
                await redis_client.delete(key)

            # Also invalidate user-specific caches for all followers
            # This would require scanning for pattern matching
            # For now, we'll invalidate the most common user caches
            logger.debug(f"Invalidated cache for plan {plan_id} and related keys")
        except Exception as e:
            logger.warning(f"Cache invalidation error: {e}")


class MealRepository(BaseRepository):
    """Repository for Meal operations with optimized queries and caching."""

    def __init__(self):
        super().__init__(Meal)
        self.cache_ttl = 1800  # 30 minutes cache for meals

    async def get_meals_for_daily_plan_cached(
        self,
        db: Session,
        daily_plan_id: int,
        gym_id: int,
        redis_client = None
    ) -> List[Meal]:
        """
        Get all meals for a daily plan with caching support.

        Args:
            db: Database session
            daily_plan_id: ID of the daily nutrition plan
            gym_id: Gym ID for validation
            redis_client: Optional Redis client

        Returns:
            List of meals with ingredients eagerly loaded
        """
        cache_key = f"gym:{gym_id}:nutrition:daily_plan:{daily_plan_id}:meals"

        # Try to get Redis client if not provided
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                redis_client = None

        # Try cache first
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for meals of daily plan {daily_plan_id}")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # Fetch from database
        meals = self.get_meals_for_daily_plan(db, daily_plan_id, gym_id)

        # Cache the result
        if redis_client and meals:
            try:
                # Serialize meals list
                serialized_meals = json.dumps([
                    NutritionSerializer._serialize_meal(meal)
                    for meal in meals
                ])
                await redis_client.setex(cache_key, self.cache_ttl, serialized_meals)
                logger.debug(f"Cached meals for daily plan {daily_plan_id}")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return meals

    def get_meals_for_daily_plan(
        self,
        db: Session,
        daily_plan_id: int,
        gym_id: int
    ) -> List[Meal]:
        """
        Get all meals for a specific daily plan with ingredients.

        Args:
            db: Database session
            daily_plan_id: ID of the daily nutrition plan
            gym_id: Gym ID for validation

        Returns:
            List of meals with ingredients eagerly loaded
        """
        return db.query(Meal).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).options(
            selectinload(Meal.ingredients)
        ).filter(
            Meal.daily_plan_id == daily_plan_id,
            NutritionPlan.gym_id == gym_id
        ).order_by(
            Meal.order
        ).all()

    def create_meal_with_ingredients(
        self,
        db: Session,
        meal_data: MealCreate,
        daily_plan_id: int,
        gym_id: int
    ) -> Optional[Meal]:
        """
        Create a meal with ingredients in a single transaction.

        Args:
            db: Database session
            meal_data: Meal creation data
            daily_plan_id: ID of the daily plan
            gym_id: Gym ID for validation

        Returns:
            Created meal or None if validation fails
        """
        # Validate daily plan belongs to gym
        daily_plan = db.query(DailyNutritionPlan).join(
            NutritionPlan
        ).filter(
            DailyNutritionPlan.id == daily_plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not daily_plan:
            return None

        # Create meal
        meal = Meal(
            daily_plan_id=daily_plan_id,
            name=meal_data.name,
            meal_type=meal_data.meal_type,
            description=meal_data.description,
            calories=meal_data.calories,
            protein=meal_data.protein,
            carbs=meal_data.carbs,
            fat=meal_data.fat,
            fiber=meal_data.fiber,
            order=meal_data.order or 0,
            instructions=meal_data.instructions,
            prep_time_minutes=meal_data.prep_time_minutes,
            notes=meal_data.notes
        )

        db.add(meal)
        db.flush()  # Get meal ID without committing

        # Add ingredients if provided
        if hasattr(meal_data, 'ingredients') and meal_data.ingredients:
            for ing_data in meal_data.ingredients:
                ingredient = MealIngredient(
                    meal_id=meal.id,
                    name=ing_data.name,
                    amount=ing_data.amount,
                    unit=ing_data.unit,
                    calories=ing_data.calories,
                    protein=ing_data.protein,
                    carbs=ing_data.carbs,
                    fat=ing_data.fat
                )
                db.add(ingredient)

        db.commit()
        db.refresh(meal)

        return meal

    async def invalidate_meal_cache(
        self,
        daily_plan_id: int,
        gym_id: int,
        redis_client = None
    ) -> None:
        """
        Invalidate meal cache for a daily plan.

        Args:
            daily_plan_id: ID of the daily plan
            gym_id: Gym ID
            redis_client: Redis client
        """
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                return

        try:
            keys_to_delete = [
                f"gym:{gym_id}:nutrition:daily_plan:{daily_plan_id}:meals",
                f"gym:{gym_id}:nutrition:meal:*"  # Pattern for individual meals
            ]
            for key in keys_to_delete:
                await redis_client.delete(key)
            logger.debug(f"Invalidated meal cache for daily plan {daily_plan_id}")
        except Exception as e:
            logger.warning(f"Meal cache invalidation error: {e}")


class PlanFollowerRepository(BaseRepository):
    """Repository for managing plan followers (users following nutrition plans) with caching."""

    def __init__(self):
        super().__init__(NutritionPlanFollower)
        self.cache_ttl = 900  # 15 minutes cache for follower data

    async def get_user_followed_plans_cached(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        include_archived: bool = False,
        redis_client = None
    ) -> List[NutritionPlanFollower]:
        """
        Get all plans a user is following with caching support.

        Args:
            db: Database session
            user_id: User ID
            gym_id: Gym ID
            include_archived: Whether to include archived follows
            redis_client: Optional Redis client

        Returns:
            List of followed plans with plan details
        """
        cache_key = f"gym:{gym_id}:user:{user_id}:followed_plans:{include_archived}"

        # Try to get Redis client if not provided
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                redis_client = None

        # Try cache first
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for user {user_id} followed plans")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # Fetch from database
        plans = self.get_user_followed_plans(db, user_id, gym_id, include_archived)

        # Cache the result
        if redis_client and plans:
            try:
                serialized = json.dumps([
                    NutritionSerializer.serialize_follower(follower)
                    for follower in plans
                ], default=str)
                await redis_client.setex(cache_key, self.cache_ttl, serialized)
                logger.debug(f"Cached followed plans for user {user_id}")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return plans

    def get_user_followed_plans(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        include_archived: bool = False
    ) -> List[NutritionPlanFollower]:
        """
        Get all plans a user is following.

        Args:
            db: Database session
            user_id: User ID
            gym_id: Gym ID
            include_archived: Whether to include archived follows

        Returns:
            List of followed plans with plan details eager loaded
        """
        query = db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan).selectinload(NutritionPlan.daily_plans)
        ).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.gym_id == gym_id
        )

        if not include_archived:
            query = query.filter(NutritionPlanFollower.is_active == True)

        return query.order_by(NutritionPlanFollower.start_date.desc()).all()

    def get_plan_followers(
        self,
        db: Session,
        plan_id: int,
        gym_id: int,
        active_only: bool = True
    ) -> List[NutritionPlanFollower]:
        """
        Get all users following a specific plan.

        Args:
            db: Database session
            plan_id: Nutrition plan ID
            gym_id: Gym ID
            active_only: Whether to only include active followers

        Returns:
            List of followers with user details
        """
        query = db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.user)
        ).filter(
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.gym_id == gym_id
        )

        if active_only:
            query = query.filter(NutritionPlanFollower.is_active == True)

        return query.all()

    def follow_plan(
        self,
        db: Session,
        user_id: int,
        plan_id: int,
        gym_id: int,
        start_date: Optional[datetime] = None
    ) -> Optional[NutritionPlanFollower]:
        """
        Create or reactivate a plan follow relationship.

        Args:
            db: Database session
            user_id: User ID
            plan_id: Plan ID
            gym_id: Gym ID
            start_date: Optional start date (defaults to now)

        Returns:
            Created or updated follower relationship
        """
        # Check if plan exists and belongs to gym
        plan = db.query(NutritionPlan).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not plan:
            return None

        # Check if already following
        existing = db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.gym_id == gym_id
        ).first()

        if existing:
            # Reactivate if inactive
            if not existing.is_active:
                existing.is_active = True
                existing.start_date = start_date or datetime.utcnow()
                existing.updated_at = datetime.utcnow()
                db.commit()
            return existing

        # Create new follower relationship
        follower = NutritionPlanFollower(
            user_id=user_id,
            plan_id=plan_id,
            gym_id=gym_id,
            start_date=start_date or datetime.utcnow(),
            is_active=True
        )

        db.add(follower)
        db.commit()
        db.refresh(follower)

        return follower

    def unfollow_plan(
        self,
        db: Session,
        user_id: int,
        plan_id: int,
        gym_id: int
    ) -> bool:
        """
        Unfollow (deactivate) a nutrition plan.

        Args:
            db: Database session
            user_id: User ID
            plan_id: Plan ID
            gym_id: Gym ID

        Returns:
            True if unfollowed successfully, False otherwise
        """
        follower = db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.plan_id == plan_id,
            NutritionPlanFollower.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).first()

        if not follower:
            return False

        follower.is_active = False
        follower.updated_at = datetime.utcnow()
        db.commit()

        return True

    async def invalidate_follower_cache(
        self,
        user_id: int,
        plan_id: int,
        gym_id: int,
        redis_client = None
    ) -> None:
        """
        Invalidate follower-related cache entries.

        Args:
            user_id: User ID
            plan_id: Plan ID
            gym_id: Gym ID
            redis_client: Optional Redis client
        """
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                return

        try:
            keys_to_delete = [
                f"gym:{gym_id}:user:{user_id}:followed_plans:True",
                f"gym:{gym_id}:user:{user_id}:followed_plans:False",
                f"gym:{gym_id}:nutrition:plan:{plan_id}:followers",
                f"gym:{gym_id}:user:{user_id}:today_meals"  # Invalidate today's meals too
            ]
            for key in keys_to_delete:
                await redis_client.delete(key)
            logger.debug(f"Invalidated follower cache for user {user_id} and plan {plan_id}")
        except Exception as e:
            logger.warning(f"Follower cache invalidation error: {e}")


class NutritionProgressRepository:
    """Repository for tracking user progress and meal completions with caching."""

    def __init__(self):
        self.cache_ttl = 300  # 5 minutes cache for progress data (frequently updated)

    async def get_today_meals_cached(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        redis_client = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get today's meal plan with caching support.

        Args:
            db: Database session
            user_id: User ID
            gym_id: Gym ID
            redis_client: Optional Redis client

        Returns:
            Dictionary with today's meals and progress
        """
        cache_key = f"gym:{gym_id}:user:{user_id}:today_meals"

        # Try to get Redis client if not provided
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                redis_client = None

        # Try cache first
        if redis_client:
            try:
                cached = await redis_client.get(cache_key)
                if cached:
                    logger.debug(f"Cache hit for today's meals for user {user_id}")
                    return NutritionSerializer.deserialize_today_meals(cached)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # Fetch from database
        today_data = self.get_today_meals(db, user_id, gym_id)

        # Cache the result
        if redis_client and today_data:
            try:
                serialized = NutritionSerializer.serialize_today_meals(today_data)
                await redis_client.setex(cache_key, self.cache_ttl, serialized)
                logger.debug(f"Cached today's meals for user {user_id}")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        return today_data

    def get_today_meals(
        self,
        db: Session,
        user_id: int,
        gym_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Get today's meal plan for a user with completion status.
        Optimized query to avoid N+1 problems.

        Args:
            db: Database session
            user_id: User ID
            gym_id: Gym ID

        Returns:
            Dictionary with today's meals and progress
        """
        today = date.today()

        # Get active followed plans with eager loading
        followed_plans = db.query(NutritionPlanFollower).options(
            joinedload(NutritionPlanFollower.plan).selectinload(NutritionPlan.daily_plans).selectinload(DailyNutritionPlan.meals)
        ).filter(
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.gym_id == gym_id,
            NutritionPlanFollower.is_active == True
        ).all()

        if not followed_plans:
            return None

        result = {
            'date': today,
            'plans': []
        }

        for follower in followed_plans:
            plan = follower.plan

            # Calculate current day for the plan
            days_since_start = (today - follower.start_date.date()).days

            # Handle recurring vs non-recurring plans
            if plan.plan_type == PlanType.TEMPLATE:
                if plan.is_recurring:
                    current_day = (days_since_start % plan.duration_days) + 1
                else:
                    if days_since_start >= plan.duration_days:
                        continue  # Plan has ended
                    current_day = days_since_start + 1
            else:
                # Live plan logic
                continue  # Skip for now, implement live plan logic separately

            # Get daily plan for current day
            daily_plan = next(
                (dp for dp in plan.daily_plans if dp.day_number == current_day),
                None
            )

            if not daily_plan:
                continue

            # Get meal completions for today
            completions = db.query(UserMealCompletion).filter(
                UserMealCompletion.user_id == user_id,
                UserMealCompletion.meal_id.in_([m.id for m in daily_plan.meals]),
                func.date(UserMealCompletion.completed_at) == today
            ).all()

            completion_map = {c.meal_id: c for c in completions}

            # Build response
            plan_data = {
                'plan_id': plan.id,
                'plan_name': plan.name,
                'day_number': current_day,
                'daily_plan_id': daily_plan.id,
                'meals': []
            }

            for meal in daily_plan.meals:
                meal_data = {
                    'meal_id': meal.id,
                    'name': meal.name,
                    'meal_type': meal.meal_type.value,
                    'calories': meal.calories,
                    'protein': meal.protein,
                    'carbs': meal.carbs,
                    'fat': meal.fat,
                    'completed': meal.id in completion_map,
                    'completed_at': completion_map[meal.id].completed_at if meal.id in completion_map else None
                }
                plan_data['meals'].append(meal_data)

            # Calculate totals
            plan_data['total_calories'] = sum(m['calories'] for m in plan_data['meals'])
            plan_data['completed_calories'] = sum(
                m['calories'] for m in plan_data['meals'] if m['completed']
            )
            plan_data['completion_percentage'] = (
                len([m for m in plan_data['meals'] if m['completed']]) / len(plan_data['meals']) * 100
                if plan_data['meals'] else 0
            )

            result['plans'].append(plan_data)

        return result if result['plans'] else None

    def complete_meal(
        self,
        db: Session,
        user_id: int,
        meal_id: int,
        gym_id: int
    ) -> Optional[UserMealCompletion]:
        """
        Mark a meal as completed for a user.

        Args:
            db: Database session
            user_id: User ID
            meal_id: Meal ID
            gym_id: Gym ID for validation

        Returns:
            Created completion record or None if validation fails
        """
        # Validate meal belongs to a plan the user is following
        meal = db.query(Meal).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).join(
            NutritionPlanFollower
        ).filter(
            Meal.id == meal_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlanFollower.user_id == user_id,
            NutritionPlanFollower.is_active == True
        ).first()

        if not meal:
            return None

        # Check if already completed today
        today = date.today()
        existing = db.query(UserMealCompletion).filter(
            UserMealCompletion.user_id == user_id,
            UserMealCompletion.meal_id == meal_id,
            func.date(UserMealCompletion.completed_at) == today
        ).first()

        if existing:
            return existing

        # Create completion record
        completion = UserMealCompletion(
            user_id=user_id,
            meal_id=meal_id,
            gym_id=gym_id,
            completed_at=datetime.utcnow()
        )

        db.add(completion)

        # Update daily progress
        self._update_daily_progress(db, user_id, gym_id, meal)

        db.commit()
        db.refresh(completion)

        return completion

    def _update_daily_progress(
        self,
        db: Session,
        user_id: int,
        gym_id: int,
        meal: Meal
    ) -> None:
        """
        Update or create daily progress record.

        Args:
            db: Database session
            user_id: User ID
            gym_id: Gym ID
            meal: Completed meal
        """
        today = date.today()

        # Get or create daily progress
        progress = db.query(UserDailyProgress).filter(
            UserDailyProgress.user_id == user_id,
            UserDailyProgress.date == today,
            UserDailyProgress.gym_id == gym_id
        ).first()

        if not progress:
            progress = UserDailyProgress(
                user_id=user_id,
                date=today,
                gym_id=gym_id,
                calories_consumed=0,
                protein_consumed=0,
                carbs_consumed=0,
                fat_consumed=0,
                fiber_consumed=0
            )
            db.add(progress)

        # Update totals
        progress.calories_consumed = (progress.calories_consumed or 0) + (meal.calories or 0)
        progress.protein_consumed = (progress.protein_consumed or 0) + (meal.protein or 0)
        progress.carbs_consumed = (progress.carbs_consumed or 0) + (meal.carbs or 0)
        progress.fat_consumed = (progress.fat_consumed or 0) + (meal.fat or 0)
        progress.fiber_consumed = (progress.fiber_consumed or 0) + (meal.fiber or 0)
        progress.meals_completed = (progress.meals_completed or 0) + 1
        progress.updated_at = datetime.utcnow()

    async def invalidate_progress_cache(
        self,
        user_id: int,
        gym_id: int,
        redis_client = None
    ) -> None:
        """
        Invalidate progress-related cache entries.

        Args:
            user_id: User ID
            gym_id: Gym ID
            redis_client: Optional Redis client
        """
        if redis_client is None:
            try:
                redis_client = await get_redis_client()
            except Exception as e:
                logger.warning(f"Could not get Redis client: {e}")
                return

        try:
            keys_to_delete = [
                f"gym:{gym_id}:user:{user_id}:today_meals",
                f"gym:{gym_id}:user:{user_id}:daily_progress",
                f"gym:{gym_id}:user:{user_id}:weekly_summary",
                f"gym:{gym_id}:user:{user_id}:nutrition_dashboard"
            ]
            for key in keys_to_delete:
                await redis_client.delete(key)
            logger.debug(f"Invalidated progress cache for user {user_id}")
        except Exception as e:
            logger.warning(f"Progress cache invalidation error: {e}")


# Export repository instances
nutrition_plan_repository = NutritionPlanRepository()
meal_repository = MealRepository()
plan_follower_repository = PlanFollowerRepository()
nutrition_progress_repository = NutritionProgressRepository()