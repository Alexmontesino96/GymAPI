"""
User Management Module - API Endpoints

This module provides comprehensive user management functionality for the gym application,
including:

- User registration and profile management
- Role-based access control
- User search and filtering capabilities
- Administrative user management functions

The user system integrates with Auth0 for authentication while maintaining local user
records for application-specific data and relationships. This dual approach provides
secure authentication while enabling customized user experiences and data management.

Each endpoint is protected with appropriate permission scopes to ensure data security
and proper access control based on user roles (Member, Trainer, Admin).
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from sqlalchemy.orm import Session

from app.core.auth0_fastapi import auth, get_current_user, get_current_user_with_permissions, Auth0User
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services.user import user_service
from app.schemas.user import User as UserSchema, UserCreate, UserUpdate, UserRoleUpdate, UserProfileUpdate, UserSearchParams

router = APIRouter()


@router.get("/", response_model=List[UserSchema])
async def read_users(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """
    Retrieve all users.
    Requires the 'read:users' scope which is assigned to trainers and administrators in Auth0.
    """
    users = user_service.get_users(db, skip=skip, limit=limit)
    return users


@router.get("/by-role/{role}", response_model=List[UserSchema])
async def read_users_by_role(
    role: UserRole,
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """
    Retrieve users filtered by role.
    Requires the 'read:users' scope which is assigned to trainers and administrators in Auth0.
    """
    users = user_service.get_users_by_role(db, role=role, skip=skip, limit=limit)
    return users


@router.get("/trainers", response_model=List[UserSchema])
async def read_trainers(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """
    Retrieve all trainers.
    Requires the 'read:users' scope which is assigned to trainers and administrators in Auth0.
    """
    trainers = user_service.get_users_by_role(db, role=UserRole.TRAINER, skip=skip, limit=limit)
    return trainers


@router.get("/members", response_model=List[UserSchema])
async def read_members(
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    user: Auth0User = Security(auth.get_user, scopes=["read:members"]),
) -> Any:
    """
    Retrieve all members.
    Requires the 'read:members' scope which is assigned to trainers and administrators in Auth0.
    """
    members = user_service.get_users_by_role(db, role=UserRole.MEMBER, skip=skip, limit=limit)
    return members


@router.post("/", response_model=UserSchema)
async def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["admin:users"]),
) -> Any:
    """
    Create a new user (Administrative endpoint).
    
    This endpoint is exclusive to administrators and allows creating users with any role.
    Requires the 'admin:users' scope which is assigned only to administrators in Auth0.
    
    Differences with /register:
    - Requires administrator authentication
    - Allows creating users with any role
    - No restrictions on user data
    - Administrative endpoint
    """
    user = user_service.create_user(db, user_in=user_in)
    return user


@router.get("/profile", response_model=UserSchema)
async def get_user_profile(
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Get the authenticated user's profile.
    If the user doesn't exist in the local database, creates a basic profile.
    """
    # Get Auth0 ID
    auth0_id = user.id
    
    if not auth0_id:
        raise HTTPException(
            status_code=400,
            detail="Token does not contain user information (sub)",
        )
    
    # Synchronize user with local database
    user_data = {
        "sub": auth0_id,
        "email": getattr(user, "email", None)
    }
    db_user = user_service.create_or_update_auth0_user(db, user_data)
    return db_user


@router.put("/profile", response_model=UserSchema)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Depends(get_current_user),
) -> Any:
    """
    Update the authenticated user's profile.
    """
    # Get current user from database
    auth0_id = user.id
    if not auth0_id:
        raise HTTPException(
            status_code=400,
            detail="Token does not contain user information (sub)",
        )
    
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found in local database",
        )
    
    # Update profile
    updated_user = user_service.update_user_profile(db, user_id=db_user.id, profile_in=profile_update)
    return updated_user


@router.put("/{user_id}/role", response_model=UserSchema)
async def update_user_role(
    user_id: int,
    role_update: UserRoleUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["admin:users"]),
) -> Any:
    """
    Update a user's role.
    Requires the 'admin:users' scope which is assigned only to administrators in Auth0.
    """
    updated_user = user_service.update_user_role(db, user_id=user_id, role_update=role_update)
    return updated_user


@router.get("/{user_id}", response_model=UserSchema)
async def read_user_by_id(
    user_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """
    Get a specific user by ID.
    Requires the 'read:users' scope which is assigned to trainers and administrators in Auth0.
    """
    db_user = user_service.get_user(db, user_id=user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    return db_user


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["admin:users"]),
) -> Any:
    """
    Update a user.
    Requires the 'admin:users' scope which is assigned only to administrators in Auth0.
    """
    updated_user = user_service.update_user(db, user_id=user_id, user_in=user_in)
    return updated_user


@router.delete("/{user_id}", response_model=UserSchema)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["admin:users"]),
) -> Any:
    """
    Delete a user.
    Requires the 'admin:users' scope which is assigned only to administrators in Auth0.
    """
    deleted_user = user_service.delete_user(db, user_id=user_id)
    return deleted_user


@router.post("/register", response_model=UserSchema)
async def register_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
) -> Any:
    """
    Register a new user (Public endpoint).
    
    This is a public endpoint that allows new users to register in the system.
    Users registered through this endpoint will always have the MEMBER role.
    
    Differences with / (create_user):
    - No authentication required
    - Forces role to MEMBER
    - Forces is_superuser to False
    - Has specific validations for email and password
    - Registration endpoint for new users
    """
    # Force role to MEMBER regardless of what is sent in the request
    user_data = user_in.model_dump()
    user_data["role"] = UserRole.MEMBER
    user_data["is_superuser"] = False  # Ensure no superusers are created
    
    # Verify that email and password are provided
    if not user_data.get("email"):
        raise HTTPException(
            status_code=400,
            detail="Email is required for registration"
        )
    
    if not user_data.get("password"):
        raise HTTPException(
            status_code=400,
            detail="Password is required for registration"
        )
    
    # Create user with sanitized data
    user_create = UserCreate(**user_data)
    try:
        user = user_service.create_user(db, user_in=user_create)
        return user
    except HTTPException as e:
        # Re-raise service exceptions
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error creating user: {str(e)}"
        )


@router.get("/search", response_model=List[UserSchema])
async def search_users(
    search_params: UserSearchParams = Depends(),
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """
    Search for users with advanced filtering options.
    
    This endpoint provides flexible user search capabilities with multiple filter
    criteria, including partial name matches, email domain filtering, role selection,
    and other profile attributes.
    
    Permissions:
        - Requires 'read:users' scope (administrators and trainers)
        
    Args:
        search_params: Search parameters object with filters
        db: Database session
        user: Authenticated user with appropriate permissions
        
    Returns:
        List[User]: List of users matching the search criteria
    """
    # Search users with provided parameters
    return user_service.search_users(db, search_params=search_params)


@router.get("/auth0/{auth0_id}", response_model=UserSchema)
async def read_user_by_auth0_id(
    auth0_id: str,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["read:users"]),
) -> Any:
    """
    Retrieve a specific user by their Auth0 ID.
    
    This endpoint returns the complete profile information for a specific user
    identified by their external Auth0 user ID (sub claim).
    
    Permissions:
        - Requires 'read:users' scope (administrators and trainers)
        
    Args:
        auth0_id: Auth0 ID (sub claim) of the user to retrieve
        db: Database session
        user: Authenticated user with appropriate permissions
        
    Returns:
        User: The requested user's profile data
        
    Raises:
        HTTPException: 404 if user not found
    """
    # Get user by Auth0 ID
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    return db_user


@router.put("/auth0/{auth0_id}", response_model=UserSchema)
async def update_user_by_auth0_id(
    auth0_id: str,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["update:users"]),
) -> Any:
    """
    Update a specific user's profile by their Auth0 ID.
    
    This administrative endpoint allows updating any user's profile information
    using their Auth0 ID as the identifier. This is useful when integrating with
    Auth0 management workflows.
    
    Permissions:
        - Requires 'update:users' scope (administrators only)
        
    Args:
        auth0_id: Auth0 ID (sub claim) of the user to update
        user_in: Updated user data (partial updates supported)
        db: Database session
        user: Authenticated administrator
        
    Returns:
        User: The updated user profile
        
    Raises:
        HTTPException: 404 if user not found
    """
    # Get user by Auth0 ID
    db_user = user_service.get_user_by_auth0_id(db, auth0_id=auth0_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Update user with provided data
    return user_service.update_user(db, user_id=db_user.id, user_in=user_in)


@router.delete("/{user_id}", response_model=UserSchema)
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    user: Auth0User = Security(auth.get_user, scopes=["delete:users"]),
) -> Any:
    """
    Delete a specific user by their ID.
    
    This administrative endpoint removes a user from the local database. Note that this
    does not delete the user's account in Auth0, only the local application data.
    
    Permissions:
        - Requires 'delete:users' scope (administrators only)
        
    Args:
        user_id: Internal database ID of the user to delete
        db: Database session
        user: Authenticated administrator
        
    Returns:
        User: The deleted user's data
        
    Raises:
        HTTPException: 404 if user not found
    """
    # Get user by ID
    db_user = user_service.get_user(db, user_id=user_id)
    
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )
    
    # Delete user
    return user_service.delete_user(db, user_id=user_id) 