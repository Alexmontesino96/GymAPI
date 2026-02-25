"""
Service for managing nutrition plan CRUD operations.
Handles creation, reading, updating, and deletion of nutrition plans.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy import and_, or_, func, desc
from datetime import datetime
import json
import logging

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal,
    NutritionGoal, DifficultyLevel, BudgetLevel,
    DietaryRestriction, PlanType
)
from app.models.user import User
from app.schemas.nutrition import (
    NutritionPlanCreate, NutritionPlanUpdate,
    NutritionPlanFilters, DailyNutritionPlanCreate
)
from app.repositories.nutrition import nutrition_plan_repository
from app.db.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    pass


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


class PermissionError(Exception):
    """Raised when user lacks permission for an operation."""
    pass


class NutritionPlanService:
    """Service for managing nutrition plans (CRUD operations)."""

    def __init__(self, db: Session, redis_client: Optional[Any] = None):
        """
        Initialize the nutrition plan service.

        Args:
            db: Database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.repository = nutrition_plan_repository
        self.redis_client = redis_client

    def create_nutrition_plan(
        self,
        plan_data: NutritionPlanCreate,
        creator_id: int,
        gym_id: int
    ) -> NutritionPlan:
        """
        Create a new nutrition plan.

        Args:
            plan_data: Plan creation data
            creator_id: ID of the user creating the plan
            gym_id: ID of the gym

        Returns:
            Created nutrition plan

        Raises:
            NotFoundError: If creator user not found
            ValidationError: If validation fails
        """
        # Validate creator exists
        creator = self.db.query(User).filter(User.id == creator_id).first()
        if not creator:
            raise NotFoundError(f"Creator user with ID {creator_id} not found")

        # Convert tags to JSON if necessary
        tags_json = None
        if plan_data.tags:
            tags_json = json.dumps(plan_data.tags)

        # Create plan using repository (which follows the pattern)
        plan_dict = plan_data.model_dump(exclude={'tags'})
        plan_dict['creator_id'] = creator_id
        plan_dict['gym_id'] = gym_id
        plan_dict['tags'] = tags_json

        db_plan = NutritionPlan(**plan_dict)
        self.db.add(db_plan)
        self.db.commit()
        self.db.refresh(db_plan)

        logger.info(f"Nutrition plan created: {db_plan.id} by user {creator_id}")

        # Invalidate cache if Redis is available
        if self.redis_client:
            asyncio.create_task(
                self.repository.invalidate_cache(db_plan.id, gym_id, self.redis_client)
            )

        return db_plan

    def get_nutrition_plan(self, plan_id: int, gym_id: int) -> NutritionPlan:
        """
        Get a nutrition plan by ID.

        Args:
            plan_id: ID of the nutrition plan
            gym_id: ID of the gym

        Returns:
            Nutrition plan

        Raises:
            NotFoundError: If plan not found
        """
        plan = self.repository.get(self.db, plan_id, gym_id)
        if not plan:
            raise NotFoundError(f"Nutrition plan with ID {plan_id} not found in gym {gym_id}")
        return plan

    def get_nutrition_plan_with_details(
        self,
        plan_id: int,
        gym_id: int,
        user_id: Optional[int] = None
    ) -> NutritionPlan:
        """
        Get plan with complete details including days and meals.

        Args:
            plan_id: ID of the nutrition plan
            gym_id: ID of the gym
            user_id: Optional user ID for permission checking

        Returns:
            Nutrition plan with all details loaded

        Raises:
            NotFoundError: If plan not found
            PermissionError: If plan is private and user is not creator
        """
        plan = self.db.query(NutritionPlan).options(
            selectinload(NutritionPlan.daily_plans).selectinload(DailyNutritionPlan.meals),
            selectinload(NutritionPlan.followers)
        ).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not plan:
            raise NotFoundError(f"Nutrition plan with ID {plan_id} not found")

        # Check permissions if plan is private
        if not plan.is_public and user_id and plan.creator_id != user_id:
            # Check if user is following the plan
            is_follower = any(f.user_id == user_id for f in plan.followers)
            if not is_follower:
                raise PermissionError("You don't have permission to view this private plan")

        return plan

    def list_nutrition_plans(
        self,
        gym_id: int,
        filters: Optional[NutritionPlanFilters] = None,
        skip: int = 0,
        limit: int = 20
    ) -> (List[NutritionPlan], int):
        """
        List nutrition plans with optional filters.

        Args:
            gym_id: ID of the gym
            filters: Optional filters to apply
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return

        Returns:
            List of nutrition plans
        """
        # Use repository method for public plans with total count
        filter_dict = filters.model_dump(exclude_none=True) if filters else {}
        return self.repository.get_public_plans_with_total(
            self.db, gym_id, filter_dict, skip, limit
        )

    async def list_nutrition_plans_cached(
        self,
        gym_id: int,
        filters: Optional[NutritionPlanFilters] = None,
        skip: int = 0,
        limit: int = 20,
        include_details: bool = False
    ) -> (List[NutritionPlan], int):
        """
        List nutrition plans with Redis caching.

        OPTIMIZATION: Cache filtered list for 10 minutes to reduce repeated loads

        Args:
            include_details: If True, includes daily_plans and meals (eager loaded)
        """
        filter_dict = filters.model_dump(exclude_none=True) if filters else {}
        return await self.repository.get_public_plans_with_total_cached(
            self.db, gym_id, filter_dict, skip, limit, include_details
        )

    def update_nutrition_plan(
        self,
        plan_id: int,
        plan_update: NutritionPlanUpdate,
        user_id: int,
        gym_id: int
    ) -> NutritionPlan:
        """
        Update a nutrition plan.

        Args:
            plan_id: ID of the plan to update
            plan_update: Update data
            user_id: ID of the user making the update
            gym_id: ID of the gym

        Returns:
            Updated nutrition plan

        Raises:
            NotFoundError: If plan not found
            PermissionError: If user is not the creator
        """
        plan = self.get_nutrition_plan(plan_id, gym_id)

        # Check permissions
        if plan.creator_id != user_id:
            raise PermissionError("Only the creator can update this plan")

        # Use repository update method
        updated_plan = self.repository.update(
            self.db,
            db_obj=plan,
            obj_in=plan_update,
            gym_id=gym_id
        )

        logger.info(f"Nutrition plan {plan_id} updated by user {user_id}")

        # Invalidate cache
        if self.redis_client:
            asyncio.create_task(
                self.repository.invalidate_cache(plan_id, gym_id, self.redis_client)
            )

        return updated_plan

    def delete_nutrition_plan(
        self,
        plan_id: int,
        user_id: int,
        gym_id: int
    ) -> bool:
        """
        Delete a nutrition plan.

        Args:
            plan_id: ID of the plan to delete
            user_id: ID of the user requesting deletion
            gym_id: ID of the gym

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If plan not found
            PermissionError: If user is not the creator
        """
        plan = self.get_nutrition_plan(plan_id, gym_id)

        # Check permissions
        if plan.creator_id != user_id:
            raise PermissionError("Only the creator can delete this plan")

        # Use repository remove method
        self.repository.remove(self.db, id=plan_id, gym_id=gym_id)

        logger.info(f"Nutrition plan {plan_id} deleted by user {user_id}")

        # Invalidate cache
        if self.redis_client:
            asyncio.create_task(
                self.repository.invalidate_cache(plan_id, gym_id, self.redis_client)
            )

        return True

    def create_daily_plan(
        self,
        plan_id: int,
        daily_plan_data: DailyNutritionPlanCreate,
        user_id: int,
        gym_id: int
    ) -> DailyNutritionPlan:
        """
        Add a daily plan to a nutrition plan.

        Args:
            plan_id: ID of the parent nutrition plan
            daily_plan_data: Daily plan data
            user_id: ID of the user creating the daily plan
            gym_id: ID of the gym

        Returns:
            Created daily nutrition plan

        Raises:
            NotFoundError: If parent plan not found
            PermissionError: If user is not the creator
            ValidationError: If day number already exists
        """
        plan = self.get_nutrition_plan(plan_id, gym_id)

        # Check permissions
        if plan.creator_id != user_id:
            raise PermissionError("Only the creator can add daily plans")

        # Check if day number already exists
        existing = self.db.query(DailyNutritionPlan).filter(
            DailyNutritionPlan.plan_id == plan_id,
            DailyNutritionPlan.day_number == daily_plan_data.day_number
        ).first()

        if existing:
            raise ValidationError(
                f"Day {daily_plan_data.day_number} already exists in this plan"
            )

        # Create daily plan
        db_daily_plan = DailyNutritionPlan(
            plan_id=plan_id,
            **daily_plan_data.model_dump()
        )

        self.db.add(db_daily_plan)
        self.db.commit()
        self.db.refresh(db_daily_plan)

        logger.info(f"Daily plan created for day {db_daily_plan.day_number} in plan {plan_id}")

        # Invalidate cache
        if self.redis_client:
            asyncio.create_task(
                self.repository.invalidate_cache(plan_id, gym_id, self.redis_client)
            )

        return db_daily_plan

    def duplicate_plan(
        self,
        source_plan_id: int,
        new_name: str,
        user_id: int,
        gym_id: int
    ) -> NutritionPlan:
        """
        Duplicate an existing nutrition plan.

        Args:
            source_plan_id: ID of the plan to duplicate
            new_name: Name for the duplicated plan
            user_id: ID of the user duplicating the plan
            gym_id: ID of the gym

        Returns:
            New duplicated nutrition plan

        Raises:
            NotFoundError: If source plan not found
        """
        source_plan = self.get_nutrition_plan_with_details(source_plan_id, gym_id, user_id)

        # Create new plan
        new_plan = NutritionPlan(
            name=new_name,
            description=f"Duplicated from: {source_plan.name}",
            goal=source_plan.goal,
            target_calories=source_plan.target_calories,
            target_protein=source_plan.target_protein,
            target_carbs=source_plan.target_carbs,
            target_fat=source_plan.target_fat,
            duration_days=source_plan.duration_days,
            is_public=False,  # Start as private
            creator_id=user_id,
            gym_id=gym_id,
            plan_type=PlanType.TEMPLATE,
            tags=source_plan.tags
        )

        self.db.add(new_plan)
        self.db.flush()  # Get ID without committing

        # Duplicate daily plans and meals
        for daily_plan in source_plan.daily_plans:
            new_daily = DailyNutritionPlan(
                plan_id=new_plan.id,
                day_number=daily_plan.day_number,
                day_name=daily_plan.day_name,
                notes=daily_plan.notes
            )
            self.db.add(new_daily)
            self.db.flush()

            # Duplicate meals
            for meal in daily_plan.meals:
                new_meal = Meal(
                    daily_plan_id=new_daily.id,
                    name=meal.name,
                    meal_type=meal.meal_type,
                    description=meal.description,
                    calories=meal.calories,
                    protein=meal.protein,
                    carbs=meal.carbs,
                    fat=meal.fat,
                    fiber=meal.fiber,
                    order=meal.order,
                    instructions=meal.instructions,
                    prep_time_minutes=meal.prep_time_minutes,
                    notes=meal.notes
                )
                self.db.add(new_meal)

        self.db.commit()
        self.db.refresh(new_plan)

        logger.info(f"Plan {source_plan_id} duplicated as {new_plan.id} by user {user_id}")

        return new_plan


# For backwards compatibility, import the service instance
import asyncio  # Needed for async cache invalidation
