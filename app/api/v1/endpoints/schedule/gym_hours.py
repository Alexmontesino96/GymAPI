from app.api.v1.endpoints.schedule.common import *

router = APIRouter()

@router.get("/gym-hours", response_model=List[GymHours])
async def get_all_gym_hours(
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Get the gym's operating hours for all days of the week.
    
    This endpoint returns the opening and closing times for each day of the week
    to help members plan their visits accordingly. The data includes whether
    the gym is closed on specific days.
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        List[GymHours]: A list of gym hours for all days of the week
    """
    return gym_hours_service.get_all_gym_hours(db)


@router.get("/gym-hours/{day}", response_model=GymHours)
async def get_gym_hours_by_day(
    day: int = Path(..., ge=0, le=6, description="Day of the week (0=Monday, 6=Sunday)"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Get the gym's operating hours for a specific day of the week.
    
    This endpoint retrieves opening and closing times for a specific day.
    If no hours are defined for the requested day, default values will be
    created using typical business hours (9:00-21:00) with Sundays closed.
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        day: Day of the week (integer 0-6 where 0=Monday, 6=Sunday)
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        GymHours: Opening and closing times for the specified day
    """
    hours = gym_hours_service.get_gym_hours_by_day(db, day=day)
    if not hours:
        # Create default hours if none exist
        hours = gym_hours_service.create_or_update_gym_hours(
            db, day=day, 
            gym_hours_data=GymHoursCreate(
                day_of_week=day,
                open_time=datetime.strptime("09:00", "%H:%M").time(),
                close_time=datetime.strptime("21:00", "%H:%M").time(),
                is_closed=(day == 6)  # Closed on Sundays
            )
        )
    return hours


@router.put("/gym-hours/{day}", response_model=GymHours)
async def update_gym_hours(
    day: int = Path(..., ge=0, le=6, description="Day of the week (0=Monday, 6=Sunday)"),
    gym_hours_data: GymHoursUpdate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Update the gym's operating hours for a specific day of the week.
    
    This endpoint allows administrators to modify the opening and closing times
    for a specific day of the week, or mark a day as closed. If hours for the
    specified day don't exist yet, they will be created.
    
    Permissions:
        - Requires 'update:schedules' scope (admin only)
        
    Args:
        day: Day of the week (integer 0-6 where 0=Monday, 6=Sunday)
        gym_hours_data: New schedule data (open_time, close_time, is_closed)
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        GymHours: Updated opening and closing times for the specified day
    """
    return gym_hours_service.create_or_update_gym_hours(db, day=day, gym_hours_data=gym_hours_data)


@router.post("/gym-hours/initialize", response_model=List[GymHours])
async def initialize_gym_hours(
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Initialize default operating hours for all days of the week.
    
    This utility endpoint creates a standard schedule for the entire week
    if none exists yet. Typically used during initial setup of the gym.
    Default hours are 9:00-21:00 Monday through Saturday, with Sunday closed.
    
    Permissions:
        - Requires 'update:schedules' scope (admin only)
        
    Args:
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        List[GymHours]: The complete set of initialized gym hours
    """
    return gym_hours_service.initialize_default_hours(db)


@router.get("/gym-hours/date/{date}", response_model=Dict[str, Any])
async def get_gym_hours_by_date(
    date: date = Path(..., description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Get the gym's operating hours for a specific date.
    
    This endpoint determines the actual operating hours for the specified date,
    taking into account both the regular weekly schedule and any special hours
    that may override it (such as holidays or special events).
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        date: The specific date to check
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        Dict: Contains operating hours info with fields:
            - regular_hours: The normal hours for that day of week
            - special_hours: Any special hours defined (if applicable)
            - is_special: Whether special hours apply
            - is_closed: Whether the gym is closed on this date
            - open_time: The actual opening time for this date
            - close_time: The actual closing time for this date
    """
    return gym_hours_service.get_hours_for_date(db, date_value=date) 