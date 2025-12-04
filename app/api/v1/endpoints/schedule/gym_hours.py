from typing import Any, List, Optional, Dict
from datetime import date, datetime, timedelta, time
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_async_db
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.models.gym import Gym
from app.core.tenant import verify_gym_access
from app.schemas.schedule import (
    GymHours, 
    GymHoursCreate, 
    GymHoursUpdate, 
    GymSpecialHours,
    ApplyDefaultsRequest,
    DailyScheduleResponse
)
from app.services import schedule
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.db.redis_client import get_redis_client
from redis import Redis
router = APIRouter()

@router.get("/regular", response_model=List[GymHours])
async def get_all_gym_hours(
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get All Regular Gym Hours (Weekly Template)

    Retrieves the gym's standard operating hours template for all days of the week (Monday-Sunday).

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[GymHoursSchema]: A list containing 7 GymHours objects, one for each day (0=Mon to 6=Sun).

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym not found.
    """
    return await schedule.gym_hours_service.get_all_gym_hours_cached(db, gym_id=current_gym.id, redis_client=redis_client)


@router.get("/regular/{day}", response_model=GymHours)
async def get_gym_hours_by_day(
    day: int = Path(..., ge=0, le=6, description="Day of the week (0=Monday, 6=Sunday)"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Regular Gym Hours for a Specific Day

    Retrieves the gym's standard operating hours for a specific day of the week.
    If no hours are explicitly defined for this day, default hours (Mon-Sat 9 AM - 9 PM,
    Sun closed) will be returned and potentially created in the database.

    Args:
        day (int): The day of the week (0=Monday, 6=Sunday).
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        GymHoursSchema: The regular operating hours object for the specified day.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym not found.
        HTTPException 422: If the day parameter is outside the 0-6 range.
    """
    return await schedule.gym_hours_service.get_gym_hours_by_day_cached(db, day=day, gym_id=current_gym.id, redis_client=redis_client)


@router.put("/regular/{day}", response_model=GymHours)
async def update_gym_hours(
    day: int = Path(..., ge=0, le=6, description="Day of the week (0=Monday, 6=Sunday)"),
    gym_hours_data: GymHoursUpdate = Body(...),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update Regular Gym Hours for a Specific Day

    Updates or creates the standard operating hours for a specific day of the week.
    Allows setting open/close times or marking the day as closed.

    Args:
        day (int): The day of the week (0=Monday, 6=Sunday).
        gym_hours_data (GymHoursUpdate): The new schedule data for the day.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires ADMIN role within the gym or SUPER_ADMIN platform role.

    Request Body (GymHoursUpdate - all fields optional):
        {
          "open_time": "HH:MM (string)",
          "close_time": "HH:MM (string)",
          "is_closed": boolean
        }
        Note: `open_time` and `close_time` are required if `is_closed` is false or omitted.

    Returns:
        GymHoursSchema: The updated or newly created regular hours object for the specified day.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User lacks required admin permissions.
        HTTPException 404: Gym not found.
        HTTPException 422: Invalid input data (e.g., day out of range, invalid time format, close_time before open_time).
    """
    # Verify admin privileges
    result = await db.execute(select(User).where(User.auth0_id == current_user.id))
    local_user = result.scalar_one_or_none()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        result = await db.execute(select(UserGym).where(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ))
        user_gym = result.scalar_one_or_none()
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator role required for this action"
            )

    # Service expects gym_id, ensures data consistency
    # The schema GymHoursUpdate doesn't include gym_id, it's added by the service layer
    return await schedule.gym_hours_service.create_or_update_gym_hours_cached(
        db,
        day=day,
        gym_hours_data=gym_hours_data, # Pass the Pydantic model directly
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/date/{date}", response_model=Dict[str, Any])
async def get_gym_hours_by_date(
    date: date = Path(..., description="Date (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Effective Gym Hours for a Specific Date

    Retrieves the actual operating hours for a specific date, taking into account
    both the regular weekly schedule and any special hours (like holidays) that may override it.

    Args:
        date (date): The specific date to query (YYYY-MM-DD format).
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        Dict[str, Any]: A dictionary containing detailed schedule information:
                         - `date`: The queried date.
                         - `day_of_week`: Integer (0-6).
                         - `regular_hours`: GymHoursSchema for the corresponding day of the week.
                         - `special_hours`: GymSpecialHoursSchema if special hours exist for this date, else null.
                         - `is_special`: Boolean indicating if special hours apply.
                         - `effective_hours`: Dict with `open_time`, `close_time`, `is_closed`, `source` ('regular' or 'special'), `source_id`.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym not found.
        HTTPException 422: Invalid date format.
    """
    return await schedule.gym_hours_service.get_hours_for_date_cached(db, date_value=date, gym_id=current_gym.id, redis_client=redis_client)


@router.post("/apply-defaults", response_model=List[GymSpecialHours])
async def apply_defaults_to_range(
    *,
    db: AsyncSession = Depends(get_async_db),
    apply_request: ApplyDefaultsRequest,
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Ensure Weekly Hours Template Exists

    Ensures that the gym has a complete weekly operating hours template (Monday-Sunday).
    If the template doesn't exist, it creates default hours. This endpoint NO LONGER
    creates special hours entries for specific dates.

    Args:
        apply_request (ApplyDefaultsRequest): Contains start_date, end_date (used for validation only).
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires ADMIN role within the gym or SUPER_ADMIN platform role.

    Request Body (ApplyDefaultsRequest):
        {
          "start_date": "YYYY-MM-DD",
          "end_date": "YYYY-MM-DD",
          "overwrite_existing": boolean (ignored in current implementation)
        }

    Returns:
        List[GymSpecialHoursSchema]: Empty list (for API compatibility).

    Raises:
        HTTPException 400: Invalid date range (e.g., end_date before start_date).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User lacks required admin permissions.
        HTTPException 404: Gym not found.
        HTTPException 422: Validation error in request body.
    """
    # Verify admin privileges
    result = await db.execute(select(User).where(User.auth0_id == current_user.id))
    local_user = result.scalar_one_or_none()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        result = await db.execute(select(UserGym).where(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ))
        user_gym = result.scalar_one_or_none()
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Administrator role required for this action"
            )

    gym_id = current_gym.id

    try:
        return await schedule.gym_hours_service.apply_defaults_to_range_cached(
            db=db,
            start_date=apply_request.start_date,
            end_date=apply_request.end_date,
            gym_id=gym_id,
            overwrite_existing=apply_request.overwrite_existing,
            redis_client=redis_client
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/date-range", response_model=List[DailyScheduleResponse])
async def get_schedule_for_date_range(
    *,
    db: AsyncSession = Depends(get_async_db),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: Auth0User = Depends(get_current_user), # Requires authentication, any role
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Effective Daily Schedule for a Date Range

    Retrieves the effective operating hours for each date in the specified range,
    combining regular weekly hours and any applicable special hours. Useful for calendar views.

    Args:
        start_date (date): The first date in the range (YYYY-MM-DD).
        end_date (date): The last date in the range (YYYY-MM-DD).
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires authenticated user (any role).

    Returns:
        List[DailyScheduleResponse]: A list of daily schedule objects, each containing:
                                     - `date`: The specific date.
                                     - `day_of_week`: Integer (0-6).
                                     - `open_time`: Effective opening time (or null).
                                     - `close_time`: Effective closing time (or null).
                                     - `is_closed`: Boolean indicating if closed.
                                     - `is_special`: Boolean indicating if special hours applied.
                                     - `description`: Description if it was a special day.
                                     - `source_id`: ID of the GymHours or GymSpecialHours record used.

    Raises:
        HTTPException 400: Invalid date range (e.g., end_date before start_date).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User doesn't belong to the gym.
        HTTPException 404: Gym not found.
        HTTPException 422: Invalid date format in query parameters.
    """
    gym_id = current_gym.id

    try:
        schedule_data = await schedule.gym_hours_service.get_schedule_for_date_range_cached(
            db=db,
            start_date=start_date,
            end_date=end_date,
            gym_id=gym_id,
            redis_client=redis_client
        )
        return schedule_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) 