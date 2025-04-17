from app.api.v1.endpoints.schedule.common import *
from app.models.schedule import ClassCategoryCustom, Class
from app.schemas.schedule import ClassCategoryCustomCreate, ClassCategoryCustomUpdate, ClassCategoryCustom as ClassCategoryCustomSchema
from app.models.gym import Gym
from app.models.user_gym import GymRoleType
from app.core.tenant import verify_gym_access, verify_trainer_role, verify_admin_role, GymSchema
from fastapi import APIRouter, Depends, Body, Path, Security, HTTPException, status, Request
from typing import List, Optional, Any
from app.services.schedule import category_service
from app.db.session import get_db
from app.core.auth0_fastapi import Auth0User, auth
from app.services.user import user_service
from app.db.redis_client import get_redis_client
from redis.asyncio import Redis

router = APIRouter()

@router.get("/categories", response_model=List[ClassCategoryCustomSchema])
async def get_categories(
    request: Request,
    active_only: bool = True,
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Custom Class Categories

    Retrieves a list of custom class categories for the current gym (specified by X-Gym-ID header).
    Can filter for active categories only.

    Args:
        request (Request): The request object.
        active_only (bool, optional): If true (default), only returns active categories. Defaults to True.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (GymSchema, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["read:schedules"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.
        - User must belong to the gym specified in X-Gym-ID.

    Returns:
        List[ClassCategoryCustomSchema]: A list of category objects.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym not found.
    """
    return await category_service.get_categories_by_gym(db, gym_id=current_gym.id, active_only=active_only, redis_client=redis_client)


@router.get("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def get_category(
    request: Request,
    category_id: int = Path(..., description="ID of the category"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_gym_access),
    user: Auth0User = Security(auth.get_user, scopes=["read:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Get Specific Custom Class Category

    Retrieves details of a specific custom class category by its ID,
    ensuring it belongs to the current gym.

    Args:
        request (Request): The request object.
        category_id (int): The ID of the category to retrieve.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (GymSchema, optional): Current gym context dependency. Defaults to Depends(verify_gym_access).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["read:schedules"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'read:schedules' scope.
        - User must belong to the gym specified in X-Gym-ID.

    Returns:
        ClassCategoryCustomSchema: The requested category object.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user doesn't belong to the gym.
        HTTPException 404: Gym or Category not found, or category doesn't belong to this gym.
    """
    return await category_service.get_category(db, category_id=category_id, gym_id=current_gym.id, redis_client=redis_client)


@router.post("/categories", response_model=ClassCategoryCustomSchema, status_code=status.HTTP_201_CREATED)
async def create_category(
    request: Request,
    category_data: ClassCategoryCustomCreate = Body(...),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_trainer_role), # Requires TRAINER or higher
    user: Auth0User = Security(auth.get_user, scopes=["create:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Create Custom Class Category

    Creates a new custom class category for the current gym.

    Args:
        request (Request): The request object.
        category_data (ClassCategoryCustomCreate): Data for the new category.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (GymSchema, optional): Current gym context dependency (requires TRAINER or ADMIN role). Defaults to Depends(verify_trainer_role).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["create:schedules"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'create:schedules' scope.
        - User must have TRAINER or ADMIN role within the current gym.

    Request Body (ClassCategoryCustomCreate):
        {
          "name": "string",
          "description": "string (optional)",
          "color": "string (optional, hex code)",
          "icon": "string (optional, name/URL)",
          "is_active": true (optional, default: true)
        }

    Returns:
        ClassCategoryCustomSchema: The newly created category object.

    Raises:
        HTTPException 400: Invalid data (e.g., duplicate name).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user lacks required role.
        HTTPException 404: Gym not found.
        HTTPException 422: Validation error in request body.
    """
    auth0_id = user.id
    # Use cached version for potentially faster lookup
    db_user = await user_service.get_user_by_auth0_id_cached(db, auth0_id=auth0_id, redis_client=redis_client)

    created_by_id = db_user.id if db_user else None

    return await category_service.create_category(
        db, category_data=category_data, gym_id=current_gym.id, created_by_id=created_by_id, redis_client=redis_client
    )


@router.put("/categories/{category_id}", response_model=ClassCategoryCustomSchema)
async def update_category(
    request: Request,
    category_id: int = Path(..., description="ID of the category"),
    category_data: ClassCategoryCustomUpdate = Body(...),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_trainer_role), # Requires TRAINER or higher
    user: Auth0User = Security(auth.get_user, scopes=["update:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> Any:
    """
    Update Custom Class Category

    Updates an existing custom class category within the current gym.

    Args:
        request (Request): The request object.
        category_id (int): The ID of the category to update.
        category_data (ClassCategoryCustomUpdate): Data fields to update.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (GymSchema, optional): Current gym context dependency (requires TRAINER or ADMIN role). Defaults to Depends(verify_trainer_role).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["update:schedules"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'update:schedules' scope.
        - User must have TRAINER or ADMIN role within the current gym.

    Request Body (ClassCategoryCustomUpdate - all fields optional):
        {
          "name": "string",
          "description": "string",
          "color": "string",
          "icon": "string",
          "is_active": true
        }

    Returns:
        ClassCategoryCustomSchema: The updated category object.

    Raises:
        HTTPException 400: Invalid data (e.g., duplicate name).
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user lacks required role.
        HTTPException 404: Gym or Category not found, or category doesn't belong to this gym.
        HTTPException 422: Validation error in request body.
    """
    return await category_service.update_category(
        db, category_id=category_id, category_data=category_data, gym_id=current_gym.id, redis_client=redis_client
    )


@router.delete(
    "/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
async def delete_category(
    request: Request,
    category_id: int = Path(..., description="ID of the category"),
    db: Session = Depends(get_db),
    current_gym: GymSchema = Depends(verify_admin_role), # Requires ADMIN role
    user: Auth0User = Security(auth.get_user, scopes=["delete:schedules"]),
    redis_client: Redis = Depends(get_redis_client)
) -> None:
    """
    Delete Custom Class Category

    Deletes or deactivates a custom class category. If the category is currently
    associated with any class definitions, it is marked as inactive instead of
    being permanently deleted.

    Args:
        request (Request): The request object.
        category_id (int): The ID of the category to delete/deactivate.
        db (Session, optional): Database session dependency. Defaults to Depends(get_db).
        current_gym (GymSchema, optional): Current gym context dependency (requires ADMIN role). Defaults to Depends(verify_admin_role).
        user (Auth0User, optional): Authenticated user dependency. Defaults to Security(auth.get_user, scopes=["delete:schedules"]).
        redis_client (Redis, optional): Redis client dependency. Defaults to Depends(get_redis_client).

    Permissions:
        - Requires 'delete:schedules' scope.
        - User must have ADMIN role within the current gym.

    Returns:
        None: HTTP 204 No Content on successful deletion/deactivation.

    Raises:
        HTTPException 401: Invalid or missing token.
        HTTPException 403: Token lacks required scope or user lacks required role.
        HTTPException 404: Gym or Category not found, or category doesn't belong to this gym.
    """
    await category_service.delete_category(db, category_id=category_id, gym_id=current_gym.id, redis_client=redis_client)
    return None 