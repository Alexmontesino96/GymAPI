from typing import Any, List, Optional
from datetime import date, datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, Security
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_async_db
from app.core.auth0_fastapi import auth, get_current_user, Auth0User
from app.models.gym import Gym
from app.core.tenant import verify_gym_access
from app.schemas.schedule import (
    GymSpecialHours, 
    GymSpecialHoursCreate, 
    GymSpecialHoursUpdate
)
from app.services import schedule
from app.models.user import User, UserRole
from app.models.user_gym import UserGym, GymRoleType
from app.db.redis_client import get_redis_client
from redis.asyncio import Redis

router = APIRouter()


@router.get("/", response_model=List[GymSpecialHours])
async def get_special_days(
    *,
    db: AsyncSession = Depends(get_async_db),
    skip: int = 0,
    limit: int = 100,
    upcoming_only: bool = Query(True, description="If True, only returns future special days"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Special Days / Hours

    Retrieves a list of special day/hour exceptions defined for the current gym.
    By default, it returns only upcoming special days.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        upcoming_only (bool, optional): If True (default), returns special days from today onwards.
                                        Note: fetching all past days (`upcoming_only=false`) is not currently implemented.
                                        Defaults to True.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires authenticated user.

    Returns:
        List[GymSpecialHoursSchema]: A list of special day objects.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User doesn't belong to the gym.
        HTTPException 404: Gym not found.
        HTTPException 501: If `upcoming_only` is false.
    """
    gym_id = current_gym.id

    if upcoming_only:
        return await schedule.gym_special_hours_service.get_upcoming_special_days_cached(
            db=db, limit=limit, gym_id=gym_id, redis_client=redis_client
        )
    else:
        # TODO: Implement endpoint to get all special days with pagination
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Fetching all special days (including past) is not yet implemented"
        )


@router.get("/{special_day_id}", response_model=GymSpecialHours)
async def get_special_day(
    *,
    db: AsyncSession = Depends(get_async_db),
    special_day_id: int = Path(..., description="ID of the special day entry"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Specific Special Day by ID

    Retrieves details of a specific special day entry using its unique ID.
    Verifies that the entry belongs to the current gym.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        special_day_id (int): The ID of the special day entry to retrieve.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires authenticated user.

    Returns:
        GymSpecialHoursSchema: The requested special day object.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User doesn't belong to the gym or doesn't have access to this entry.
        HTTPException 404: Gym or Special Day entry not found, or entry doesn't belong to this gym.
    """
    special_day = await schedule.gym_special_hours_service.get_special_hours_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    )
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special day entry not found"
        )

    # Verify ownership/access (should belong to the current_gym)
    if special_day.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this special day entry"
        )

    return special_day


@router.get("/date/{date}", response_model=GymSpecialHours)
async def get_special_day_by_date(
    *,
    db: AsyncSession = Depends(get_async_db),
    date: date = Path(..., description="Date (YYYY-MM-DD)"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Special Day by Date

    Retrieves the special day entry for a specific date within the current gym, if one exists.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        date (date): The specific date to query (YYYY-MM-DD format).
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires authenticated user.

    Returns:
        GymSpecialHoursSchema: The special day object for the specified date.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User doesn't belong to the gym.
        HTTPException 404: Gym not found, or no special entry exists for this date in this gym.
        HTTPException 422: Invalid date format.
    """
    gym_id = current_gym.id

    special_day = await schedule.gym_special_hours_service.get_special_hours_by_date_cached(
        db=db, date_value=date, gym_id=gym_id, redis_client=redis_client
    )

    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No special hours found for date {date}"
        )

    return special_day


@router.post("/", response_model=GymSpecialHours, status_code=status.HTTP_201_CREATED)
async def create_special_day(
    *,
    db: AsyncSession = Depends(get_async_db),
    special_day_in: GymSpecialHoursCreate,
    overwrite: bool = Query(False, description="If True, overwrites existing entry for this date"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Create Special Day / Hours

    Creates a new special day entry (e.g., for a holiday or event).
    Times should be entered in HH:MM format.
    Optionally allows overwriting an existing entry for the same date if `overwrite=true`.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        special_day_in (GymSpecialHoursCreate): Data for the new special day.
        overwrite (bool, optional): If True, overwrites an existing entry for the same date. Defaults to False.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires ADMIN role within the gym or SUPER_ADMIN platform role.

    Request Body (GymSpecialHoursCreate):
        {
          "date": "YYYY-MM-DD",
          "open_time": "HH:MM (string, optional unless is_closed=false)",
          "close_time": "HH:MM (string, optional unless is_closed=false)",
          "is_closed": boolean (default: false),
          "description": "string (optional)"
        }

    Returns:
        GymSpecialHoursSchema: The created or updated special day object.

    Raises:
        HTTPException 400: Invalid input data (e.g., times required but missing, close_time before open_time).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User lacks required admin permissions.
        HTTPException 404: Gym not found.
        HTTPException 409: Conflict - entry for date exists and `overwrite` is false.
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

    # Check if entry already exists for this date
    existing = await schedule.gym_special_hours_service.get_special_hours_by_date_cached(
        db=db, date_value=special_day_in.date, gym_id=gym_id, redis_client=redis_client
    )

    # Prepare data, assigning gym_id and creator
    obj_in_data = special_day_in.model_dump()
    obj_in_data["created_by"] = getattr(local_user, "id", None)

    # Validate times based on is_closed status (Pydantic model handles this)
    # This is redundant here as Pydantic should catch it, but kept for clarity
    if not obj_in_data.get("is_closed", False):
        if obj_in_data.get("open_time") is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="open_time is required when not closed")
        if obj_in_data.get("close_time") is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="close_time is required when not closed")

    try:
        if existing and overwrite:
            # Update existing entry
            update_data = GymSpecialHoursUpdate(
                open_time=obj_in_data.get("open_time"),
                close_time=obj_in_data.get("close_time"),
                is_closed=obj_in_data.get("is_closed", False),
                description=obj_in_data.get("description")
            )
            return await schedule.gym_special_hours_service.update_special_day_cached(
                db=db, special_day_id=existing.id, special_hours_data=update_data, redis_client=redis_client
            )
        elif existing:
            # Conflict if exists and overwrite is false
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Special hours already exist for {special_day_in.date}. Use overwrite=true to replace."
            )
        else:
            # Create new entry
            # The service layer will handle adding the gym_id
            special_hours_data_create = GymSpecialHoursCreate(**obj_in_data)
            return await schedule.gym_special_hours_service.create_special_day_cached(
                db=db,
                special_hours_data=special_hours_data_create,
                gym_id=gym_id, # Pass gym_id to the service
                redis_client=redis_client
            )
    except ValueError as e:
        # Catch potential validation errors from Pydantic (e.g., time format)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{special_day_id}", response_model=GymSpecialHours)
async def update_special_day(
    *,
    db: AsyncSession = Depends(get_async_db),
    special_day_id: int = Path(..., description="ID of the special day entry"),
    special_day_in: GymSpecialHoursUpdate,
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update Special Day by ID

    Updates an existing special day entry using its unique ID.
    Times should be entered in HH:MM format.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        special_day_id (int): The ID of the special day entry to update.
        special_day_in (GymSpecialHoursUpdate): Fields to update.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires ADMIN role within the gym or SUPER_ADMIN platform role.

    Request Body (GymSpecialHoursUpdate - all fields optional):
        {
          "open_time": "HH:MM (string)",
          "close_time": "HH:MM (string)",
          "is_closed": boolean,
          "description": "string"
        }

    Returns:
        GymSpecialHoursSchema: The updated special day object.

    Raises:
        HTTPException 400: Invalid input data (e.g., close_time before open_time).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User lacks required admin permissions or access to this entry.
        HTTPException 404: Gym or Special Day entry not found, or entry doesn't belong to this gym.
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

    # Verify the special day exists and belongs to the current gym
    special_day = await schedule.gym_special_hours_service.get_special_hours_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    )
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special day entry not found"
        )
    if special_day.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this special day entry"
        )

    return await schedule.gym_special_hours_service.update_special_day_cached(
        db=db, special_day_id=special_day_id, special_hours_data=special_day_in, redis_client=redis_client
    )


@router.put("/date/{date}", response_model=GymSpecialHours)
async def update_special_day_by_date(
    *,
    db: AsyncSession = Depends(get_async_db),
    date: date = Path(..., description="Date (YYYY-MM-DD)"),
    special_day_in: GymSpecialHoursUpdate,
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update Special Day by Date

    Updates an existing special day entry by its date within the current gym.
    Returns 404 if no special entry exists for the specified date.
    Times should be entered in HH:MM format.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        date (date): The date (YYYY-MM-DD) of the special day entry to update.
        special_day_in (GymSpecialHoursUpdate): Fields to update.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires ADMIN role within the gym or SUPER_ADMIN platform role.

    Request Body (GymSpecialHoursUpdate - all fields optional):
        {
          "open_time": "HH:MM (string)",
          "close_time": "HH:MM (string)",
          "is_closed": boolean,
          "description": "string"
        }

    Returns:
        GymSpecialHoursSchema: The updated special day object.

    Raises:
        HTTPException 400: Invalid input data (e.g., close_time before open_time).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User lacks required admin permissions.
        HTTPException 404: Gym not found, or no Special Day entry exists for this date in this gym.
        HTTPException 422: Validation error in request body or invalid date format.
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

    # Find the special day by date within the gym
    special_day = await schedule.gym_special_hours_service.get_special_hours_by_date_cached(
        db=db, date_value=date, gym_id=gym_id, redis_client=redis_client
    )

    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No special hours found for date {date}"
        )

    # Update the found special day entry
    return await schedule.gym_special_hours_service.update_special_day_cached(
        db=db, special_day_id=special_day.id, special_hours_data=special_day_in, redis_client=redis_client
    )


@router.delete("/{special_day_id}", response_model=GymSpecialHours)
async def delete_special_day(
    *,
    db: AsyncSession = Depends(get_async_db),
    special_day_id: int = Path(..., description="ID of the special day entry"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Delete Special Day by ID

    Deletes a specific special day entry using its unique ID.

    Args:
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        special_day_id (int): The ID of the special day entry to delete.
        current_user (Auth0User, optional): Authenticated user dependency. Defaults to Depends(get_current_user).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires ADMIN role within the gym or SUPER_ADMIN platform role.

    Returns:
        GymSpecialHoursSchema: The deleted special day object.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: User lacks required admin permissions or access to this entry.
        HTTPException 404: Gym or Special Day entry not found, or entry doesn't belong to this gym.
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

    # Verify the special day exists and belongs to the current gym
    special_day = await schedule.gym_special_hours_service.get_special_hours_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    )
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special day entry not found"
        )
    if special_day.gym_id != current_gym.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this special day entry"
        )

    return await schedule.gym_special_hours_service.delete_special_day_cached(
        db=db, special_day_id=special_day_id, redis_client=redis_client
    ) 