"""
Service for managing meals and ingredients within nutrition plans.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_
from datetime import datetime
import logging

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal, MealIngredient,
    MealType
)
from app.models.user import User
from app.schemas.nutrition import (
    MealCreate, MealUpdate, MealIngredientCreate
)
from app.repositories.nutrition import meal_repository
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


class MealService:
    """Service for managing meals and ingredients."""

    def __init__(self, db: Session, redis_client: Optional[Any] = None):
        """
        Initialize the meal service.

        Args:
            db: Database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.repository = meal_repository
        self.redis_client = redis_client

    def create_meal(
        self,
        meal_data: MealCreate,
        user_id: int,
        gym_id: int
    ) -> Meal:
        """
        Create a new meal in a daily plan.

        Args:
            meal_data: Meal creation data
            user_id: ID of the user creating the meal
            gym_id: ID of the gym

        Returns:
            Created meal

        Raises:
            NotFoundError: If daily plan not found
            PermissionError: If user is not the plan creator
            ValidationError: If validation fails
        """
        # Validate that daily plan exists and user has permission
        daily_plan = self.db.query(DailyNutritionPlan).join(
            NutritionPlan
        ).filter(
            DailyNutritionPlan.id == meal_data.daily_plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not daily_plan:
            raise NotFoundError(f"Daily plan {meal_data.daily_plan_id} not found")

        # Check if user is the creator of the parent plan
        plan = self.db.query(NutritionPlan).filter(
            NutritionPlan.id == daily_plan.plan_id
        ).first()

        if plan.creator_id != user_id:
            raise PermissionError("Only the plan creator can add meals")

        # Use repository to create meal with ingredients
        meal = self.repository.create_meal_with_ingredients(
            self.db,
            meal_data,
            meal_data.daily_plan_id,
            gym_id
        )

        if not meal:
            raise ValidationError("Failed to create meal")

        logger.info(f"Meal '{meal.name}' created in daily plan {meal_data.daily_plan_id}")

        # Invalidate cache for the parent plan
        if self.redis_client and plan:
            cache_key = f"gym:{gym_id}:nutrition:plan:{plan.id}"
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Cache invalidation error: {e}")

        return meal

    def update_meal(
        self,
        meal_id: int,
        meal_update: MealUpdate,
        user_id: int,
        gym_id: int
    ) -> Meal:
        """
        Update an existing meal.

        Args:
            meal_id: ID of the meal to update
            meal_update: Update data
            user_id: ID of the user updating the meal
            gym_id: ID of the gym

        Returns:
            Updated meal

        Raises:
            NotFoundError: If meal not found
            PermissionError: If user is not the plan creator
        """
        # Get meal with plan information
        meal = self.db.query(Meal).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).filter(
            Meal.id == meal_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not meal:
            raise NotFoundError(f"Meal {meal_id} not found")

        # Check permissions through the plan
        plan = meal.daily_plan.plan
        if plan.creator_id != user_id:
            raise PermissionError("Only the plan creator can update meals")

        # Update meal fields
        update_data = meal_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(meal, field):
                setattr(meal, field, value)

        meal.updated_at = datetime.utcnow()

        self.db.commit()
        self.db.refresh(meal)

        logger.info(f"Meal {meal_id} updated")

        # Invalidate cache
        if self.redis_client:
            cache_key = f"gym:{gym_id}:nutrition:plan:{plan.id}"
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Cache invalidation error: {e}")

        return meal

    def delete_meal(
        self,
        meal_id: int,
        user_id: int,
        gym_id: int
    ) -> bool:
        """
        Delete a meal.

        Args:
            meal_id: ID of the meal to delete
            user_id: ID of the user deleting the meal
            gym_id: ID of the gym

        Returns:
            True if deleted successfully

        Raises:
            NotFoundError: If meal not found
            PermissionError: If user is not the plan creator
        """
        # Get meal with plan information
        meal = self.db.query(Meal).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).filter(
            Meal.id == meal_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not meal:
            raise NotFoundError(f"Meal {meal_id} not found")

        # Check permissions through the plan
        plan = meal.daily_plan.plan
        if plan.creator_id != user_id:
            raise PermissionError("Only the plan creator can delete meals")

        # Delete meal (ingredients will cascade)
        self.db.delete(meal)
        self.db.commit()

        logger.info(f"Meal {meal_id} deleted")

        # Invalidate cache
        if self.redis_client:
            cache_key = f"gym:{gym_id}:nutrition:plan:{plan.id}"
            try:
                self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning(f"Cache invalidation error: {e}")

        return True

    def add_ingredient_to_meal(
        self,
        meal_id: int,
        ingredient_data: MealIngredientCreate,
        user_id: int,
        gym_id: int
    ) -> MealIngredient:
        """
        Add an ingredient to a meal.

        Args:
            meal_id: ID of the meal
            ingredient_data: Ingredient data
            user_id: ID of the user adding the ingredient
            gym_id: ID of the gym

        Returns:
            Created ingredient

        Raises:
            NotFoundError: If meal not found
            PermissionError: If user is not the plan creator
        """
        # Get meal with plan information
        meal = self.db.query(Meal).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).filter(
            Meal.id == meal_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not meal:
            raise NotFoundError(f"Meal {meal_id} not found")

        # Check permissions through the plan
        plan = meal.daily_plan.plan
        if plan.creator_id != user_id:
            raise PermissionError("Only the plan creator can add ingredients")

        # Create ingredient
        ingredient = MealIngredient(
            meal_id=meal_id,
            **ingredient_data.model_dump()
        )

        self.db.add(ingredient)

        # Update meal totals
        self._recalculate_meal_nutrition(meal)

        self.db.commit()
        self.db.refresh(ingredient)

        logger.info(f"Ingredient '{ingredient.name}' added to meal {meal_id}")

        return ingredient

    def remove_ingredient_from_meal(
        self,
        ingredient_id: int,
        user_id: int,
        gym_id: int
    ) -> bool:
        """
        Remove an ingredient from a meal.

        Args:
            ingredient_id: ID of the ingredient to remove
            user_id: ID of the user removing the ingredient
            gym_id: ID of the gym

        Returns:
            True if removed successfully

        Raises:
            NotFoundError: If ingredient not found
            PermissionError: If user is not the plan creator
        """
        # Get ingredient with meal and plan information
        ingredient = self.db.query(MealIngredient).join(
            Meal
        ).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).filter(
            MealIngredient.id == ingredient_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not ingredient:
            raise NotFoundError(f"Ingredient {ingredient_id} not found")

        # Check permissions through the plan
        plan = ingredient.meal.daily_plan.plan
        if plan.creator_id != user_id:
            raise PermissionError("Only the plan creator can remove ingredients")

        meal = ingredient.meal

        # Delete ingredient
        self.db.delete(ingredient)

        # Update meal totals
        self._recalculate_meal_nutrition(meal)

        self.db.commit()

        logger.info(f"Ingredient {ingredient_id} removed from meal {meal.id}")

        return True

    def get_meals_for_daily_plan(
        self,
        daily_plan_id: int,
        gym_id: int
    ) -> List[Meal]:
        """
        Get all meals for a daily plan.

        Args:
            daily_plan_id: ID of the daily plan
            gym_id: ID of the gym

        Returns:
            List of meals with ingredients

        Raises:
            NotFoundError: If daily plan not found
        """
        meals = self.repository.get_meals_for_daily_plan(
            self.db,
            daily_plan_id,
            gym_id
        )

        if not meals:
            # Verify daily plan exists
            daily_plan = self.db.query(DailyNutritionPlan).join(
                NutritionPlan
            ).filter(
                DailyNutritionPlan.id == daily_plan_id,
                NutritionPlan.gym_id == gym_id
            ).first()

            if not daily_plan:
                raise NotFoundError(f"Daily plan {daily_plan_id} not found")

        return meals

    def duplicate_meal(
        self,
        source_meal_id: int,
        target_daily_plan_id: int,
        user_id: int,
        gym_id: int
    ) -> Meal:
        """
        Duplicate a meal to another daily plan.

        Args:
            source_meal_id: ID of the meal to duplicate
            target_daily_plan_id: ID of the target daily plan
            user_id: ID of the user duplicating the meal
            gym_id: ID of the gym

        Returns:
            New duplicated meal

        Raises:
            NotFoundError: If source meal or target plan not found
            PermissionError: If user lacks permissions
        """
        # Get source meal
        source_meal = self.db.query(Meal).options(
            joinedload(Meal.ingredients)
        ).join(
            DailyNutritionPlan
        ).join(
            NutritionPlan
        ).filter(
            Meal.id == source_meal_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not source_meal:
            raise NotFoundError(f"Source meal {source_meal_id} not found")

        # Validate target daily plan
        target_plan = self.db.query(DailyNutritionPlan).join(
            NutritionPlan
        ).filter(
            DailyNutritionPlan.id == target_daily_plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not target_plan:
            raise NotFoundError(f"Target daily plan {target_daily_plan_id} not found")

        # Check permissions
        if target_plan.plan.creator_id != user_id:
            raise PermissionError("You can only duplicate meals to your own plans")

        # Create duplicate meal
        new_meal = Meal(
            daily_plan_id=target_daily_plan_id,
            name=f"{source_meal.name} (Copy)",
            meal_type=source_meal.meal_type,
            description=source_meal.description,
            calories=source_meal.calories,
            protein=source_meal.protein,
            carbs=source_meal.carbs,
            fat=source_meal.fat,
            fiber=source_meal.fiber,
            order=source_meal.order,
            instructions=source_meal.instructions,
            prep_time_minutes=source_meal.prep_time_minutes,
            notes=source_meal.notes
        )

        self.db.add(new_meal)
        self.db.flush()  # Get ID without committing

        # Duplicate ingredients
        for ingredient in source_meal.ingredients:
            new_ingredient = MealIngredient(
                meal_id=new_meal.id,
                name=ingredient.name,
                amount=ingredient.amount,
                unit=ingredient.unit,
                calories=ingredient.calories,
                protein=ingredient.protein,
                carbs=ingredient.carbs,
                fat=ingredient.fat
            )
            self.db.add(new_ingredient)

        self.db.commit()
        self.db.refresh(new_meal)

        logger.info(f"Meal {source_meal_id} duplicated to daily plan {target_daily_plan_id}")

        return new_meal

    def _recalculate_meal_nutrition(self, meal: Meal) -> None:
        """
        Recalculate meal nutrition totals from ingredients.

        Args:
            meal: Meal to recalculate
        """
        # Sum nutrition from all ingredients
        total_calories = 0
        total_protein = 0
        total_carbs = 0
        total_fat = 0

        for ingredient in meal.ingredients:
            total_calories += ingredient.calories or 0
            total_protein += ingredient.protein or 0
            total_carbs += ingredient.carbs or 0
            total_fat += ingredient.fat or 0

        # Update meal totals
        meal.calories = total_calories
        meal.protein = total_protein
        meal.carbs = total_carbs
        meal.fat = total_fat
        meal.updated_at = datetime.utcnow()

        logger.debug(f"Recalculated nutrition for meal {meal.id}")