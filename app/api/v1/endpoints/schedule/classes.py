from app.api.v1.endpoints.schedule.common import *
from app.core.tenant import verify_gym_access
from app.models.gym import Gym
from app.db.redis_client import get_redis_client
from redis.asyncio import Redis

router = APIRouter()

@router.get("/classes", response_model=List[Class])
async def get_classes(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Class Definitions

    Retrieves a list of class definitions (templates) for the current gym.

    Args:
        skip (int, optional): Number of records to skip for pagination. Defaults to 0.
        limit (int, optional): Maximum number of records to return. Defaults to 100.
        active_only (bool, optional): If true, only returns active class definitions. Defaults to True.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[ClassSchema]: A list of class definition objects.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym not found.
    """
    return await class_service.get_classes(
        db,
        skip=skip,
        limit=limit,
        active_only=active_only,
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/classes/{class_id}", response_model=ClassWithSessions)
async def get_class(
    class_id: int = Path(..., description="ID of the class definition"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Specific Class Definition with Sessions

    Retrieves details of a specific class definition, including a list of its
    scheduled sessions within the current gym.

    Args:
        class_id (int): The ID of the class definition.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        ClassWithSessionsSchema: The requested class definition object including its sessions.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Class or Gym not found, or class doesn't belong to this gym.
    """
    # Service already verifies class belongs to gym
    class_obj = await class_service.get_class(db, class_id=class_id, gym_id=current_gym.id, redis_client=redis_client)

    # Obtain sessions specific to this class and gym
    sessions = await class_session_service.get_sessions_by_class(
        db,
        class_id=class_id,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Combine into the response model
    response = ClassWithSessions.model_validate(class_obj)
    response.sessions = sessions

    return response


@router.post("/classes", response_model=Class, status_code=status.HTTP_201_CREATED)
async def create_class(
    class_data: ClassCreate = Body(...),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Create Class Definition

    Creates a new class definition (template) for the current gym.

    Args:
        class_data (ClassCreate): Data for the new class definition.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'create:schedules' scope.

    Request Body (ClassCreate):
        {
          "name": "string",
          "description": "string (optional)",
          "duration": integer (minutes, >0),
          "max_capacity": integer (>0),
          "difficulty_level": "string (beginner|intermediate|advanced)",
          "category_id": integer (optional, custom category ID),
          "category_enum": "string (optional, standard enum)",
          "is_active": true (optional, default: true)
        }

    Returns:
        ClassSchema: The newly created class definition object.

    Raises:
        HTTPException 400: Invalid data (e.g., category_id does not belong to gym).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym not found.
        HTTPException 422: Validation error in request body.
    """
    # Get current user's local ID to record as creator
    auth0_id = user.id
    # Use cached version
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    created_by_id = db_user.id if db_user else None

    # Process input data, exclude auxiliary 'category' field if present
    input_dict = class_data.model_dump(exclude_unset=True, exclude={"category"})

    # Verify custom category belongs to the gym if provided
    if class_data.category_id:
        from app.models.schedule import ClassCategoryCustom
        result = await db.execute(select(ClassCategoryCustom).where(
            ClassCategoryCustom.id == class_data.category_id,
            ClassCategoryCustom.gym_id == current_gym.id
        ))
    category = result.scalar_one_or_none()

        if not category:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected category does not belong to this gym"
            )

    # Create the class using validated data
    class_obj_validated = ClassCreate(**input_dict)
    return await class_service.create_class(
        db,
        class_data=class_obj_validated,
        created_by_id=created_by_id,
        gym_id=current_gym.id,  # Pass gym_id explicitly
        redis_client=redis_client
    )


@router.put("/classes/{class_id}", response_model=Class)
async def update_class(
    class_id: int = Path(..., description="ID of the class definition"),
    class_data: ClassUpdate = Body(...),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:write"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update Class Definition

    Updates an existing class definition.

    Args:
        class_id (int): The ID of the class definition to update.
        class_data (ClassUpdate): Fields to update.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:write"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'update:schedules' scope (typically for trainers/admins).

    Request Body (ClassUpdate - all fields optional):
        {
          "name": "string",
          "description": "string",
          "duration": integer,
          "max_capacity": integer,
          "difficulty_level": "string",
          "category_id": integer,
          "category_enum": "string",
          "is_active": boolean
        }

    Returns:
        ClassSchema: The updated class definition object.

    Raises:
        HTTPException 400: Invalid data (e.g., category_id does not belong to gym).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Class or Gym not found, or class doesn't belong to gym.
        HTTPException 422: Validation error in request body.
    """
    # Service `get_class` already verifies ownership
    class_obj = await class_service.get_class(db, class_id=class_id, gym_id=current_gym.id, redis_client=redis_client)

    # Verify new category_id belongs to the gym if it's being updated
    if class_data.category_id is not None and class_data.category_id != class_obj.category_id:
        from app.models.schedule import ClassCategoryCustom
        result = await db.execute(select(ClassCategoryCustom).where(
            ClassCategoryCustom.id == class_data.category_id
        ))
    category = result.scalar_one_or_none()

        if not category or category.gym_id != current_gym.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected category does not belong to this gym"
            )

    return await class_service.update_class(db, class_id=class_id, class_data=class_data, gym_id=current_gym.id, redis_client=redis_client)


@router.delete("/classes/{class_id}", response_model=Class)
async def delete_class(
    class_id: int = Path(..., description="ID of the class definition"),
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:admin"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Delete Class Definition

    Deletes or deactivates a class definition. If the class has scheduled sessions,
    it will be marked as inactive instead of being deleted.

    Args:
        class_id (int): The ID of the class definition to delete/deactivate.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:admin"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'delete:schedules' scope (typically for admins).

    Returns:
        ClassSchema: The class object (potentially marked as `is_active: false`).

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Class or Gym not found, or class doesn't belong to gym.
    """
    # Service `get_class` already verifies ownership
    class_obj = await class_service.get_class(db, class_id=class_id, gym_id=current_gym.id, redis_client=redis_client)

    return await class_service.delete_class(db, class_id=class_id, gym_id=current_gym.id, redis_client=redis_client)


@router.get("/classes/category/{category}", response_model=List[Class])
async def get_classes_by_category(
    category: ClassCategory = Path(..., description="Standard class category enum"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Classes by Standard Category

    Retrieves active classes filtered by a standard `ClassCategory` enum value.
    Note: This filters by the standard enum, not custom categories.

    Args:
        category (ClassCategory): The standard category enum to filter by.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[ClassSchema]: List of classes matching the standard category.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym not found.
        HTTPException 422: Invalid category enum value.
    """
    # Fetch all active classes for the gym (cached)
    classes = await class_service.get_classes(
        db,
        skip=0, # Fetch all active to filter in memory - consider performance for large datasets
        limit=1000, # Adjust limit as needed
        active_only=True,
        gym_id=current_gym.id,
        redis_client=redis_client
    )

    # Filter by the standard category enum
    filtered_classes = [cls for cls in classes if cls.category_enum == category]

    # Apply pagination to the filtered list
    paginated_results = filtered_classes[skip : skip + limit]
    return paginated_results


@router.get("/classes/difficulty/{difficulty}", response_model=List[Class])
async def get_classes_by_difficulty(
    difficulty: ClassDifficultyLevel = Path(..., description="Class difficulty level"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Classes by Difficulty Level

    Retrieves active classes filtered by difficulty level.

    Args:
        difficulty (ClassDifficultyLevel): The difficulty level enum (`beginner`, `intermediate`, `advanced`).
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[ClassSchema]: List of classes matching the difficulty level.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym not found.
        HTTPException 422: Invalid difficulty enum value.
    """
    # Convert enum to string for service method
    difficulty_str = difficulty.value
    return await class_service.get_classes_by_difficulty(
        db,
        difficulty=difficulty_str,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    )


@router.get("/classes/search", response_model=List[Class])
async def search_classes(
    query: str = Query(..., description="Search term for name or description"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_async_db),
    current_gym: Gym = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["resource:read"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Search Classes

    Searches active classes by name or description within the current gym.

    Args:
        query (str): The text to search for in class name or description.
        skip (int, optional): Pagination skip. Defaults to 0.
        limit (int, optional): Pagination limit. Defaults to 100.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (Gym, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["resource:read"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.

    Returns:
        List[ClassSchema]: List of classes matching the search query.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope.
        HTTPException 404: Gym not found.
    """
    return await class_service.search_classes(
        db,
        search=query,
        skip=skip,
        limit=limit,
        gym_id=current_gym.id,
        redis_client=redis_client
    ) 