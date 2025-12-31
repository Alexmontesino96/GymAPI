"""
Service for managing LIVE nutrition plans.
Handles real-time meal publishing, plan scheduling, and archival.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func
from datetime import datetime, date, timedelta
import logging
import json

from app.models.nutrition import (
    NutritionPlan, DailyNutritionPlan, Meal,
    NutritionPlanFollower, PlanType, PlanStatus
)
from app.models.user import User
from app.schemas.nutrition import (
    NutritionPlanCreate,
    ArchivePlanRequest,
    DailyNutritionPlanCreate
)
from app.db.redis_client import RedisClient

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


class LivePlanService:
    """Service for managing LIVE nutrition plans and scheduling."""

    def __init__(self, db: Session, redis_client: Optional[RedisClient] = None):
        """
        Initialize the live plan service.

        Args:
            db: Database session
            redis_client: Optional Redis client for caching
        """
        self.db = db
        self.redis_client = redis_client

    def create_live_nutrition_plan(
        self,
        plan_data: NutritionPlanCreate,
        creator_id: int,
        gym_id: int,
        start_date: datetime
    ) -> NutritionPlan:
        """
        Create a new LIVE nutrition plan.

        Args:
            plan_data: Plan creation data
            creator_id: ID of the user creating the plan
            gym_id: ID of the gym
            start_date: When the live plan should start

        Returns:
            Created live nutrition plan

        Raises:
            NotFoundError: If creator not found
            ValidationError: If validation fails
        """
        # Validate creator exists
        creator = self.db.query(User).filter(User.id == creator_id).first()
        if not creator:
            raise NotFoundError(f"Creator user with ID {creator_id} not found")

        # Ensure it's marked as LIVE type
        tags_json = json.dumps(plan_data.tags) if plan_data.tags else None

        db_plan = NutritionPlan(
            **plan_data.model_dump(exclude={'tags', 'plan_type'}),
            creator_id=creator_id,
            gym_id=gym_id,
            tags=tags_json,
            plan_type=PlanType.LIVE,
            live_start_date=start_date,
            is_live_active=False  # Will be activated when first day is published
        )

        self.db.add(db_plan)
        self.db.commit()
        self.db.refresh(db_plan)

        logger.info(f"Live nutrition plan created: {db_plan.id} starting {start_date}")

        return db_plan

    def publish_daily_plan(
        self,
        plan_id: int,
        daily_plan: DailyNutritionPlan,
        user_id: int,
        gym_id: int
    ) -> DailyNutritionPlan:
        """
        Publish a daily plan for a LIVE nutrition plan.

        Args:
            plan_id: ID of the live plan
            daily_plan: Daily plan to publish
            user_id: ID of the user publishing
            gym_id: ID of the gym

        Returns:
            Published daily plan

        Raises:
            NotFoundError: If plan not found
            PermissionError: If user is not the creator
            ValidationError: If plan is not LIVE type
        """
        # Get the plan
        plan = self.db.query(NutritionPlan).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not plan:
            raise NotFoundError(f"Plan {plan_id} not found")

        # Check permissions
        if plan.creator_id != user_id:
            raise PermissionError("Only the creator can publish daily plans")

        # Validate it's a LIVE plan
        if plan.plan_type != PlanType.LIVE:
            raise ValidationError("Can only publish to LIVE plans")

        # Set the daily plan's plan_id
        daily_plan.plan_id = plan_id

        # Calculate which day number this should be
        if plan.live_start_date:
            days_since_start = (date.today() - plan.live_start_date.date()).days
            daily_plan.day_number = days_since_start + 1
        else:
            # If no start date set, this is day 1
            daily_plan.day_number = 1
            plan.live_start_date = datetime.utcnow()

        # Activate the plan if this is the first daily plan
        if not plan.is_live_active:
            plan.is_live_active = True

        self.db.add(daily_plan)
        self.db.commit()
        self.db.refresh(daily_plan)

        logger.info(f"Published day {daily_plan.day_number} for live plan {plan_id}")

        # Notify followers
        self._notify_followers_new_day(daily_plan)

        # Invalidate cache
        if self.redis_client:
            # Invalidate plan cache
            cache_key = f"gym:{gym_id}:nutrition:plan:{plan_id}"
            try:
                self.redis_client.delete(cache_key)
                # Also invalidate follower caches
                followers = self.db.query(NutritionPlanFollower).filter(
                    NutritionPlanFollower.plan_id == plan_id,
                    NutritionPlanFollower.is_active == True
                ).all()
                for follower in followers:
                    user_cache_key = f"gym:{gym_id}:user:{follower.user_id}:today_meals"
                    self.redis_client.delete(user_cache_key)
            except Exception as e:
                logger.warning(f"Cache invalidation error: {e}")

        return daily_plan

    def update_live_plan_status(
        self,
        plan_id: int,
        gym_id: int
    ) -> NutritionPlan:
        """
        Update the status of a LIVE plan based on current date.

        Args:
            plan_id: ID of the plan
            gym_id: ID of the gym

        Returns:
            Updated plan

        Raises:
            NotFoundError: If plan not found
        """
        plan = self.db.query(NutritionPlan).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.plan_type == PlanType.LIVE
        ).first()

        if not plan:
            raise NotFoundError(f"Live plan {plan_id} not found")

        today = date.today()

        # Check if plan should be completed
        if plan.live_start_date and plan.is_live_active:
            days_since_start = (today - plan.live_start_date.date()).days

            if days_since_start >= plan.duration_days:
                # Plan has ended, auto-archive it
                self._auto_archive_finished_live_plan(plan)

        self.db.commit()
        self.db.refresh(plan)

        return plan

    def archive_live_plan(
        self,
        plan_id: int,
        archive_request: ArchivePlanRequest,
        user_id: int,
        gym_id: int
    ) -> NutritionPlan:
        """
        Archive a LIVE plan and optionally create a template version.

        Args:
            plan_id: ID of the plan to archive
            archive_request: Archive request details
            user_id: ID of the user archiving
            gym_id: ID of the gym

        Returns:
            Archived plan (or new template if created)

        Raises:
            NotFoundError: If plan not found
            PermissionError: If user is not the creator
            ValidationError: If plan is not LIVE type
        """
        plan = self.db.query(NutritionPlan).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id
        ).first()

        if not plan:
            raise NotFoundError(f"Plan {plan_id} not found")

        # Check permissions
        if plan.creator_id != user_id:
            raise PermissionError("Only the creator can archive the plan")

        # Validate it's a LIVE plan
        if plan.plan_type != PlanType.LIVE:
            raise ValidationError("Can only archive LIVE plans")

        # Mark as inactive
        plan.is_live_active = False

        # Create template version if requested
        template_plan = None
        if archive_request.create_template:
            template_plan = self._create_archived_version(
                plan,
                archive_request.template_title
            )

        self.db.commit()

        logger.info(f"Archived live plan {plan_id}")

        return template_plan if template_plan else plan

    def get_active_live_plans(
        self,
        gym_id: int,
        include_upcoming: bool = False
    ) -> List[NutritionPlan]:
        """
        Get all active LIVE plans for a gym.

        Args:
            gym_id: ID of the gym
            include_upcoming: Whether to include plans that haven't started yet

        Returns:
            List of active live plans
        """
        query = self.db.query(NutritionPlan).filter(
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.plan_type == PlanType.LIVE
        )

        if not include_upcoming:
            query = query.filter(NutritionPlan.is_live_active == True)
        else:
            # Include plans that will start in the future
            today = date.today()
            query = query.filter(
                or_(
                    NutritionPlan.is_live_active == True,
                    and_(
                        NutritionPlan.live_start_date != None,
                        NutritionPlan.live_start_date >= today
                    )
                )
            )

        return query.order_by(NutritionPlan.live_start_date.desc()).all()

    def get_live_plan_schedule(
        self,
        plan_id: int,
        gym_id: int
    ) -> Dict[str, Any]:
        """
        Get the publishing schedule for a LIVE plan.

        Args:
            plan_id: ID of the plan
            gym_id: ID of the gym

        Returns:
            Dictionary with schedule information
        """
        plan = self.db.query(NutritionPlan).options(
            joinedload(NutritionPlan.daily_plans)
        ).filter(
            NutritionPlan.id == plan_id,
            NutritionPlan.gym_id == gym_id,
            NutritionPlan.plan_type == PlanType.LIVE
        ).first()

        if not plan:
            raise NotFoundError(f"Live plan {plan_id} not found")

        today = date.today()
        schedule = {
            'plan_id': plan_id,
            'plan_name': plan.name,
            'start_date': plan.live_start_date,
            'duration_days': plan.duration_days,
            'is_active': plan.is_live_active,
            'published_days': [],
            'upcoming_days': []
        }

        if plan.live_start_date:
            # Calculate published and upcoming days
            for day_num in range(1, plan.duration_days + 1):
                day_date = plan.live_start_date.date() + timedelta(days=day_num - 1)

                # Check if this day has been published
                daily_plan = next(
                    (dp for dp in plan.daily_plans if dp.day_number == day_num),
                    None
                )

                if daily_plan:
                    schedule['published_days'].append({
                        'day_number': day_num,
                        'date': day_date,
                        'published': True,
                        'daily_plan_id': daily_plan.id
                    })
                elif day_date <= today:
                    # Should have been published but wasn't
                    schedule['upcoming_days'].append({
                        'day_number': day_num,
                        'date': day_date,
                        'status': 'overdue'
                    })
                else:
                    # Future day
                    schedule['upcoming_days'].append({
                        'day_number': day_num,
                        'date': day_date,
                        'status': 'scheduled'
                    })

            # Calculate completion status
            days_elapsed = (today - plan.live_start_date.date()).days + 1
            days_to_publish = min(days_elapsed, plan.duration_days)
            schedule['completion_percentage'] = (
                len(schedule['published_days']) / days_to_publish * 100
                if days_to_publish > 0 else 0
            )

        return schedule

    def _auto_archive_finished_live_plan(self, plan: NutritionPlan) -> None:
        """
        Automatically archive a finished LIVE plan.

        Args:
            plan: The plan to archive
        """
        if plan.is_live_active:
            plan.is_live_active = False

            logger.info(f"Auto-archived finished live plan {plan.id}")

            # Notify creator
            # TODO: Send notification to creator that plan has ended

    def _create_archived_version(
        self,
        live_plan: NutritionPlan,
        template_title: Optional[str] = None
    ) -> NutritionPlan:
        """
        Create a TEMPLATE version of a LIVE plan for reuse.

        Args:
            live_plan: The live plan to archive
            template_title: Optional custom title for the template

        Returns:
            New template plan
        """
        # Create template version
        template_plan = NutritionPlan(
            name=template_title or f"{live_plan.name} (Template)",
            description=f"Template created from live plan: {live_plan.name}",
            goal=live_plan.goal,
            target_calories=live_plan.target_calories,
            target_protein=live_plan.target_protein,
            target_carbs=live_plan.target_carbs,
            target_fat=live_plan.target_fat,
            duration_days=live_plan.duration_days,
            is_public=False,  # Start as private
            creator_id=live_plan.creator_id,
            gym_id=live_plan.gym_id,
            plan_type=PlanType.TEMPLATE,
            is_recurring=False,
            tags=live_plan.tags
        )

        self.db.add(template_plan)
        self.db.flush()  # Get ID

        # Copy all daily plans and meals
        daily_plans = self.db.query(DailyNutritionPlan).filter(
            DailyNutritionPlan.plan_id == live_plan.id
        ).order_by(DailyNutritionPlan.day_number).all()

        for daily_plan in daily_plans:
            new_daily = DailyNutritionPlan(
                plan_id=template_plan.id,
                day_number=daily_plan.day_number,
                day_name=daily_plan.day_name,
                notes=daily_plan.notes
            )
            self.db.add(new_daily)
            self.db.flush()

            # Copy meals
            meals = self.db.query(Meal).filter(
                Meal.daily_plan_id == daily_plan.id
            ).all()

            for meal in meals:
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

        logger.info(f"Created template {template_plan.id} from live plan {live_plan.id}")

        return template_plan

    def _notify_followers_new_day(self, daily_plan: DailyNutritionPlan) -> None:
        """
        Notify followers that a new day has been published.

        Args:
            daily_plan: The newly published daily plan
        """
        # Get active followers
        followers = self.db.query(NutritionPlanFollower).filter(
            NutritionPlanFollower.plan_id == daily_plan.plan_id,
            NutritionPlanFollower.is_active == True
        ).all()

        for follower in followers:
            # TODO: Send push notification or email
            # For now, just log
            logger.info(
                f"Notifying user {follower.user_id} about new day {daily_plan.day_number} "
                f"in plan {daily_plan.plan_id}"
            )

        logger.info(f"Notified {len(followers)} followers about new daily plan")