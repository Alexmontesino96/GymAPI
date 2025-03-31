from app.api.v1.endpoints.schedule.common import *
from app.repositories.schedule import gym_special_hours_repository

router = APIRouter()

@router.get("/special-days", response_model=List[GymSpecialHours])
async def get_special_days(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Get all upcoming special days with modified operating hours.
    
    This endpoint retrieves a list of upcoming dates with non-standard operating hours,
    such as holidays, special events, or temporary schedule changes. By default,
    it returns the next 100 special days.
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        skip: Number of records to skip (for pagination)
        limit: Maximum number of records to return
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        List[GymSpecialHours]: A list of upcoming special days with their modified hours
    """
    return gym_special_hours_service.get_upcoming_special_days(db, limit=limit)


@router.get("/special-days/{special_day_id}", response_model=GymSpecialHours)
async def get_special_day(
    special_day_id: int = Path(..., description="ID of the special day"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"])
) -> Any:
    """
    Get details for a specific special day by ID.
    
    This endpoint retrieves the complete information for a particular special day,
    including its date, modified operating hours, and description of why the
    schedule is different from normal.
    
    Permissions:
        - Requires 'read:schedules' scope
        
    Args:
        special_day_id: The unique ID of the special day
        db: Database session dependency
        user: Authenticated user with appropriate scope
        
    Returns:
        GymSpecialHours: Details of the requested special day
        
    Raises:
        HTTPException: 404 error if the special day does not exist
    """
    special_day = gym_special_hours_repository.get(db, id=special_day_id)
    if not special_day:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Special day not found"
        )
    return special_day


@router.post("/special-days", response_model=GymSpecialHours)
async def create_special_day(
    special_day_data: GymSpecialHoursCreate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Create a new special day with modified operating hours.
    
    This endpoint allows administrators to define dates with non-standard
    operating hours, such as holidays, early closings, or special events.
    The system automatically tracks which admin created each special day.
    
    Permissions:
        - Requires 'update:schedules' scope (admin only)
        
    Args:
        special_day_data: The special day details (date, hours, description)
        db: Database session dependency
        user: Authenticated admin user
        
    Returns:
        GymSpecialHours: The newly created special day record
    """
    # Get current user ID to record as creator
    auth0_id = user.id
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    special_day_dict = special_day_data.model_dump()
    if db_user:
        special_day_dict["created_by"] = db_user.id
    
    return gym_special_hours_service.create_special_day(
        db, special_hours_data=GymSpecialHoursCreate(**special_day_dict)
    )


@router.put("/special-days/{special_day_id}", response_model=GymSpecialHours)
async def update_special_day(
    special_day_id: int = Path(..., description="ID of the special day"),
    special_day_data: GymSpecialHoursUpdate = Body(...),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Update an existing special day.
    
    This endpoint allows administrators to modify the details of a previously
    created special day, such as changing the operating hours or updating
    the description. The system preserves the original creator information.
    
    Permissions:
        - Requires 'update:schedules' scope (admin only)
        
    Args:
        special_day_id: The unique ID of the special day to update
        special_day_data: The updated special day details
        db: Database session dependency
        user: Authenticated admin user
        
    Returns:
        GymSpecialHours: The updated special day record
        
    Raises:
        HTTPException: 404 error if the special day does not exist (raised by service)
    """
    return gym_special_hours_service.update_special_day(
        db, special_day_id=special_day_id, special_hours_data=special_day_data
    )


@router.delete("/special-days/{special_day_id}", response_model=GymSpecialHours)
async def delete_special_day(
    special_day_id: int = Path(..., description="ID of the special day"),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"])
) -> Any:
    """
    Delete a special day.
    
    This endpoint allows administrators to remove a special day from the system.
    This is useful when plans change or a special schedule is no longer needed.
    The operation returns the deleted record for confirmation purposes.
    
    Permissions:
        - Requires 'update:schedules' scope (admin only)
        
    Args:
        special_day_id: The unique ID of the special day to delete
        db: Database session dependency
        user: Authenticated admin user
        
    Returns:
        GymSpecialHours: The deleted special day record
        
    Raises:
        HTTPException: 404 error if the special day does not exist (raised by service)
    """
    return gym_special_hours_service.delete_special_day(db, special_day_id=special_day_id) 