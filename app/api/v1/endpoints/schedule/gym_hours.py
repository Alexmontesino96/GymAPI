from typing import Any, List, Optional, Dict
from datetime import date, datetime, timedelta, time
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body, Security
from sqlalchemy.orm import Session

from app.db.session import get_db
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
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get the gym's regular operating hours for all days of the week.
    
    This endpoint returns the opening and closing times for each day of the week
    to help members plan their visits accordingly. The data includes whether
    the gym is closed on specific days.
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        db: Database session dependency
        current_gym: The current gym context
        user: Authenticated user with appropriate scope
        redis_client: Redis client for caching
        
    Returns:
        List[GymHours]: A list of regular hours for all days of the week
    """
    return await schedule.gym_hours_service.get_all_gym_hours_cached(db, gym_id=current_gym.id, redis_client=redis_client)


@router.get("/regular/{day}", response_model=GymHours)
async def get_gym_hours_by_day(
    day: int = Path(..., ge=0, le=6, description="Day of the week (0=Monday, 6=Sunday)"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get the gym's regular operating hours for a specific day of the week.
    
    This endpoint retrieves opening and closing times for a specific day.
    If no regular hours are defined for the requested day, default values will be
    created using typical business hours (9:00-21:00) with Sundays closed.
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        day: Day of the week (integer 0-6 where 0=Monday, 6=Sunday)
        db: Database session dependency
        current_gym: The current gym context
        user: Authenticated user with appropriate scope
        redis_client: Redis client for caching
        
    Returns:
        GymHours: Regular opening and closing times for the specified day
    """
    return await schedule.gym_hours_service.get_gym_hours_by_day_cached(db, day=day, gym_id=current_gym.id, redis_client=redis_client)


@router.put("/regular/{day}", response_model=GymHours)
async def update_gym_hours(
    day: int = Path(..., ge=0, le=6, description="Day of the week (0=Monday, 6=Sunday)"),
    gym_hours_data: GymHoursUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    current_user: Auth0User = Depends(get_current_user),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update the gym's regular operating hours for a specific day of the week.
    
    This endpoint allows administrators to modify the opening and closing times
    for a specific day of the week, or mark a day as closed. If regular hours for the
    specified day don't exist yet, they will be created.
    
    Permissions:
        - Requires admin or platform admin role
        
    Args:
        day: Day of the week (integer 0-6 where 0=Monday, 6=Sunday)
        gym_hours_data: New schedule data (open_time, close_time, is_closed)
        db: Database session dependency
        current_gym: The current gym context
        current_user: Authenticated user
        redis_client: Redis client for caching
        
    Returns:
        GymHours: Updated regular opening and closing times for the specified day
    """
    # Verificar si el usuario es admin o super_admin
    local_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        # Verificar si tiene rol de ADMIN en el gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador para esta acción"
            )
    
    # Añadir el gimnasio actual a los datos
    gym_hours_dict = gym_hours_data.model_dump()
    gym_hours_dict["gym_id"] = current_gym.id
    updated_gym_hours_data = GymHoursUpdate(**gym_hours_dict)
    
    return await schedule.gym_hours_service.create_or_update_gym_hours_cached(
        db, 
        day=day, 
        gym_hours_data=updated_gym_hours_data,
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/date/{date}", response_model=Dict[str, Any])
async def get_gym_hours_by_date(
    date: date = Path(..., description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get the gym's effective operating hours for a specific date.
    
    This endpoint determines the actual operating hours for the specified date,
    taking into account both the regular weekly schedule and any special hours
    that may override it (such as holidays or special events).
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        date: The specific date to check
        db: Database session dependency
        current_gym: The current gym context
        user: Authenticated user with appropriate scope
        redis_client: Redis client for caching
        
    Returns:
        Dict: Contains operating hours info with fields:
            - regular_hours: The normal hours for that day of week
            - special_hours: Any special hours defined (if applicable)
            - is_special: Whether special hours apply
            - is_closed: Whether the gym is closed on this date
            - open_time: The actual opening time for this date
            - close_time: The actual closing time for this date
    """
    return await schedule.gym_hours_service.get_hours_for_date_cached(db, date_value=date, gym_id=current_gym.id, redis_client=redis_client)


@router.post("/apply-defaults", response_model=List[GymSpecialHours])
async def apply_defaults_to_range(
    *,
    db: Session = Depends(get_db),
    apply_request: ApplyDefaultsRequest,
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Apply regular weekly hours to a range of dates as special hours.
    
    This endpoint allows administrators to initialize special hours for a date range
    using the regular weekly schedule as a template. This is useful when setting up
    initial schedules or resetting a period to default hours.
    
    Permissions:
        - Requires admin or platform admin role
        
    Args:
        apply_request: Contains start_date, end_date and overwrite_existing flag
        db: Database session dependency
        current_gym: The current gym context
        current_user: Authenticated user
        redis_client: Redis client for caching
        
    Returns:
        List[GymSpecialHours]: Created or updated special hours entries
    """
    # Verificar si el usuario es admin o super_admin
    local_user = db.query(User).filter(User.auth0_id == current_user.id).first()
    if not local_user or (local_user.role != UserRole.ADMIN and local_user.role != UserRole.SUPER_ADMIN):
        # Verificar si tiene rol de ADMIN en el gimnasio
        user_gym = db.query(UserGym).filter(
            UserGym.user_id == local_user.id,
            UserGym.gym_id == current_gym.id,
            UserGym.role.in_([GymRoleType.ADMIN, GymRoleType.OWNER])
        ).first()
        
        if not user_gym:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Se requiere rol de administrador para esta acción"
            )
    
    # Obtener el ID del gimnasio desde el objeto current_gym
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
    db: Session = Depends(get_db),
    start_date: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (YYYY-MM-DD)"),
    current_user: Auth0User = Depends(get_current_user),
    current_gym: Gym = Depends(verify_gym_access),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get the gym's complete schedule for a range of dates.
    
    This endpoint retrieves the effective operating hours for each date in the specified range,
    including both regular weekly hours and any special hours that apply. It's useful for
    generating calendar views or planning future operations.
    
    Permissions:
        - Requires authentication
        
    Args:
        start_date: The first date in the range to retrieve
        end_date: The last date in the range to retrieve
        db: Database session dependency
        current_gym: The current gym context
        current_user: Authenticated user
        redis_client: Redis client for caching
        
    Returns:
        List[DailyScheduleResponse]: A list of daily schedules with effective hours
    """
    # Obtener el ID del gimnasio
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